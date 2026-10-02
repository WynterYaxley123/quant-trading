"""Retrospective *engineering-only* fit on a hashed factor readiness matrix.

This is deliberately not fit_horizon/current_predictions: those production
interfaces require true as-of availability at a historical signal timestamp,
which the reconstructed membership and post-cutoff lake do not prove. The
frozen NumPyRidge objective, horizon windows, feature orders, target centering
and z-score fusion are reused without claiming an ex-ante signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.etf_quant.domain import ModelPrediction, StrategyConfig
from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant.models.fusion import fuse_predictions


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _external(path: Path, *, directory: bool) -> Path:
    path = path.resolve(strict=True)
    if path.is_dir() != directory or any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("EXTERNAL_EVIDENCE_PATH_REQUIRED")
    return path


def fit_retrospective_horizon(
    frame: pd.DataFrame,
    sessions: tuple[pd.Timestamp, ...],
    universe: tuple[str, ...],
    spec,
    report: dict,
) -> tuple[dict, tuple]:
    """Actual frozen Ridge math; no fabricated available_at or performance."""
    h = int(spec.horizon)
    signal_date = sessions[-1]
    cutoff = sessions[-1 - h]
    start = cutoff - pd.DateOffset(months=spec.training_window_months)
    days = tuple(d for d in sessions if start <= d <= cutoff)
    if (
        cutoff.date().isoformat() != report["label_cutoff"]
        or start.date().isoformat() != report["window_start"]
        or len(days) != report["candidate_training_dates"]
    ):
        raise ValueError("FROZEN_HORIZON_WINDOW_MISMATCH")
    index = {day: i for i, day in enumerate(sessions)}
    X, y, accepted = [], [], []
    for day in days:
        label_end = sessions[index[day] + h]
        a = frame.loc[(day, list(universe)), :]
        b = frame.loc[(label_end, list(universe)), :]
        start_close = a["source_c_close"].to_numpy(dtype=float)
        end_close = b["source_c_close"].to_numpy(dtype=float)
        features = a.loc[:, list(spec.factor_names)].to_numpy(dtype=float)
        if (
            not np.isfinite(start_close).all()
            or not np.isfinite(end_close).all()
            or not np.isfinite(features).all()
            or np.any(start_close <= 0)
        ):
            continue  # whole cross-section, never partial target centering
        raw = end_close / start_close - 1.0
        if not np.isfinite(raw).all():
            raise ValueError("NONFINITE_MATURE_TARGET")
        excess = raw - raw.mean()
        X.extend(features)
        y.extend(excess)
        accepted.append(day)
    if len(accepted) != report["training_dates_diagnostic_common_universe"]:
        raise ValueError("READINESS_TRAINING_DATE_MISMATCH")
    if len(accepted) < spec.minimum_valid_training_days:
        raise ValueError("INSUFFICIENT_COMMON_TRAINING_DAYS")
    model = NumPyRidge(alpha=spec.alpha).fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
    current = frame.loc[(signal_date, list(universe)), list(spec.factor_names)].to_numpy(
        dtype=float
    )
    if not np.isfinite(current).all():
        raise ValueError("COMMON_UNIVERSE_SIGNAL_FEATURE_MISSING")
    raw_predictions = model.predict(current)
    predictions = tuple(
        ModelPrediction(spec.horizon, signal_date.date(), code, float(score))
        for code, score in zip(universe, raw_predictions)
    )
    result = {
        "horizon": h,
        "alpha": spec.alpha,
        "factor_names": list(spec.factor_names),
        "feature_dimensions": len(spec.factor_names),
        "target_identity": spec.target_identity,
        "preprocessing": "NONE_RAW_X_NO_TRAIN_STANDARDIZATION",
        "target_centering": "SAME_DATE_CROSS_SECTIONAL_MEAN_SUBTRACTED",
        "training_window_months": spec.training_window_months,
        "window_start": start.date().isoformat(),
        "label_cutoff": cutoff.date().isoformat(),
        "training_first": accepted[0].date().isoformat(),
        "training_last": accepted[-1].date().isoformat(),
        "training_dates": len(accepted),
        "training_observations": len(y),
        "industries": len(universe),
        "coefficients": {name: float(value) for name, value in zip(spec.factor_names, model.coef_)},
        "intercept": float(model.intercept_),
        "raw_predictions": {code: float(score) for code, score in zip(universe, raw_predictions)},
        "formal_available_at_hypothetical_signal": None,
    }
    return result, predictions


def audit(readiness_path: Path, factor_path: Path, output: Path) -> dict:
    readiness_path = _external(readiness_path, directory=False)
    factor_path = _external(factor_path, directory=False)
    output = _external(output, directory=True)
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if (
        readiness.get("contract") != "ETF_QUANT_RETROSPECTIVE_READINESS_AUDIT_V1"
        or readiness.get("factor_matrix_sha256") != _sha256(factor_path)
        or Path(readiness.get("factor_matrix", "")).name != factor_path.name
    ):
        raise ValueError("FACTOR_MATRIX_HASH_OR_CONTRACT_BLOCKER")
    universe = tuple(sorted(readiness["diagnostic_common_universe"]))
    if len(universe) != readiness["diagnostic_common_universe_size"] or len(universe) < 5:
        raise ValueError("COMMON_DIAGNOSTIC_UNIVERSE_BLOCKER")
    frame = pd.read_csv(factor_path, dtype={"industry_code": str}, parse_dates=["trade_date"])
    if frame.duplicated(["trade_date", "industry_code"]).any():
        raise ValueError("DUPLICATE_FACTOR_ROW_BLOCKER")
    if len(frame) != readiness["industry_sessions"]:
        raise ValueError("FACTOR_MATRIX_ROW_COUNT_BLOCKER")
    frame = frame.set_index(["trade_date", "industry_code"]).sort_index()
    sessions = tuple(sorted(frame.index.get_level_values("trade_date").unique()))
    if sessions[-1].date().isoformat() != readiness["fixed_data_cutoff"]:
        raise ValueError("FIXED_CUTOFF_MISMATCH")
    config = StrategyConfig()
    models, predictions = {}, {}
    for spec in config.horizons:
        h = int(spec.horizon)
        models[str(h)], predictions[spec.horizon] = fit_retrospective_horizon(
            frame, sessions, universe, spec, readiness["horizons"][str(h)]
        )
    fused = fuse_predictions(predictions, config=config, industry_universe=universe)
    z = {
        str(int(h)): {p.industry_code: p.prediction for p in rows}
        for h, rows in fused.horizon_zscores
    }
    ranked = [
        {"rank": r.rank, "industry_code": r.industry_code, "fused_score": r.score}
        for r in fused.rankings
    ]
    report = {
        "contract": "ETF_QUANT_RETROSPECTIVE_RIDGE_ENGINEERING_V1",
        "classification": "HISTORICAL_ENGINEERING_VALIDATION_ONLY",
        "not_formal_signal": True,
        "hypothetical_signal_date": sessions[-1].date().isoformat(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "historical_data_available_at_signal": None,
        "historical_membership_pit_proven": False,
        "formal_shadow_epoch_created": False,
        "broker_or_order_created": False,
        "nav_or_performance_generated": False,
        "readiness_sha256": _sha256(readiness_path),
        "factor_matrix_sha256": _sha256(factor_path),
        "universe_policy": "DIAGNOSTIC_DATA_AVAILABILITY_INTERSECTION_NOT_FORMAL_ADMISSION",
        "common_model_universe": list(universe),
        "common_model_universe_size": len(universe),
        "models": models,
        "horizon_zscores": z,
        "engineering_top20": ranked[:20],
        "engineering_top5": ranked[:5],
        "full_engineering_ranking": ranked,
        "warning": "Retrospective fit from currently observed data; not a 2026-09-24 ex-ante prediction, strategy backtest, or performance result.",
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    path = output / f"etf_quant_engineering_ridge_{run_id}.json"
    temp = output / ("." + path.name + "." + uuid.uuid4().hex + ".partial")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    return {
        "report": str(path),
        "common_universe": len(universe),
        "horizons": {h: v["training_dates"] for h, v in models.items()},
        "engineering_top5": ranked[:5],
        "formal_signal": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--factors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.readiness, args.factors, args.output), sort_keys=True))


if __name__ == "__main__":
    main()

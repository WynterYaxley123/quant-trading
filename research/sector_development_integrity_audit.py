"""Read-only integrity audit of the frozen E001-E100 Development baseline.

This is not a model candidate or a baseline runner. It reads the two existing
research runs, reconstructs selected rows from SHA-verified canonical bars,
and writes only an audit evidence JSON under the ignored research reports tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.sector_development_baseline import (
    EXPECTED_BRANCH, EXPECTED_FEATURES, EXPECTED_IMAGE_ID, EXPECTED_PREDICTION_HASH,
    EXPECTED_SNAPSHOT, EXPECTED_SPLIT_HASH,
)
from research.sector_index_baseline import FEATURE_WARMUP
from research.sector_development_protocol import prediction_config_hash, split_policy_hash
from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
from strategies.sw_sector_rotation.src.model.model import NumPyRidge
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

ROOT = Path("reports/research/shenwan_sector_index")
RUNS = ("20260924_145948_233618_utc", "20260924_150613_787827_utc")
ARTIFACTS = (
    "predictions.csv", "per_date_metrics.csv", "aggregate_metrics.json",
    "training_diagnostics.csv", "data_quality_diagnostics.json",
)
LABEL_ORDINALS = (1, 25, 50, 75, 100)
MODEL_ORDINALS = (1, 50, 100)
FORTY_ORDINALS = (1, 10, 20, 30, 40, 50, 60, 70, 80, 100)
HORIZONS = (10, 40, 120)
TOL = 2e-10


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector_hash(values: np.ndarray) -> str:
    """Hash float64 values rounded only for cross-serialization comparison."""
    arr = np.round(np.asarray(values, dtype="<f8"), 10)
    return hashlib.sha256(arr.tobytes()).hexdigest()


def feature_hash(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def near(a: float, b: float, *, tol: float = TOL) -> float:
    diff = float(a) - float(b)
    if not np.isfinite(diff) or abs(diff) > tol:
        raise AssertionError(f"numeric mismatch: {a} versus {b}, diff={diff}")
    return diff


def endpoint(calendar: pd.DatetimeIndex, origin: pd.Timestamp, horizon: int) -> pd.Timestamp:
    pos = int(calendar.get_loc(origin))
    if pos + horizon >= len(calendar):
        raise AssertionError("label endpoint unavailable inside Development/Purge 1")
    return calendar[pos + horizon]


def label_from_bars(
    frames: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex,
    code: str, origin: pd.Timestamp, horizon: int,
) -> tuple[pd.Timestamp, float, float, float]:
    end = endpoint(calendar, origin, horizon)
    close_t = float(frames[code].at[origin, "close"])
    close_end = float(frames[code].at[end, "close"])
    return end, close_t, close_end, close_end / close_t - 1.0


def ordered_top(scores: dict[str, float], count: int = 5) -> list[str]:
    return [code for code, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:count]]


def independent_metrics(scores: np.ndarray, labels: np.ndarray,
                        top_labels: np.ndarray) -> dict[str, float]:
    rank_scores = pd.Series(scores).rank(method="average").to_numpy(dtype=float)
    rank_labels = pd.Series(labels).rank(method="average").to_numpy(dtype=float)
    top = float(np.mean(top_labels))
    universe = float(np.mean(labels))
    return {"IC": float(np.corrcoef(scores, labels)[0, 1]),
            "RankIC": float(np.corrcoef(rank_scores, rank_labels)[0, 1]),
            "Top5_forward_return": top, "Universe_forward_return": universe,
            "Top5_minus_universe": top - universe}


def _source() -> tuple[list[str], pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    processed = Path("data/processed/shenwan")
    admission = json.loads((processed / "sector_admission.json").read_text(encoding="utf-8"))
    if admission["data_snapshot_id"] != EXPECTED_SNAPSHOT:
        raise AssertionError("canonical snapshot changed")
    codes = load_sector_catalog(processed)["sector_code"].astype(str).tolist()
    # The loader SHA-verifies the complete source file, but only bars through
    # E220/Purge 1 are returned to this audit. No sealed-phase scores are read.
    panel = load_sector_panel(codes, admission["common_start_date"], "2026-03-02",
                              processed_dir=processed, allow_invalid_for_audit=True)
    if len(codes) != 124 or panel["date"].max() != pd.Timestamp("2026-03-02"):
        raise AssertionError("Development source coverage changed")
    calendar = pd.DatetimeIndex(sorted(panel["date"].unique()))
    frames = {code: panel.loc[panel["sector_code"].eq(code)].set_index("date").sort_index()
              for code in codes}
    return codes, calendar, frames


def _artifacts():
    directories = [ROOT / run for run in RUNS]
    hashes = {}
    for name in ARTIFACTS:
        values = [sha256_file(path / name) for path in directories]
        if values[0] != values[1]:
            raise AssertionError(f"repeat-run artifact differs: {name}")
        hashes[name] = values[0]
    meta = [json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            for path in directories]
    for item in meta:
        if (item["split_policy_hash"] != EXPECTED_SPLIT_HASH
                or item["prediction_config_hash"] != EXPECTED_PREDICTION_HASH
                or item["synthetic_portfolio_config_hash"] is not None
                or item["docker_image_id"] != EXPECTED_IMAGE_ID
                or item["data_snapshot_id"] != EXPECTED_SNAPSHOT
                or item["branch"] != EXPECTED_BRANCH
                or item["git_head"] != "c901e30fa3061de0463b90edd057589bd25ca6c7"
                or item["features"] != list(EXPECTED_FEATURES)
                or item["alpha"] != 0.01
                or item["horizons"] != list(HORIZONS)
                or item["fusion"] != [0.25, 0.50, 0.25]
                or item["top_k"] != 5
                or item["training_window_calendar_months"] != 6
                or item["minimum_valid_training_days"] != 30
                or item["target_definition"] != "close[t+h]/close[t]-1"
                or item["artifact_sha256"] != hashes
                or item["phase"] != "DEVELOPMENT"
                or item["executable"] is not False
                or item["validation_access"] != "SEALED"
                or item["final_oos_access"] != "SEALED"):
            raise AssertionError("frozen metadata identity mismatch")
    semantic = [{k: v for k, v in item.items() if k != "run_id"} for item in meta]
    if semantic[0] != semantic[1]:
        raise AssertionError("repeat-run semantic metadata differs")
    if split_policy_hash() != EXPECTED_SPLIT_HASH or prediction_config_hash() != EXPECTED_PREDICTION_HASH:
        raise AssertionError("current frozen protocol hash differs")
    first = directories[0]
    return (pd.read_csv(first / "predictions.csv", dtype={"sector_code": str}),
            pd.read_csv(first / "per_date_metrics.csv"),
            pd.read_csv(first / "training_diagnostics.csv"),
            json.loads((first / "aggregate_metrics.json").read_text(encoding="utf-8")),
            hashes, {"run_ids": list(RUNS), "metadata_semantically_identical": True})


def audit() -> dict:
    predictions, metrics, training, aggregate, hashes, determinism = _artifacts()
    codes, calendar, frames = _source()
    if (set(predictions["ordinal"]) != set(range(1, 101))
            or len(predictions) != 100 * 124 * 3
            or predictions.duplicated(["ordinal", "horizon", "sector_code"]).any()
            or set(training["ordinal"]) != set(range(1, 101))):
        raise AssertionError("Development output grid invalid")
    dates = predictions.groupby("ordinal")["signal_date"].first().to_dict()
    if dates[1] != "2025-04-02" or dates[100] != "2025-08-26":
        raise AssertionError("Development signal ordinal drift")
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(EXPECTED_FEATURES):
        raise AssertionError("feature-order source changed")
    evidence = {"scope": "DEVELOPMENT_ONLY_E001_E100", "target_labels": [],
                "training_windows": [], "xy_rows": [], "ridge": [],
                "prediction_orientation": [], "per_date_metrics": [],
                "aggregate": [], "forty_day": [], "outlier_120": None,
                "artifact_sha256": hashes, "determinism": determinism,
                "frozen_hashes": {"split_policy_hash": EXPECTED_SPLIT_HASH,
                                  "prediction_config_hash": EXPECTED_PREDICTION_HASH,
                                  "synthetic_portfolio_config_hash": None},
                "feature_order": list(EXPECTED_FEATURES),
                "training_anchor": "label_cutoff = common_calendar[signal_pos-h]; "
                                   "train_start = label_cutoff - 6 calendar months"}

    # A: inspect 45 sector/date/horizon labels, chosen without inspecting returns.
    for ordinal in LABEL_ORDINALS:
        signal = pd.Timestamp(dates[ordinal])
        day = predictions.loc[predictions["ordinal"].eq(ordinal)]
        top = day.loc[day["horizon"].eq(10) & day["top5"], "sector_code"].tolist()
        non_top = next(code for code in codes if code not in top)
        fixed = next(code for code in ("801193", *codes) if code not in {top[0], non_top})
        for horizon in HORIZONS:
            for code in (top[0], non_top, fixed):
                row = day.loc[day["horizon"].eq(horizon) & day["sector_code"].eq(code)].iloc[0]
                end, close_t, close_end, independent = label_from_bars(
                    frames, calendar, code, signal, horizon)
                if row["label_end"] != str(end.date()):
                    raise AssertionError("label_end mismatch")
                diff = near(row["realized_forward_return"], independent)
                evidence["target_labels"].append({
                    "ordinal": ordinal, "sector": code, "horizon": horizon,
                    "signal_date": str(signal.date()), "label_end": str(end.date()),
                    "close_t": close_t, "close_label_end": close_end,
                    "stored_label": float(row["realized_forward_return"]),
                    "independent_label": independent, "difference": diff})

    # B-E: independent source-to-matrix construction and Ridge arithmetic.
    for ordinal in MODEL_ORDINALS:
        signal = pd.Timestamp(dates[ordinal])
        signal_pos = int(calendar.get_loc(signal))
        starts = [calendar[signal_pos - h] - pd.DateOffset(months=6) for h in HORIZONS]
        warmup_pos = int(calendar.searchsorted(min(starts))) - FEATURE_WARMUP
        if warmup_pos < 0:
            raise AssertionError("factor warmup absent")
        visible_calendar = calendar[warmup_pos:signal_pos + 1]
        visible = {code: frames[code].loc[visible_calendar,
                       ["open", "high", "low", "close", "volume", "amount"]]
                   for code in codes}
        if any(len(frame) != len(visible_calendar) for frame in visible.values()):
            raise AssertionError("source panel gap in model window")
        official_panel = core.build_panel(visible, include_rsrs=False,
                                          calendar=visible_calendar)
        independent_features = {code: compute_all_price_features(visible[code], include_rsrs=False)
                                for code in codes}
        for horizon in HORIZONS:
            cutoff = calendar[signal_pos - horizon]
            start = cutoff - pd.DateOffset(months=6)
            candidate = visible_calendar[(visible_calendar >= start)
                                         & (visible_calendar <= cutoff)]
            label_col = f"fwd{horizon}"
            training_rows, xx, yy, panel_xx, panel_yy = [], [], [], [], []
            for code in sorted(codes):
                panel_rows = official_panel[code].loc[candidate]
                feature_rows = independent_features[code].loc[candidate, list(EXPECTED_FEATURES)]
                for origin in candidate:
                    end, _, _, y = label_from_bars(frames, calendar, code, origin, horizon)
                    if origin > signal or end > signal:
                        raise AssertionError("training chronology leakage")
                    vector = feature_rows.loc[origin].to_numpy(dtype=float)
                    if not np.isfinite(vector).all() or not np.isfinite(y):
                        raise AssertionError("unexpected training exclusion")
                    np.testing.assert_allclose(
                        vector, panel_rows.loc[origin, list(EXPECTED_FEATURES)].to_numpy(dtype=float),
                        rtol=0, atol=1e-12)
                    near(y, panel_rows.at[origin, label_col], tol=1e-12)
                    training_rows.append((origin, code, end, vector, y))
                    xx.append(vector)
                    yy.append(y)
                    panel_xx.append(panel_rows.loc[origin, list(EXPECTED_FEATURES)].to_numpy(dtype=float))
                    panel_yy.append(float(panel_rows.at[origin, label_col]))
            X = np.vstack(xx)
            y = np.asarray(yy, dtype=float)
            panel_X = np.vstack(panel_xx)
            panel_y = np.asarray(panel_yy, dtype=float)
            np.testing.assert_allclose(X, panel_X, rtol=0, atol=1e-12)
            np.testing.assert_allclose(y, panel_y, rtol=0, atol=1e-12)
            diag = training.loc[training["ordinal"].eq(ordinal)
                                & training["horizon"].eq(horizon)].iloc[0]
            valid_dates = sorted({row[0] for row in training_rows})
            label_ends = sorted({row[2] for row in training_rows})
            if (diag["train_start"] != str(start.date())
                    or diag["label_cutoff"] != str(cutoff.date())
                    or diag["first_train_origin"] != str(valid_dates[0].date())
                    or diag["last_train_origin"] != str(valid_dates[-1].date())
                    or diag["last_train_label_end"] != str(label_ends[-1].date())
                    or int(diag["training_candidate_days"]) != len(candidate)
                    or int(diag["training_valid_days"]) != len(valid_dates)
                    or int(diag["training_observations"]) != len(training_rows)):
                raise AssertionError("training-window diagnostics mismatch")
            evidence["training_windows"].append({
                "ordinal": ordinal, "horizon": horizon, "signal_date": str(signal.date()),
                "train_start_calendar": str(start.date()), "label_cutoff": str(cutoff.date()),
                "feature_date_earliest": str(valid_dates[0].date()),
                "feature_date_latest": str(valid_dates[-1].date()),
                "label_end_earliest": str(label_ends[0].date()),
                "label_end_latest": str(label_ends[-1].date()),
                "valid_training_dates": len(valid_dates),
                "stacked_observations": len(training_rows),
                "latest_label_not_after_signal": bool(label_ends[-1] <= signal)})
            for index in sorted({0, len(training_rows) // 2, len(training_rows) - 1}):
                origin, code, end, vector, target = training_rows[index]
                evidence["xy_rows"].append({
                    "ordinal": ordinal, "horizon": horizon, "stack_index": index,
                    "feature_date": str(origin.date()), "sector_code": code,
                    "feature_values_sha256": feature_hash(vector),
                    "target": float(target), "label_end": str(end.date()),
                    "independent_panel_row_match": True})
            # Exact NumPyRidge objective/centering/augmented least-squares;
            # also compare with the unchanged repository primitive, not sklearn.
            x_mean, y_mean = X.mean(axis=0), y.mean()
            A = np.vstack((X - x_mean, np.sqrt(0.01) * np.eye(X.shape[1])))
            b = np.concatenate((y - y_mean, np.zeros(X.shape[1])))
            coef = np.linalg.lstsq(A, b, rcond=None)[0]
            intercept = float(y_mean - x_mean @ coef)
            model = NumPyRidge(alpha=0.01).fit(X, y)
            np.testing.assert_allclose(model.coef_, coef, rtol=0, atol=1e-12)
            near(model.intercept_, intercept, tol=1e-12)
            scored = predictions.loc[predictions["ordinal"].eq(ordinal)
                                     & predictions["horizon"].eq(horizon)].set_index("sector_code")
            ordered_codes = sorted(codes)
            X_predict = np.vstack([independent_features[code].loc[signal,
                                   list(EXPECTED_FEATURES)].to_numpy(dtype=float)
                                   for code in ordered_codes])
            computed = X_predict @ coef + intercept
            primitive = model.predict(X_predict)
            np.testing.assert_allclose(computed, primitive, rtol=0, atol=1e-12)
            stored = scored.loc[ordered_codes, "prediction_score"].to_numpy(dtype=float)
            difference = np.abs(computed - stored)
            if not np.isfinite(difference).all() or float(difference.max()) > TOL:
                raise AssertionError("Ridge predictions do not reproduce official output")
            evidence["ridge"].append({
                "ordinal": ordinal, "horizon": horizon,
                "training_rows": len(X), "feature_count": X.shape[1],
                "target_vector_sha256": vector_hash(y),
                "runner_panel_target_vector_sha256": vector_hash(panel_y),
                "feature_matrix_sha256": vector_hash(X),
                "runner_panel_feature_matrix_sha256": vector_hash(panel_X),
                "coefficient_vector_sha256": vector_hash(coef),
                "primitive_coefficient_vector_sha256": vector_hash(model.coef_),
                "intercept": intercept,
                "independent_prediction_vector_sha256": vector_hash(computed),
                "stored_prediction_vector_sha256": vector_hash(stored),
                "max_abs_prediction_difference": float(difference.max()),
                "max_abs_coef_difference_vs_primitive": float(np.max(np.abs(model.coef_ - coef)))})
            if any((vector_hash(X) != vector_hash(panel_X),
                    vector_hash(y) != vector_hash(panel_y),
                    vector_hash(coef) != vector_hash(model.coef_),
                    vector_hash(computed) != vector_hash(stored))):
                raise AssertionError("normalized matrix, target, coefficient, or prediction hash differs")

    # F-G: rank orientation, fused Top5, and registered per-date metrics.
    for ordinal in MODEL_ORDINALS:
        signal = pd.Timestamp(dates[ordinal])
        day = predictions.loc[predictions["ordinal"].eq(ordinal)]
        fused = day.loc[day["horizon"].eq(10)].set_index("sector_code")["fused_score"].to_dict()
        expected_top = ordered_top(fused)
        top_flags = day.loc[day["horizon"].eq(10) & day["top5"], "sector_code"].tolist()
        if set(top_flags) != set(expected_top) or len(top_flags) != 5:
            raise AssertionError("Top5 not highest fused predictions")
        fused_order = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        ranks = day.loc[day["horizon"].eq(10)].set_index("sector_code")["fused_rank"].to_dict()
        if any(int(ranks[code]) != index for index, (code, _) in enumerate(fused_order, 1)):
            raise AssertionError("fused ranks reversed/misaligned")
        for horizon in HORIZONS:
            selected = day.loc[day["horizon"].eq(horizon)].set_index("sector_code")
            horizon_scores = selected["prediction_score"].to_dict()
            ordered = sorted(horizon_scores.items(), key=lambda kv: (-kv[1], kv[0]))
            if any(int(selected.at[code, "cross_sectional_rank"]) != index
                   for index, (code, _) in enumerate(ordered, 1)):
                raise AssertionError("horizon rank orientation mismatch")
            evidence["prediction_orientation"].append({
                "ordinal": ordinal, "horizon": horizon,
                "top10": [{"sector": code, "prediction_score": float(value), "rank": rank}
                          for rank, (code, value) in enumerate(ordered[:10], 1)],
                "fused_top5": expected_top})
            ordered_codes = sorted(codes)
            scores = np.asarray([horizon_scores[code] for code in ordered_codes], dtype=float)
            labels = np.asarray([label_from_bars(frames, calendar, code, signal, horizon)[3]
                                 for code in ordered_codes], dtype=float)
            top_labels = np.asarray([label_from_bars(frames, calendar, code, signal, horizon)[3]
                                     for code in expected_top], dtype=float)
            values = independent_metrics(scores, labels, top_labels)
            official = metrics.loc[metrics["ordinal"].eq(ordinal)
                                   & metrics["horizon"].eq(horizon)].set_index("metric")
            for stem, value in values.items():
                name = f"{stem}_{horizon}"
                stored = float(official.at[name, "value"])
                diff = near(stored, value)
                evidence["per_date_metrics"].append({
                    "ordinal": ordinal, "horizon": horizon, "metric": name,
                    "stored": stored, "independent": value, "difference": diff})

    # All registered aggregates are recomputed from existing Development rows.
    if len(metrics) != 1500 or set(metrics["ordinal"]) != set(range(1, 101)):
        raise AssertionError("aggregate input metric grid differs")
    for name, registered in aggregate.items():
        values = metrics.loc[metrics["metric"].eq(name), "value"].dropna().to_numpy(dtype=float)
        computed = {"valid_dates": len(values), "null_dates": 100 - len(values),
                    "mean": float(np.mean(values)), "median": float(np.median(values)),
                    "std": float(np.std(values, ddof=0)),
                    "min": float(np.min(values)), "max": float(np.max(values))}
        if computed["valid_dates"] != registered["valid_dates"] or computed["null_dates"] != registered["null_dates"]:
            raise AssertionError("aggregate date count differs")
        diffs = {key: near(registered[key], computed[key])
                 for key in ("mean", "median", "std", "min", "max")}
        evidence["aggregate"].append({"metric": name, "stored": registered,
                                      "independent": computed, "differences": diffs})

    # Existing 40-day negative result: ten fixed dates, source labels and
    # spread direction only. No reversed ranking or alternative performance.
    for ordinal in FORTY_ORDINALS:
        signal = pd.Timestamp(dates[ordinal])
        day = predictions.loc[predictions["ordinal"].eq(ordinal)
                              & predictions["horizon"].eq(40)].set_index("sector_code")
        scores = day["prediction_score"].to_dict()
        highest = ordered_top(scores, count=10)
        if any(int(day.at[code, "cross_sectional_rank"]) != index
               for index, code in enumerate(highest, 1)):
            raise AssertionError("40-day rank reversed")
        checked = []
        for code in highest:
            end, _, _, label = label_from_bars(frames, calendar, code, signal, 40)
            near(day.at[code, "realized_forward_return"], label)
            if day.at[code, "label_end"] != str(end.date()):
                raise AssertionError("40-day high-score label_end differs")
            checked.append({"sector": code, "rank": int(day.at[code, "cross_sectional_rank"]),
                            "label": label})
        labels = np.asarray([label_from_bars(frames, calendar, code, signal, 40)[3]
                             for code in codes], dtype=float)
        fused_top = day.loc[day["top5"]].index.tolist()
        top_mean = float(np.mean([label_from_bars(frames, calendar, code, signal, 40)[3]
                                  for code in fused_top]))
        universe_mean = float(np.mean(labels))
        spread = top_mean - universe_mean
        official = metrics.loc[metrics["ordinal"].eq(ordinal)
                               & metrics["metric"].eq("Top5_minus_universe_40"), "value"].iloc[0]
        near(official, spread)
        evidence["forty_day"].append({"ordinal": ordinal, "signal_date": str(signal.date()),
                                      "highest_horizon_score_sectors": checked,
                                      "fused_top5": fused_top,
                                      "top5_minus_universe": spread,
                                      "stored_spread": float(official)})

    # One requested 120-day positive max, no trimming or re-estimation.
    outliers = metrics.loc[metrics["metric"].eq("Top5_minus_universe_120")]
    outlier = outliers.loc[outliers["value"].idxmax()]
    ordinal = int(outlier["ordinal"])
    signal = pd.Timestamp(dates[ordinal])
    day = predictions.loc[predictions["ordinal"].eq(ordinal)
                          & predictions["horizon"].eq(120)].set_index("sector_code")
    top = day.loc[day["top5"]].index.tolist()
    if len(top) != 5 or len(set(top)) != 5 or day.index.has_duplicates:
        raise AssertionError("120-day outlier duplicated sector")
    if set(top) != set(ordered_top(day["fused_score"].to_dict())):
        raise AssertionError("120-day outlier Top5 not highest fused scores")
    by_code = {}
    for code in codes:
        end, _, _, label = label_from_bars(frames, calendar, code, signal, 120)
        if day.at[code, "label_end"] != str(end.date()):
            raise AssertionError("120-day outlier wrong endpoint")
        near(day.at[code, "realized_forward_return"], label)
        by_code[code] = label
    if not np.isfinite(list(by_code.values())).all():
        raise AssertionError("120-day outlier NaN labels")
    top_mean = float(np.mean([by_code[code] for code in top]))
    universe_mean = float(np.mean(list(by_code.values())))
    spread = top_mean - universe_mean
    near(outlier["value"], spread)
    evidence["outlier_120"] = {
        "ordinal": ordinal, "signal_date": str(signal.date()),
        "top5": [{"sector": code, "forward_label": by_code[code]} for code in top],
        "valid_universe_sector_count": len(by_code), "universe_mean": universe_mean,
        "top5_mean": top_mean, "spread": spread, "stored_spread": float(outlier["value"])}
    evidence["status"] = "DEVELOPMENT BASELINE INTEGRITY CONFIRMED"
    evidence["forty_day_conclusion"] = "NEGATIVE_DEVELOPMENT_RESULT_CONFIRMED"
    return evidence


def main() -> int:
    result = audit()
    target = ROOT / "development_integrity_audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": result["status"], "audit_path": str(target),
                      "label_checks": len(result["target_labels"]),
                      "training_windows": len(result["training_windows"]),
                      "xy_rows": len(result["xy_rows"]), "ridge_checks": len(result["ridge"]),
                      "metric_checks": len(result["per_date_metrics"]),
                      "aggregate_metrics": len(result["aggregate"]),
                      "forty_day_dates": len(result["forty_day"]),
                      "outlier_120_ordinal": result["outlier_120"]["ordinal"]},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

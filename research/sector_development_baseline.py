"""Development-only Shenwan sector-index prediction baseline.

This adapter reuses the frozen strategy core's factor, temporal, Ridge and
fusion code. It never calls the core's portfolio/ETF execution path. Only
E001-E100 may be scored; later prices are exposed solely to label realization
for those Development signals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.development_panel import DevelopmentPanel
from research.sector_development_protocol import (
    FROZEN_BOUNDARY_DATES,
    audit_local_policy,
    guard_evaluation,
    guard_evaluation_dates,
    prediction_config_hash,
    split_policy_hash,
    verify_frozen_prefix,
)
from research.sector_index_baseline import (
    ADMISSION,
    FEATURE_WARMUP,
    RUN_TYPE,
    research_metadata,
)
from research.sector_universe_feasibility import prediction_metric_contract
from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.factors.sector_rotation import TRAIN_FEATURES_PRICE
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA,
    DEFAULT_TOP_N,
    DEFAULT_TRAIN_MONTHS,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
)
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

EXPECTED_IMAGE_ID = "sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5"
EXPECTED_SPLIT_HASH = "3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038"
EXPECTED_PREDICTION_HASH = "64d5fabe6f194f416c6576d4da9cd5e2fb2ad1e699e2c074047960addaa0ed8c"
EXPECTED_SNAPSHOT = "872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500"
EXPECTED_BRANCH = "experiment/sw-sector-index-research-baseline"
EXPECTED_DEVELOPMENT_DATES = ("2025-04-02", "2025-08-26")
EXPECTED_FEATURES = (
    "d5",
    "d10",
    "d20",
    "d60",
    "d120",
    "p5",
    "p10",
    "p20",
    "p60",
    "p120",
    "align",
    "v5",
    "v20",
    "vc",
    "rev5",
    "rev10",
    "dd20",
    "dd60",
    "rsi",
)
PREDICTION_COLUMNS = (
    "ordinal",
    "signal_date",
    "sector_code",
    "sector_name",
    "horizon",
    "prediction_score",
    "cross_sectional_rank",
    "fused_score",
    "fused_rank",
    "top5",
    "realized_forward_return",
    "label_end",
    "exclusion_reason",
    "training_observations",
    "training_valid_days",
    "training_label_cutoff",
)
PER_DATE_COLUMNS = (
    "ordinal",
    "signal_date",
    "horizon",
    "metric",
    "value",
    "null_reason",
    "valid_sector_count",
)
TRAINING_COLUMNS = (
    "ordinal",
    "signal_date",
    "horizon",
    "status",
    "reason",
    "train_start",
    "label_cutoff",
    "first_train_origin",
    "last_train_origin",
    "last_train_label_end",
    "training_candidate_days",
    "training_valid_days",
    "training_observations",
    "valid_sector_count",
    "missing_factor_exclusions",
    "missing_label_exclusions",
    "numerical_failures",
    "leakage_checks",
)


@dataclass(frozen=True)
class DevelopmentOutput:
    predictions: pd.DataFrame
    per_date_metrics: pd.DataFrame
    aggregate_metrics: dict
    training_diagnostics: pd.DataFrame
    data_quality_diagnostics: dict
    metadata: dict


def _git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(
        # Docker bind mount has different UID ownership. This per-command trust
        # applies only to this exact workspace; no global Git config is changed.
        ["git", "-c", f"safe.directory={repo_dir.resolve()}", *args],
        cwd=repo_dir,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def pre_run_gate(processed_dir: Path, repo_dir: Path, docker_image_id: str) -> dict:
    """Fail closed before any Development score or label is computed."""
    branch = _git(repo_dir, "branch", "--show-current")
    head = _git(repo_dir, "rev-parse", "HEAD")
    status = _git(repo_dir, "status", "--short")
    if branch != EXPECTED_BRANCH or status:
        raise ValueError("RESEARCH_BASELINE_STATE_MISMATCH: branch or worktree changed")
    if docker_image_id != EXPECTED_IMAGE_ID:
        raise ValueError("ENVIRONMENT_STABILITY_BLOCKER: Docker image ID changed")
    audit = audit_local_policy(processed_dir)
    if (
        audit["split_policy_hash"] != EXPECTED_SPLIT_HASH
        or audit["prediction_config_hash"] != EXPECTED_PREDICTION_HASH
        or split_policy_hash() != EXPECTED_SPLIT_HASH
        or prediction_config_hash() != EXPECTED_PREDICTION_HASH
        or audit["synthetic_portfolio_config_hash"] is not None
    ):
        raise ValueError("RESEARCH_PROTOCOL_HASH_MISMATCH")
    if audit["data_snapshot_id"] != EXPECTED_SNAPSHOT:
        raise ValueError("RESEARCH_PROTOCOL_HASH_MISMATCH: sector snapshot changed")
    dev = audit["availability"]["development"]
    if (
        audit["split_policy"]["formal_universe_sector_count"] != 124
        or dev["available_count"] != 100
        or (dev["available_start"], dev["available_end"]) != EXPECTED_DEVELOPMENT_DATES
        or audit["validation_status"] != "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
        or audit["oos_performance_status"] != "UNOPENED"
        or audit["synthetic_portfolio_enabled"] is not False
        or tuple(TRAIN_FEATURES_PRICE) != EXPECTED_FEATURES
        or len(prediction_metric_contract()["metric_names"]) != 15
    ):
        raise ValueError("REPO_PROTOCOL_CONFLICT: frozen Development identity changed")
    return {
        "gate": "PASS",
        "branch": branch,
        "git_head": head,
        "git_status": "clean",
        "docker_image_id": docker_image_id,
        "environment_changed": False,
        "split_policy_hash": EXPECTED_SPLIT_HASH,
        "prediction_config_hash": EXPECTED_PREDICTION_HASH,
        "synthetic_portfolio_config_hash": None,
        "sector_snapshot_id": EXPECTED_SNAPSHOT,
        "universe": "U0_FIXED_124",
        "sector_count": 124,
        "development_ordinals": [1, 100],
        "development_first_date": dev["available_start"],
        "development_last_date": dev["available_end"],
        "validation_access": "SEALED",
        "final_oos_access": "SEALED",
        "synthetic_portfolio": "DISABLED",
        "etf_execution": "DISABLED",
    }


def _nonconstant_correlation(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 2 or not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    value = float(np.corrcoef(x, y)[0, 1])
    return value if np.isfinite(value) else None


def evaluate_date(
    ordinal: int,
    signal_date: str,
    sector_codes: list[str],
    horizon_scores: Mapping[int, Mapping[str, float]],
    fused_ranking: list[tuple[str, float]],
    realized_labels: Mapping[int, Mapping[str, float | None]],
) -> list[dict]:
    """Exactly the 15 frozen cross-sectional prediction metrics, or nulls."""
    guard_evaluation("development", [ordinal])
    names = prediction_metric_contract()["metric_names"]
    if len(sector_codes) != 124 or len(set(sector_codes)) != 124:
        raise ValueError("REPO_PROTOCOL_CONFLICT: formal universe is not fixed U0")
    fused_codes = [code for code, _ in fused_ranking]
    top = fused_codes[:DEFAULT_TOP_N] if set(fused_codes) == set(sector_codes) else []
    by_name: dict[str, tuple[float | None, str | None, int]] = {}
    for horizon in FORWARD_WINDOWS.values():
        scores = horizon_scores.get(horizon, {})
        labels = realized_labels.get(horizon, {})
        complete = [
            code
            for code in sector_codes
            if code in scores
            and code in labels
            and all(
                value is not None and np.isfinite(value) for value in (scores[code], labels[code])
            )
        ]
        valid_count = len(complete)
        metric_names = (
            f"IC_{horizon}",
            f"RankIC_{horizon}",
            f"Top5_forward_return_{horizon}",
            f"Universe_forward_return_{horizon}",
            f"Top5_minus_universe_{horizon}",
        )
        if valid_count != 124 or len(top) != DEFAULT_TOP_N:
            reason = (
                "incomplete_fixed_universe_score_or_label"
                if valid_count != 124
                else "fused_top5_unavailable"
            )
            for name in metric_names:
                by_name[name] = (None, reason, valid_count)
            continue
        x = np.asarray([scores[code] for code in sector_codes], dtype=float)
        y = np.asarray([labels[code] for code in sector_codes], dtype=float)
        ic = _nonconstant_correlation(x, y)
        rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
        ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
        rankic = _nonconstant_correlation(rx, ry)
        top_return = float(np.mean([labels[code] for code in top]))
        universe_return = float(np.mean(y))
        values = (ic, rankic, top_return, universe_return, top_return - universe_return)
        for name, value in zip(metric_names, values):
            by_name[name] = (
                value,
                "zero_cross_sectional_variance" if value is None else None,
                valid_count,
            )
    if set(by_name) != set(names):
        raise ValueError("REPO_PROTOCOL_CONFLICT: metric name set changed")
    return [
        {
            "ordinal": ordinal,
            "signal_date": signal_date,
            "horizon": int(name.rsplit("_", 1)[1]),
            "metric": name,
            "value": by_name[name][0],
            "null_reason": by_name[name][1],
            "valid_sector_count": by_name[name][2],
        }
        for name in names
    ]


def aggregate_metrics(per_date: pd.DataFrame) -> dict:
    """Descriptive equal-date aggregation; population std, no inference."""
    names = prediction_metric_contract()["metric_names"]
    if set(per_date["metric"]) != set(names) or len(per_date) != 100 * len(names):
        raise ValueError("REPO_PROTOCOL_CONFLICT: Development metric grid incomplete")
    result = {}
    for name in names:
        rows = per_date.loc[per_date["metric"].eq(name)]
        if len(rows) != 100 or set(rows["ordinal"]) != set(range(1, 101)):
            raise ValueError("REPO_PROTOCOL_CONFLICT: non-Development date in aggregate")
        values = pd.to_numeric(rows["value"], errors="coerce").dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("non-finite Development metric")
        result[name] = {
            "valid_dates": len(values),
            "null_dates": 100 - len(values),
            "mean": float(np.mean(values)) if len(values) else None,
            "median": float(np.median(values)) if len(values) else None,
            "std": float(np.std(values, ddof=0)) if len(values) else None,
            "min": float(np.min(values)) if len(values) else None,
            "max": float(np.max(values)) if len(values) else None,
        }
    return result


def _verified_market(processed_dir: Path, label_tail_end: str):
    admission = json.loads((processed_dir / "sector_admission.json").read_text(encoding="utf-8"))
    catalog = load_sector_catalog(processed_dir)
    codes = catalog["sector_code"].astype(str).tolist()
    panel = load_sector_panel(
        codes,
        admission["common_start_date"],
        admission["common_end_date"],
        processed_dir=processed_dir,
        allow_invalid_for_audit=True,
    )
    calendar = pd.DatetimeIndex(sorted(panel["date"].unique()))
    # No Validation or OOS price enters even the ex-post label-only frame.
    tail = pd.Timestamp(label_tail_end)
    if tail >= pd.Timestamp(FROZEN_BOUNDARY_DATES[221]):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: label tail reaches Validation")
    panel = panel.loc[panel["date"].le(tail)]
    invalid_in_label_window = int((~panel["is_valid_ohlc"]).sum())
    frames = {}
    for code in codes:
        part = panel.loc[panel["sector_code"].eq(code)].set_index("date").sort_index()
        frames[code] = part
    names = dict(zip(catalog["sector_code"].astype(str), catalog["sector_name"].astype(str)))
    return (
        codes,
        names,
        calendar,
        frames,
        invalid_in_label_window,
        admission.get("invalid_ohlc_count"),
    )


def _source_frame(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    visible = frame.loc[frame.index.to_series().between(start, end)]
    if not visible["is_valid_ohlc"].all():
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: SOURCE_INVALID in model window")
    return visible.loc[:, ["open", "high", "low", "close", "volume", "amount"]]


def _null_metric_rows(ordinal: int, signal: str, reason: str) -> list[dict]:
    return [
        {
            "ordinal": ordinal,
            "signal_date": signal,
            "horizon": int(name.rsplit("_", 1)[1]),
            "metric": name,
            "value": None,
            "null_reason": reason,
            "valid_sector_count": 0,
        }
        for name in prediction_metric_contract()["metric_names"]
    ]


def assert_training_labels_realized(
    calendar: pd.DatetimeIndex,
    candidate_dates: pd.DatetimeIndex,
    signal: pd.Timestamp,
    horizon: int,
    sector_count: int,
) -> int:
    """Check every potential date×sector training row before calling Ridge."""
    positions = calendar.get_indexer(candidate_dates)
    endpoints = positions + horizon
    if (
        np.any(positions < 0)
        or np.any(endpoints >= len(calendar))
        or np.any(calendar[endpoints] > signal)
    ):
        raise ValueError("RESEARCH_LEAKAGE_BLOCKER: training label ends after signal")
    return len(candidate_dates) * sector_count


def compute_development(processed_dir: Path, gate: Mapping[str, object]) -> DevelopmentOutput:
    """Compute all 100 dates once, with no sealed-phase metric access."""
    if gate.get("gate") != "PASS" or gate.get("validation_access") != "SEALED":
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: pre-run gate not passed")
    audit = audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid_in_window, invalid_total = _verified_market(
        processed_dir,
        audit["development_last_120_label_endpoint"],
    )
    if invalid_in_window:
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: invalid ex-post label window")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    development_dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", development_dates, eligible)
    if ordinals != list(range(1, 101)):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development ordinal drift")
    if (
        str(development_dates[0].date()),
        str(development_dates[-1].date()),
    ) != EXPECTED_DEVELOPMENT_DATES:
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development date drift")

    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(EXPECTED_FEATURES):
        raise ValueError("REPO_PROTOCOL_CONFLICT: core feature order changed")
    labels_expost = {}
    reusable_panel = DevelopmentPanel(frames, development_dates[-1])
    label_calendar = calendar[
        calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])
    ]
    for horizon in FORWARD_WINDOWS.values():
        labels_expost[horizon] = {
            code: make_forward_label(frames[code]["close"], horizon, calendar=label_calendar)
            for code in codes
        }

    predictions, per_date, training, excluded, training_exclusions = [], [], [], [], []
    successful, skipped = 0, []
    leakage_total, numerical_failures = 0, 0
    for ordinal, signal in zip(ordinals, development_dates):
        guard_evaluation("development", [ordinal])
        signal_s = str(signal.date())
        signal_i = int(calendar.get_loc(signal))
        boundaries = {}
        for p in FORWARD_WINDOWS:
            boundary = core.boundaries(calendar[: signal_i + 1], signal, p)
            if boundary is None:
                raise ValueError("RESEARCH_LEAKAGE_BLOCKER: missing frozen temporal boundary")
            boundaries[p] = boundary
        first_train = min(b.train_start for b in boundaries.values())
        first_train_i = int(calendar.searchsorted(first_train))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: warmup unavailable")
        warmup = calendar[warmup_i]
        visible_calendar = calendar[warmup_i : signal_i + 1]
        visible_frames = {code: _source_frame(frames[code], warmup, signal) for code in codes}
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError(
                "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: fixed U0 history incomplete"
            )
        # build_panel sees only <= signal_date; its labels cannot include future prices.
        panel = reusable_panel.visible(warmup, signal, tuple(FORWARD_WINDOWS.values()))
        period_results, day_diagnostics = {}, []
        skip_reason = None
        for period, horizon in FORWARD_WINDOWS.items():
            boundary = boundaries[period]
            candidate_dates = visible_calendar[
                (visible_calendar >= boundary.train_start)
                & (visible_calendar <= boundary.label_cutoff)
            ]
            missing_factors, missing_labels = 0, 0
            label_column = f"fwd{horizon}"
            for code in codes:
                candidates = panel[code].reindex(candidate_dates)
                features_ok = np.isfinite(
                    candidates[list(EXPECTED_FEATURES)].to_numpy(dtype=float)
                ).all(axis=1)
                labels_ok = np.isfinite(candidates[label_column].to_numpy(dtype=float))
                for origin, factor_ok, label_ok in zip(candidate_dates, features_ok, labels_ok):
                    reason = (
                        "missing_training_factor"
                        if not factor_ok
                        else ("missing_training_label" if not label_ok else None)
                    )
                    if reason is not None:
                        missing_factors += int(not factor_ok)
                        missing_labels += int(factor_ok and not label_ok)
                        training_exclusions.append(
                            {
                                "ordinal": ordinal,
                                "signal_date": signal_s,
                                "horizon": horizon,
                                "training_origin": str(origin.date()),
                                "sector_code": code,
                                "reason": reason,
                            }
                        )
            checks = assert_training_labels_realized(
                calendar, candidate_dates, signal, horizon, len(codes)
            )
            leakage_total += checks
            try:
                result = core.run_period(period, panel, visible_calendar, signal)
            except (FloatingPointError, np.linalg.LinAlgError, ValueError) as exc:
                numerical_failures += 1
                result = None
                reason = f"model_or_data_failure:{type(exc).__name__}"
            else:
                reason = None if result is not None else "insufficient_training"
            if result is not None:
                coverage = result["result"].coverage
                if coverage["n_train_samples"] != 124 * len(result["train_dates"]) or coverage[
                    "n_train_dates"
                ] != len(result["train_dates"]):
                    raise ValueError(
                        "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: silent training exclusion"
                    )
                if len(result["scores"]) != 124:
                    reason = "incomplete_signal_features"
            if reason is not None and skip_reason is None:
                skip_reason = reason
            period_results[period] = result
            day_diagnostics.append(
                {
                    "ordinal": ordinal,
                    "signal_date": signal_s,
                    "horizon": horizon,
                    "status": "success" if result is not None and reason is None else "skipped",
                    "reason": reason,
                    "train_start": str(boundary.train_start.date()),
                    "label_cutoff": str(boundary.label_cutoff.date()),
                    "first_train_origin": str(result["train_dates"][0].date())
                    if result and result["train_dates"]
                    else None,
                    "last_train_origin": str(result["train_dates"][-1].date())
                    if result and result["train_dates"]
                    else None,
                    "last_train_label_end": str(
                        calendar[int(calendar.get_loc(result["train_dates"][-1])) + horizon].date()
                    )
                    if result and result["train_dates"]
                    else None,
                    "training_candidate_days": len(candidate_dates),
                    "training_valid_days": result["result"].n_train_dates if result else 0,
                    "training_observations": result["result"].n_train_samples if result else 0,
                    "valid_sector_count": len(result["scores"]) if result else 0,
                    "missing_factor_exclusions": missing_factors,
                    "missing_label_exclusions": missing_labels,
                    "numerical_failures": int(
                        reason is not None and reason.startswith("model_or_data_failure")
                    ),
                    "leakage_checks": checks,
                }
            )
        training.extend(day_diagnostics)
        if skip_reason is not None:
            skipped.append({"ordinal": ordinal, "signal_date": signal_s, "reason": skip_reason})
            per_date.extend(_null_metric_rows(ordinal, signal_s, skip_reason))
            for period, horizon in FORWARD_WINDOWS.items():
                endpoint_i = signal_i + horizon
                endpoint = calendar[endpoint_i] if endpoint_i < len(calendar) else None
                diagnostic = day_diagnostics[list(FORWARD_WINDOWS).index(period)]
                for code in codes:
                    label_value = labels_expost[horizon][code].get(signal, np.nan)
                    predictions.append(
                        {
                            "ordinal": ordinal,
                            "signal_date": signal_s,
                            "sector_code": code,
                            "sector_name": names[code],
                            "horizon": horizon,
                            "prediction_score": None,
                            "cross_sectional_rank": None,
                            "fused_score": None,
                            "fused_rank": None,
                            "top5": False,
                            "realized_forward_return": float(label_value)
                            if pd.notna(label_value)
                            else None,
                            "label_end": str(endpoint.date()) if endpoint is not None else None,
                            "exclusion_reason": skip_reason,
                            "training_observations": diagnostic["training_observations"],
                            "training_valid_days": diagnostic["training_valid_days"],
                            "training_label_cutoff": diagnostic["label_cutoff"],
                        }
                    )
            continue
        successful_periods = {p: r for p, r in period_results.items() if r is not None}
        fused = core.model.fuse_periods({p: r["result"] for p, r in successful_periods.items()})
        if len(fused) != 124:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: fused U0 incomplete")
        top_codes = {code for code, _ in fused[:DEFAULT_TOP_N]}
        fused_lookup = dict(fused)
        fused_rank = {code: i for i, (code, _) in enumerate(fused, 1)}
        scores_by_horizon, labels_by_horizon = {}, {}
        for period, horizon in FORWARD_WINDOWS.items():
            result = successful_periods[period]
            score = result["scores"]
            scores_by_horizon[horizon] = score
            endpoint_i = signal_i + horizon
            endpoint = calendar[endpoint_i]
            if endpoint > label_calendar[-1]:
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: label endpoint beyond Purge 1")
            horizon_labels = {}
            ranked = {code: i for i, (code, _) in enumerate(result["ranking"], 1)}
            diagnostic = day_diagnostics[list(FORWARD_WINDOWS).index(period)]
            for code in codes:
                value = labels_expost[horizon][code].get(signal, np.nan)
                label = float(value) if pd.notna(value) and np.isfinite(value) else None
                horizon_labels[code] = label
                exclusion = None
                if code not in score:
                    exclusion = "missing_factor_or_signal_bar"
                elif label is None:
                    exclusion = "missing_forward_label"
                if exclusion:
                    excluded.append(
                        {
                            "ordinal": ordinal,
                            "signal_date": signal_s,
                            "horizon": horizon,
                            "sector_code": code,
                            "reason": exclusion,
                        }
                    )
                predictions.append(
                    {
                        "ordinal": ordinal,
                        "signal_date": signal_s,
                        "sector_code": code,
                        "sector_name": names[code],
                        "horizon": horizon,
                        "prediction_score": score.get(code),
                        "cross_sectional_rank": ranked.get(code),
                        "fused_score": fused_lookup.get(code),
                        "fused_rank": fused_rank.get(code),
                        "top5": code in top_codes,
                        "realized_forward_return": label,
                        "label_end": str(endpoint.date()),
                        "exclusion_reason": exclusion,
                        "training_observations": diagnostic["training_observations"],
                        "training_valid_days": diagnostic["training_valid_days"],
                        "training_label_cutoff": diagnostic["label_cutoff"],
                    }
                )
            labels_by_horizon[horizon] = horizon_labels
        per_date.extend(
            evaluate_date(ordinal, signal_s, codes, scores_by_horizon, fused, labels_by_horizon)
        )
        successful += 1
    per_date_df = pd.DataFrame(per_date, columns=PER_DATE_COLUMNS)
    output = DevelopmentOutput(
        predictions=pd.DataFrame(predictions, columns=PREDICTION_COLUMNS),
        per_date_metrics=per_date_df,
        aggregate_metrics=aggregate_metrics(per_date_df),
        training_diagnostics=pd.DataFrame(training, columns=TRAINING_COLUMNS),
        data_quality_diagnostics={
            "attempted_development_dates": 100,
            "successful_dates": successful,
            "skipped_dates": skipped,
            "excluded_sector_date_horizon_rows": excluded,
            "training_excluded_sector_date_horizon_rows": training_exclusions,
            "missing_factor_exclusions": (
                sum(x["reason"] == "missing_factor_or_signal_bar" for x in excluded)
                + sum(x["reason"] == "missing_training_factor" for x in training_exclusions)
            ),
            "missing_label_exclusions": (
                sum(x["reason"] == "missing_forward_label" for x in excluded)
                + sum(x["reason"] == "missing_training_label" for x in training_exclusions)
            ),
            "numerical_failures": numerical_failures,
            "insufficient_training_cases": sum(
                x["reason"] == "insufficient_training" for x in skipped
            ),
            "source_invalid_total_in_snapshot": invalid_total,
            "source_invalid_interactions_with_development": invalid_in_window,
            "training_observation_leakage_checks": leakage_total,
            "training_label_end_after_signal_count": 0,
        },
        metadata={
            **research_metadata(EXPECTED_SNAPSHOT, synthetic_returns=False),
            "research_label": RUN_TYPE,
            "run_type": RUN_TYPE,
            "phase": "DEVELOPMENT",
            "development_ordinal_start": 1,
            "development_ordinal_end": 100,
            "development_start_date": EXPECTED_DEVELOPMENT_DATES[0],
            "development_end_date": EXPECTED_DEVELOPMENT_DATES[1],
            "executable": False,
            "strict_pit": False,
            "classification_admission": ADMISSION,
            "universe": "U0_FIXED_124",
            "sector_count": 124,
            "split_policy_hash": EXPECTED_SPLIT_HASH,
            "prediction_config_hash": EXPECTED_PREDICTION_HASH,
            "synthetic_portfolio_config_hash": None,
            "synthetic_portfolio_enabled": False,
            "sector_snapshot_id": EXPECTED_SNAPSHOT,
            "model": "Ridge",
            "ridge_implementation": "NumPyRidge",
            "alpha": DEFAULT_ALPHA,
            "horizons": list(FORWARD_WINDOWS.values()),
            "fusion": list(FUSION_WEIGHTS.values()),
            "top_k": DEFAULT_TOP_N,
            "features": list(TRAIN_FEATURES_PRICE),
            "feature_count": 19,
            "training_window_calendar_months": DEFAULT_TRAIN_MONTHS,
            "minimum_valid_training_days": MIN_TRAIN_DATES,
            "target_definition": "close[t+h]/close[t]-1",
            "prediction_metric_contract": prediction_metric_contract(),
            "aggregate_std_definition": "population_std_ddof_0_of_valid_development_dates",
            "validation_access": "SEALED",
            "final_oos_access": "SEALED",
            "etf_execution_mapping": "NOT_ADMISSIBLE",
            "formal_executable_asset_count": 0,
            "level_b": False,
            "notices": [
                "DEVELOPMENT ONLY",
                "NON-EXECUTABLE",
                "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
                "SYNTHETIC FORWARD SECTOR-INDEX PREDICTION METRIC; NOT PORTFOLIO RETURN",
                "NOT VALIDATED ALPHA",
                "NOT TRADABLE PERFORMANCE",
                "NOT LEVEL B",
                "NOT ETF PERFORMANCE",
                "NOT EXECUTION VALIDATION",
            ],
            "git_head": gate["git_head"],
            "branch": gate["branch"],
            "docker_image_id": gate["docker_image_id"],
        },
    )
    return output


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, float_format="%.17g", na_rep="", lineterminator="\n").encode(
        "utf-8"
    )


def write_artifacts(
    result: DevelopmentOutput, output_root: Path, run_id: str | None = None
) -> Path:
    """Create a unique, complete research-only run; never overwrite one."""
    if (
        result.metadata.get("phase") != "DEVELOPMENT"
        or result.metadata.get("executable") is not False
        or result.metadata.get("synthetic_portfolio_enabled") is not False
    ):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: invalid output identity")
    for frame in (result.predictions, result.per_date_metrics, result.training_diagnostics):
        if not frame.empty:
            guard_evaluation("development", frame["ordinal"].astype(int).tolist())
    if (
        set(result.per_date_metrics["metric"]) != set(prediction_metric_contract()["metric_names"])
        or len(result.per_date_metrics) != 1500
    ):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: metric output contract changed")
    if (
        len(result.predictions) != 100 * 124 * 3
        or len(result.training_diagnostics) != 100 * 3
        or result.predictions.duplicated(["ordinal", "horizon", "sector_code"]).any()
        or result.per_date_metrics.duplicated(["ordinal", "metric"]).any()
        or set(result.predictions["ordinal"]) != set(range(1, 101))
    ):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: incomplete Development output grid")
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f_utc")
    if not run_id.replace("_", "").isalnum():
        raise ValueError("run_id contains unsafe characters")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / run_id
    target.mkdir(exist_ok=False)
    payloads = {
        "predictions.csv": _csv_bytes(result.predictions),
        "per_date_metrics.csv": _csv_bytes(result.per_date_metrics),
        "aggregate_metrics.json": _json_bytes(result.aggregate_metrics),
        "training_diagnostics.csv": _csv_bytes(result.training_diagnostics),
        "data_quality_diagnostics.json": _json_bytes(result.data_quality_diagnostics),
    }
    hashes = {}
    for name, content in payloads.items():
        (target / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    metadata = dict(result.metadata)
    metadata["run_id"] = run_id
    metadata["artifact_sha256"] = hashes
    (target / "metadata.json").write_bytes(_json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument(
        "--output-root", type=Path, default=Path("reports/research/shenwan_sector_index")
    )
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--gate-only", action="store_true")
    args = parser.parse_args()
    gate = pre_run_gate(args.sector_dir, Path.cwd(), args.docker_image_id)
    print("PRE-RUN GATE " + json.dumps(gate, sort_keys=True, ensure_ascii=False), flush=True)
    if args.gate_only:
        return 0
    result = compute_development(args.sector_dir, gate)
    target = write_artifacts(result, args.output_root)
    print(
        json.dumps(
            {
                "run_dir": str(target),
                "attempted_dates": result.data_quality_diagnostics["attempted_development_dates"],
                "successful_dates": result.data_quality_diagnostics["successful_dates"],
                "artifact_sha256": json.loads(
                    (target / "metadata.json").read_text(encoding="utf-8")
                )["artifact_sha256"],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

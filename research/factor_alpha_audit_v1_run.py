"""Execute the frozen Factor Alpha Audit V1 on Development signals only.

Diagnostic research: single-factor IC/RankIC, quantile structure, stability
blocks, redundancy and coverage for the frozen 19 price factors. No model is
fitted, no factor is selected, flipped, or deleted, and no sealed-phase
signal date is ever evaluated. Purge 1 prices are used only to realize
Development labels, exactly as in the frozen baseline adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import factor_alpha_audit_v1_protocol as protocol
from research import sector_development_baseline as baseline
from research.sector_development_protocol import (
    guard_evaluation, guard_evaluation_dates, verify_frozen_prefix,
)
from research.sector_index_baseline import FEATURE_WARMUP
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
from strategies.sw_sector_rotation.src.model.model import FORWARD_WINDOWS
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

HORIZONS = protocol.HORIZONS
FACTOR_ORDER = protocol.FACTOR_ORDER
ITERATION1_RUN_ID = "iteration1_20260924_163607_787266_utc"
ITERATION1_D0_PREDICTIONS_SHA256 = (
    "b1e7da60109e048e79a9dee14d8c1b15aa9afa010768c28d00efa4d4d14869f1"
)
ARTIFACT_NAMES = (
    "factor_horizon_summary.csv", "factor_daily_metrics.csv",
    "factor_quantile_summary.csv", "factor_quantile_daily.csv",
    "factor_stability_blocks.csv", "factor_correlation_spearman.csv",
    "factor_redundancy_flags.csv", "factor_coverage.csv", "audit_summary.json",
)
DAILY_COLUMNS = (
    "ordinal", "signal_date", "factor", "horizon", "valid_pairs",
    "ic", "rankic", "skipped", "skip_reason",
)
HORIZON_SUMMARY_COLUMNS = (
    "factor", "horizon", "valid_dates", "skipped_dates",
    "ic_mean", "ic_median", "ic_std", "ic_min", "ic_max",
    "rankic_mean", "rankic_median", "rankic_std", "rankic_min", "rankic_max",
    "positive_rankic_dates", "negative_rankic_dates", "zero_rankic_dates",
    "q5_minus_q1_mean", "quantile_monotonicity", "rankic_t_stat_descriptive",
)
QUANTILE_DAILY_COLUMNS = (
    "ordinal", "signal_date", "factor", "horizon", "valid_pairs",
    "q1_mean", "q2_mean", "q3_mean", "q4_mean", "q5_mean", "q5_minus_q1",
    "skipped", "skip_reason",
)
QUANTILE_SUMMARY_COLUMNS = (
    "factor", "horizon", "valid_dates", "q1_mean", "q2_mean", "q3_mean",
    "q4_mean", "q5_mean", "q5_minus_q1_mean", "quantile_monotonicity",
)
BLOCK_COLUMNS = (
    "factor", "horizon", "block", "block_ordinal_start", "block_ordinal_end",
    "valid_dates", "rankic_mean", "rankic_median",
    "full_development_rankic_mean", "full_development_sign", "same_sign_block_count",
)
CORR_COLUMNS = (
    "factor_a", "factor_b", "mean_daily_spearman", "valid_dates", "flagged_redundant",
)
FLAGS_COLUMNS = (
    "factor_a", "factor_b", "mean_daily_spearman", "abs_mean_daily_spearman", "valid_dates",
)
COVERAGE_COLUMNS = (
    "factor", "horizon", "development_dates_total", "valid_factor_observations",
    "missing_factor_observations", "valid_sectors_min", "valid_sectors_median",
    "valid_sectors_max", "valid_factor_label_pairs", "skipped_ic_dates",
)


@dataclass(frozen=True)
class AuditOutput:
    daily_metrics: pd.DataFrame
    horizon_summary: pd.DataFrame
    quantile_daily: pd.DataFrame
    quantile_summary: pd.DataFrame
    stability_blocks: pd.DataFrame
    correlation: pd.DataFrame
    redundancy_flags: pd.DataFrame
    coverage: pd.DataFrame
    audit_summary: dict
    metadata: dict


def _stat(values: list[float]) -> dict:
    """Population descriptive statistics over valid dates (null when empty)."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if not len(arr):
        return {"mean": None, "median": None, "std": None, "min": None, "max": None}
    return {"mean": float(np.mean(arr)), "median": float(np.median(arr)),
            "std": float(np.std(arr, ddof=0)), "min": float(np.min(arr)),
            "max": float(np.max(arr))}


def headline_rows(horizon_summary: pd.DataFrame) -> list[dict]:
    """NaN-free JSON-native headline rows for audit_summary.json."""
    int_keys = {"horizon", "valid_dates", "positive_rankic_dates",
                "negative_rankic_dates", "zero_rankic_dates"}
    keys = ("factor", "horizon", "valid_dates", "ic_mean", "rankic_mean",
            "rankic_median", "rankic_std", "q5_minus_q1_mean",
            "quantile_monotonicity", "positive_rankic_dates",
            "negative_rankic_dates", "zero_rankic_dates")
    rows = []
    for record in horizon_summary.loc[:, list(keys)].to_dict("records"):
        cleaned = {}
        for key, value in record.items():
            if isinstance(value, str):
                cleaned[key] = value
            elif value is None or pd.isna(value):
                cleaned[key] = None
            elif key in int_keys:
                cleaned[key] = int(value)
            else:
                cleaned[key] = float(value)
        rows.append(cleaned)
    return rows


def factor_identity_gate(factor_matrix: np.ndarray, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str]) -> dict:
    """Sampled audit-vs-independent recomputation of factor values (hard gate)."""
    if tuple(FACTOR_ORDER) != tuple(baseline.EXPECTED_FEATURES):
        raise ValueError("FACTOR_ORDER_FROZEN_VIOLATION")
    sampled = list(protocol.IDENTITY_SAMPLE_ORDINALS)
    sectors = codes[:protocol.IDENTITY_SAMPLE_SECTOR_COUNT]
    max_diff = 0.0
    comparisons = 0
    for ordinal in sampled:
        signal = development_dates[ordinal - 1]
        for code in sectors:
            independent = compute_all_price_features(
                baseline._source_frame(frames[code], frames[code].index[0], signal),
                include_rsrs=False,
            ).loc[signal, list(FACTOR_ORDER)].to_numpy(dtype=float)
            recorded = factor_matrix[ordinal - 1, codes.index(code), :]
            if independent.shape != recorded.shape or not np.isfinite(independent).all():
                raise ValueError("FACTOR_IDENTITY_BLOCKER: independent recomputation invalid")
            diff = float(np.max(np.abs(independent - recorded)))
            max_diff = max(max_diff, diff)
            comparisons += len(FACTOR_ORDER)
            if diff > protocol.FACTOR_IDENTITY_TOLERANCE:
                raise ValueError("FACTOR_IDENTITY_BLOCKER")
    return {
        "status": "PASS", "sampled_ordinals": sampled,
        "sampled_dates": [str(development_dates[i - 1].date()) for i in sampled],
        "sampled_factors": list(FACTOR_ORDER), "sampled_sector_count": len(sectors),
        "comparisons": comparisons, "max_abs_diff": max_diff,
        "tolerance_abs": protocol.FACTOR_IDENTITY_TOLERANCE,
        "column_order_matches_frozen": True,
    }


def target_identity_gate(label_matrix: dict, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str],
                         d0_control_dir: Path) -> dict:
    """Sampled audit-vs-direct-arithmetic-vs-D0-artifact labels (hard gate)."""
    digest = hashlib.sha256((d0_control_dir / "predictions.csv").read_bytes()).hexdigest()
    if digest != ITERATION1_D0_PREDICTIONS_SHA256:
        raise ValueError("TARGET_IDENTITY_BLOCKER: D0 control artifact hash changed")
    d0 = pd.read_csv(d0_control_dir / "predictions.csv", dtype={"sector_code": str})
    lookup = {(int(row.ordinal), int(row.horizon), str(row.sector_code)): row
              for row in d0.itertuples(index=False)}
    sampled = list(protocol.IDENTITY_SAMPLE_ORDINALS)
    sectors = codes[:protocol.IDENTITY_SAMPLE_SECTOR_COUNT]
    max_diff_direct = 0.0
    max_diff_d0 = 0.0
    comparisons = 0
    for ordinal in sampled:
        signal = development_dates[ordinal - 1]
        signal_i = int(calendar.get_loc(signal))
        for horizon in HORIZONS:
            endpoint = calendar[signal_i + horizon]
            for code in sectors:
                recorded = float(label_matrix[horizon][ordinal - 1, codes.index(code)])
                close = frames[code]["close"]
                direct = float(close.loc[endpoint]) / float(close.loc[signal]) - 1.0
                row = lookup[(ordinal, horizon, code)]
                artifact = float(row.realized_forward_return)
                if str(row.label_end) != str(endpoint.date()):
                    raise ValueError("TARGET_IDENTITY_BLOCKER: endpoint semantics drift")
                diff_direct = abs(recorded - direct)
                diff_d0 = abs(recorded - artifact)
                max_diff_direct = max(max_diff_direct, diff_direct)
                max_diff_d0 = max(max_diff_d0, diff_d0)
                comparisons += 1
                if (diff_direct > protocol.TARGET_IDENTITY_TOLERANCE
                        or diff_d0 > protocol.TARGET_IDENTITY_TOLERANCE):
                    raise ValueError("TARGET_IDENTITY_BLOCKER")
    return {
        "status": "PASS", "sampled_ordinals": sampled,
        "sampled_dates": [str(development_dates[i - 1].date()) for i in sampled],
        "sampled_horizons": list(HORIZONS), "sampled_sector_count": len(sectors),
        "comparisons": comparisons, "max_abs_diff_direct_arithmetic": max_diff_direct,
        "max_abs_diff_d0_control_artifact": max_diff_d0,
        "tolerance_abs": protocol.TARGET_IDENTITY_TOLERANCE,
        "endpoint_semantics": "common_trading_calendar_t_plus_h_confirmed",
        "d0_control_predictions_sha256": digest,
    }


def build_tables(factor_matrix: np.ndarray, label_matrix: dict,
                 development_dates: pd.DatetimeIndex, codes: list[str]) -> dict[str, pd.DataFrame]:
    """All preregistered tables from the frozen factor/label matrices."""
    n_dates, _, n_factors = factor_matrix.shape
    ordinals = list(range(1, n_dates + 1))
    date_strings = [str(day.date()) for day in development_dates]
    daily_rows, qdaily_rows = [], []
    summary_rows, qsummary_rows, block_rows, coverage_rows = [], [], [], []
    for j, factor in enumerate(FACTOR_ORDER):
        factor_col = factor_matrix[:, :, j]
        finite_per_date = np.isfinite(factor_col).sum(axis=1)
        for horizon in HORIZONS:
            labels = label_matrix[horizon]
            ic_values, rankic_values, q_spreads = [], [], []
            quantile_means_lists = {q: [] for q in range(1, protocol.QUANTILE_COUNT + 1)}
            per_date_rankic: dict[int, float] = {}
            valid_pairs_total, skipped_dates = 0, 0
            for d in range(n_dates):
                x, y = factor_col[d], labels[d]
                result = protocol.cross_sectional_ic(x, y)
                daily_rows.append({
                    "ordinal": ordinals[d], "signal_date": date_strings[d],
                    "factor": factor, "horizon": horizon,
                    "valid_pairs": result["valid_pairs"], "ic": result["ic"],
                    "rankic": result["rankic"], "skipped": result["skipped"],
                    "skip_reason": result["skip_reason"],
                })
                valid_pairs_total += result["valid_pairs"]
                if result["skipped"]:
                    skipped_dates += 1
                    qdaily_rows.append({
                        "ordinal": ordinals[d], "signal_date": date_strings[d],
                        "factor": factor, "horizon": horizon,
                        "valid_pairs": result["valid_pairs"], "q1_mean": None,
                        "q2_mean": None, "q3_mean": None, "q4_mean": None,
                        "q5_mean": None, "q5_minus_q1": None,
                        "skipped": True, "skip_reason": result["skip_reason"],
                    })
                    continue
                ic_values.append(result["ic"])
                rankic_values.append(result["rankic"])
                per_date_rankic[ordinals[d]] = result["rankic"]
                mask = np.isfinite(x) & np.isfinite(y)
                members = [codes[i] for i in np.flatnonzero(mask)]
                assignments = protocol.assign_quantiles(x[mask], members)
                spread = protocol.quantile_spread(
                    assignments, {code: float(y[codes.index(code)]) for code in members},
                )
                means = spread["quantile_means"]
                q_spreads.append(spread["q5_minus_q1"])
                for q in range(1, protocol.QUANTILE_COUNT + 1):
                    quantile_means_lists[q].append(means[q])
                qdaily_rows.append({
                    "ordinal": ordinals[d], "signal_date": date_strings[d],
                    "factor": factor, "horizon": horizon,
                    "valid_pairs": result["valid_pairs"],
                    "q1_mean": means[1], "q2_mean": means[2], "q3_mean": means[3],
                    "q4_mean": means[4], "q5_mean": means[5],
                    "q5_minus_q1": spread["q5_minus_q1"],
                    "skipped": False, "skip_reason": None,
                })
            ic_stats, ric_stats = _stat(ic_values), _stat(rankic_values)
            q_agg = {q: (float(np.mean(vals)) if vals else None)
                     for q, vals in quantile_means_lists.items()}
            monotonicity = protocol.quantile_monotonicity(
                [q_agg[q] for q in range(1, protocol.QUANTILE_COUNT + 1)])
            summary_rows.append({
                "factor": factor, "horizon": horizon,
                "valid_dates": len(rankic_values), "skipped_dates": skipped_dates,
                "ic_mean": ic_stats["mean"], "ic_median": ic_stats["median"],
                "ic_std": ic_stats["std"], "ic_min": ic_stats["min"], "ic_max": ic_stats["max"],
                "rankic_mean": ric_stats["mean"], "rankic_median": ric_stats["median"],
                "rankic_std": ric_stats["std"], "rankic_min": ric_stats["min"],
                "rankic_max": ric_stats["max"],
                "positive_rankic_dates": sum(1 for v in rankic_values if v > 0),
                "negative_rankic_dates": sum(1 for v in rankic_values if v < 0),
                "zero_rankic_dates": sum(1 for v in rankic_values if v == 0),
                "q5_minus_q1_mean": (float(np.mean(q_spreads)) if q_spreads else None),
                "quantile_monotonicity": monotonicity,
                "rankic_t_stat_descriptive": protocol.descriptive_t_stat(rankic_values),
            })
            qsummary_rows.append({
                "factor": factor, "horizon": horizon,
                "valid_dates": len(q_spreads),
                "q1_mean": q_agg[1], "q2_mean": q_agg[2], "q3_mean": q_agg[3],
                "q4_mean": q_agg[4], "q5_mean": q_agg[5],
                "q5_minus_q1_mean": (float(np.mean(q_spreads)) if q_spreads else None),
                "quantile_monotonicity": monotonicity,
            })
            block_means = []
            for block, start, end in protocol.STABILITY_BLOCKS:
                values = [per_date_rankic[o] for o in range(start, end + 1)
                          if o in per_date_rankic]
                stats = _stat(values)
                block_means.append(stats["mean"])
                block_rows.append({
                    "factor": factor, "horizon": horizon, "block": block,
                    "block_ordinal_start": start, "block_ordinal_end": end,
                    "valid_dates": len(values), "rankic_mean": stats["mean"],
                    "rankic_median": stats["median"],
                    "full_development_rankic_mean": ric_stats["mean"],
                    "full_development_sign": None, "same_sign_block_count": None,
                })
            sign_info = protocol.block_summary(block_means, ric_stats["mean"])
            for row in block_rows[-len(protocol.STABILITY_BLOCKS):]:
                row["full_development_sign"] = sign_info["full_development_sign"]
                row["same_sign_block_count"] = sign_info["same_sign_block_count"]
            coverage_rows.append({
                "factor": factor, "horizon": horizon,
                "development_dates_total": n_dates,
                "valid_factor_observations": int(finite_per_date.sum()),
                "missing_factor_observations": int(n_dates * len(codes) - finite_per_date.sum()),
                "valid_sectors_min": int(finite_per_date.min()),
                "valid_sectors_median": float(np.median(finite_per_date)),
                "valid_sectors_max": int(finite_per_date.max()),
                "valid_factor_label_pairs": valid_pairs_total,
                "skipped_ic_dates": skipped_dates,
            })
    corr_rows, flag_rows = [], []
    sums = np.zeros((n_factors, n_factors), dtype=float)
    counts = np.zeros((n_factors, n_factors), dtype=int)
    for d in range(n_dates):
        for a in range(n_factors):
            for b in range(n_factors):
                result = protocol.cross_sectional_spearman(
                    factor_matrix[d, :, a], factor_matrix[d, :, b])
                if not result["skipped"]:
                    sums[a, b] += result["spearman"]
                    counts[a, b] += 1
    for a, factor_a in enumerate(FACTOR_ORDER):
        for b, factor_b in enumerate(FACTOR_ORDER):
            mean = (float(sums[a, b] / counts[a, b]) if counts[a, b] else None)
            flagged = bool(a != b and protocol.redundancy_flag(mean))
            corr_rows.append({
                "factor_a": factor_a, "factor_b": factor_b,
                "mean_daily_spearman": mean, "valid_dates": int(counts[a, b]),
                "flagged_redundant": flagged,
            })
            if a < b and protocol.redundancy_flag(mean):
                flag_rows.append({
                    "factor_a": factor_a, "factor_b": factor_b,
                    "mean_daily_spearman": mean,
                    "abs_mean_daily_spearman": abs(float(mean)),
                    "valid_dates": int(counts[a, b]),
                })
    return {
        "factor_daily_metrics.csv": pd.DataFrame(daily_rows, columns=DAILY_COLUMNS),
        "factor_horizon_summary.csv": pd.DataFrame(summary_rows, columns=HORIZON_SUMMARY_COLUMNS),
        "factor_quantile_daily.csv": pd.DataFrame(qdaily_rows, columns=QUANTILE_DAILY_COLUMNS),
        "factor_quantile_summary.csv": pd.DataFrame(qsummary_rows, columns=QUANTILE_SUMMARY_COLUMNS),
        "factor_stability_blocks.csv": pd.DataFrame(block_rows, columns=BLOCK_COLUMNS),
        "factor_correlation_spearman.csv": pd.DataFrame(corr_rows, columns=CORR_COLUMNS),
        "factor_redundancy_flags.csv": pd.DataFrame(flag_rows, columns=FLAGS_COLUMNS),
        "factor_coverage.csv": pd.DataFrame(coverage_rows, columns=COVERAGE_COLUMNS),
    }


def audit_development(processed_dir: Path, d0_control_dir: Path, gate: dict) -> AuditOutput:
    """Compute the whole Development audit once, sealed phases untouched."""
    if gate.get("gate") != "PASS" or gate.get("validation_access") != "SEALED":
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: pre-run gate not passed")
    protocol.verify_frozen_factor_alpha_audit_v1_protocol()
    audit = baseline.audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid_in_window, invalid_total = baseline._verified_market(
        processed_dir, audit["development_last_120_label_endpoint"],
    )
    if invalid_in_window or len(codes) != 124:
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: invalid fixed universe")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    development_dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", development_dates, eligible)
    if (ordinals != list(range(1, 101))
            or (str(development_dates[0].date()), str(development_dates[-1].date()))
            != baseline.EXPECTED_DEVELOPMENT_DATES):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development ordinal drift")
    label_calendar = calendar[calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])]
    labels_expost = {
        horizon: {code: make_forward_label(frames[code]["close"], horizon, calendar=label_calendar)
                  for code in codes}
        for horizon in HORIZONS
    }
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(baseline.EXPECTED_FEATURES):
        raise ValueError("REPO_PROTOCOL_CONFLICT: feature order")
    n_dates, n_codes = len(development_dates), len(codes)
    factor_matrix = np.empty((n_dates, n_codes, len(FACTOR_ORDER)), dtype=float)
    label_matrix = {h: np.full((n_dates, n_codes), np.nan, dtype=float) for h in HORIZONS}
    for d, (ordinal, signal) in enumerate(zip(ordinals, development_dates)):
        protocol.guard_audit_scope("development", [ordinal])
        signal_i = int(calendar.get_loc(signal))
        boundaries = {p: core.boundaries(calendar[:signal_i + 1], signal, p)
                      for p in FORWARD_WINDOWS}
        if any(value is None for value in boundaries.values()):
            raise ValueError("RESEARCH_LEAKAGE_BLOCKER: missing frozen temporal boundary")
        first_train_i = int(calendar.searchsorted(
            min(b.train_start for b in boundaries.values())))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: warmup unavailable")
        visible_calendar = calendar[warmup_i:signal_i + 1]
        visible_frames = {code: baseline._source_frame(frames[code], calendar[warmup_i], signal)
                          for code in codes}
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: U0 history incomplete")
        # Identical call path to the Ridge pipeline's factor inputs.
        panel = core.build_panel(visible_frames, include_rsrs=False, calendar=visible_calendar)
        for c, code in enumerate(codes):
            factor_matrix[d, c, :] = panel[code].loc[signal, list(FACTOR_ORDER)].to_numpy(dtype=float)
            for horizon in HORIZONS:
                value = labels_expost[horizon][code].get(signal, np.nan)
                label_matrix[horizon][d, c] = float(value) if pd.notna(value) else np.nan
    factor_identity = factor_identity_gate(factor_matrix, frames, calendar,
                                           development_dates, codes)
    target_identity = target_identity_gate(label_matrix, frames, calendar,
                                           development_dates, codes, d0_control_dir)
    tables = build_tables(factor_matrix, label_matrix, development_dates, codes)
    summary_headlines = headline_rows(tables["factor_horizon_summary.csv"])
    audit_summary = {
        "audit_type": protocol.AUDIT_TYPE,
        "protocol_name": protocol.PROTOCOL_NAME,
        "protocol_hash": protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH,
        "sample": {
            "development_eligible_ids": "E001-E100",
            "development_ordinals": [1, 100],
            "development_first_date": str(development_dates[0].date()),
            "development_last_date": str(development_dates[-1].date()),
            "sector_count": n_codes,
        },
        "config": {
            "factor_order": list(FACTOR_ORDER), "horizons": list(HORIZONS),
            "min_valid_sector_pairs": protocol.MIN_VALID_SECTOR_PAIRS,
            "quantile_count": protocol.QUANTILE_COUNT,
            "redundancy_threshold": protocol.REDUNDANCY_THRESHOLD,
            "stability_blocks": [list(block) for block in protocol.STABILITY_BLOCKS],
            "t_stats": "DESCRIPTIVE_ONLY",
        },
        "identity": {"factor_identity": factor_identity, "target_identity": target_identity},
        "counts": {
            "factor_horizon_rows": len(tables["factor_horizon_summary.csv"]),
            "daily_metric_rows": len(tables["factor_daily_metrics.csv"]),
            "skipped_daily_rows": int(tables["factor_daily_metrics.csv"]["skipped"].sum()),
            "redundancy_flagged_pairs": len(tables["factor_redundancy_flags.csv"]),
            "correlation_pairs_computed": int(
                (tables["factor_correlation_spearman.csv"]["valid_dates"] > 0).sum()),
        },
        "factor_horizon_headlines": summary_headlines,
        "notices": [
            "DEVELOPMENT ONLY", "DIAGNOSTIC ONLY", "NO FACTOR SELECTION",
            "NO PARAMETER SELECTION", "NO SIGN OPTIMIZATION", "DESCRIPTIVE T STATS ONLY",
            "NOT VALIDATED", "NOT TRADABLE", "NOT LEVEL B",
        ],
    }
    metadata = {
        "researchLabel": "SECTOR_INDEX_RESEARCH_ONLY",
        "phase": "DEVELOPMENT",
        "auditType": protocol.AUDIT_TYPE,
        "gitCommit": gate["git_head"],
        "protocolHash": protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH,
        "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
        "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
        "factorOrder": list(FACTOR_ORDER),
        "horizons": list(HORIZONS),
        "developmentEligibleIds": "E001-E100",
        "minimumValidSectorPairs": protocol.MIN_VALID_SECTOR_PAIRS,
        "quantileCount": protocol.QUANTILE_COUNT,
        "redundancyThreshold": protocol.REDUNDANCY_THRESHOLD,
        "strictPit": False,
        "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "executable": False,
        "tradable": False,
        "validation": "SEALED",
        "finalOos": "SEALED",
        "NO_PARAMETER_SELECTION": True,
        "NO_FACTOR_SELECTION": True,
        "DIAGNOSTIC_ONLY": True,
        "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
        "universe": "U0_FIXED_124", "sector_count": n_codes,
        "development_ordinals": [1, 100],
        "development_first_date": str(development_dates[0].date()),
        "development_last_date": str(development_dates[-1].date()),
        "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "synthetic_portfolio_config_hash": None,
        "etf_execution": "DISABLED", "level_b": "DISABLED",
        "synthetic_portfolio": "DISABLED",
        "branch": gate["branch"], "docker_image_id": gate["docker_image_id"],
        "environment_changed": False,
        "factor_identity_check": factor_identity,
        "target_identity_check": target_identity,
        "iteration1_d0_control_run_id": ITERATION1_RUN_ID,
        "iteration1_d0_predictions_sha256": ITERATION1_D0_PREDICTIONS_SHA256,
        "source_invalid_total_in_snapshot": invalid_total,
        "source_invalid_interactions_with_development": invalid_in_window,
    }
    return AuditOutput(
        daily_metrics=tables["factor_daily_metrics.csv"],
        horizon_summary=tables["factor_horizon_summary.csv"],
        quantile_daily=tables["factor_quantile_daily.csv"],
        quantile_summary=tables["factor_quantile_summary.csv"],
        stability_blocks=tables["factor_stability_blocks.csv"],
        correlation=tables["factor_correlation_spearman.csv"],
        redundancy_flags=tables["factor_redundancy_flags.csv"],
        coverage=tables["factor_coverage.csv"],
        audit_summary=audit_summary,
        metadata=metadata,
    )


def write_run(output_root: Path, result: AuditOutput, repeat_of: Path | None = None) -> Path:
    """Create a unique diagnostic run; non-metadata bytes must be reproducible."""
    if (result.metadata.get("phase") != "DEVELOPMENT"
            or result.metadata.get("executable") is not False
            or result.metadata.get("tradable") is not False
            or result.metadata.get("DIAGNOSTIC_ONLY") is not True
            or result.metadata.get("NO_FACTOR_SELECTION") is not True
            or result.metadata.get("NO_PARAMETER_SELECTION") is not True):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: invalid audit output identity")
    if (len(result.daily_metrics) != 100 * len(FACTOR_ORDER) * len(HORIZONS)
            or len(result.quantile_daily) != 100 * len(FACTOR_ORDER) * len(HORIZONS)
            or len(result.horizon_summary) != len(FACTOR_ORDER) * len(HORIZONS)
            or len(result.stability_blocks) != len(FACTOR_ORDER) * len(HORIZONS) * 4
            or len(result.correlation) != len(FACTOR_ORDER) ** 2):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: audit output grid incomplete")
    guard_evaluation("development", sorted(set(result.daily_metrics["ordinal"].astype(int))))
    run_id = datetime.now(timezone.utc).strftime("factor_alpha_audit_%Y%m%d_%H%M%S_%f_utc")
    if not run_id.replace("_", "").isalnum():
        raise ValueError("run_id contains unsafe characters")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / run_id
    target.mkdir(exist_ok=False)
    payloads = {
        "factor_horizon_summary.csv": baseline._csv_bytes(result.horizon_summary),
        "factor_daily_metrics.csv": baseline._csv_bytes(result.daily_metrics),
        "factor_quantile_summary.csv": baseline._csv_bytes(result.quantile_summary),
        "factor_quantile_daily.csv": baseline._csv_bytes(result.quantile_daily),
        "factor_stability_blocks.csv": baseline._csv_bytes(result.stability_blocks),
        "factor_correlation_spearman.csv": baseline._csv_bytes(result.correlation),
        "factor_redundancy_flags.csv": baseline._csv_bytes(result.redundancy_flags),
        "factor_coverage.csv": baseline._csv_bytes(result.coverage),
        "audit_summary.json": baseline._json_bytes(result.audit_summary),
    }
    hashes = {}
    for name, content in payloads.items():
        (target / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    metadata = dict(result.metadata)
    metadata["run_id"] = run_id
    metadata["content_sha256"] = hashes
    if repeat_of is not None:
        previous = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if (previous["content_sha256"] != hashes
                or previous["protocolHash"] != metadata["protocolHash"]):
            raise ValueError("FACTOR_AUDIT_DETERMINISM_BLOCKER")
        metadata["determinism_repeat_of"] = previous["run_id"]
        metadata["determinism"] = "PASS_CONTENT_SHA256_IDENTICAL"
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def pre_run_gate(processed_dir: Path, repo_dir: Path, docker_image_id: str) -> dict:
    """Fail closed before any Development factor or label is computed."""
    protocol.verify_frozen_factor_alpha_audit_v1_protocol()
    gate = baseline.pre_run_gate(processed_dir, repo_dir, docker_image_id)
    if tuple(FACTOR_ORDER) != tuple(baseline.EXPECTED_FEATURES) or len(FACTOR_ORDER) != 19:
        raise ValueError("FACTOR_ORDER_FROZEN_VIOLATION")
    return {
        **gate,
        "audit_type": protocol.AUDIT_TYPE,
        "factor_alpha_audit_v1_protocol_hash":
            protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH,
        "factor_count": 19, "horizons": list(HORIZONS),
        "min_valid_sector_pairs": protocol.MIN_VALID_SECTOR_PAIRS,
        "quantile_count": protocol.QUANTILE_COUNT,
        "redundancy_threshold": protocol.REDUNDANCY_THRESHOLD,
        "NO_PARAMETER_SELECTION": True, "NO_FACTOR_SELECTION": True,
        "DIAGNOSTIC_ONLY": True, "audit_results_viewed_before_freeze": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index"))
    parser.add_argument("--d0-control-dir", type=Path,
                        default=Path("reports/research/shenwan_sector_index")
                        / ITERATION1_RUN_ID / "D0")
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo_dir = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(args.processed_dir, repo_dir, args.docker_image_id)
    print("FACTOR ALPHA AUDIT V1 PRE-RUN GATE", flush=True)
    print(json.dumps(gate, sort_keys=True, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    result = audit_development(args.processed_dir, args.d0_control_dir, gate)
    target = write_run(args.output_root, result, args.repeat_of)
    print(f"FACTOR ALPHA AUDIT V1 RUN COMPLETE: {target}", flush=True)
    print(json.dumps({"run_dir": str(target),
                      "content_sha256": json.loads(
                          (target / "metadata.json").read_text(encoding="utf-8"))["content_sha256"]},
                     sort_keys=True, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

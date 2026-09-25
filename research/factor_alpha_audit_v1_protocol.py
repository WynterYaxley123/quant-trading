"""Preregistered, result-free Factor Alpha Audit V1 protocol.

Only pure array/tabular diagnostics and the canonical protocol identity live
here. This module does not load sector data, fit any model, or compute audit
results. Every frozen rule (sample, labels, IC/RankIC, stability blocks,
quantiles, redundancy threshold, identity gates, determinism) is fixed in the
canonical payload before any result exists; a future runner must fail closed
on semantic drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite, sqrt

import numpy as np
import pandas as pd

from research.sector_development_baseline import (
    EXPECTED_FEATURES, EXPECTED_PREDICTION_HASH, EXPECTED_SNAPSHOT, EXPECTED_SPLIT_HASH,
)
from research.sector_development_protocol import (
    canonical_hash, guard_evaluation, prediction_config_hash, split_policy_hash,
)

PROTOCOL_NAME = "SHENWAN_FACTOR_ALPHA_AUDIT_V1"
AUDIT_TYPE = "FACTOR_ALPHA_AUDIT_V1"
FACTOR_ORDER: tuple[str, ...] = tuple(EXPECTED_FEATURES)
HORIZONS: tuple[int, ...] = (10, 40, 120)
MIN_VALID_SECTOR_PAIRS = 30
QUANTILE_COUNT = 5
REDUNDANCY_THRESHOLD = 0.80
STABILITY_BLOCKS: tuple[tuple[int, int, int], ...] = (
    (1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 100),
)
IDENTITY_SAMPLE_ORDINALS: tuple[int, ...] = (1, 50, 100)
IDENTITY_SAMPLE_SECTOR_COUNT = 10
FACTOR_IDENTITY_TOLERANCE = 1e-9
TARGET_IDENTITY_TOLERANCE = 1e-12

# Set only after the canonical payload is frozen. Never derive this constant
# dynamically at import: the runner must fail closed on semantic drift.
FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH = (
    "87e6e9c3ac79f1f41239d8c91080b16fd142343dea470084226e23512286b815"
)


def factor_alpha_audit_v1_payload() -> dict:
    """One canonical, result-free protocol identity; no data or result I/O."""
    if (split_policy_hash() != EXPECTED_SPLIT_HASH
            or prediction_config_hash() != EXPECTED_PREDICTION_HASH
            or tuple(EXPECTED_FEATURES) != FACTOR_ORDER):
        raise ValueError("FACTOR_AUDIT_BASELINE_IDENTITY_MISMATCH")
    return {
        "protocol_name": PROTOCOL_NAME,
        "audit_type": AUDIT_TYPE,
        "research_identity": {
            "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
            "phase": "DEVELOPMENT",
            "audit_scope": "DIAGNOSTIC_ONLY",
            "executable": False,
            "tradable": False,
            "strict_pit": False,
            "classification_admission": "FIXED_CLASSIFICATION_RESEARCH",
            "sector_snapshot_id": EXPECTED_SNAPSHOT,
            "etf_execution": "DISABLED",
            "level_b": "DISABLED",
            "synthetic_portfolio": "DISABLED",
            "validation_access": "SEALED",
            "final_oos_access": "SEALED",
        },
        "baseline_identity": {
            "split_policy_hash": EXPECTED_SPLIT_HASH,
            "prediction_config_hash": EXPECTED_PREDICTION_HASH,
            "synthetic_portfolio_config_hash": None,
        },
        "selection_flags": {
            "NO_PARAMETER_SELECTION": True,
            "NO_FACTOR_SELECTION": True,
            "DIAGNOSTIC_ONLY": True,
        },
        "sample": {
            "universe": "U0_FIXED_124",
            "sector_count": 124,
            "development_eligible_ids": "E001-E100",
            "development_ordinals": [1, 100],
            "signal_dates_from_split_policy_not_hardcoded": True,
            "forbidden_signal_phases": ["purge_1", "validation", "purge_2", "final_oos"],
            "label_realization_window_ends_at": "development_last_120_label_endpoint",
        },
        "factors": {
            "factor_order": list(FACTOR_ORDER),
            "factor_count": 19,
            "source": "frozen_strategy_core_compute_all_price_features_via_build_panel",
            "identical_to_ridge_input": True,
            "include_rsrs": False,
            "missing_policy": "exclude_pair_no_imputation_no_fill_no_zero",
            "direction_policy": "signed_results_no_auto_flip_no_direction_optimization",
        },
        "labels": {
            "horizons_sessions": list(HORIZONS),
            "definition": "close[t+h]/close[t]-1",
            "endpoint_semantics": "common_project_trading_calendar_t_plus_h_endpoint",
            "missing_endpoint": "label_missing_endpoint_never_shifted_or_filled",
            "transformation": "none_absolute_forward_return",
        },
        "ic_audit": {
            "min_valid_sector_pairs": MIN_VALID_SECTOR_PAIRS,
            "below_min_pairs": "mark_skipped_with_reason",
            "pearson_ic": True,
            "spearman_rankic": True,
            "rank_tie_method": "average",
            "zero_variance": "null_with_reason",
            "aggregation_std": "population_std_ddof_0_of_valid_dates",
            "rankic_sign_counts": ["positive", "negative", "zero_exactly_0.0"],
            "descriptive_t_stat": "mean_over_sample_std_ddof_1_times_sqrt_n_DESCRIPTIVE_ONLY",
        },
        "stability": {
            "blocks": [
                {"block": block, "ordinal_start": start, "ordinal_end": end,
                 "ids": f"E{start:03d}-E{end:03d}"}
                for block, start, end in STABILITY_BLOCKS
            ],
            "block_count": 4,
            "same_sign_rule": "block_mean_rankic_times_full_mean_rankic_strictly_positive",
            "zero_block_mean_never_counts": True,
            "null_when_full_mean_null_or_zero": True,
            "descriptive_only": True,
        },
        "quantiles": {
            "quantile_count": QUANTILE_COUNT,
            "sort": "raw_factor_value_ascending",
            "tie_break": "sector_code_ascending",
            "assignment": "contiguous_blocks_q1_lowest_first_remainder_to_earliest_quantiles",
            "members_per_quantile": "n_div_5_each_plus_1_for_first_n_mod_5_quantiles",
            "q_spread": "q5_minus_q1_per_date_then_equal_date_mean",
            "quantile_means": "equal_date_mean_of_per_date_quantile_means",
            "monotonicity": "spearman_quantile_index_1_to_5_vs_aggregate_quantile_mean_return",
            "same_valid_dates_as_ic_audit": True,
            "descriptive_only": True,
        },
        "redundancy": {
            "method": "per_date_cross_sectional_spearman_then_mean_over_valid_dates",
            "pairs": "ordered_factor_pairs_including_diagonal",
            "common_valid_sectors_per_date_min": MIN_VALID_SECTOR_PAIRS,
            "flag_rule": "abs_mean_daily_spearman_gte_threshold",
            "threshold": REDUNDANCY_THRESHOLD,
            "no_automatic_factor_removal": True,
        },
        "missingness": {
            "imputation": "FORBIDDEN",
            "fill": "FORBIDDEN",
            "zero_fill": "FORBIDDEN",
            "interpolation": "FORBIDDEN",
            "report": ["valid_factor_observations", "missing_observations",
                       "valid_sectors_per_date_min_median_max",
                       "valid_factor_label_pairs", "skipped_ic_dates"],
        },
        "identity_tests": {
            "factor_identity": {
                "sample_ordinals": list(IDENTITY_SAMPLE_ORDINALS),
                "sample_factors": list(FACTOR_ORDER),
                "sample_sectors": "first_10_sector_codes_ascending",
                "independent_path": "compute_all_price_features_on_independently_windowed_frame",
                "column_order_check": True,
                "tolerance_abs": FACTOR_IDENTITY_TOLERANCE,
                "on_mismatch": "FACTOR_IDENTITY_BLOCKER",
            },
            "target_identity": {
                "sample_ordinals": list(IDENTITY_SAMPLE_ORDINALS),
                "sample_horizons": list(HORIZONS),
                "sample_sectors": "first_10_sector_codes_ascending",
                "independent_paths": ["direct_close_calendar_arithmetic",
                                      "frozen_iteration1_d0_control_artifact"],
                "endpoint_check": "label_end_must_equal_calendar_t_plus_h",
                "tolerance_abs": TARGET_IDENTITY_TOLERANCE,
                "on_mismatch": "TARGET_IDENTITY_BLOCKER",
            },
        },
        "determinism": {
            "rerun_with_unchanged_inputs": True,
            "non_metadata_artifacts_byte_identical": True,
            "allowed_differences": ["run_timestamps", "run_id_in_metadata"],
            "on_mismatch": "FACTOR_AUDIT_DETERMINISM_BLOCKER",
        },
        "artifacts": [
            "metadata.json", "factor_horizon_summary.csv", "factor_daily_metrics.csv",
            "factor_quantile_summary.csv", "factor_quantile_daily.csv",
            "factor_stability_blocks.csv", "factor_correlation_spearman.csv",
            "factor_redundancy_flags.csv", "factor_coverage.csv", "audit_summary.json",
        ],
        "statistical_policy": {
            "t_stats": "DESCRIPTIVE_ONLY",
            "p_value_ranking": "FORBIDDEN",
            "t_stat_threshold_promotion": "FORBIDDEN",
            "multiple_testing_winner_selection": "FORBIDDEN",
            "winner_crowning": "FORBIDDEN",
        },
        "prohibitions": [
            "delete_factor", "flip_factor_sign", "redefine_momentum", "change_horizon",
            "tune_ridge_alpha", "tune_train_window", "tune_fusion_weights", "tune_top_k",
            "try_other_models", "automatic_factor_combination_search",
            "highest_ic_subset_selection", "create_D4_D5_D6", "open_validation",
            "open_final_oos", "portfolio_backtest", "etf_mapping", "qmt",
            "modify_dashboard_or_api", "parameter_search",
        ],
    }


def factor_alpha_audit_v1_protocol_hash(payload: Mapping | None = None) -> str:
    """SHA-256 of canonical sorted JSON; excludes timestamps and results."""
    return canonical_hash(factor_alpha_audit_v1_payload() if payload is None else payload)


def verify_frozen_factor_alpha_audit_v1_protocol(*, supplied_hash: str | None = None) -> dict:
    """Hard fail if the committed payload or a supplied runner hash drifts."""
    payload = factor_alpha_audit_v1_payload()
    actual = factor_alpha_audit_v1_protocol_hash(payload)
    if (actual != FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH
            or (supplied_hash is not None and supplied_hash != actual)):
        raise ValueError("FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH_MISMATCH")
    if (tuple(payload["factors"]["factor_order"]) != FACTOR_ORDER
            or payload["ic_audit"]["min_valid_sector_pairs"] != MIN_VALID_SECTOR_PAIRS
            or payload["quantiles"]["quantile_count"] != QUANTILE_COUNT
            or payload["redundancy"]["threshold"] != REDUNDANCY_THRESHOLD
            or payload["labels"]["horizons_sessions"] != list(HORIZONS)):
        raise ValueError("FACTOR_ALPHA_AUDIT_V1_PROTOCOL_RULE_MISMATCH")
    return payload


def guard_audit_scope(phase: str, ordinals: Sequence[int]) -> None:
    """Structural guard for the runner; Development ordinals only."""
    if tuple(FACTOR_ORDER) != tuple(EXPECTED_FEATURES) or len(FACTOR_ORDER) != 19:
        raise ValueError("FACTOR_ORDER_FROZEN_VIOLATION")
    guard_evaluation(phase, ordinals)


def block_for_ordinal(ordinal: int) -> int | None:
    """Fixed block membership; never adapted to market regimes."""
    for block, start, end in STABILITY_BLOCKS:
        if start <= ordinal <= end:
            return block
    return None


def cross_sectional_ic(x: Sequence[float], y: Sequence[float],
                       *, min_pairs: int = MIN_VALID_SECTOR_PAIRS) -> dict:
    """Signed Pearson IC and Spearman RankIC on pairwise-finite observations.

    Returns ``{"valid_pairs", "skipped", "skip_reason", "ic", "rankic"}``.
    No imputation: non-finite observations are excluded, and below the pair
    minimum the date is skipped with a reason instead of being dropped
    silently. Zero cross-sectional variance yields null metrics with a reason.
    """
    if isinstance(min_pairs, bool) or not isinstance(min_pairs, int) or min_pairs < 1:
        raise ValueError("min_pairs must be a positive integer")
    xv = np.asarray(x, dtype=float)
    yv = np.asarray(y, dtype=float)
    if xv.ndim != 1 or yv.ndim != 1 or len(xv) != len(yv):
        raise ValueError("IC inputs must be aligned 1D arrays")
    mask = np.isfinite(xv) & np.isfinite(yv)
    n = int(mask.sum())
    base = {"valid_pairs": n, "skipped": False, "skip_reason": None,
            "ic": None, "rankic": None}
    if n < min_pairs:
        return {**base, "skipped": True,
                "skip_reason": "below_min_valid_sector_pairs"}
    xs, ys = xv[mask], yv[mask]
    if float(np.std(xs)) == 0.0 or float(np.std(ys)) == 0.0:
        return {**base, "skipped": True, "skip_reason": "zero_cross_sectional_variance"}
    ic = float(np.corrcoef(xs, ys)[0, 1])
    rx = pd.Series(xs).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(ys).rank(method="average").to_numpy(dtype=float)
    rankic = float(np.corrcoef(rx, ry)[0, 1])
    if not (isfinite(ic) and isfinite(rankic)):
        return {**base, "skipped": True, "skip_reason": "non_finite_correlation"}
    return {**base, "ic": ic, "rankic": rankic}


def cross_sectional_spearman(x: Sequence[float], y: Sequence[float],
                             *, min_pairs: int = MIN_VALID_SECTOR_PAIRS) -> dict:
    """Signed pairwise Spearman correlation on jointly finite observations.

    Same missingness rules as :func:`cross_sectional_ic`: no imputation, skip
    below the pair minimum, skip on zero cross-sectional variance.
    """
    if isinstance(min_pairs, bool) or not isinstance(min_pairs, int) or min_pairs < 1:
        raise ValueError("min_pairs must be a positive integer")
    xv = np.asarray(x, dtype=float)
    yv = np.asarray(y, dtype=float)
    if xv.ndim != 1 or yv.ndim != 1 or len(xv) != len(yv):
        raise ValueError("Spearman inputs must be aligned 1D arrays")
    mask = np.isfinite(xv) & np.isfinite(yv)
    n = int(mask.sum())
    if n < min_pairs:
        return {"valid_pairs": n, "skipped": True,
                "skip_reason": "below_min_valid_sector_pairs", "spearman": None}
    xs, ys = xv[mask], yv[mask]
    if float(np.std(xs)) == 0.0 or float(np.std(ys)) == 0.0:
        return {"valid_pairs": n, "skipped": True,
                "skip_reason": "zero_cross_sectional_variance", "spearman": None}
    rx = pd.Series(xs).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(ys).rank(method="average").to_numpy(dtype=float)
    value = float(np.corrcoef(rx, ry)[0, 1])
    if not isfinite(value):
        return {"valid_pairs": n, "skipped": True,
                "skip_reason": "non_finite_correlation", "spearman": None}
    return {"valid_pairs": n, "skipped": False, "skip_reason": None, "spearman": value}


def assign_quantiles(values: Sequence[float], codes: Sequence[str],
                     *, quantile_count: int = QUANTILE_COUNT) -> dict[str, int]:
    """Deterministic contiguous quantile assignment on finite observations.

    Sectors sort by raw value ascending with sector code ascending as the
    deterministic tie-breaker. Each quantile gets ``n//quantile_count``
    members and the first ``n%quantile_count`` quantiles (Q1 first) receive
    one extra. Non-finite values are excluded (never imputed). Returns a
    ``code -> quantile (1..quantile_count)`` mapping only for valid codes.
    """
    if isinstance(quantile_count, bool) or not isinstance(quantile_count, int) or quantile_count < 2:
        raise ValueError("quantile_count must be an integer >= 2")
    vals = np.asarray(values, dtype=float)
    codes = [str(c) for c in codes]
    if vals.ndim != 1 or len(vals) != len(codes) or len(set(codes)) != len(codes):
        raise ValueError("quantile inputs must be aligned and uniquely coded")
    order = sorted((i for i in range(len(codes)) if np.isfinite(vals[i])),
                   key=lambda i: (float(vals[i]), codes[i]))
    n = len(order)
    if n < quantile_count:
        raise ValueError("quantile assignment requires at least quantile_count valid rows")
    base, remainder = divmod(n, quantile_count)
    sizes = [base + (1 if q < remainder else 0) for q in range(quantile_count)]
    out: dict[str, int] = {}
    cursor = 0
    for q, size in enumerate(sizes, start=1):
        for i in order[cursor:cursor + size]:
            out[codes[i]] = q
        cursor += size
    return out


def quantile_spread(assignments: Mapping[str, int], returns: Mapping[str, float],
                    *, quantile_count: int = QUANTILE_COUNT) -> dict:
    """Per-quantile mean forward return and Q5-Q1 for one date/factor/horizon."""
    buckets: dict[int, list[float]] = {q: [] for q in range(1, quantile_count + 1)}
    for code, quantile in assignments.items():
        value = returns.get(code)
        if value is None or not np.isfinite(float(value)):
            raise ValueError("quantile member has missing return; pair filtering must precede")
        buckets[int(quantile)].append(float(value))
    means = {q: (float(np.mean(vals)) if vals else None)
             for q, vals in buckets.items()}
    if any(v is None for v in means.values()):
        raise ValueError("every quantile must contain at least one member")
    return {"quantile_means": means,
            "q5_minus_q1": means[quantile_count] - means[1]}


def quantile_monotonicity(quantile_means: Sequence[float]) -> float | None:
    """Spearman of quantile index [1..q] vs aggregate quantile mean returns.

    Descriptive only; never used for promotion or factor selection.
    """
    means = np.asarray(quantile_means, dtype=float)
    if means.ndim != 1 or len(means) < 2 or not np.isfinite(means).all():
        return None
    index = np.arange(1, len(means) + 1, dtype=float)
    if float(np.std(means)) == 0.0:
        return None
    rx = pd.Series(index).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(means).rank(method="average").to_numpy(dtype=float)
    value = float(np.corrcoef(rx, ry)[0, 1])
    return value if isfinite(value) else None


def block_summary(block_means: Sequence[float | None],
                  full_mean: float | None) -> dict:
    """Full-sample sign and same-sign block count; descriptive only."""
    if full_mean is None or not isfinite(float(full_mean)) or float(full_mean) == 0.0:
        return {"full_development_sign": None, "same_sign_block_count": None}
    sign = 1.0 if float(full_mean) > 0 else -1.0
    count = sum(1 for value in block_means
                if value is not None and isfinite(float(value))
                and float(value) * sign > 0.0)
    return {"full_development_sign": ("positive" if sign > 0 else "negative"),
            "same_sign_block_count": int(count)}


def redundancy_flag(mean_daily_spearman: float | None,
                    *, threshold: float = REDUNDANCY_THRESHOLD) -> bool:
    """Flag only; never deletes a factor."""
    if mean_daily_spearman is None or not isfinite(float(mean_daily_spearman)):
        return False
    return abs(float(mean_daily_spearman)) >= threshold


def descriptive_t_stat(values: Sequence[float]) -> float | None:
    """mean / (sample std ddof=1 / sqrt(n)); DESCRIPTIVE ONLY, never selection."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = len(arr)
    if n < 2:
        return None
    std = float(np.std(arr, ddof=1))
    if std == 0.0:
        return None
    value = float(np.mean(arr)) / (std / sqrt(n))
    return value if isfinite(value) else None

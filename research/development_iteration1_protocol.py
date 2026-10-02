"""Preregistered, non-executing Development Iteration-1 protocol.

The only callable transformations here are pure array operations for synthetic
correctness tests and a future separately authorized runner. This module does
not load sector data, fit Ridge, score dates, or calculate candidate results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import isfinite

import numpy as np
import pandas as pd

from research.sector_development_baseline import (
    EXPECTED_FEATURES,
    EXPECTED_PREDICTION_HASH,
    EXPECTED_SNAPSHOT,
    EXPECTED_SPLIT_HASH,
)
from research.sector_development_protocol import (
    canonical_hash,
    guard_evaluation,
    prediction_config_hash,
    prediction_config_payload,
    split_policy_hash,
)

PROTOCOL_NAME = "DEVELOPMENT_ITERATION_1_PREREGISTERED"
FROZEN_CANDIDATE_IDS = ("D0", "D1", "D2", "D3")
FROZEN_CANDIDATES = (
    {"id": "D0", "x_preprocessing": "NONE", "training_target": "ABSOLUTE_FORWARD_RETURN"},
    {
        "id": "D1",
        "x_preprocessing": "TRAIN_ONLY_COLUMN_STANDARDIZATION",
        "training_target": "ABSOLUTE_FORWARD_RETURN",
    },
    {
        "id": "D2",
        "x_preprocessing": "NONE",
        "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
    },
    {
        "id": "D3",
        "x_preprocessing": "TRAIN_ONLY_COLUMN_STANDARDIZATION",
        "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
    },
)
COMPARISON_WEIGHTS = {10: 0.25, 40: 0.50, 120: 0.25}

# Set only after the canonical payload is frozen. Never derive this constant
# dynamically at import: a future runner must fail closed on semantic drift.
FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH = (
    "f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125"
)


def development_iteration1_payload() -> dict:
    """One canonical, result-free protocol identity; no data or performance I/O."""
    baseline = prediction_config_payload()
    if (
        split_policy_hash() != EXPECTED_SPLIT_HASH
        or prediction_config_hash() != EXPECTED_PREDICTION_HASH
        or tuple(baseline["features"]) != EXPECTED_FEATURES
    ):
        raise ValueError("ITERATION1_BASELINE_IDENTITY_MISMATCH")
    return {
        "protocol_name": PROTOCOL_NAME,
        "research_identity": {
            "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
            "phase": "DEVELOPMENT",
            "executable": False,
            "strict_pit": False,
            "classification_admission": "FIXED_CLASSIFICATION_RESEARCH",
            "sector_snapshot_id": EXPECTED_SNAPSHOT,
            "etf_execution": "DISABLED",
            "level_b": "DISABLED",
            "synthetic_portfolio": "DISABLED",
        },
        "baseline_identity": {
            "split_policy_hash": EXPECTED_SPLIT_HASH,
            "prediction_config_hash": EXPECTED_PREDICTION_HASH,
            "synthetic_portfolio_config_hash": None,
        },
        "candidate_family": {
            "total_budget": 4,
            "new_beyond_baseline": 3,
            "closed_after_run": True,
            "candidates": deepcopy(list(FROZEN_CANDIDATES)),
        },
        "common_config": {
            "universe": "U0_FIXED_124",
            "sector_count": 124,
            "feature_names_ordered": list(EXPECTED_FEATURES),
            "rsi_definition": "RSI14",
            "model": "NumPyRidge",
            "ridge_alpha": 0.01,
            "horizons_sessions": [10, 40, 120],
            "fusion_weights": [0.25, 0.50, 0.25],
            "top_k": 5,
            "training_window_calendar_months": 6,
            "training_window_anchor": "per_horizon_label_cutoff",
            "minimum_valid_training_days": 30,
            "base_forward_label": "close[t+h]/close[t]-1",
            "missing_data_policy": "fixed_universe_complete_case_no_fill_or_replacement",
            "source_invalid_policy": "reject_if_in_model_or_label_window",
            "prediction_order": "higher_score_first_sector_code_ascending_tie_break",
            "fused_top5": "highest_five_fused_scores",
            "rsrs_in_training": False,
            "macro_enabled": False,
            "flow_enabled": False,
            "risk_state": "record_only",
        },
        "transformations": {
            "train_only_x_standardization": {
                "fit_scope": "each_signal_date_and_horizon_legal_X_train_only",
                "mean": "column_arithmetic_mean",
                "std": "column_population_std_ddof_0",
                "train_apply": "(X_train-mean)/std",
                "prediction_apply": "(X_predict-SAME_training_mean)/SAME_training_std",
                "zero_std_policy": "all_scaled_values_zero_for_that_column",
                "forbidden_fit_sources": [
                    "prediction_date_cross_section",
                    "global_dataset",
                    "future_rows",
                    "validation",
                    "final_oos",
                ],
                "required_diagnostics": [
                    "scaler_training_rows",
                    "per_feature_mean",
                    "per_feature_std",
                    "zero_std_features",
                ],
            },
            "cross_sectional_excess_training_target": {
                "base_label": "close[t+h]/close[t]-1",
                "demean_group": "same_training_feature_date_and_horizon",
                "mean_population": "admissible_training_rows_with_realized_label_only",
                "formula": "raw_y(t,s,h)-mean_admissible_raw_y(t,h)",
                "one_sector": "zero",
                "zero_sectors": "no_training_row",
                "evaluation_realized_label": "unchanged_absolute_forward_return",
            },
        },
        "evaluation": {
            "metric_names": list(baseline["prediction_metric_contract"]["metric_names"]),
            "metric_count": 15,
            "contract": "unchanged_frozen_development_prediction_metric_contract",
            "candidate_scores": "Ridge_predictions_not_inverted",
            "label": "absolute_forward_return_for_all_candidates",
            "portfolio_metrics": "FORBIDDEN",
        },
        "comparison": {
            "primary": "Weighted_RankIC",
            "primary_terms": [
                ["mean(RankIC_10)", 0.25],
                ["mean(RankIC_40)", 0.50],
                ["mean(RankIC_120)", 0.25],
            ],
            "secondary_tie_break": "Weighted_Spread",
            "secondary_terms": [
                ["mean(Top5_minus_universe_10)", 0.25],
                ["mean(Top5_minus_universe_40)", 0.50],
                ["mean(Top5_minus_universe_120)", 0.25],
            ],
            "missing_horizon_mean": "comparison_null_ineligible",
            "exact_double_tie": "no_arbitrary_winner_both_remain_for_review_if_eligible",
            "forbidden_selection": [
                "best_single_horizon",
                "best_date",
                "maximum_return",
                "120d_outlier",
                "subjective_visual_choice",
            ],
        },
        "promotion": {
            "rule": "Weighted_RankIC > 0 AND Weighted_Spread > 0",
            "eligible_status": "DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW",
            "otherwise": "NO_ITERATION1_CANDIDATE_PROMOTED",
            "validation_admission": False,
        },
        "phase_guards": {
            "allowed_evaluation_phase_after_separate_authorization": "development",
            "allowed_development_ordinals": [1, 100],
            "purge_1": "NO_EVALUATION",
            "validation": "SEALED",
            "purge_2": "NO_EVALUATION",
            "final_oos": "SEALED",
            "candidate_performance_authorized_by_this_preregistration": False,
            "future_candidate_run_requires_separate_task": True,
        },
    }


def development_iteration1_protocol_hash(payload: Mapping | None = None) -> str:
    """SHA-256 of canonical sorted JSON; excludes timestamps and results."""
    return canonical_hash(development_iteration1_payload() if payload is None else payload)


def verify_frozen_iteration1_protocol(*, supplied_hash: str | None = None) -> dict:
    """Hard fail if the committed payload or a supplied runner hash drifts."""
    payload = development_iteration1_payload()
    actual = development_iteration1_protocol_hash(payload)
    if actual != FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH or (
        supplied_hash is not None and supplied_hash != actual
    ):
        raise ValueError("DEVELOPMENT_ITERATION1_PROTOCOL_HASH_MISMATCH")
    if (
        tuple(item["id"] for item in payload["candidate_family"]["candidates"])
        != FROZEN_CANDIDATE_IDS
        or payload["candidate_family"]["total_budget"] != 4
        or payload["candidate_family"]["new_beyond_baseline"] != 3
        or payload["candidate_family"]["candidates"] != list(FROZEN_CANDIDATES)
    ):
        raise ValueError("DEVELOPMENT_ITERATION1_CANDIDATE_BUDGET_MISMATCH")
    return payload


def guard_iteration1_scope(
    candidate_id: str, phase: str, ordinals: Sequence[int], *, supplied_hash: str
) -> dict:
    """Structural guard for a future runner; does not authorize its execution."""
    payload = verify_frozen_iteration1_protocol(supplied_hash=supplied_hash)
    if candidate_id not in FROZEN_CANDIDATE_IDS:
        raise ValueError("DEVELOPMENT_ITERATION1_CANDIDATE_BUDGET_EXCEEDED")
    guard_evaluation(phase, ordinals)
    return next(
        item for item in payload["candidate_family"]["candidates"] if item["id"] == candidate_id
    )


def assert_training_chronology(
    feature_dates: Sequence, label_end_dates: Sequence, signal_date
) -> None:
    """No selected training row can consume a feature or label after signal."""
    origins, ends = pd.DatetimeIndex(feature_dates), pd.DatetimeIndex(label_end_dates)
    signal = pd.Timestamp(signal_date)
    if (
        len(origins) != len(ends)
        or origins.hasnans
        or ends.hasnans
        or pd.isna(signal)
        or origins.tz is not None
        or ends.tz is not None
        or bool((origins > signal).any())
        or bool((ends > signal).any())
        or bool((ends < origins).any())
    ):
        raise ValueError("RESEARCH_LEAKAGE_BLOCKER: invalid Iteration-1 training chronology")


def standardize_train_predict(x_train, x_predict):
    """D1/D3: fit per-column population statistics on legal X_train only."""
    train = np.asarray(x_train, dtype=float)
    predict = np.asarray(x_predict, dtype=float)
    if (
        train.ndim != 2
        or predict.ndim != 2
        or not train.shape[0]
        or not train.shape[1]
        or train.shape[1] != predict.shape[1]
        or not np.isfinite(train).all()
        or not np.isfinite(predict).all()
    ):
        raise ValueError("Iteration-1 scaler requires finite aligned 2D matrices")
    mean = train.mean(axis=0)
    std = train.std(axis=0, ddof=0)
    zero = std == 0.0
    divisor = np.where(zero, 1.0, std)
    scaled_train = (train - mean) / divisor
    scaled_predict = (predict - mean) / divisor
    scaled_train[:, zero] = 0.0
    scaled_predict[:, zero] = 0.0
    if not np.isfinite(scaled_train).all() or not np.isfinite(scaled_predict).all():
        raise ValueError("Iteration-1 scaler generated non-finite values")
    diagnostics = {
        "scaler_training_rows": int(train.shape[0]),
        "per_feature_mean": mean.tolist(),
        "per_feature_std": std.tolist(),
        "zero_std_features": np.flatnonzero(zero).astype(int).tolist(),
    }
    return scaled_train, scaled_predict, diagnostics


def cross_sectional_excess_training_target(raw_y, training_feature_dates, *, horizon: int):
    """D2/D3: demean already-admissible, realized rows within each date only.

    The caller must supply one horizon's legal training rows, after filtering
    invalid sector/date/label observations and checking label chronology.
    """
    if horizon not in COMPARISON_WEIGHTS or isinstance(horizon, bool):
        raise ValueError("Iteration-1 excess target requires one frozen horizon")
    y = np.asarray(raw_y, dtype=float)
    dates = pd.DatetimeIndex(training_feature_dates)
    if (
        y.ndim != 1
        or len(y) != len(dates)
        or dates.hasnans
        or dates.tz is not None
        or not np.isfinite(y).all()
    ):
        raise ValueError("Iteration-1 excess target requires finite aligned rows")
    excess = np.empty_like(y)
    for date in dates.unique():
        mask = dates == date
        excess[mask] = y[mask] - y[mask].mean()
    return excess


def _weighted_mean(metric_means: Mapping[str, float | None], stem: str) -> float | None:
    values = []
    for horizon, weight in COMPARISON_WEIGHTS.items():
        value = metric_means.get(f"{stem}_{horizon}")
        if value is None or isinstance(value, bool) or not isfinite(float(value)):
            return None
        values.append(weight * float(value))
    return float(sum(values))


def weighted_rankic(metric_means: Mapping[str, float | None]) -> float | None:
    return _weighted_mean(metric_means, "RankIC")


def weighted_spread(metric_means: Mapping[str, float | None]) -> float | None:
    return _weighted_mean(metric_means, "Top5_minus_universe")


def eligible_for_further_review(rankic: float | None, spread: float | None) -> bool:
    """Strict conjunction; a missing value or least-bad score never promotes."""
    return (
        rankic is not None
        and spread is not None
        and not isinstance(rankic, bool)
        and not isinstance(spread, bool)
        and isfinite(float(rankic))
        and isfinite(float(spread))
        and rankic > 0
        and spread > 0
    )

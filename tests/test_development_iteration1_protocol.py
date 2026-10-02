"""Synthetic-only preregistration guards; no real candidate performance."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from research import development_iteration1_protocol as p
from research.sector_development_baseline import (
    EXPECTED_FEATURES,
    EXPECTED_PREDICTION_HASH,
    EXPECTED_SNAPSHOT,
    EXPECTED_SPLIT_HASH,
)
from research.sector_development_protocol import prediction_config_hash, split_policy_hash
from research.sector_universe_feasibility import prediction_metric_contract


def test_exact_four_candidate_family_and_d0_baseline_control():
    payload = p.verify_frozen_iteration1_protocol()
    family = payload["candidate_family"]
    assert tuple(item["id"] for item in family["candidates"]) == ("D0", "D1", "D2", "D3")
    assert family["total_budget"] == 4
    assert family["new_beyond_baseline"] == 3
    assert family["closed_after_run"] is True
    assert family["candidates"] == list(p.FROZEN_CANDIDATES)
    assert family["candidates"][0] == {
        "id": "D0",
        "x_preprocessing": "NONE",
        "training_target": "ABSOLUTE_FORWARD_RETURN",
    }
    assert payload["baseline_identity"] == {
        "split_policy_hash": EXPECTED_SPLIT_HASH,
        "prediction_config_hash": EXPECTED_PREDICTION_HASH,
        "synthetic_portfolio_config_hash": None,
    }
    assert split_policy_hash() == EXPECTED_SPLIT_HASH
    assert prediction_config_hash() == EXPECTED_PREDICTION_HASH


def test_d1_d2_d3_have_only_the_two_declared_transformations():
    candidates = {
        row["id"]: row
        for row in p.development_iteration1_payload()["candidate_family"]["candidates"]
    }
    assert candidates["D1"] == {
        "id": "D1",
        "x_preprocessing": "TRAIN_ONLY_COLUMN_STANDARDIZATION",
        "training_target": "ABSOLUTE_FORWARD_RETURN",
    }
    assert candidates["D2"] == {
        "id": "D2",
        "x_preprocessing": "NONE",
        "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
    }
    assert candidates["D3"] == {
        "id": "D3",
        "x_preprocessing": "TRAIN_ONLY_COLUMN_STANDARDIZATION",
        "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
    }
    assert all(
        "INVERSE" not in str(row).upper() and "BOTTOM" not in str(row).upper()
        for row in candidates.values()
    )


def test_all_original_model_and_research_identity_are_frozen():
    payload = p.development_iteration1_payload()
    common = payload["common_config"]
    assert common["universe"] == "U0_FIXED_124" and common["sector_count"] == 124
    assert tuple(common["feature_names_ordered"]) == EXPECTED_FEATURES
    assert len(common["feature_names_ordered"]) == 19
    assert common["rsi_definition"] == "RSI14"
    assert common["model"] == "NumPyRidge" and common["ridge_alpha"] == 0.01
    assert common["horizons_sessions"] == [10, 40, 120]
    assert common["fusion_weights"] == [0.25, 0.50, 0.25]
    assert common["top_k"] == 5
    assert common["training_window_calendar_months"] == 6
    assert common["training_window_anchor"] == "per_horizon_label_cutoff"
    assert common["minimum_valid_training_days"] == 30
    assert common["base_forward_label"] == "close[t+h]/close[t]-1"
    identity = payload["research_identity"]
    assert identity["run_type"] == "SECTOR_INDEX_RESEARCH_ONLY"
    assert identity["executable"] is False and identity["strict_pit"] is False
    assert identity["classification_admission"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert identity["sector_snapshot_id"] == EXPECTED_SNAPSHOT
    assert (
        identity["etf_execution"]
        == identity["level_b"]
        == identity["synthetic_portfolio"]
        == "DISABLED"
    )


def test_only_existing_15_absolute_label_metrics_and_sealed_phases():
    payload = p.development_iteration1_payload()
    evaluation = payload["evaluation"]
    assert evaluation["metric_names"] == prediction_metric_contract()["metric_names"]
    assert evaluation["metric_count"] == 15
    assert evaluation["label"] == "absolute_forward_return_for_all_candidates"
    assert evaluation["portfolio_metrics"] == "FORBIDDEN"
    phase = payload["phase_guards"]
    assert phase["allowed_development_ordinals"] == [1, 100]
    assert phase["validation"] == "SEALED" and phase["final_oos"] == "SEALED"
    assert phase["candidate_performance_authorized_by_this_preregistration"] is False
    for ordinal in (101, 220, 221, 280, 281, 400, 401, 460):
        with pytest.raises(PermissionError):
            p.guard_iteration1_scope(
                "D1",
                "development",
                [ordinal],
                supplied_hash=p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH,
            )
    with pytest.raises(PermissionError):
        p.guard_iteration1_scope(
            "D1", "validation", [1], supplied_hash=p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
        )


def test_candidate_budget_guard_rejects_fifth_member():
    with pytest.raises(ValueError, match="CANDIDATE_BUDGET_EXCEEDED"):
        p.guard_iteration1_scope(
            "D4", "development", [1], supplied_hash=p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
        )
    payload = p.development_iteration1_payload()
    payload["candidate_family"]["candidates"].append(
        {"id": "D4", "x_preprocessing": "NONE", "training_target": "ABSOLUTE_FORWARD_RETURN"}
    )
    assert (
        p.development_iteration1_protocol_hash(payload)
        != p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    )


def test_standardizer_uses_only_training_stats_for_prediction_and_zero_std_zero():
    train = np.array([[1.0, 7.0], [3.0, 7.0]])
    predict = np.array([[5.0, 70.0]])
    scaled_train, scaled_predict, diagnostics = p.standardize_train_predict(train, predict)
    np.testing.assert_allclose(scaled_train, [[-1.0, 0.0], [1.0, 0.0]])
    np.testing.assert_allclose(scaled_predict, [[3.0, 0.0]])
    assert diagnostics == {
        "scaler_training_rows": 2,
        "per_feature_mean": [2.0, 7.0],
        "per_feature_std": [1.0, 0.0],
        "zero_std_features": [1],
    }
    second_predict = np.array([[5000.0, -700.0]])
    second_train, _, second_diagnostics = p.standardize_train_predict(train, second_predict)
    np.testing.assert_array_equal(second_train, scaled_train)
    assert second_diagnostics == diagnostics  # Prediction data cannot refit scaler.
    np.testing.assert_array_equal(train, [[1.0, 7.0], [3.0, 7.0]])
    with pytest.raises(ValueError):
        p.standardize_train_predict(train, [[np.nan, 0.0]])


def test_training_chronology_guard_rejects_future_feature_or_label():
    dates = pd.to_datetime(["2025-01-01", "2025-01-02"])
    p.assert_training_chronology(dates, dates + pd.Timedelta(days=3), "2025-01-10")
    with pytest.raises(ValueError, match="RESEARCH_LEAKAGE_BLOCKER"):
        p.assert_training_chronology(
            dates, pd.to_datetime(["2025-01-03", "2025-01-11"]), "2025-01-10"
        )
    with pytest.raises(ValueError, match="RESEARCH_LEAKAGE_BLOCKER"):
        p.assert_training_chronology(
            pd.to_datetime(["2025-01-11"]), pd.to_datetime(["2025-01-12"]), "2025-01-10"
        )


def test_excess_target_demeans_each_legal_date_not_stacked_global_vector():
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-01", "2025-01-02"])
    raw = np.array([1.0, 10.0, 3.0, 20.0])
    excess = p.cross_sectional_excess_training_target(raw, dates, horizon=40)
    np.testing.assert_allclose(excess, [-1.0, -5.0, 1.0, 5.0])
    for date in dates.unique():
        assert abs(float(excess[dates == date].mean())) < 1e-12
    assert not np.allclose(excess, raw - raw.mean())
    np.testing.assert_allclose(
        p.cross_sectional_excess_training_target([7.0], [pd.Timestamp("2025-01-01")], horizon=40),
        [0.0],
    )
    assert len(p.cross_sectional_excess_training_target([], [], horizon=40)) == 0
    with pytest.raises(ValueError, match="frozen horizon"):
        p.cross_sectional_excess_training_target(raw, dates, horizon=20)


def test_weighted_comparison_exact_formulas_and_strict_joint_promotion():
    means = {
        "RankIC_10": 0.1,
        "RankIC_40": 0.2,
        "RankIC_120": -0.1,
        "Top5_minus_universe_10": 0.04,
        "Top5_minus_universe_40": 0.02,
        "Top5_minus_universe_120": -0.04,
    }
    assert p.weighted_rankic(means) == pytest.approx(0.25 * 0.1 + 0.50 * 0.2 + 0.25 * -0.1)
    assert p.weighted_spread(means) == pytest.approx(0.25 * 0.04 + 0.50 * 0.02 + 0.25 * -0.04)
    comparison = p.development_iteration1_payload()["comparison"]
    assert comparison["primary"] == "Weighted_RankIC"
    assert comparison["secondary_tie_break"] == "Weighted_Spread"
    assert p.eligible_for_further_review(0.001, 0.001)
    for rankic, spread in [
        (0.0, 0.1),
        (0.1, 0.0),
        (-0.1, 0.1),
        (0.1, -0.1),
        (None, 0.1),
        (0.1, None),
    ]:
        assert not p.eligible_for_further_review(rankic, spread)
    missing = dict(means)
    del missing["RankIC_120"]
    assert p.weighted_rankic(missing) is None


def test_protocol_hash_is_deterministic_and_detects_mutation():
    payload = p.development_iteration1_payload()
    assert p.development_iteration1_protocol_hash() == p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    assert (
        p.development_iteration1_protocol_hash(payload)
        == p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    )
    assert (
        p.verify_frozen_iteration1_protocol(
            supplied_hash=p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
        )
        == payload
    )
    shuffled = {key: payload[key] for key in reversed(list(payload))}
    assert (
        p.development_iteration1_protocol_hash(shuffled)
        == p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    )
    mutated = deepcopy(payload)
    mutated["common_config"]["ridge_alpha"] = 0.02
    assert (
        p.development_iteration1_protocol_hash(mutated)
        != p.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    )
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        p.verify_frozen_iteration1_protocol(supplied_hash="wrong")

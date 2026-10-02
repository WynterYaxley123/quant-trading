"""Deterministic offline tests for unadopted sector-universe diagnostics."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.sector_universe_feasibility import (
    POLICY_SIGNAL_COUNTS,
    _history_masks,
    audit_universe_feasibility,
    missing_blocks,
    prediction_metric_contract,
    sample_budget_policy,
)
from src.data.loaders.shenwan_sector_loader import load_sector_catalog
from strategies.sw_sector_rotation.src.model.model import NumPyRidge


@pytest.fixture(scope="module")
def actual():
    return audit_universe_feasibility(Path("data/processed/shenwan"))


@pytest.mark.external_runtime
def test_u0_reproduces_formal_239_sessions(actual):
    assert actual["formal_universe"] == {
        "mode": "FIXED_124_CURRENT_RULE",
        "sector_count": 124,
        "sector_codes_unchanged": True,
    }
    assert actual["U0"]["signal_eligible_sessions"] == 239
    assert actual["U0"]["signal_eligible"]["start"] == "2025-04-02"
    assert actual["U0"]["continuous_common_start"] == "2023-09-27"
    assert actual["common_calendar"]["trading_sessions"] == 1158


@pytest.mark.external_runtime
def test_801193_missing_diagnostics_are_deterministic(actual):
    gap = actual["sector_801193"]
    assert gap["first_available"] == "2022-03-02"
    assert gap["last_unavailable"] == "2023-09-26"
    assert gap["unavailable_sessions"] == 336
    assert gap["missing_block_count"] == 9
    assert gap["largest_missing_block"] == {
        "start": "2022-08-05",
        "end": "2023-09-06",
        "sessions": 266,
    }
    assert sum(block["sessions"] for block in gap["missing_blocks"]) == 336
    assert gap["cause_classification"] == "UNKNOWN_FROM_LOCAL_OHLCVA_ONLY"


def test_missing_blocks_use_trading_sessions_not_calendar_days():
    dates = pd.bdate_range("2025-01-02", periods=6)
    blocks = missing_blocks(dates, np.array([False, False, True, False, True, True]))
    assert [block["sessions"] for block in blocks] == [2, 1]
    assert blocks[0]["end"] == str(dates[1].date())


@pytest.mark.external_runtime
def test_other_sectors_have_separate_continuity_bottleneck(actual):
    other = actual["other_continuity_bottlenecks"]
    assert other["affected_sector_count"] == 122
    assert len(other["unaffected_sector_codes"]) == 1
    shared = other["shared_unavailable_blocks_for_fixed_123"]
    assert len(shared) == 7
    assert sum(block["sessions"] for block in shared) == 7
    assert shared[-1]["end"] == "2023-09-08"


@pytest.mark.external_runtime
def test_u1_is_counterfactual_and_formal_catalog_stays_124(actual):
    assert actual["U1"]["sector_count"] == 123
    assert actual["U1"]["status"] == "DIAGNOSTIC_ONLY_NOT_APPROVED_UNIVERSE_CHANGE"
    assert actual["U1"]["requires"] == "UNIVERSE_CHANGE_REQUIRES_READMISSION"
    assert actual["U1"]["continuous_common_start"] == "2023-09-11"
    assert actual["U1"]["continuous_common_end"] == "2026-09-18"
    assert actual["U1"]["signal_eligible_sessions"] == 247
    catalog = load_sector_catalog(Path("data/processed/shenwan"))
    assert len(catalog) == 124
    assert "801193" in set(catalog["sector_code"].astype(str))


@pytest.mark.external_runtime
def test_u1_factor_training_and_label_ranges_are_separate(actual):
    u1 = actual["U1"]
    assert u1["factor_ready"]["start"] == "2022-11-03"
    assert u1["training_ready"]["start"] == "2025-03-21"
    assert u1["label_ready"]["end"] == "2026-03-27"
    assert u1["signal_eligible"] == {
        "start": "2025-03-21",
        "end": "2026-03-27",
        "session_count": 247,
    }


@pytest.mark.external_runtime
def test_u2_is_diagnostic_only_with_asof_sector_counts(actual):
    u2 = actual["U2"]
    assert u2["status"] == "DIAGNOSTIC_ONLY_NOT_APPROVED_DYNAMIC_UNIVERSE"
    assert u2["retained_catalog_sector_count"] == 124
    assert u2["signal_eligible_sessions"] == 247
    assert u2["asof_ready_sector_count"] == {"min": 123, "median": 124.0, "max": 124}
    assert u2["requires"] == "DYNAMIC_UNIVERSE_POLICY_AND_READMISSION"


def test_dynamic_membership_does_not_depend_on_future_prices():
    dates = pd.bdate_range("2022-01-03", periods=500)
    available = np.ones((500, 7), dtype=bool)
    _, original = _history_masks(dates, available)
    changed_future = available.copy()
    changed_future[451:, :] = False
    _, changed = _history_masks(dates, changed_future)
    np.testing.assert_array_equal(original[:451], changed[:451])


@pytest.mark.parametrize(
    "name,required,deficit,decisions",
    [
        ("A", 380, 141, (6, 4, 4)),
        ("B", 400, 161, (8, 4, 4)),
        ("C", 460, 221, (10, 6, 6)),
        ("D", 480, 241, (12, 6, 6)),
    ],
)
def test_sample_budget_and_ten_session_decision_arithmetic(name, required, deficit, decisions):
    budget = sample_budget_policy(name, POLICY_SIGNAL_COUNTS[name], 239)
    assert budget["required_eligible_sessions"] == required
    assert budget["additional_eligible_sessions_needed"] == deficit
    assert budget["purge_1_sessions"] == budget["purge_2_sessions"] == 120
    assert tuple(budget["nominal_10_session_decision_counts"].values()) == decisions
    assert budget["mathematically_feasible"] is False


def test_mathematical_nonempty_is_not_research_adequacy():
    minimum = sample_budget_policy("minimum", (1, 1, 1), 243)
    assert minimum["mathematically_feasible"] is True
    assert minimum["research_adequacy_approved"] is False
    assert minimum["nominal_10_session_decision_counts"] == {
        "development": 1,
        "validation": 1,
        "final_oos": 1,
    }


@pytest.mark.external_runtime
def test_u1_and_u2_are_mathematically_nonempty_but_no_candidate_policy_fits(actual):
    for scenario in ("U1", "U2"):
        budget = actual["sample_budgets"][scenario]
        assert budget["strict_three_way_nonempty"]["feasible"] is True
        assert budget["strict_three_way_nonempty"]["signal_slots_after_purge"] == 7
        assert all(not row["mathematically_feasible"] for row in budget["policies"].values())


@pytest.mark.external_runtime
def test_u0_additional_raw_sessions_use_verified_120_session_tail(actual):
    assert actual["u0_raw_to_last_signal_tail_sessions"] == 120
    assert actual["u0_additional_raw_sessions_if_continuity_persists"] == {
        "A": 141,
        "B": 161,
        "C": 221,
        "D": 241,
    }


def test_prediction_metric_contract_is_deterministic_and_non_executable():
    first = prediction_metric_contract()
    assert prediction_metric_contract() == first
    assert len(first["metric_names"]) == 15
    assert first["metric_names"][:3] == ["IC_10", "IC_40", "IC_120"]
    assert first["minimum_sectors_per_date_horizon"] == 6
    assert first["zero_variance_correlation"] is None
    assert first["execution"] is False
    assert first["etf_costs"] is None


@pytest.mark.external_runtime
def test_synthetic_semantics_and_oos_remain_unfrozen(actual):
    assert actual["rebalance_semantics"] == "REFERENCE_10_SESSIONS_ANCHOR_NOT_FROZEN"
    assert (
        actual["synthetic_holding_semantics"] == "SYNTHETIC_PORTFOLIO_SEMANTICS_REQUIRES_APPROVAL"
    )
    assert actual["strategy_config_hash"] is None
    assert actual["oos_status"] == "UNLOCKED_UNOPENED"
    assert actual["oos_signal_start"] is None
    assert actual["oos_signal_end"] is None


@pytest.mark.external_runtime
def test_audit_cannot_fit_model_or_compute_performance(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("model or performance operation is out of scope")

    monkeypatch.setattr(NumPyRidge, "fit", forbidden)
    monkeypatch.setattr(NumPyRidge, "predict", forbidden)
    result = audit_universe_feasibility(Path("data/processed/shenwan"))
    assert result["performance_metrics_viewed"] is False
    assert result["level_b_run"] is False
    assert result["strategy_parameters_changed"] is False


@pytest.mark.external_runtime
def test_no_etf_network_or_docker_process_dependency(monkeypatch):
    original_csv = pd.read_csv
    original_text = Path.read_text

    def guarded_csv(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF file access is forbidden")
        return original_csv(path, *args, **kwargs)

    def guarded_text(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF file access is forbidden")
        return original_text(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("network/process operation is forbidden")

    monkeypatch.setattr(pd, "read_csv", guarded_csv)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert (
        audit_universe_feasibility(Path("data/processed/shenwan"))["U0"]["signal_eligible_sessions"]
        == 239
    )

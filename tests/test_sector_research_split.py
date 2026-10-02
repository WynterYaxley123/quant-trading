"""Offline split/lock safeguards; no model fit or performance calculation."""

from __future__ import annotations

import inspect
import socket
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from research.sector_research_split import (
    UNLOCKED,
    audit_split,
    candidate_three_way,
    label_tail_end,
    strategy_config_hash,
    strategy_config_payload,
    strict_budget,
    verify_training_label_availability,
)
from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    as_of_truncate,
    temporal_boundaries,
)


@pytest.fixture(scope="module")
def actual():
    return audit_split(Path("data/processed/shenwan"))


def _dates(count=239):
    return pd.bdate_range("2025-04-02", periods=count)


def _complete_policies():
    return (
        {"interval_sessions": 10, "anchor": "first_eligible_signal"},
        {
            "portfolio_formation": "equal_weight_top5",
            "entry_convention": "next_session_reference",
            "holding_convention": "until_next_rebalance",
            "overlap_policy": "single_target_portfolio",
            "return_measurement": "sector_close_to_close",
            "turnover_semantics": "target_weight_difference",
        },
        {
            "policy_version": "synthetic-test-only",
            "development_signals": 60,
            "validation_signals": 40,
            "final_oos_signals": 40,
            "boundary_purge_sessions": 120,
            "oos_start": "2026-01-01",
            "oos_end": "2026-03-01",
        },
        {
            "mode": "synthetic-test-only",
            "sector_codes": ["801081", "801193"],
            "admission_mode": "FIXED_CLASSIFICATION_RESEARCH",
        },
    )


def test_trading_sessions_not_calendar_days_control_purge():
    dates = _dates(23)
    candidate = candidate_three_way(dates, 10)
    assert candidate["development"]["count"] == 1
    assert candidate["purge_1"]["count"] == 10
    assert candidate["validation"]["count"] == 1
    assert candidate["purge_2"]["count"] == 10
    assert candidate["final_oos_candidate"]["count"] == 1
    assert (
        pd.Timestamp(candidate["validation"]["start"])
        - pd.Timestamp(candidate["development"]["end"])
    ).days > 10


def test_future_labels_never_enter_training():
    calendar = _dates(400)
    signals = calendar[150:300]
    assert verify_training_label_availability(calendar, signals, (10, 40, 120)) == 450
    for horizon in (10, 40, 120):
        t = calendar[250]
        boundary = temporal_boundaries(calendar, t, horizon)
        assert boundary is not None
        cutoff_pos = int(calendar.get_loc(boundary.label_cutoff))
        assert calendar[cutoff_pos + horizon] <= t
        assert calendar[cutoff_pos + 1 + horizon] > t


@pytest.mark.parametrize("horizon,minimum,purge", [(10, 23, 20), (40, 83, 80), (120, 243, 240)])
def test_horizon_purge_exact(horizon, minimum, purge):
    budget = strict_budget(239, horizon)
    assert budget["required_boundary_purge_sessions"] == horizon
    assert budget["total_purge_sessions"] == purge
    assert budget["minimum_sessions_for_nonempty_phases"] == minimum
    assert strict_budget(minimum - 1, horizon)["feasible"] is False
    assert strict_budget(minimum, horizon)["feasible"] is True


@pytest.mark.external_runtime
def test_combined_baseline_uses_max_horizon(actual):
    assert actual["combined_horizon_sessions"] == 120
    assert actual["combined_three_way"] == strict_budget(239, 120)
    assert actual["combined_candidate"] is None


def test_development_label_end_precedes_validation_signal():
    dates = _dates()
    for horizon in (10, 40):
        candidate = candidate_three_way(dates, horizon)
        d_last = int(dates.get_loc(pd.Timestamp(candidate["development"]["end"])))
        v_first = int(dates.get_loc(pd.Timestamp(candidate["validation"]["start"])))
        assert d_last + horizon < v_first
        assert dates[d_last + horizon] == pd.Timestamp(candidate["purge_1"]["end"])


def test_validation_label_end_precedes_oos_signal():
    dates = _dates()
    for horizon in (10, 40):
        candidate = candidate_three_way(dates, horizon)
        v_last = int(dates.get_loc(pd.Timestamp(candidate["validation"]["end"])))
        o_first = int(dates.get_loc(pd.Timestamp(candidate["final_oos_candidate"]["start"])))
        assert v_last + horizon < o_first
        assert dates[v_last + horizon] == pd.Timestamp(candidate["purge_2"]["end"])


@pytest.mark.external_runtime
def test_actual_239_sessions_make_strict_three_way_impossible(actual):
    assert actual["eligible_signal_start"] == "2025-04-02"
    assert actual["eligible_signal_end"] == "2026-03-27"
    assert actual["eligible_signal_sessions"] == 239
    assert actual["combined_three_way"]["minimum_sessions_for_nonempty_phases"] == 243
    assert actual["combined_three_way"]["available_minus_required"] == -4
    assert actual["status"] == "STRICT_3WAY_SPLIT_NOT_FEASIBLE"
    assert actual["combined_strict_date_proof"]["earliest_oos_is_eligible"] is False


@pytest.mark.external_runtime
def test_two_phase_budget_does_not_authorize_dropping_validation(actual):
    assert actual["two_phase_dev_validation"]["signal_slots_after_purge"] == 119
    assert actual["two_phase_dev_final_oos"]["signal_slots_after_purge"] == 119
    assert actual["combined_candidate"] is None


@pytest.mark.external_runtime
def test_oos_remains_unopened_and_unlocked(actual):
    assert actual["oos_status"] == UNLOCKED
    assert actual["oos_signal_start"] is None
    assert actual["oos_signal_end"] is None
    assert actual["oos_label_tail_end"] is None
    assert actual["locked_at"] is None
    assert actual["performance_metrics_viewed"] is False


def test_label_realization_tail_is_not_feature_input():
    dates = _dates(50)
    signal = dates[20]
    tail = label_tail_end(dates, signal, 10)
    assert tail == str(dates[30].date())
    prices = pd.DataFrame({"close": range(50)}, index=dates)
    visible = as_of_truncate(prices, signal)
    assert visible.index.max() == signal
    assert pd.Timestamp(tail) not in visible.index


def test_split_dates_do_not_depend_on_returns():
    frame = pd.DataFrame({"date": _dates(), "return": range(239)})
    first = candidate_three_way(frame["date"], 40)
    frame["return"] = -frame["return"] * 100
    assert candidate_three_way(frame["date"], 40) == first
    assert list(inspect.signature(candidate_three_way).parameters) == ["dates", "horizon"]


def test_config_hash_deterministic_and_ephemeral_fields_ignored():
    rebalance, holding, split, universe = _complete_policies()
    payload = strategy_config_payload(
        "snapshot-a",
        rebalance_policy=rebalance,
        holding_policy=holding,
        split_policy=split,
        universe_policy=universe,
    )
    first = strategy_config_hash(payload)
    assert first is not None and len(first) == 64
    assert strategy_config_hash(payload) == first
    assert strategy_config_hash({**payload, "timestamp": "tomorrow", "uuid": "random"}) == first


def test_data_snapshot_is_included_in_config_hash():
    rebalance, holding, split, universe = _complete_policies()
    policies = dict(
        rebalance_policy=rebalance,
        holding_policy=holding,
        split_policy=split,
        universe_policy=universe,
    )
    a = strategy_config_payload("snapshot-a", **policies)
    b = strategy_config_payload("snapshot-b", **policies)
    assert a["data_snapshot_id"] == "snapshot-a"
    assert strategy_config_hash(a) != strategy_config_hash(b)


def test_payload_preserves_frozen_signal_definition():
    payload = strategy_config_payload("snapshot-a")
    assert len(payload["features"]) == 19
    assert payload["ridge_alpha"] == 0.01
    assert payload["horizons_sessions"] == {"short": 10, "medium": 40, "long": 120}
    assert payload["fusion_weights"] == {"short": 0.25, "medium": 0.50, "long": 0.25}
    assert payload["top_n"] == 5
    assert payload["training_window_calendar_months"] == 6
    assert payload["minimum_valid_training_days"] == 30
    assert payload["risk_state"] == "record_only"
    assert payload["data_admission_mode"] == "FIXED_CLASSIFICATION_RESEARCH"


@pytest.mark.external_runtime
def test_missing_rebalance_or_holding_blocks_config_hash(actual):
    rebalance, holding, split, universe = _complete_policies()
    snapshot = actual["data_snapshot_id"]
    assert strategy_config_hash(strategy_config_payload(snapshot)) is None
    assert (
        strategy_config_hash(strategy_config_payload(snapshot, rebalance_policy=rebalance)) is None
    )
    assert strategy_config_hash(strategy_config_payload(snapshot, holding_policy=holding)) is None
    assert (
        strategy_config_hash(
            strategy_config_payload(snapshot, rebalance_policy=rebalance, holding_policy=holding)
        )
        is None
    )
    assert (
        strategy_config_hash(
            strategy_config_payload(
                snapshot, rebalance_policy=rebalance, holding_policy=holding, split_policy=split
            )
        )
        is None
    )
    assert (
        strategy_config_hash(
            strategy_config_payload(
                snapshot,
                rebalance_policy=rebalance,
                holding_policy=holding,
                universe_policy=universe,
            )
        )
        is None
    )
    assert actual["strategy_config_hash"] is None


def test_incomplete_universe_or_non_strict_split_cannot_hash():
    rebalance, holding, split, universe = _complete_policies()
    policies = dict(
        rebalance_policy=rebalance,
        holding_policy=holding,
        split_policy=split,
        universe_policy=universe,
    )
    assert strategy_config_hash(strategy_config_payload("snapshot-a", **policies)) is not None
    assert (
        strategy_config_hash(
            strategy_config_payload(
                "snapshot-a", **{**policies, "universe_policy": {**universe, "sector_codes": []}}
            )
        )
        is None
    )
    assert (
        strategy_config_hash(
            strategy_config_payload(
                "snapshot-a",
                **{**policies, "split_policy": {**split, "boundary_purge_sessions": 10}},
            )
        )
        is None
    )


@pytest.mark.external_runtime
def test_actual_training_cutoffs_all_verified(actual):
    assert actual["training_label_availability"] == "PASS"
    assert actual["training_label_checks"] == 239 * 3


@pytest.mark.external_runtime
def test_no_etf_dependency_network_or_docker_process(monkeypatch):
    original_text = Path.read_text
    original_csv = pd.read_csv

    def guard_path(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF data is out of scope")
        return original_text(path, *args, **kwargs)

    def guard_csv(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF data is out of scope")
        return original_csv(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("network/process operation is out of scope")

    monkeypatch.setattr(Path, "read_text", guard_path)
    monkeypatch.setattr(pd, "read_csv", guard_csv)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert audit_split(Path("data/processed/shenwan"))["status"] == "STRICT_3WAY_SPLIT_NOT_FEASIBLE"


def test_bad_or_unsorted_calendar_is_rejected():
    with pytest.raises(ValueError, match="calendar"):
        candidate_three_way(list(reversed(_dates(30))), 10)
    with pytest.raises(ValueError, match="budget"):
        strict_budget(239, 0)

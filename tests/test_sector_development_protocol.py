"""Offline regression checks for the sealed ordinal Development protocol."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pandas as pd
import pytest

from research import sector_development_protocol as protocol


@pytest.fixture(scope="module")
def actual():
    # Existing SHA-verified local raw/canonical sector snapshot, never network.
    return protocol.audit_local_policy(Path("data/processed/shenwan"))


@pytest.fixture
def synthetic_prefix(monkeypatch):
    dates = pd.bdate_range("2025-01-01", periods=239)
    codes = [f"{i:06d}" for i in range(124)]
    monkeypatch.setattr(protocol, "FROZEN_PREFIX_SHA256",
                        protocol.canonical_hash([str(d.date()) for d in dates]))
    monkeypatch.setattr(protocol, "FROZEN_CODES_SHA256", protocol.canonical_hash(codes))
    monkeypatch.setattr(protocol, "FROZEN_BOUNDARY_DATES", {})
    return dates, codes


def test_formal_universe_is_fixed_124(actual):
    p = actual["split_policy"]
    assert p["formal_universe"] == "SW_LEVEL2_FIXED_124"
    assert p["formal_universe_sector_count"] == 124


def test_u1_remains_diagnostic(actual):
    assert actual["split_policy"]["u1_exclude_801193"] == "DIAGNOSTIC_ONLY"


def test_u2_remains_diagnostic(actual):
    assert actual["split_policy"]["u2_dynamic"] == "DIAGNOSTIC_ONLY"


def test_policy_c_total_and_deficit(actual):
    assert actual["split_policy"]["required_eligible_sessions"] == 460
    assert actual["observed_eligible_count"] == 239
    assert 460 - actual["observed_eligible_count"] == 221


@pytest.mark.parametrize("phase,start,end,count", [
    ("development", 1, 100, 100),
    ("purge_1", 101, 220, 120),
    ("validation", 221, 280, 60),
    ("purge_2", 281, 400, 120),
    ("final_oos", 401, 460, 60),
])
def test_frozen_ordinal_intervals(actual, phase, start, end, count):
    item = actual["availability"][phase]
    assert (item["ordinal_start"], item["ordinal_end"], item["required_count"]) == (
        start, end, count)
    assert protocol.phase_for_ordinal(start) == phase
    assert protocol.phase_for_ordinal(end) == phase


def test_current_239_phase_counts_and_seals(actual):
    a = actual["availability"]
    assert [a[p]["available_count"] for p, _, _ in protocol.PHASES] == [100, 120, 19, 0, 0]
    assert a["validation"]["remaining_count"] == 41
    assert actual["validation_status"] == "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
    assert actual["final_oos_status"] == "FINAL_OOS_POLICY_LOCKED_DATES_NOT_YET_AVAILABLE"


def test_current_exact_dates_are_from_verified_calendar(actual):
    a = actual["availability"]
    assert (a["development"]["available_start"], a["development"]["available_end"]) == (
        "2025-04-02", "2025-08-26")
    assert (a["purge_1"]["available_start"], a["purge_1"]["available_end"]) == (
        "2025-08-27", "2026-03-02")
    assert (a["validation"]["available_start"], a["validation"]["available_end"]) == (
        "2026-03-03", "2026-03-27")
    assert actual["development_last_120_label_endpoint"] == "2026-03-02"


@pytest.mark.parametrize("ordinal", [221, 239, 280, 281, 400, 401, 460])
def test_development_cannot_open_sealed_ordinals(ordinal):
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_evaluation("development", [ordinal])


def test_development_cannot_emit_purge_metrics():
    with pytest.raises(PermissionError, match="PURGED_ORDINAL_ACCESS_ERROR"):
        protocol.guard_evaluation("development", [101, 220])


def test_non_development_phase_not_authorized():
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_evaluation("final_oos", [1])


def test_development_only_ordinals_pass():
    protocol.guard_evaluation("development", [1, 50, 100])


def test_date_guard_maps_and_seals(synthetic_prefix):
    dates, _ = synthetic_prefix
    assert protocol.guard_evaluation_dates("development", [dates[0], dates[99]], dates) == [1, 100]
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_evaluation_dates("development", [dates[220]], dates)


def test_append_preserves_existing_ordinals_and_hashes(synthetic_prefix):
    dates, codes = synthetic_prefix
    initial = protocol.availability_metadata(dates, codes, data_snapshot_id="before")
    extended = dates.append(pd.bdate_range(dates[-1] + pd.Timedelta(days=1), periods=221))
    after = protocol.availability_metadata(extended, codes, data_snapshot_id="after")
    assert len(protocol.verify_frozen_prefix(extended, codes)) == 460
    assert initial["split_policy_hash"] == after["split_policy_hash"]
    assert initial["prediction_config_hash"] == after["prediction_config_hash"]
    assert after["availability"]["final_oos"]["available_count"] == 60
    assert after["oos_performance_status"] == "UNOPENED"


def test_historical_reindex_triggers_review(synthetic_prefix):
    dates, codes = synthetic_prefix
    shifted = dates[1:].append(pd.DatetimeIndex([dates[-1] + pd.offsets.BDay(1)]))
    with pytest.raises(ValueError, match="SPLIT_REPRODUCIBILITY_REVIEW"):
        protocol.verify_frozen_prefix(shifted, codes)


def test_historical_price_revision_changes_fingerprint():
    original = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        "sector_code": ["801010", "801010"],
        "sector_name": ["sample", "sample"],
        "open": [1.0, 2.0], "high": [1.0, 2.0],
        "low": [1.0, 2.0], "close": [1.0, 2.0],
        "volume": [1.0, 2.0], "amount": [1.0, 2.0],
        "is_valid_ohlc": [True, True],
    })
    old_hash = protocol.historical_panel_hash(original)
    appended = pd.concat([original, original.iloc[[-1]].assign(date=pd.Timestamp("2027-01-01"))])
    assert protocol.historical_panel_hash(appended) == old_hash
    revised = original.copy()
    revised.loc[0, "close"] = 1.01
    assert protocol.historical_panel_hash(revised) != old_hash


def test_universe_revision_triggers_review(synthetic_prefix):
    dates, codes = synthetic_prefix
    with pytest.raises(ValueError, match="SPLIT_REPRODUCIBILITY_REVIEW"):
        protocol.verify_frozen_prefix(dates, codes[:-1] + ["999999"])


def test_split_hash_is_deterministic_and_no_ephemera(actual):
    assert protocol.split_policy_hash() == actual["split_policy_hash"]
    assert actual["split_policy_hash"] == "3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038"
    assert not {"timestamp", "uuid", "run_id", "data_snapshot_id"} & set(actual["split_policy"])
    assert actual["frozen_history_sha256"] == protocol.FROZEN_HISTORY_SHA256


def test_prediction_hash_is_deterministic(actual):
    assert protocol.prediction_config_hash() == actual["prediction_config_hash"]
    assert actual["prediction_config_hash"] == "64d5fabe6f194f416c6576d4da9cd5e2fb2ad1e699e2c074047960addaa0ed8c"
    assert len(actual["prediction_config"]["features"]) == 19
    assert actual["prediction_config"]["split_policy_hash"] == actual["split_policy_hash"]


def test_changed_core_parameter_fails_prediction_freeze(monkeypatch):
    monkeypatch.setattr(protocol, "DEFAULT_ALPHA", 0.02)
    with pytest.raises(ValueError, match="RESEARCH_SEMANTICS_FREEZE_REQUIRED"):
        protocol.prediction_config_payload()


def test_metric_definition_is_in_prediction_hash(monkeypatch):
    original = protocol.prediction_config_hash()
    contract = protocol.prediction_metric_contract()
    contract["top5_tie_break"] = "changed"
    monkeypatch.setattr(protocol, "prediction_metric_contract", lambda: contract)
    assert protocol.prediction_config_hash() != original


def test_frozen_metric_contract_is_full_and_prediction_only(actual):
    contract = actual["prediction_metric_contract"]
    assert len(contract["metric_names"]) == 15
    assert contract["minimum_sectors_per_date_horizon"] == 6
    assert contract["label"] == "sector_close[t+h]/sector_close[t]-1"
    assert contract["execution"] is False
    assert contract["missing_rule"] and contract["top5_tie_break"]
    assert contract["date_aggregation"] and contract["overlap_policy"]


def test_synthetic_portfolio_remains_disabled(actual):
    assert actual["synthetic_portfolio_enabled"] is False
    assert actual["synthetic_portfolio_config_hash"] is None


def test_no_performance_outputs_or_results(actual):
    assert all(actual[key] is False for key in (
        "performance_metrics_viewed", "validation_metrics_viewed", "oos_metrics_viewed",
        "level_b_run"))
    assert not {"IC_10", "Sharpe", "drawdown", "equity_curve", "synthetic_total_return"} & set(actual)


def test_no_etf_execution_or_network_dependency(actual, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert protocol.audit_local_policy(Path("data/processed/shenwan"))["validation_metrics_viewed"] is False
    assert actual["split_policy"]["sector_data_admission"] == "FIXED_CLASSIFICATION_RESEARCH"
    text = Path(protocol.__file__).read_text(encoding="utf-8")
    assert "etf_mapping" not in text and "requests" not in text and "docker compose" not in text


def test_policy_json_can_round_trip_without_generated_ids(actual):
    decoded = json.loads(json.dumps(actual, ensure_ascii=False, sort_keys=True))
    assert decoded["split_policy_hash"] == actual["split_policy_hash"]
    assert decoded["prediction_config_hash"] == actual["prediction_config_hash"]

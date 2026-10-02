"""Deterministic signal-only preparation tests; never fit or backtest."""

import socket
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from research.sector_index_baseline import (
    ADMISSION,
    RUN_TYPE,
    SYNTHETIC_RETURN_TYPE,
    SectorResearchResult,
    audit_signal_range,
    load_and_audit,
    research_metadata,
)
from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    make_forward_label,
    temporal_boundaries,
)
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors, select_top


@pytest.fixture(scope="module")
def actual_audit():
    return load_and_audit(Path("data/processed/shenwan"))


def _synthetic_panel(n_sessions: int = 650) -> tuple[pd.DataFrame, list[str], dict]:
    calendar = pd.bdate_range("2022-01-03", periods=n_sessions)
    codes = ["801081", "801193", "801104"]
    panel = pd.DataFrame(
        [(day, code, True) for day in calendar for code in codes],
        columns=["date", "sector_code", "is_valid_ohlc"],
    )
    metadata = {
        "common_start_date": str(calendar[0].date()),
        "common_end_date": str(calendar[-1].date()),
        "admission_level": ADMISSION,
        "strict_pit": False,
        "invalid_ohlc_count": 0,
        "data_snapshot_id": "synthetic-test-only",
    }
    return panel, codes, metadata


@pytest.mark.external_runtime
def test_real_signal_range_is_independent_of_etf_mapping_and_delay(actual_audit):
    assert actual_audit["raw_common_start"] == "2021-12-13"
    assert actual_audit["raw_common_end"] == "2026-09-18"
    assert actual_audit["signal_only_eligible_start"] == "2025-04-02"
    assert actual_audit["signal_only_eligible_end"] == "2026-03-27"
    assert actual_audit["signal_only_session_count"] == 239
    assert actual_audit["old_range_matches_signal_only"] is True
    assert actual_audit["execution_delay_sessions"] is None
    assert "ETF mapping" in actual_audit["excluded_execution_constraints"]


def test_extraneous_execution_metadata_cannot_shrink_signal_range():
    panel, codes, meta = _synthetic_panel()
    original = audit_signal_range(panel, codes, meta)
    with_etf = audit_signal_range(
        panel,
        codes,
        {
            **meta,
            "etf_mapping_admission": "NOT_ADMISSIBLE",
            "etf_listing_date": "2099-01-01",
            "next_session_etf_execution_delay": 100,
            "etf_tradability": False,
        },
    )
    assert (original["signal_only_eligible_start"], original["signal_only_eligible_end"]) == (
        with_etf["signal_only_eligible_start"],
        with_etf["signal_only_eligible_end"],
    )


@pytest.mark.external_runtime
def test_factor_warmup_training_purge_and_last_label_endpoint(actual_audit):
    start = actual_audit["start_derivation"]
    assert actual_audit["feature_count"] == 19
    assert actual_audit["factor_warmup_prior_sessions"] == 120
    assert start["factor_warmup_start"] == "2023-09-27"
    assert start["horizons"]["long"]["label_cutoff"] == "2024-09-30"
    assert start["horizons"]["long"]["rolling_training_calendar_start"] == "2024-03-30"
    assert start["horizons"]["long"]["first_training_session"] == "2024-04-01"
    assert start["horizons"]["long"]["training_session_count"] == 123
    assert start["horizons"]["medium"]["label_cutoff"] == "2025-02-05"
    assert start["horizons"]["short"]["label_cutoff"] == "2025-03-19"
    assert actual_audit["minimum_valid_training_days"] == 30
    assert actual_audit["first_signal_feature_ready_sector_count"] == 124
    assert actual_audit["first_signal_actual_valid_training_days"] == {
        "short": 118,
        "medium": 119,
        "long": 123,
    }
    assert actual_audit["max_label_horizon_and_purge_sessions"] == 120
    assert actual_audit["end_derivation"]["max_horizon_label_endpoint"] == "2026-09-18"
    assert actual_audit["previous_session_rejection"]["signal_date"] == "2025-04-01"
    assert actual_audit["previous_session_rejection"]["first_bad_session"] == "2023-09-22"


def test_short_history_cannot_satisfy_warmup_and_rolling_training():
    panel, codes, meta = _synthetic_panel(350)
    result = audit_signal_range(panel, codes, meta)
    assert result["signal_only_eligible_start"] is None
    assert result["signal_only_eligible_end"] is None


def test_labels_and_purge_hide_future_from_training():
    calendar = pd.bdate_range("2024-01-01", periods=300)
    t = calendar[200]
    close = pd.Series(range(100, 400), index=calendar, dtype=float)
    for horizon in (10, 40, 120):
        b = temporal_boundaries(calendar[:201], t, horizon, 6)
        assert b is not None
        assert b.label_cutoff == calendar[200 - horizon]
        visible = close.loc[:t]
        labels = make_forward_label(visible, horizon, calendar=calendar[:201])
        assert labels.loc[b.label_cutoff] == pytest.approx(
            close.loc[t] / close.loc[b.label_cutoff] - 1.0
        )
        assert labels.loc[t:].isna().all()
        changed_future = close.copy()
        changed_future.loc[changed_future.index > t] *= 1000
        changed_labels = make_forward_label(
            changed_future.loc[:t], horizon, calendar=calendar[:201]
        )
        pd.testing.assert_series_equal(labels, changed_labels)


def test_missing_and_invalid_sessions_are_not_filled():
    panel, codes, meta = _synthetic_panel()
    gap = pd.Timestamp(panel["date"].unique()[100])
    missing = panel.loc[~((panel["date"] == gap) & (panel["sector_code"] == "801193"))]
    result = audit_signal_range(missing, codes, meta)
    assert result["sector_801193_missing_common_sessions"] == 1
    assert result["last_incomplete_session"] == str(gap.date())
    assert result["first_full_session_after_last_gap"] > str(gap.date())
    assert len(missing) == len(panel) - 1  # no synthetic fill row

    invalid = panel.copy()
    invalid.loc[
        (invalid["date"] == gap) & (invalid["sector_code"] == "801193"), "is_valid_ohlc"
    ] = False
    invalid_result = audit_signal_range(invalid, codes, {**meta, "invalid_ohlc_count": 1})
    assert invalid_result["invalid_ohlc_in_common"] == 1
    assert invalid_result["last_incomplete_session"] == str(gap.date())
    assert invalid_result["start_derivation"]["factor_warmup_start"] > str(gap.date())


@pytest.mark.external_runtime
def test_actual_801193_gap_and_source_invalid_bars_remain_visible(actual_audit):
    assert actual_audit["sector_801193_missing_common_sessions"] == 336
    assert actual_audit["last_incomplete_session"] == "2023-09-26"
    assert actual_audit["first_full_session_after_last_gap"] == "2023-09-27"
    assert actual_audit["incomplete_or_invalid_session_count"] == 336
    assert actual_audit["source_invalid_ohlc_total"] == 20
    assert actual_audit["invalid_ohlc_in_common"] == 0


def test_sector_top5_ranking_is_deterministic():
    scores = {
        "801006": 0.3,
        "801005": 0.3,
        "801004": 0.4,
        "801003": 0.5,
        "801002": 0.6,
        "801001": 0.7,
    }
    ranked = rank_sectors(scores)
    assert [code for code, _ in select_top(ranked, 5)] == [
        "801001",
        "801002",
        "801003",
        "801004",
        "801005",
    ]


def test_result_contract_is_non_executable_and_synthetic_only():
    meta = research_metadata("synthetic-test-only", synthetic_returns=True)
    result = SectorResearchResult(
        dates=("2025-04-02",),
        rankings={},
        selected_sector_codes={"2025-04-02": ["801081"]},
        selected_sector_names={"2025-04-02": ["半导体"]},
        model_scores={},
        horizon_scores={},
        fused_scores={},
        realized_forward_sector_returns={},
        research_equity_curve={"2025-04-02": 1.0},
        turnover=None,
        coverage={},
        missing_invalid_diagnostics={},
        metadata=meta,
    )
    assert result.metadata["run_type"] == RUN_TYPE
    assert result.metadata["return_type"] == SYNTHETIC_RETURN_TYPE
    assert result.metadata["executable"] is False
    assert result.metadata["strict_pit"] is False
    assert result.metadata["sector_data_admission"] == ADMISSION
    assert result.metadata["etf_commission"] is None
    assert result.metadata["etf_slippage"] is None
    assert result.metadata["etf_fills"] is None
    with pytest.raises(ValueError, match="synthetic"):
        replace(result, metadata={**meta, "return_type": None})
    with pytest.raises(ValueError, match="non-executable"):
        replace(result, metadata={**meta, "executable": True})
    with pytest.raises(ValueError, match="costs/fills"):
        replace(result, metadata={**meta, "etf_commission": 0.0})


@pytest.mark.external_runtime
def test_frozen_model_assumptions_and_no_network(monkeypatch, actual_audit):
    assert actual_audit["ridge_alpha"] == 0.01
    assert actual_audit["rolling_training_months"] == 6
    assert actual_audit["label_horizons_sessions"] == {"short": 10, "medium": 40, "long": 120}
    assert actual_audit["fusion_weights"] == {"short": 0.25, "medium": 0.50, "long": 0.25}
    assert actual_audit["top_n"] == 5

    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert load_and_audit(Path("data/processed/shenwan"))["signal_only_session_count"] == 239


@pytest.mark.external_runtime
def test_real_preparation_never_reads_etf_data(monkeypatch):
    original_csv = pd.read_csv
    original_text = Path.read_text

    def guarded_csv(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF data read is forbidden")
        return original_csv(path, *args, **kwargs)

    def guarded_text(path, *args, **kwargs):
        if "etf" in str(path).lower():
            raise AssertionError("ETF data read is forbidden")
        return original_text(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_csv)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    assert load_and_audit(Path("data/processed/shenwan"))["signal_only_session_count"] == 239

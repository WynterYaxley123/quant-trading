"""Contract tests for the four approved ETF-Quant data contracts.

Synthetic fixtures only. No network, no lake, no Validation data, no real market
rows. These pin the semantics the user froze, so a later change cannot silently
alter them.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategies.etf_quant.data import (  # noqa: E402
    MIN_CONSTITUENT_COVERAGE_RATIO,
    MIN_VALID_CONSTITUENTS,
    PRODUCTION_DATA_CONTRACTS_V1,
    SOURCE_C_BASE,
    SOURCE_C_IDENTITY,
    SOURCE_C_NOT_OFFICIAL,
)
from strategies.etf_quant.data import membership as mem  # noqa: E402
from strategies.etf_quant.data import tradability as trad  # noqa: E402

SHANGHAI = timezone(timedelta(hours=8))


def row(symbol, code, snapshot, source="sw", system="sw"):
    return {"symbol": symbol, "industry_code": code, "as_of_date": snapshot,
            "source": source, "classification_system": system}


# --- the frozen contract identity -------------------------------------------

def test_approved_contracts_are_the_frozen_identities():
    assert PRODUCTION_DATA_CONTRACTS_V1 == {
        "industry_universe": "TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE",
        "bj_constituent_policy": "INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS",
        "etf_tradability": "ETF_BAR_DERIVED_TRADABILITY_V1",
        "fetch_budget": "PRODUCTION_FETCH_BUDGET_APPROVED",
    }


def test_source_c_identity_is_internal_and_not_an_official_index():
    assert SOURCE_C_IDENTITY == "INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1"
    assert SOURCE_C_NOT_OFFICIAL == "NOT OFFICIAL SHENWAN INDEX"
    assert SOURCE_C_BASE == 1000.0


def test_coverage_gates_remain_frozen():
    """The gates may not be relaxed to raise the pass rate."""
    assert MIN_VALID_CONSTITUENTS == 5
    assert MIN_CONSTITUENT_COVERAGE_RATIO == 0.80


# --- TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE ----------------------------------

def test_asof_takes_the_snapshot_in_force_not_the_latest():
    rows = mem.shenwan_rows([
        row("600000.SH", "480100", date(2020, 1, 23)),
        row("600000.SH", "480200", date(2021, 7, 30)),
    ])
    early = mem.session_universe(rows, date(2021, 1, 4))
    late = mem.session_universe(rows, date(2022, 1, 4))
    assert early.members["600000.SH"] == "4801"
    assert late.members["600000.SH"] == "4802"
    assert early.snapshot_date == date(2020, 1, 23)


def test_future_snapshot_never_reaches_a_past_session():
    """The lookahead this policy exists to prevent."""
    rows = mem.shenwan_rows([row("600000.SH", "480100", date(2024, 1, 31))])
    with pytest.raises(mem.MembershipError, match="NO_MEMBERSHIP_AT_OR_BEFORE_SESSION"):
        mem.session_universe(rows, date(2023, 1, 4))


def test_retired_industry_absent_from_a_later_session():
    rows = mem.shenwan_rows([
        row("600000.SH", "210200", date(2020, 1, 23)),   # retired at the 2021 break
        row("600000.SH", "220800", date(2021, 7, 30)),
    ])
    assert mem.session_universe(rows, date(2021, 1, 4)).taxonomy_active_count == 1
    codes_2021 = set(mem.session_universe(rows, date(2021, 1, 4)).members.values())
    codes_2022 = set(mem.session_universe(rows, date(2022, 1, 4)).members.values())
    assert codes_2021 == {"2102"} and codes_2022 == {"2208"}


def test_union_is_not_used_as_a_daily_universe():
    rows = mem.shenwan_rows([
        row("600000.SH", "210200", date(2020, 1, 23)),
        row("600001.SH", "220800", date(2021, 7, 30)),
    ])
    daily = mem.session_universe(rows, date(2021, 1, 4))
    assert set(daily.members) == {"600000.SH"}, "a later member leaked into an earlier session"


def test_non_shenwan_axes_are_rejected():
    """EastMoney's 3/4-digit board codes are a different taxonomy."""
    rows = mem.shenwan_rows([
        row("600000.SH", "480100", date(2020, 1, 23), source="eastmoney"),
        row("600001.SH", "480100", date(2020, 1, 23), system="eastmoney"),
        row("600002.SH", "480100", date(2020, 1, 23)),
    ])
    assert [r.symbol for r in rows] == ["600002.SH"]


def test_short_board_codes_are_not_shenwan():
    rows = mem.shenwan_rows([row("600000.SH", "4801", date(2020, 1, 23)),
                             row("600001.SH", "480100", date(2020, 1, 23))])
    assert [r.symbol for r in rows] == ["600001.SH"]


def test_empty_shenwan_membership_is_explicit_not_silent():
    with pytest.raises(mem.MembershipError, match="SHENWAN_MEMBERSHIP_UNAVAILABLE"):
        mem.shenwan_rows([])


def test_level_hierarchy_is_prefix_based():
    assert mem.level_of("240301", 2) == "24"
    assert mem.level_of("240301", 4) == "2403"
    assert mem.level_of("240301", 6) == "240301"
    with pytest.raises(mem.MembershipError):
        mem.level_of("240301", 5)


def test_taxonomy_counts_are_derived_never_hardcoded():
    rows = mem.shenwan_rows([
        row("600000.SH", "110100", date(2020, 1, 23)),
        row("600001.SH", "110200", date(2020, 1, 23)),
        row("600000.SH", "220100", date(2021, 7, 30)),
        row("600001.SH", "220200", date(2021, 7, 30)),
        row("600002.SH", "330100", date(2021, 7, 30)),
    ])
    counts = mem.taxonomy_counts(rows, [date(2021, 1, 4), date(2022, 1, 4)])
    assert counts["observed_active_counts"] == [2, 3]
    assert counts["taxonomy_active_last"] == 3
    assert counts["union_over_sessions"] == 5
    assert counts["sessions_by_observed_count"] == {"2": 1, "3": 1}
    # Unmeasured counts must be labelled as unlabelled, never coerced to a known regime.
    assert counts["regime_labels"][2] == "UNLABELLED_MEASURED_COUNT"


def test_measured_regime_labels_are_labels_not_thresholds():
    """The measured 118/162 counts name a regime; they must not select a universe."""
    rows = mem.shenwan_rows(
        [row(f"60000{i}.SH", f"11{i:02d}00", date(2020, 1, 23)) for i in range(3)]
    )
    counts = mem.taxonomy_counts(rows, [date(2021, 1, 4)])
    assert counts["observed_active_counts"] == [3]
    assert counts["regime_labels"][3] == "UNLABELLED_MEASURED_COUNT"
    assert 118 in mem.MEASURED_TAXONOMY_REGIMES.values()


def test_universe_resolution_ignores_the_measured_regime_constants():
    """A synthetic 4-industry taxonomy must resolve normally, with no 118/162 branch."""
    rows = mem.shenwan_rows([
        row("600000.SH", "110100", date(2020, 1, 23)),
        row("600001.SH", "110200", date(2020, 1, 23)),
        row("600002.SH", "110300", date(2020, 1, 23)),
        row("600003.SH", "110400", date(2020, 1, 23)),
    ])
    universe = mem.session_universe(rows, date(2021, 1, 4))
    assert universe.taxonomy_active_count == 4
    assert len(universe.members) == 4


# --- INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS ------------------------------------

def test_bj_members_are_required_symbols_not_filtered():
    rows = mem.shenwan_rows([
        row("600000.SH", "220900", date(2020, 1, 23)),
        row("832317.BJ", "220900", date(2020, 1, 23)),
        row("430047.BJ", "220900", date(2020, 1, 23)),
    ])
    required = mem.required_symbols(rows, [date(2021, 1, 4)])
    assert "832317.BJ" in required and "430047.BJ" in required


def test_bj_accounting_reports_share_so_exclusion_cannot_be_silent():
    rows = mem.shenwan_rows(
        [row(f"60000{i}.SH", "220900", date(2020, 1, 23)) for i in range(7)]
        + [row(f"83231{i}.BJ", "220900", date(2020, 1, 23)) for i in range(3)]
    )
    report = mem.bj_constituent_accounting(rows, date(2021, 1, 4))
    assert report["bj_members"] == 3
    assert report["total_members"] == 10
    assert report["max_bj_share"] == pytest.approx(0.30)
    assert report["max_bj_share_industry"] == "2209"
    assert report["industries_bj_share_ge_20pct"] == 1


def test_historical_only_members_are_surfaced():
    rows = mem.shenwan_rows([
        row("600000.SH", "220900", date(2020, 1, 23)),
        row("600001.SH", "220900", date(2020, 1, 23)),
        row("600000.SH", "220900", date(2021, 7, 30)),
    ])
    only = mem.historical_only_symbols(rows, [date(2020, 6, 1), date(2022, 1, 4)])
    assert only == ("600001.SH",)


def test_exchange_parsing_rejects_malformed_symbols():
    assert mem.exchange_of("600519.SH") == "SH"
    assert mem.exchange_of("000001.SZ") == "SZ"
    assert mem.exchange_of("832317.BJ") == "BJ"
    for bad in ("600519", "600519.XX", "SH"):
        with pytest.raises(mem.MembershipError):
            mem.exchange_of(bad)


# --- ETF_BAR_DERIVED_TRADABILITY_V1 -----------------------------------------

SIGNAL = date(2026, 9, 24)
EXEC = date(2026, 9, 25)


def bar(**over):
    base = {"symbol": "510300.SH", "trade_date": EXEC, "open": 4.10, "high": 4.20,
            "low": 4.05, "close": 4.15, "volume": 1_000_000, "amount": 4_100_000.0,
            "fetched_at": datetime.combine(EXEC, datetime.min.time(), SHANGHAI) + timedelta(hours=15, minutes=30)}
    base.update(over)
    return base


def test_all_five_clauses_satisfied_passes():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar())
    assert verdict.status == trad.PASS
    assert verdict.tradable is True
    assert verdict.reason == "ALL_FIVE_CLAUSES_SATISFIED"


def test_verdict_always_carries_the_evidence_qualifier():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar())
    assert verdict.qualifier == trad.TRADABILITY_QUALIFIER
    assert "NOT_REALTIME" in verdict.qualifier
    assert verdict.contract == "ETF_BAR_DERIVED_TRADABILITY_V1"


@pytest.mark.parametrize("field,value,reason", [
    ("open", 0.0, "T1_OPEN_NOT_POSITIVE"),
    ("open", -1.0, "T1_OPEN_NOT_POSITIVE"),
    ("open", None, "T1_OPEN_NOT_POSITIVE"),
    ("volume", 0, "T1_VOLUME_NOT_POSITIVE"),
    ("volume", -5, "T1_VOLUME_NOT_POSITIVE"),
    ("amount", 0.0, "T1_AMOUNT_NOT_POSITIVE"),
    ("amount", None, "T1_AMOUNT_NOT_POSITIVE"),
])
def test_each_missing_clause_blocks(field, value, reason):
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar(**{field: value}))
    assert verdict.status == trad.BLOCKED
    assert verdict.reason == reason


def test_missing_bar_blocks():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=None)
    assert verdict.status == trad.BLOCKED and verdict.reason == "T1_BAR_MISSING"


def test_not_admitted_blocks():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=False, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar())
    assert verdict.reason == "INSTRUMENT_NOT_ADMITTED"


def test_same_day_execution_is_a_lookahead_and_blocks():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=SIGNAL, bar=bar(trade_date=SIGNAL))
    assert verdict.reason == "EXECUTION_DATE_NOT_AFTER_SIGNAL_DATE"


def test_no_execution_session_blocks():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=None, bar=None)
    assert verdict.reason == "NO_EXECUTION_SESSION"


def test_t1_close_cannot_substitute_for_t1_open():
    """A T+1 bar with no open at all must block, not fall back to close."""
    without_open = bar()
    del without_open["open"]
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=without_open)
    assert verdict.status == trad.BLOCKED and verdict.reason == "T1_OPEN_NOT_POSITIVE"


def test_t2_open_cannot_substitute_for_t1():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar(trade_date=date(2026, 9, 28)))
    assert verdict.reason == "T1_BAR_DATE_MISMATCH"


def test_previous_close_cannot_substitute_for_t1():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar(trade_date=SIGNAL))
    assert verdict.reason == "T1_BAR_DATE_MISMATCH"


def test_other_symbol_bar_cannot_substitute():
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar(symbol="510500.SH"))
    assert verdict.reason == "T1_BAR_SYMBOL_MISMATCH"


def test_unfinalized_same_session_bar_blocks():
    early = datetime.combine(EXEC, datetime.min.time(), SHANGHAI) + timedelta(hours=14, minutes=30)
    verdict = trad.evaluate(etf_code="510300.SH", admitted=True, signal_date=SIGNAL,
                            execution_date=EXEC, bar=bar(fetched_at=early))
    assert verdict.reason == "T1_BAR_NOT_FINALIZED"


def test_finality_boundary_is_1505_shanghai():
    at_1500 = datetime.combine(EXEC, datetime.min.time(), SHANGHAI) + timedelta(hours=15)
    at_1505 = datetime.combine(EXEC, datetime.min.time(), SHANGHAI) + timedelta(hours=15, minutes=5)
    assert trad.is_finalized(bar(fetched_at=at_1500), fetched_at=at_1500) is False
    assert trad.is_finalized(bar(fetched_at=at_1505), fetched_at=at_1505) is True


def test_next_session_resolution_uses_the_real_calendar_not_a_timedelta():
    sessions = [date(2026, 9, 24), date(2026, 9, 28), date(2026, 9, 29)]
    assert trad.next_session(sessions, date(2026, 9, 24)) == date(2026, 9, 28)
    assert trad.next_session([date(2026, 9, 24)], date(2026, 9, 24)) is None


def test_evaluate_for_sessions_blocks_when_calendar_has_no_next_session():
    verdict = trad.evaluate_for_sessions(etf_code="510300.SH", admitted=True,
                                         signal_date=date(2026, 9, 24),
                                         sessions=[date(2026, 9, 24)], bars_by_date={})
    assert verdict.status == trad.BLOCKED
    assert verdict.reason == "NO_NEXT_SESSION_IN_CALENDAR"


def test_evaluate_for_sessions_passes_with_a_finalized_next_bar():
    sessions = [SIGNAL, EXEC]
    verdict = trad.evaluate_for_sessions(etf_code="510300.SH", admitted=True,
                                         signal_date=SIGNAL, sessions=sessions,
                                         bars_by_date={EXEC: bar()})
    assert verdict.status == trad.PASS

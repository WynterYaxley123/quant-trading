"""Source-C construction tests. Synthetic fixtures only; no lake, no network."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategies.etf_quant.data import membership as mem  # noqa: E402
from strategies.etf_quant.data import source_c as sc  # noqa: E402


def member(symbol, code, snapshot=date(2020, 1, 23)):
    return {
        "symbol": symbol,
        "industry_code": code,
        "as_of_date": snapshot,
        "source": "sw",
        "classification_system": "sw",
    }


SESSION = date(2026, 9, 24)


def five_members(code="220900"):
    return mem.shenwan_rows([member(f"60000{i}.SH", code) for i in range(5)])


def flat_prices(symbols, close=10.0, prev=10.0, exact=True):
    return ({s: close for s in symbols}, {s: prev for s in symbols}, {s: exact for s in symbols})


# --- constituent return arithmetic ------------------------------------------


def test_exact_adjusted_return_is_computed():
    value, reason = sc.constituent_return(close=11.0, prev_close=10.0, adj_is_exact=True)
    assert reason is None and value == pytest.approx(0.1)


def test_non_exact_adjustment_refuses_to_produce_a_return():
    """The core adjustment gate: a raw price must never wear an adjusted label."""
    value, reason = sc.constituent_return(close=11.0, prev_close=10.0, adj_is_exact=False)
    assert value is None and reason == sc.REASON_NOT_EXACT


def test_missing_adj_flag_is_not_exact():
    for flag in (None, 0, 1, "true"):
        value, reason = sc.constituent_return(close=11.0, prev_close=10.0, adj_is_exact=flag)
        assert value is None and reason == sc.REASON_NOT_EXACT


@pytest.mark.parametrize(
    "close,prev,expected",
    [
        (None, 10.0, sc.REASON_NO_BAR),
        (10.0, None, sc.REASON_PREV_MISSING),
        (None, None, sc.REASON_NO_BAR),
    ],
)
def test_missing_prices_are_distinguished(close, prev, expected):
    """No bar and no prior close are different facts and must not be collapsed."""
    value, reason = sc.constituent_return(close=close, prev_close=prev, adj_is_exact=True)
    assert value is None and reason == expected


@pytest.mark.parametrize("close,prev", [(0.0, 10.0), (10.0, 0.0), (-1.0, 10.0), (10.0, -1.0)])
def test_non_positive_prices_are_rejected(close, prev):
    value, reason = sc.constituent_return(close=close, prev_close=prev, adj_is_exact=True)
    assert value is None and reason == sc.REASON_NON_POSITIVE


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_prices_are_rejected(bad):
    value, reason = sc.constituent_return(close=bad, prev_close=10.0, adj_is_exact=True)
    assert value is None and reason in (sc.REASON_INVALID_VALUE, sc.REASON_NON_POSITIVE)


# --- the frozen coverage gate -----------------------------------------------


def test_five_valid_of_five_passes():
    rows = five_members()
    symbols = [r.symbol for r in rows]
    closes, prevs, exact = flat_prices(symbols)
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 5 and item.eligible == 5
    assert item.coverage_ratio == pytest.approx(1.0)
    assert item.status == sc.VALID and item.industry_return == pytest.approx(0.0)


def test_four_valid_of_five_fails_the_count_gate():
    rows = five_members()
    symbols = [r.symbol for r in rows]
    closes, prevs, exact = flat_prices(symbols)
    closes[symbols[0]] = None
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 4 and item.status == sc.INVALID
    assert item.industry_return is None


def test_ratio_gate_uses_full_membership_as_denominator():
    """Ten members, eight valid: count passes but 0.80 is exactly the boundary."""
    symbols = [f"6000{i:02d}.SH" for i in range(10)]
    closes, prevs, exact = flat_prices(symbols)
    for s in symbols[:2]:
        closes[s] = None
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 8 and item.coverage_ratio == pytest.approx(0.80)
    assert item.status == sc.VALID, "0.80 is inclusive per the frozen gate"

    closes[symbols[2]] = None  # now 7/10 = 0.70
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.status == sc.INVALID
    assert item.industry_return is None


def test_non_exact_constituents_lower_the_ratio_and_never_enter_the_mean():
    """A non-exact row must be excluded, not silently used at factor 1.0."""
    symbols = [f"6000{i:02d}.SH" for i in range(10)]
    closes, prevs, exact = flat_prices(symbols)
    for s in symbols[:2]:
        exact[s] = False
    closes[symbols[0]] = 99.0  # a wild return that must NOT leak in
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 8
    assert item.coverage_ratio == pytest.approx(0.80)
    assert item.status == sc.VALID
    assert item.industry_return == pytest.approx(0.0), "non-exact rows contaminated the mean"
    assert item.reasons.get(sc.REASON_NOT_EXACT) == 2


def test_ratio_gate_blocks_the_mean_when_coverage_is_insufficient():
    """Half the basket non-exact: the count may pass, but 0.50 must refuse a mean."""
    symbols = [f"6000{i:02d}.SH" for i in range(10)]
    closes, prevs, exact = flat_prices(symbols)
    for s in symbols[:5]:
        exact[s] = False
    closes[symbols[0]] = 99.0
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 5
    assert item.coverage_ratio == pytest.approx(0.50)
    assert item.status == sc.INVALID
    assert item.industry_return is None, "a mean over 50% coverage must not be published"


def test_equal_weight_mean_is_arithmetic_not_geometric():
    symbols = ["600000.SH", "600001.SH", "600002.SH", "600003.SH", "600004.SH"]
    closes = dict.fromkeys(symbols, 10.0)
    prevs = dict.fromkeys(symbols, 10.0)
    exact = dict.fromkeys(symbols, True)
    closes["600000.SH"] = 11.0  # +10%
    closes["600001.SH"] = 9.0  # -10%
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.industry_return == pytest.approx(0.0)


def test_invalid_date_holds_the_level_and_is_not_a_zero_return():
    valid = sc.IndustryDate(SESSION, "2209", 5, 5, 1.0, 0.10, sc.VALID, {})
    invalid = sc.IndustryDate(
        date(2026, 9, 25), "2209", 5, 1, 0.2, None, sc.INVALID, {sc.REASON_NOT_EXACT: 4}
    )
    levels = sc.index_levels([valid, invalid])
    assert levels[0]["index_level"] == pytest.approx(1100.0)
    assert levels[1]["index_level"] == pytest.approx(1100.0), "an invalid date moved the level"


def test_index_base_is_1000_and_compounds():
    a = sc.IndustryDate(SESSION, "2209", 5, 5, 1.0, 0.10, sc.VALID, {})
    b = sc.IndustryDate(date(2026, 9, 25), "2209", 5, 5, 1.0, -0.10, sc.VALID, {})
    levels = sc.index_levels([a, b])
    assert levels[0]["index_level"] == pytest.approx(1000.0 * 1.10)
    assert levels[1]["index_level"] == pytest.approx(1000.0 * 1.10 * 0.90)


def test_non_positive_base_is_refused():
    with pytest.raises(sc.SourceCError, match="BASE_MUST_BE_POSITIVE"):
        sc.index_levels([], base=0.0)


def test_series_carries_its_identity_and_disclaimer():
    item = sc.IndustryDate(SESSION, "2209", 5, 5, 1.0, 0.0, sc.VALID, {})
    out = sc.index_levels([item])[0]
    assert out["identity"] == "INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1"
    assert out["disclaimer"] == "NOT OFFICIAL SHENWAN INDEX"


# --- session build + as-of interaction --------------------------------------


def test_build_session_uses_asof_membership_only():
    rows = mem.shenwan_rows(
        [
            member("600000.SH", "220900", date(2020, 1, 23)),
            member("600001.SH", "220900", date(2020, 1, 23)),
            member("600000.SH", "220900", date(2020, 1, 23)),
            member("600002.SH", "330100", date(2020, 1, 23)),
        ]
    )
    symbols = [r.symbol for r in rows]
    closes, prevs, exact = flat_prices(symbols)
    items = sc.build_session(
        rows=rows, session=SESSION, closes=closes, prev_closes=prevs, adj_exact=exact
    )
    assert [i.industry_code for i in items] == ["2209", "3301"]
    assert items[0].eligible == 2 and items[1].eligible == 1
    assert all(i.status == sc.INVALID for i in items), "fewer than 5 constituents must not pass"


def test_bj_constituents_count_toward_eligible_and_lower_the_ratio():
    """INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS: BJ is in the denominator, so a gap shows."""
    symbols = [f"60000{i}.SH" for i in range(5)] + ["832317.BJ", "833874.BJ"]
    rows = mem.shenwan_rows([member(s, "220900") for s in symbols])
    closes, prevs, exact = flat_prices(symbols)
    closes["832317.BJ"] = None  # a BJ name with no bar
    closes["833874.BJ"] = None
    items = sc.build_session(
        rows=rows, session=SESSION, closes=closes, prev_closes=prevs, adj_exact=exact
    )
    assert items[0].eligible == 7, "BJ members were dropped from the denominator"
    assert items[0].valid == 5
    assert items[0].coverage_ratio == pytest.approx(5 / 7)


def test_bj_impact_report_quantifies_the_cost_of_the_policy():
    symbols = [f"60000{i}.SH" for i in range(8)] + ["832317.BJ", "833874.BJ"]
    rows = mem.shenwan_rows([member(s, "220900") for s in symbols])
    closes, prevs, exact = flat_prices(symbols)
    closes["832317.BJ"] = None
    report = sc.bj_coverage_impact(
        rows=rows, session=SESSION, closes=closes, prev_closes=prevs, adj_exact=exact
    )
    assert report["total_bj_members"] == 2
    assert report["total_bj_missing"] == 1
    assert report["industries_affected"] == 1


def test_reasons_are_recorded_so_a_low_ratio_is_explainable():
    symbols = [f"60000{i}.SH" for i in range(6)]
    closes, prevs, exact = flat_prices(symbols)
    closes[symbols[0]] = None
    exact[symbols[1]] = False
    prevs[symbols[2]] = None
    closes[symbols[3]] = 0.0
    item = sc.industry_date(
        session=SESSION,
        industry_code="2209",
        constituents=symbols,
        closes=closes,
        prev_closes=prevs,
        adj_exact=exact,
    )
    assert item.valid == 2 and item.status == sc.INVALID
    assert item.reasons == {
        sc.REASON_NO_BAR: 1,
        sc.REASON_NOT_EXACT: 1,
        sc.REASON_PREV_MISSING: 1,
        sc.REASON_NON_POSITIVE: 1,
    }

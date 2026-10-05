"""Synthetic V7 recovery, complete-history and production accounting regressions."""

import json
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import polars as pl
import pytest
from test_etf_quant_v2_shadow import make_plan, registry, release, synthetic_facts

from strategies.etf_quant.domain import TargetPosition, TradingCalendar
from strategies.etf_quant.runtime import storage
from strategies.etf_quant.simulation import mark_to_market, new_portfolio
from strategies.etf_quant.simulation.lots import rebalance_at_open
from strategies.etf_quant_v2.accounting import settle_t_plus_one
from strategies.etf_quant_v2.facts import MembershipLookup, history_window, load_liquidity
from strategies.etf_quant_v2.runtime import SHANGHAI
from strategies.etf_quant_v2.shadow import cycle, load_state


def test_membership_views_preserve_latest_rows_without_random_reduction_or_repeated_builds():
    first, change = date(2026, 9, 24), date(2026, 9, 29)
    frame = pl.DataFrame(
        {
            "symbol": [str(i) for i in range(400)] + ["0"],
            "as_of_date": [first] * 400 + [change],
            "industry_code": ["SYNTHETIC_A"] * 400 + ["SYNTHETIC_B"],
        }
    )
    lookup = MembershipLookup(frame)
    assert lookup.visible(date(2026, 9, 23)).is_empty()
    for day in (first, date(2026, 9, 25), date(2026, 9, 28), change, date(2026, 9, 30)):
        reference = (
            frame.filter(pl.col("as_of_date") <= day)
            .sort("as_of_date")
            .unique("symbol", keep="last")
            .sort("symbol")
        )
        assert lookup.visible(day).to_dicts() == reference.to_dicts()
    assert lookup.builds == 3  # Empty, original membership, actual change.
    rng = np.random.default_rng(1704)
    values = dict(zip([str(i) for i in range(400)], rng.normal(0, 0.01, 400), strict=True))
    results = set()
    for _ in range(30):
        independent = MembershipLookup(frame).visible(first)
        mean = np.mean([values[s] for s in independent["symbol"].to_list()])
        results.add(np.asarray([mean]).tobytes())
    assert len(results) == 1


@pytest.mark.parametrize("months", [6, 9, 12, 18, 24])
def test_history_covers_every_supported_window_and_maturity(months):
    facts = synthetic_facts()
    day = facts.dates[-1]
    earliest = history_window(facts.dates, day, months, (10, 40, 120))
    expected = (pd.Timestamp(facts.dates[-121]) - pd.DateOffset(months=months)).date()
    assert earliest == expected
    records, _ = facts.model_inputs(day, training_months=months)
    assert min(r.day for r in records) >= earliest
    # Every configured horizon has the entire requested window available.
    for h in (10, 40, 120):
        cutoff = facts.dates[-1 - h]
        window = (pd.Timestamp(cutoff) - pd.DateOffset(months=months)).date()
        selected = {r.day for r in records if h in r.returns and window <= r.day <= cutoff}
        assert selected == {d for d in facts.dates if window <= d <= cutoff}


def test_unsupported_or_truncated_history_fails_explicitly():
    days = tuple(d.date() for d in pd.bdate_range("2025-01-01", "2026-10-12"))
    with pytest.raises(ValueError, match="FULL_FORWARD_HISTORY"):
        history_window(days, days[-1], 24, (10, 40, 120))
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        history_window(days, days[-1], 20, (10, 40, 120))


@pytest.mark.parametrize("crash", [None, False, True])
def test_missed_t1_is_terminal_preserved_and_future_cycle_is_idempotent(
    tmp_path, monkeypatch, crash
):
    facts = synthetic_facts(end="2026-10-14")
    reg = registry(facts.industries)
    root = tmp_path / "SYNTHETIC_V2"
    options = dict(
        calendar=TradingCalendar(facts.dates),
        code_commit="f" * 40,
        registry_entries=reg["entries"],
        raw_opens={},
        raw_closes={},
        benchmark_close=100.0,
    )
    first, prefix, plan = make_plan(facts, date(2026, 10, 8), reg)
    cycle(
        root,
        release(),
        plan,
        now=first,
        snapshot_observed_at=first,
        factual_prefix_sha256=prefix.prefix_hash(first.date()),
        **options,
    )
    old = load_state(root)
    later, prefix, plan = make_plan(facts, date(2026, 10, 12), reg)
    if crash is not None:
        original = storage.atomic_bytes

        def interrupt(path, payload, **kwargs):
            if path == root / "latest.json":
                if crash:
                    original(path, payload, **kwargs)
                raise SystemExit("SYNTHETIC_RECOVERY_CRASH")
            return original(path, payload, **kwargs)

        monkeypatch.setattr(storage, "atomic_bytes", interrupt)
        with pytest.raises(SystemExit, match="RECOVERY_CRASH"):
            cycle(
                root,
                release(),
                plan,
                now=later,
                snapshot_observed_at=later,
                factual_prefix_sha256=prefix.prefix_hash(later.date()),
                **options,
            )
        monkeypatch.setattr(storage, "atomic_bytes", original)
    result = cycle(
        root,
        release(),
        plan,
        now=later,
        snapshot_observed_at=later,
        factual_prefix_sha256=prefix.prefix_hash(later.date()),
        **options,
    )
    current = load_state(root)
    assert current["fills"] == []
    assert current["portfolio"]["cash"] == old["portfolio"]["cash"] == "10000"
    assert current["recovery_events"][0]["original_intent"] == old["pending"]
    assert current["terminal_epochs"][0]["status"] == "ABANDONED_MISSED_T1"
    assert current["terminal_epochs"][0]["fillable"] is False
    assert current["intents"][0]["status"] == "ABANDONED_MISSED_T1"
    assert current["intents"][0]["fillable"] is False
    assert current["epoch"]["epoch_id"].endswith("0002")
    assert current["pending"]["signal_date"] == "2026-10-12"
    assert result["view"]["epoch_count"] == 2
    before = (root / "latest.json").read_bytes()
    assert (
        cycle(
            root,
            release(),
            plan,
            now=later,
            snapshot_observed_at=later,
            factual_prefix_sha256=prefix.prefix_hash(later.date()),
            **options,
        )["status"]
        == "ALREADY_PROCESSED"
    )
    assert (root / "latest.json").read_bytes() == before
    assert len(load_state(root)["recovery_events"]) == 1


@pytest.mark.parametrize("symbol", ["../escape", "510001.SH/../../escape", "abc.SH"])
def test_refresh_rejects_symbols_before_provider_import_or_filesystem(tmp_path, symbol):
    from strategies.etf_quant_v2.refresh import refresh

    output = tmp_path / "absent"
    with pytest.raises(ValueError, match="SYMBOL_CONTRACT"):
        refresh([symbol], date(2026, 9, 30), output, tmp_path / "source")
    assert not output.exists()


def test_empty_signal_state_fails_closed_with_clear_guard(tmp_path):
    state = {
        "strategy_version": "ETF_QUANT_V2",
        "mode": "SIMULATION_ONLY",
        "broker_enabled": False,
        "real_order_path": False,
        "signals": [],
    }
    storage.publish_account_generation(
        tmp_path,
        "SYNTHETIC_EMPTY",
        {"state.json": storage.json_bytes(state), "view.json": b"{}"},
        {},
    )
    with pytest.raises(ValueError, match="EMPTY_SIGNAL"):
        load_state(tmp_path)


@pytest.mark.parametrize(
    "symbol", ["../escape", "510001.SH/../../escape", "510001", "abc.SH", "510001.SH\\escape"]
)
def test_symbol_is_validated_before_liquidity_path(tmp_path, symbol):
    day = date(2026, 9, 30)
    directory = tmp_path / str(day)
    directory.mkdir()
    sessions = [str(d.date()) for d in pd.bdate_range(end=day, periods=20)]
    from strategies.etf_quant_v2.refresh import PIN

    (directory / "summary.json").write_text(
        json.dumps(
            {
                "data_cutoff": str(day),
                "calendar": sessions,
                "source_commit": PIN,
                "window": sessions,
                "receipts": [{"symbol": symbol, "liquidity_amount": 1}],
            }
        )
    )
    with pytest.raises(ValueError, match="SYMBOL_CONTRACT"):
        load_liquidity(tmp_path, day)


def test_compatibility_accounting_is_exactly_production_lots_costs_cash_and_nav():
    signal = datetime(2026, 10, 8, 16, tzinfo=SHANGHAI)
    processed = datetime(2026, 10, 9, 16, tzinfo=SHANGHAI)
    calendar = TradingCalendar((signal.date(), processed.date()))
    state = new_portfolio(signal)
    opens, closes = {"510001.SH": Decimal("10")}, {"510001.SH": Decimal("11")}
    actual, fills = settle_t_plus_one(
        state,
        signal_at=signal,
        processed_at=processed,
        calendar=calendar,
        weights={"510001.SH": 0.25},
        raw_opens=opens,
        raw_closes=closes,
        finalized=True,
    )
    expected, reference_fills = rebalance_at_open(
        state,
        (TargetPosition("510001.SH", 0.25),),
        opens,
        signal_day=signal.date(),
        execution_day=processed.date(),
        processed_at=processed.replace(hour=9, minute=30),
        calendar=calendar,
        batch_id=f"v2-{signal.date()}",
        lot_size=100,
    )
    expected = mark_to_market(expected, closes, as_of=processed)
    assert actual == expected and fills == reference_fills
    assert actual.positions[0].quantity == 200
    assert actual.cash == Decimal("7998.39970000")
    assert actual.total_equity == Decimal("10198.39970000")

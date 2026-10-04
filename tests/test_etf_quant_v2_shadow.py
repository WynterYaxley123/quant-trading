"""Deterministic factual-to-forward-ledger acceptance; no external market input."""

import json
import shutil
import subprocess
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.domain import TradingCalendar
from strategies.etf_quant_v2.facts import ForwardFacts, factors_from_closes
from strategies.etf_quant_v2.mapping import candidate_pools
from strategies.etf_quant_v2.runtime import SHANGHAI, FrozenSpecification, prepare_signal
from strategies.etf_quant_v2.shadow import cycle, load_state, public_view, temporal_gate


def synthetic_facts():
    days = tuple(d.date() for d in pd.bdate_range("2023-01-02", "2026-10-12"))
    rng = np.random.default_rng(651)
    changes = rng.normal(0.0003, 0.009, (len(days), 12))
    closes = 100 * np.exp(np.cumsum(changes, axis=0))
    return ForwardFacts(
        days,
        tuple(f"SYNTHETIC_{j}" for j in range(12)),
        factors_from_closes(closes, days),
        closes,
        np.zeros(closes.shape, dtype=np.int64),
        datetime(2026, 10, 8, 16, tzinfo=SHANGHAI),
        "a" * 64,
        {},
    )


def release():
    # Public release identity only; all prices/industries/runtime are synthetic.
    return json.loads(
        (
            Path(__file__).resolve().parents[1] / "strategies/etf_quant_v2/config/release.json"
        ).read_bytes()
    )


def registry(industries):
    entries = []
    for code in industries:
        for etf in ("510001.SH", "510002.SH"):
            entries.append(
                dict(
                    industry_code=code,
                    industry_name=code,
                    etf_code=etf,
                    tracking_index="SYNTHETIC",
                    mapping_class="VERIFIED_INDUSTRY_PROXY",
                    available_at="2026-10-04T12:00:00+08:00",
                    evidence_date="2026-09-30",
                    membership_date="2026-09-24",
                    target_exposure=45.0,
                    second_exposure=30.0,
                    unknown_exposure=0.0,
                    complete_weights=True,
                    active=True,
                    target_is_largest=True,
                    weight_source_sha256="d" * 64,
                    product_source_sha256="e" * 64,
                    confidence="SYNTHETIC_COMPLETE",
                    weight_source_url="https://synthetic.invalid/",
                )
            )
    return {"proxy_threshold": 40, "entries": entries}


def make_plan(facts, day, entries):
    end = facts.dates.index(day) + 1
    now = datetime.combine(day, datetime.min.time().replace(hour=16), SHANGHAI)
    current_facts = ForwardFacts(
        facts.dates[:end],
        facts.industries,
        facts.features[:end],
        facts.closes[:end],
        facts.segments[:end],
        now,
        facts.snapshot_sha256,
        {},
    )
    observations, current = current_facts.model_inputs(day)
    spec = FrozenSpecification(
        "SYNTHETIC",
        (10, 40, 120),
        (0.25, 0.5, 0.25),
        30,
        12,
        "RAW",
        release()["candidate_sha256"],
        datetime(2026, 10, 4, tzinfo=SHANGHAI),
        date(2025, 12, 30),
        date(2026, 4, 2),
        True,
        final_oos_authorized=True,
    )
    plan = prepare_signal(
        spec,
        observations,
        current,
        calendar=facts.dates,
        signal_at=now,
        snapshot_available_at=now,
        finalized=True,
        mapping_available_at=spec.frozen_at,
        mapping_pools=candidate_pools(entries, {"510001.SH": 2000.0, "510002.SH": 1000.0}, now),
        exposure_vectors={},
    )
    return now, current_facts, plan


def test_facts_factors_ridge_mapping_intent_delayed_lots_nav_and_view(tmp_path):
    facts = synthetic_facts()
    reg = registry(facts.industries)
    now, prefix, plan = make_plan(facts, date(2026, 10, 8), reg)
    assert [len(m["coefficients"]) for m in plan["models"]] == [5, 19, 19]
    assert all(m["alpha"] == 30 and m["training_dates"] >= 30 for m in plan["models"])
    assert plan["validation_accepted"] is False and plan["historical_final_oos_accepted"] is True
    assert len(plan["rankings"][:5]) == 5 and len(plan["allocation"]["executed"]) == 2
    assert len(plan["allocation"]["skipped"]) == 3
    assert all(r["weight"] <= 0.35 for r in plan["allocation"]["executed"])
    options = dict(
        calendar=TradingCalendar(facts.dates),
        code_commit="f" * 40,
        registry_entries=reg["entries"],
        raw_opens={},
        raw_closes={},
        benchmark_close=100.0,
    )
    root = tmp_path / "etf-quant-v2"
    first = cycle(
        root,
        release(),
        plan,
        now=now,
        snapshot_observed_at=now,
        factual_prefix_sha256=prefix.prefix_hash(now.date()),
        **options,
    )
    assert first["view"]["intent_count"] == 1 and first["view"]["fill_count"] == 0
    assert first["view"]["nav"] == [] and first["view"]["cash"] == "10000"
    assert first["view"]["cash_weight"] == pytest.approx(
        sum(r["weight_forfeited"] for r in plan["allocation"]["skipped"])
    )
    later, next_prefix, next_plan = make_plan(facts, date(2026, 10, 9), reg)
    assert next_prefix.prefix_hash(now.date()) == prefix.prefix_hash(now.date())
    changed = deepcopy(next_prefix)
    changed.closes[0, 0] += 1
    assert changed.prefix_hash(now.date()) != prefix.prefix_hash(now.date())
    second_options = options | {
        "raw_opens": {"510001.SH": Decimal(10), "510002.SH": Decimal(10)},
        "raw_closes": {"510001.SH": Decimal(11), "510002.SH": Decimal(11)},
        "benchmark_close": 101.0,
    }
    second = cycle(
        root,
        release(),
        next_plan,
        now=later,
        snapshot_observed_at=later,
        factual_prefix_sha256=next_prefix.prefix_hash(later.date()),
        **second_options,
    )
    state = load_state(root)
    assert state and len(state["fills"]) == 2 and len(state["intents"]) == 1
    for fill in state["fills"]:
        assert Decimal(fill["intent"]["quantity"]) % 100 == 0
        assert Decimal(fill["price"]) == Decimal("10.005")
        assert Decimal(fill["commission"]) == Decimal(fill["price"]) * Decimal(
            fill["intent"]["quantity"]
        ) * Decimal(".0003")
        assert fill["economic_execution_at"].endswith("09:30:00+08:00")
        assert fill["accounted_at"] == later.isoformat()
    assert second["view"]["balance"] != "10000" and float(second["view"]["cash"]) >= 0
    assert second["view"]["benchmark"]["points"] == [{"date": "2026-10-09", "normalized_nav": 1.01}]
    repeated = cycle(
        root,
        release(),
        next_plan,
        now=later,
        snapshot_observed_at=later,
        factual_prefix_sha256=next_prefix.prefix_hash(later.date()),
        **second_options,
    )
    assert repeated["status"] == "ALREADY_PROCESSED" and repeated["view"]["signal_count"] == 2
    assert load_state(root) == state
    node = shutil.which("node")
    if node:
        repository = Path(__file__).resolve().parents[1]
        script = (
            "import {observeV2Current} from "
            + json.dumps((repository / "services/etf-quant-api/v2-current.mjs").as_uri())
            + "; const v=await observeV2Current({repoRoot:process.argv[1],runtimeRoot:process.argv[2]});process.stdout.write(JSON.stringify(v));"
        )
        observed = json.loads(
            subprocess.run(
                [node, "--input-type=module", "-e", script, str(repository), str(root)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        assert observed["fill_count"] == 2 and observed["signal_count"] == 2
        assert observed["nav"] == second["view"]["nav"]
        assert observed["balance"] == second["view"]["balance"]
        assert observed["final_oos"]["open_count"] == 1


def test_holiday_arming_is_empty_and_no_retroactive_epoch(tmp_path):
    calendar = (date(2026, 9, 30), date(2026, 10, 8), date(2026, 10, 9))
    available = datetime.fromisoformat(release()["available_at"])
    now = datetime(2026, 10, 4, 16, tzinfo=SHANGHAI)
    assert temporal_gate(now, calendar, date(2026, 9, 30), available) == "ARMED_NON_TRADING_DAY"
    view = public_view(None, release(), latest_data_date="2026-09-30", armed=True)
    assert (
        view["armed"]
        and view["epoch_count"]
        == view["signal_count"]
        == view["intent_count"]
        == view["fill_count"]
        == 0
    )
    assert view["nav"] == view["benchmark"]["points"] == []
    assert (
        temporal_gate(
            datetime(2026, 10, 8, 14, tzinfo=SHANGHAI), calendar, date(2026, 10, 8), available
        )
        == "ARMED_WAITING_FOR_MARKET_CLOSE"
    )

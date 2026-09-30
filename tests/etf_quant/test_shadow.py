from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd
import pytest

from strategies.etf_quant.domain import StrategyConfig
from strategies.etf_quant.mapping.registry import load_registry
from strategies.etf_quant.runtime import shadow
from strategies.etf_quant.runtime.storage import GateError, json_bytes, read_generation
from strategies.etf_quant.runtime.view import empty_view
from strategies.etf_quant.simulation.lots import affordable_units

from test_exports_industry import industry_provider, TZ
from test_registry_sidecar import registry_doc, provider as etf_provider


def inputs(tmp_path, end="2026-09-23", empty=False):
    p = industry_provider(500)
    p.tables["industry_membership"]["classification_system"] = "sw"
    days = tuple(d.date() for d in pd.bdate_range(end=end, periods=500))
    date_map = dict(zip(p.sessions, days))
    for name in ("stock_bars", "industry_membership"):
        field = "trade_date" if name == "stock_bars" else "as_of_date"
        p.tables[name][field] = p.tables[name][field].map(date_map)
    p.sessions = (*days, (pd.Timestamp(days[-1]) + pd.offsets.BDay()).date())
    p.cutoff = days[-1]
    p.created_at = datetime.combine(days[-1], datetime.min.time(), TZ).replace(hour=17)
    e = etf_provider()
    stock_instruments = p.tables["instruments"]
    p.tables.update(e.tables)
    p.tables["instruments"] = pd.concat([e.tables["instruments"], stock_instruments], ignore_index=True)
    p.tables["etf_bars"] = p.tables["etf_bars"].loc[p.tables["etf_bars"].trade_date <= p.cutoff].copy()
    p.tables["trading_status"] = p.tables["trading_status"].loc[p.tables["trading_status"].trade_date <= p.cutoff].copy()
    p.tables["trading_calendar"] = pd.DataFrame({"trade_date": p.sessions, "is_trading": True})
    p.tables["benchmark_csi300"] = pd.DataFrame({"trade_date": days, "symbol": "000300.SH", "close": 3000., "frequency": "1d"})
    p.manifest = {"snapshot_id": "a" * 64, "source_commit": "b" * 40,
                  "source_version": "SYNTHETIC", "adjustment_rejected_rows": 0}
    doc, evidence = registry_doc(tmp_path)
    if empty: doc["entries"] = []
    path = tmp_path / "registry.json"
    path.write_bytes(json_bytes(doc))
    return p, load_registry(path, evidence_root=evidence)


def advance(p):
    p = deepcopy(p)
    day = p.sessions[-1]
    old = p.tables["stock_bars"].loc[p.tables["stock_bars"].trade_date == p.cutoff].copy()
    old["trade_date"] = day
    old["adj_close"] *= 1.001
    p.tables["stock_bars"] = pd.concat([p.tables["stock_bars"], old], ignore_index=True)
    e = etf_provider()
    for name in ("etf_bars", "trading_status"):
        new = e.tables[name].loc[e.tables[name].trade_date == day]
        p.tables[name] = pd.concat([p.tables[name], new], ignore_index=True)
    p.tables["benchmark_csi300"] = pd.concat([p.tables["benchmark_csi300"],
        pd.DataFrame([{"trade_date": day, "symbol": "000300.SH", "close": 3010., "frequency": "1d"}])], ignore_index=True)
    p.cutoff = day
    p.sessions = (*p.sessions, (pd.Timestamp(day) + pd.offsets.BDay()).date())
    p.tables["trading_calendar"] = pd.DataFrame({"trade_date": p.sessions, "is_trading": True})
    p.created_at = datetime.combine(day, datetime.min.time(), TZ).replace(hour=17)
    p.manifest["snapshot_id"] = "c" * 64
    return p


def run(p, reg, root):
    return shadow.daily_cycle(p, reg, root, now=p.created_at + timedelta(hours=1), code_commit="d" * 40,
                              classification_version="SWCLASS2021")


def read(root):
    pointer = json.loads((root / "latest.json").read_bytes())
    manifest, files = read_generation(root / "runs", pointer)
    return json.loads(files["view.json"]), json.loads(files["state.json"])


def test_lot_floor_cash_and_minimum_fee():
    assert affordable_units(Decimal(10000), Decimal(3), StrategyConfig().costs) == 3300
    assert affordable_units(Decimal(1), Decimal(3), StrategyConfig().costs) == 0
    costs = replace(StrategyConfig().costs, minimum_commission="5")
    assert affordable_units(Decimal(304), Decimal(3), costs) == 0
    with pytest.raises(ValueError): affordable_units(Decimal(1000), Decimal(1), costs, 0)


def test_empty_mapping_no_epoch_fake_account_or_nav(tmp_path):
    p, reg = inputs(tmp_path, empty=True)
    root = tmp_path / "runtime"
    assert run(p, reg, root)["status"] == "MAPPING_ADMISSION_BLOCKED"
    view, state = read(root)
    assert view["status"]["epoch"] is state["portfolio"] is None
    assert view["portfolio_summary"]["total_equity"] is view["portfolio_summary"]["cash"] is None
    assert view["nav"] == view["holdings"] == view["trades"] == []
    assert len(view["models"]) == 3 and all(m["available_at"] is None for m in view["models"])


def test_forward_intent_delayed_t1_epoch_no_preepoch_nav_and_idempotency(tmp_path):
    p, reg = inputs(tmp_path)
    root = tmp_path / "runtime"
    assert run(p, reg, root)["status"] == "WAITING_FOR_T1_OPEN"
    view, state = read(root)
    assert view["status"]["epoch"] is None and state["pending"] is not None and view["nav"] == []
    q = advance(p)
    assert run(q, reg, root)["status"] == "RUNNING"
    view, state = read(root)
    assert len(view["nav"]) == 1 and len(view["holdings"]) == 5 and len(view["trades"]) == 5
    epoch = view["status"]["epoch"]
    assert view["nav"][0]["timestamp"] == epoch["started_at"]
    assert all(t["processed_at"] == epoch["started_at"] and t["market_execution_at"] < t["processed_at"] for t in view["trades"])
    assert all(Decimal(p["quantity"]) % 100 == 0 for p in view["holdings"])
    assert Decimal(view["portfolio_summary"]["cash"]) >= 0
    assert view["portfolio_summary"]["daily_return"] is None
    assert Decimal(view["portfolio_summary"]["total_pnl"]) == Decimal(view["portfolio_summary"]["total_equity"]) - 10000
    assert view["portfolio_summary"]["turnover"] > 0
    assert all(p["etf_name"] and p["industry_name"] and "unrealized_return" in p for p in view["holdings"])
    assert all(Decimal(t["total_cash_impact"]) < 0 and t["rebalance_reason"] == "INITIAL_BUILD" for t in view["trades"])
    pointer_before = (root / "latest.json").read_bytes()
    assert run(q, reg, root)["status"] == "IDEMPOTENT_NO_CHANGE"
    assert (root / "latest.json").read_bytes() == pointer_before
    assert state["pending"] is None  # same member set -> no weight-only rebalance
    assert view["benchmark"]["points"][0]["normalized"] == 1
    assert not view["status"]["validation_opened"] and not view["status"]["final_oos_read"]


@pytest.mark.parametrize("mutation,code", [
    (lambda q: q.tables["stock_bars"].loc.__setitem__((0, "adj_close"), 99.), "HISTORICAL_REVISION"),
    (lambda q: q.tables["instruments"].loc.__setitem__((0, "name"), "SYNTHETIC_CHANGED_LISTING_EVIDENCE"), "HISTORICAL_REVISION"),
    (lambda q: q.tables["etf_bars"].drop(q.tables["etf_bars"].index[q.tables["etf_bars"].trade_date == q.cutoff], inplace=True), "EXECUTION_BAR"),
])
def test_failed_run_preserves_latest_and_no_partial_state(tmp_path, mutation, code):
    p, reg = inputs(tmp_path)
    root = tmp_path / "runtime"
    run(p, reg, root)
    before = (root / "latest.json").read_bytes()
    q = advance(p)
    mutation(q)
    with pytest.raises(GateError, match=code): run(q, reg, root)
    assert (root / "latest.json").read_bytes() == before
    _, state = read(root)
    assert state["portfolio"] is None and state["trades"] == []
    pointer = json.loads((root / "last_attempt.json").read_bytes())
    failure_manifest, _ = read_generation(root / "failures", pointer)
    assert failure_manifest["status"] == "FAILED"


def test_atomic_failure_cannot_advance_pointer(tmp_path, monkeypatch):
    p, reg = inputs(tmp_path)
    root = tmp_path / "runtime"
    run(p, reg, root)
    before = (root / "latest.json").read_bytes()
    original = shadow.publish_generation
    def fail(root, *a, **kw):
        if root.name == "runs": raise GateError("SYNTHETIC_ATOMIC_FAILURE")
        return original(root, *a, **kw)
    monkeypatch.setattr(shadow, "publish_generation", fail)
    with pytest.raises(GateError, match="ATOMIC_FAILURE"): run(advance(p), reg, root)
    assert (root / "latest.json").read_bytes() == before


def test_lock_and_stale_session_fail_closed(tmp_path):
    p, reg = inputs(tmp_path)
    root = tmp_path / "runtime"
    root.mkdir()
    (root / ".cycle.lock").write_bytes(b"SYNTHETIC_OTHER_RUN")
    with pytest.raises(GateError, match="CONCURRENT"): run(p, reg, root)
    (root / ".cycle.lock").unlink()
    with pytest.raises(GateError, match="CURRENT_FINALIZED"):
        shadow.daily_cycle(p, reg, root, now=p.created_at + timedelta(days=1), code_commit="d" * 40)
    assert not (root / "latest.json").exists()


def test_no_runtime_default_fabricated_results():
    view = empty_view()
    assert view["portfolio_summary"]["sharpe"] is view["portfolio_summary"]["total_return"] is None
    assert view["benchmark"]["points"] == [] and view["benchmark"]["nasdaq"] == "DEFERRED"


def test_unknown_instrument_dates_are_null_not_fabricated_and_still_frozen(tmp_path):
    p, _ = inputs(tmp_path, empty=True)
    p.tables["instruments"].loc[0, "list_date"] = None
    prefix = shadow.source_prefix(p)
    symbol = p.tables["instruments"].iloc[0].symbol
    assert prefix["instruments"][symbol]["date"] is None
    shadow.check_prefix(prefix, shadow.source_prefix(p), str(p.cutoff))
    q = deepcopy(p)
    q.tables["instruments"].loc[0, "asset_type"] = "SYNTHETIC_CHANGED_TYPE"
    with pytest.raises(GateError, match="HISTORICAL_REVISION"):
        shadow.check_prefix(prefix, shadow.source_prefix(q), str(p.cutoff))

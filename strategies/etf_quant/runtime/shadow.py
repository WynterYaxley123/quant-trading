"""Manual forward Shadow cycle. No scheduler, broker, replay or Research reads."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, time
from decimal import Decimal
import json
import math
import os
from pathlib import Path
from uuid import uuid4

import numpy as np

from ..domain import PortfolioState, Position, StrategyConfig, TargetPosition, TradingCalendar
from ..mapping.registry import active, eligible_bar, select_mappings
from ..portfolio import RebalanceStatus, rebalance_decision, size_targets
from ..schemas import to_primitive
from ..simulation import mark_to_market, nav_point, new_portfolio
from ..simulation.lots import rebalance_at_open
from .exports import SHANGHAI, observed_time
from .industry import build_industry_series
from .prediction import current_predictions
from .storage import (GateError, atomic_bytes, contained, digest, external_root, json_bytes,
                      publish_generation, read_generation)
from .view import empty_view, public_strategy


@contextmanager
def runtime_lock(root):
    """No stale-lock stealing: ambiguous interrupted work requires review."""
    path = root / ".cycle.lock"
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise GateError("CONCURRENT_OR_INTERRUPTED_RUN_BLOCKER") from error
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(json_bytes({"pid": os.getpid()}))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        path.unlink(missing_ok=True)


def _portfolio(doc):
    if doc is None:
        return None
    if doc.get("mode") != "SIMULATION_ONLY" or doc.get("product") != "ETF_QUANT" or doc.get("initial_cash") != "10000":
        raise GateError("RUNTIME_PORTFOLIO_BLOCKER")
    return PortfolioState(as_of=observed_time(doc["as_of"]), cash=Decimal(doc["cash"]),
        initial_cash=Decimal(doc["initial_cash"]), realized_pnl=Decimal(doc["realized_pnl"]),
        positions=tuple(Position(p["asset_id"], Decimal(p["quantity"]), Decimal(p["average_cost"]), Decimal(p["mark_price"]))
                        for p in doc["positions"]), applied_fill_ids=tuple(doc["applied_fill_ids"]),
        executed_intent_ids=tuple(doc["executed_intent_ids"]))


def source_prefix(provider):
    result = {}
    from .exports import KEYS
    for name, frame in provider.tables.items():
        date_key = "as_of_date" if name == "industry_membership" else "trade_date"
        if date_key not in frame:
            continue
        records = {}
        for row in frame.to_dict("records"):
            if row[date_key] > provider.cutoff:
                continue
            key = "|".join(str(row[k]) for k in KEYS[name])
            # Observation time can advance on re-fetch; economic values/identity
            # may not silently change in a consumed historical prefix.
            economic = {k: str(v) for k, v in row.items() if k != "fetched_at"}
            records[key] = {"date": str(row[date_key]), "hash": digest(json_bytes(economic))}
        result[name] = records
    return result


def check_prefix(previous, current, cutoff):
    for name, records in previous.items():
        candidate = {k: v for k, v in current.get(name, {}).items() if v["date"] <= cutoff}
        if candidate != records:
            raise GateError("CONSUMED_EXPORT_HISTORICAL_REVISION_BLOCKER", {"dataset": name})


def portfolio_view(state, ledger):
    points = ledger["nav"]
    equity = state.total_equity
    value = to_primitive(state)
    last = ledger["last_rebalance_at"]
    peak, drawdown = 1., 0.
    for point in points:
        n = float(point["normalized_nav"])
        peak = max(peak, n)
        drawdown = max(drawdown, 1 - n / peak)
    # Sharpe uses only forward epoch daily observations; never fabricate
    # pre-epoch NAV=1 to inflate sample length.
    rets = np.diff([float(p["normalized_nav"]) for p in points]) / np.asarray([float(p["normalized_nav"]) for p in points[:-1]])
    sharpe = float(rets.mean() / rets.std(ddof=1) * math.sqrt(252)) if len(rets) >= 2 and rets.std(ddof=1) > 0 else None
    summary = {"status": "RUNNING", "cash": value["cash"], "market_value": str(state.market_value),
        "total_equity": str(equity), "initial_cash": "10000", "realized_pnl": value["realized_pnl"],
        "unrealized_pnl": str(state.unrealized_pnl), "total_return": float(equity / state.initial_cash - 1),
        "max_drawdown": drawdown, "sharpe": sharpe, "rebalance_count": ledger["rebalance_count"], "last_rebalance_at": last}
    holdings = [{**p, "market_value": str(Decimal(p["quantity"]) * Decimal(p["mark_price"])),
        "weight": float(Decimal(p["quantity"]) * Decimal(p["mark_price"]) / equity),
        "unrealized_pnl": str((Decimal(p["mark_price"]) - Decimal(p["average_cost"])) * Decimal(p["quantity"]))}
                for p in value["positions"]]
    return summary, holdings


def daily_cycle(provider, registry, runtime_root: Path, *, now: datetime, code_commit: str,
                config=None, lot_size=100, min_constituents=5, coverage_threshold=.8,
                classification_version=None):
    """All computation uses one verified export. T0 intent survives until T+1.

    Authorized delayed EOD accounting: a prior persisted T0 intent is priced at
    finalized T+1 OPEN, but fill.executed_at and epoch.started_at are the actual
    processing time. market_execution_at is disclosed separately. No epoch NAV
    precedes the actual start. A missed T+1 is blocked, never replayed later.
    """
    config = StrategyConfig() if config is None else config
    root = external_root(runtime_root)
    if not isinstance(code_commit, str) or len(code_commit) != 40 or any(c not in "0123456789abcdef" for c in code_commit):
        raise GateError("IMPLEMENTATION_COMMIT_REQUIRED")
    run_id = now.strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex[:12]
    with runtime_lock(root):
        try:
            return _daily(provider, registry, root, now, code_commit, run_id, config, lot_size,
                          min_constituents, coverage_threshold, classification_version)
        except Exception as error:
            code = error.code if isinstance(error, GateError) else "RUNTIME_CYCLE_BLOCKER"
            failure = {"schema_version": "1.0.0", "run_id": run_id, "status": "FAILED", "blocker": code,
                "processed_at": now.isoformat(), "exception_class": type(error).__name__,
                "validation_opened": False, "final_oos_read": False}
            # Keep latest successful pointer/state untouched, disclose failure separately.
            failure_pointer = publish_generation(root / "failures", run_id, {"failure.json": json_bytes(failure)},
                {"status": "FAILED", "created_at": now.isoformat()})
            atomic_bytes(root / "last_attempt.json", json_bytes(failure_pointer))
            if isinstance(error, GateError):
                raise
            raise GateError(code) from error


def _daily(provider, registry, root, now, code_commit, run_id, config, lot_size, minimum, coverage, classification):
    local_now = now.astimezone(SHANGHAI)
    if (now < provider.created_at or provider.cutoff != local_now.date() or local_now.time() < time(15, 5)):
        raise GateError("CURRENT_FINALIZED_SESSION_REQUIRED")
    strategy = {**public_strategy(config, lot_size=lot_size), "minimum_constituents": minimum,
                "coverage_threshold": coverage, "classification_version": classification}
    strategy_hash = digest(json_bytes(strategy))
    previous, ledger, portfolio, parent_pointer = None, None, None, None
    latest = root / "latest.json"
    prefix = source_prefix(provider)
    if latest.exists():
        parent_pointer = json.loads(latest.read_bytes())
        m, bodies = read_generation(root / "runs", parent_pointer)
        previous = json.loads(bodies["view.json"])
        ledger = json.loads(bodies["state.json"])
        previous_prefix = json.loads(bodies["prefix.json"])
        if (m["mapping_hash"] != registry.sha256 or m["strategy_hash"] != strategy_hash
                or m["source_commit"] != provider.manifest["source_commit"]):
            raise GateError("RUNTIME_CONFIG_OR_SOURCE_DRIFT_BLOCKER")
        check_prefix(previous_prefix, prefix, previous["status"]["cutoff"])
        if previous["status"]["cutoff"] > str(provider.cutoff):
            raise GateError("RUNTIME_TIME_REVERSAL_BLOCKER")
        if previous["status"]["cutoff"] == str(provider.cutoff):
            return {"status": "IDEMPOTENT_NO_CHANGE", "run_id": m["run_id"], "snapshot_id": m["snapshot_id"]}
        portfolio = _portfolio(ledger["portfolio"])
    if ledger is None:
        ledger = {"portfolio": None, "epoch": None, "members": [], "pending": None, "nav": [], "trades": [],
                  "benchmark": [], "benchmark_base": None, "rebalance_count": 0, "last_rebalance_at": None}
    view = empty_view(config=config)
    view["strategy"] = strategy
    # Build current series/model FIRST, but an earlier committed intent's
    # targets/weights NEVER use these current predictions.
    series = build_industry_series(provider, min_constituents=minimum, coverage_threshold=coverage,
                                   classification_version=classification)
    models, predictions, fused = current_predictions(series, provider, signal_at=now, config=config)
    selected = select_mappings(registry, fused.rankings, provider, signal_at=now)
    pending = ledger["pending"]
    if pending is not None:
        if (pending["execution_date"] != str(provider.cutoff) or observed_time(pending["persisted_at"]) >= provider.created_at
                or pending["mapping_hash"] != registry.sha256 or pending["strategy_hash"] != strategy_hash):
            raise GateError("PERSISTED_T0_INTENT_INTEGRITY_BLOCKER")
        opens = {}
        for asset in set(pending["members"]) | ({p.asset_id for p in portfolio.positions} if portfolio else set()):
            bar, why = eligible_bar(provider, asset, provider.cutoff)
            if bar is None:
                raise GateError("T1_EXECUTION_BAR_BLOCKER", {"reason": why})
            opens[asset] = Decimal(str(bar["open"]))
        for entry in pending["mapping_entries"]:
            actual = next((r for r in registry.entries if r["industry_code"] == entry["industry_code"]
                           and r["etf_code"] == entry["etf_code"]), None)
            if actual is None or not active(actual, provider.cutoff, observed_time(pending["persisted_at"])):
                raise GateError("T1_MAPPING_CONTINUITY_BLOCKER")
        if portfolio is None:
            portfolio = new_portfolio(now, config)
            ledger["epoch"] = {"epoch_id": "EPOCH_" + run_id, "started_at": now.isoformat(),
                "market_cutoff": str(provider.cutoff), "provider_snapshot_id": provider.manifest["snapshot_id"],
                "mapping_hash": registry.sha256, "strategy_config_hash": strategy_hash, "initial_cash": "10000",
                "code_commit": code_commit, "bookkeeping": "DELAYED_EOD_ACTUAL_PROCESSED_AT"}
        targets = tuple(TargetPosition(r["asset_id"], r["target_weight"]) for r in pending["targets"])
        from datetime import date
        portfolio, fills = rebalance_at_open(portfolio, targets, opens, signal_day=date.fromisoformat(pending["signal_date"]),
            execution_day=provider.cutoff, processed_at=now, calendar=TradingCalendar(provider.sessions),
            batch_id=pending["intent_id"], config=config, lot_size=lot_size)
        market_open = datetime.combine(provider.cutoff, time(9, 30), SHANGHAI).isoformat()
        ledger["trades"].extend({**to_primitive(f), "processed_at": now.isoformat(), "market_execution_at": market_open,
            "execution_price_source": "FINALIZED_T1_RAW_OPEN", "accounting_mode": "AUTHORIZED_DELAYED_EOD",
            "intent_persisted_at": pending["persisted_at"], "provider_snapshot_id": provider.manifest["snapshot_id"]} for f in fills)
        ledger["members"] = pending["members"]
        ledger["rebalance_count"] += 1
        ledger["last_rebalance_at"] = now.isoformat()
        ledger["pending"] = None
    if portfolio is not None:
        marks = {}
        for p in portfolio.positions:
            bar, why = eligible_bar(provider, p.asset_id, provider.cutoff)
            if bar is None:
                raise GateError("EOD_MARK_BLOCKER", {"reason": why})
            marks[p.asset_id] = Decimal(str(bar["close"]))
        portfolio = mark_to_market(portfolio, marks, as_of=now)
        ledger["portfolio"] = to_primitive(portfolio)
        point = to_primitive(nav_point(portfolio))
        point.update(trade_date=str(provider.cutoff), processed_at=now.isoformat())
        if now < observed_time(ledger["epoch"]["started_at"]):
            raise GateError("PRE_EPOCH_NAV_PROHIBITED")
        ledger["nav"].append(point)
        benchmark = provider.tables["benchmark_csi300"]
        today = benchmark.loc[benchmark.trade_date == provider.cutoff]
        if len(today) != 1:
            raise GateError("CSI300_EOD_COVERAGE_BLOCKER")
        close = float(today.iloc[0].close)
        if ledger["benchmark_base"] is None:
            ledger["benchmark_base"] = close
        ledger["benchmark"].append({"trade_date": str(provider.cutoff), "normalized": close / ledger["benchmark_base"],
            "close": close, "snapshot_id": provider.manifest["snapshot_id"]})
        view["portfolio_summary"], view["holdings"] = portfolio_view(portfolio, ledger)
        view["nav"], view["trades"] = ledger["nav"], ledger["trades"]
        view["benchmark"].update(status="RUNNING", points=ledger["benchmark"])
    if selected["status"] == "READY":
        current = [r["etf_code"] for r in selected["selected"]]
        if rebalance_decision(ledger["members"], current) is RebalanceStatus.REQUIRED:
            allocation = size_targets({r["etf_code"]: r["score"] for r in selected["selected"]})
            if not allocation.targets:
                raise GateError("ALLOCATION_CAPACITY_BLOCKER")
            ledger["pending"] = {"intent_id": "INTENT_" + run_id, "persisted_at": now.isoformat(),
                "signal_date": str(provider.cutoff), "execution_date": str(selected["execution_date"]), "members": current,
                "targets": to_primitive(allocation.targets), "mapping_entries": to_primitive(selected["selected"]),
                "strategy_hash": strategy_hash, "mapping_hash": registry.sha256,
                "signal_snapshot_id": provider.manifest["snapshot_id"]}
    phase = "RUNNING" if portfolio else "WAITING_FOR_T1_OPEN" if ledger["pending"] else "MAPPING_ADMISSION_BLOCKED"
    view["status"].update(phase=phase, reason=None if portfolio else phase, snapshot_id=provider.manifest["snapshot_id"],
        source_commit=provider.manifest["source_commit"], source_version=provider.manifest["source_version"], code_commit=code_commit,
        cutoff=str(provider.cutoff), updated_at=now.isoformat(), signal_date=str(provider.cutoff),
        execution_date=ledger["pending"]["execution_date"] if ledger["pending"] else None, epoch=ledger["epoch"],
        mapping_hash=registry.sha256, strategy_hash=strategy_hash)
    view["mappings"] = {"status": selected["status"], "reason": selected["reason"],
        "entries": to_primitive(selected["selected"]), "diagnostics": selected["diagnostics"]}
    for h, model in models.items():
        view["models"].append({"horizon": int(h), "factor_names": list(model.spec.factor_names), "alpha": .01,
            "coefficients": list(model.coefficients), "intercept": model.intercept,
            "training": to_primitive(model.training), "current_snapshot_observed_at": provider.created_at.isoformat(),
            "available_at": None, "source_published_at": None, "quality_flag": series.quality_flag,
            "model_hash": digest(json_bytes(to_primitive(model)))})
        view["rankings"][str(int(h)) + "d"] = [{"rank": i + 1, "industry_code": p.industry_code, "score": p.prediction}
            for i, p in enumerate(sorted(predictions[h], key=lambda p: (-p.prediction, p.industry_code)))]
    view["rankings"]["fusion"] = to_primitive(fused.rankings)
    latest_audit = [r for r in series.audit if r["trade_date"] == str(provider.cutoff)]
    view["health"].update(status=phase, blockers=[] if portfolio else [phase],
        adjustment_exact_rows=int(provider.tables["stock_bars"].adj_is_exact.sum()), adjustment_rejected_rows=0,
        coverage=latest_audit, source_snapshot=provider.manifest["snapshot_id"], source_schema="1.0.0")
    view["portfolio_summary"]["status"] = phase if portfolio is None else "RUNNING"
    manifest = {"status": "SUCCESSFUL_OBSERVATION", "phase": phase, "snapshot_id": provider.manifest["snapshot_id"],
        "mapping_hash": registry.sha256, "strategy_hash": strategy_hash, "source_commit": provider.manifest["source_commit"],
        "code_commit": code_commit, "parent_run": parent_pointer, "created_at": now.isoformat(),
        "validation_opened": False, "final_oos_read": False}
    pointer = publish_generation(root / "runs", run_id,
        {"view.json": json_bytes(view), "state.json": json_bytes(ledger), "prefix.json": json_bytes(prefix)}, manifest)
    atomic_bytes(latest, json_bytes(pointer))
    return {"status": phase, **pointer, "snapshot_id": provider.manifest["snapshot_id"], "epoch": ledger["epoch"]}

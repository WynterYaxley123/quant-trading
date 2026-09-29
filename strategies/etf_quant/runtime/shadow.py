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

from ..domain import PortfolioState, Position, StrategyConfig, TargetPosition, TradingCalendar, decimal_math
from ..mapping.registry import active, eligible_bar, select_mappings
from ..mapping.pit import PITEvidenceBook, select_pit_mappings
from ..portfolio import RebalanceStatus, rebalance_decision, size_targets
from ..portfolio.partial import rebalance_decision_v2
from ..portfolio.policy import POLICY_B40_WITH_CASH, REBALANCE_TRIGGER
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
        date_key = "list_date" if name == "instruments" else "as_of_date" if name == "industry_membership" else "trade_date"
        if date_key not in frame:
            continue
        records = {}
        for row in frame.to_dict("records"):
            # Undated instrument evidence is not allowed to silently change
            # after it influenced listing/tradability admission. Future known
            # listings are not part of the already-consumed historical prefix.
            row_day = row[date_key]
            if row_day is not None and row_day > provider.cutoff:
                continue
            key = "|".join(str(row[k]) for k in KEYS[name])
            # Observation time can advance on re-fetch; economic values/identity
            # may not silently change in a consumed historical prefix.
            economic = {k: str(v) for k, v in row.items() if k != "fetched_at"}
            records[key] = {"date": str(row_day) if row_day is not None else None, "hash": digest(json_bytes(economic))}
        result[name] = records
    return result


def check_prefix(previous, current, cutoff, *, previous_decision_at=None):
    for name, records in previous.items():
        if name in ("execution_evidence", "strict_mapping"):
            if previous_decision_at is None:
                raise GateError("PIT_PREFIX_TIME_BLOCKER")
            candidate = {k: v for k, v in current.get(name, {}).items()
                         if observed_time(v["available_at"]) <= observed_time(previous_decision_at)}
        else:
            candidate = {k: v for k, v in current.get(name, {}).items() if v["date"] is None or v["date"] <= cutoff}
        if candidate != records:
            raise GateError("CONSUMED_EXPORT_HISTORICAL_REVISION_BLOCKER", {"dataset": name})


def _registry_prefix(registry, decision_at):
    return {"|".join((row["industry_code"], row["etf_code"], str(row["effective_from"]))):
        {"date": str(row["available_at"].date()), "available_at": row["available_at"].isoformat(),
         "hash": digest(json_bytes(to_primitive(row)))} for row in registry.entries
         if row["verification_status"] == "VERIFIED" and row["available_at"] <= decision_at}


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
        "max_drawdown": drawdown, "sharpe": sharpe, "rebalance_count": ledger["rebalance_count"], "last_rebalance_at": last,
        "total_pnl": str(equity - state.initial_cash),
        "daily_return": float(rets[-1]) if len(rets) else None,
        "turnover": float(Decimal(ledger["turnover_notional"]) / state.initial_cash),
        "turnover_definition": "CUMULATIVE_ABSOLUTE_SLIPPED_NOTIONAL_DIVIDED_BY_INITIAL_CASH"}
    holdings = [{**p, "market_value": str(Decimal(p["quantity"]) * Decimal(p["mark_price"])),
        "weight": float(Decimal(p["quantity"]) * Decimal(p["mark_price"]) / equity),
        "unrealized_pnl": str((Decimal(p["mark_price"]) - Decimal(p["average_cost"])) * Decimal(p["quantity"])),
        "unrealized_return": float(Decimal(p["mark_price"]) / Decimal(p["average_cost"]) - 1),
        **ledger["holding_metadata"][p["asset_id"]]}
                for p in value["positions"]]
    return summary, holdings


def _slot_transitions(previous, current):
    """Audit ETF/Cash slot changes; the rebalance trigger remains ETF SET only."""
    old = {row["industry_code"]: row for row in previous}
    new = {row["industry_code"]: row for row in current}
    changes = []
    for code in sorted(set(old) | set(new)):
        before, after = old.get(code), new.get(code)
        before_etf = before.get("etf_code") if before else None
        after_etf = after.get("etf_code") if after else None
        if before_etf == after_etf:
            reason = "NO_CHANGE"
        elif before is None or after is None:
            reason = "SIGNAL_MEMBER_CHANGED"
        elif before_etf is None:
            reason = "MAPPING_BECAME_AVAILABLE"
        elif after_etf is None:
            reason = "LIQUIDITY_OR_EVIDENCE_FAILED"
        elif before.get("mapping_type") == "PROXY_EXPOSURE" and after.get("mapping_type") == "STRICT_MAPPING":
            reason = "STRICT_SUPERSEDED_PROXY"
        elif before.get("mapping_type") == "STRICT_MAPPING" and after.get("mapping_type") == "PROXY_EXPOSURE":
            reason = "STRICT_EXPIRED_PROXY_ADMITTED"
        else:
            reason = "PROXY_OR_INSTRUMENT_REPLACED"
        changes.append({"industry_code": code, "previous_state": before.get("mapping_type") if before else None,
            "current_state": after.get("mapping_type") if after else None,
            "previous_etf": before_etf, "current_etf": after_etf, "reason": reason})
    return changes


def daily_cycle(provider, registry, runtime_root: Path, *, now: datetime, code_commit: str,
                config=None, lot_size=100, min_constituents=5, coverage_threshold=.8,
                classification_version=None, execution_policy="STRICT_TOP5", pit_evidence: PITEvidenceBook | None = None):
    """All computation uses one verified export. T0 intent survives until T+1.

    Authorized delayed EOD accounting: a prior persisted T0 intent is priced at
    finalized T+1 OPEN, but fill.executed_at and epoch.started_at are the actual
    processing time. market_execution_at is disclosed separately. No epoch NAV
    precedes the actual start. A missed T+1 is blocked, never replayed later.
    """
    config = StrategyConfig() if config is None else config
    if execution_policy not in ("STRICT_TOP5", POLICY_B40_WITH_CASH):
        raise GateError("UNKNOWN_EXECUTION_POLICY_BLOCKER")
    if execution_policy == POLICY_B40_WITH_CASH and not isinstance(pit_evidence, PITEvidenceBook):
        raise GateError("EXPLICIT_PIT_EVIDENCE_REQUIRED")
    if execution_policy == "STRICT_TOP5" and pit_evidence is not None:
        raise GateError("STRICT_PATH_PIT_EVIDENCE_FORBIDDEN")
    root = external_root(runtime_root)
    if not isinstance(code_commit, str) or len(code_commit) != 40 or any(c not in "0123456789abcdef" for c in code_commit):
        raise GateError("IMPLEMENTATION_COMMIT_REQUIRED")
    run_id = now.strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex[:12]
    with runtime_lock(root):
        try:
            with decimal_math():
                return _daily(provider, registry, root, now, code_commit, run_id, config, lot_size,
                              min_constituents, coverage_threshold, classification_version,
                              execution_policy, pit_evidence)
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


def _daily(provider, registry, root, now, code_commit, run_id, config, lot_size, minimum, coverage, classification,
           execution_policy, pit_evidence):
    local_now = now.astimezone(SHANGHAI)
    if (now < provider.created_at or provider.cutoff != local_now.date() or local_now.time() < time(15, 5)):
        raise GateError("CURRENT_FINALIZED_SESSION_REQUIRED")
    strategy = {**public_strategy(config, lot_size=lot_size), "minimum_constituents": minimum,
                "coverage_threshold": coverage, "classification_version": classification}
    if execution_policy == POLICY_B40_WITH_CASH:
        strategy.update(execution_policy=execution_policy, rebalance=REBALANCE_TRIGGER,
                        cash_semantics="UNALLOCATED_EXECUTION_CAPACITY")
    strategy_hash = digest(json_bytes(strategy))
    mapping_hash = (registry.sha256 if execution_policy == "STRICT_TOP5" else digest(json_bytes({
        "execution_policy": execution_policy, "registry_identity": registry.identity,
        "taxonomy_sha256": registry.taxonomy_sha256})))
    previous, ledger, portfolio, parent_pointer = None, None, None, None
    latest = root / "latest.json"
    prefix = source_prefix(provider)
    if execution_policy == POLICY_B40_WITH_CASH:
        prefix["execution_evidence"] = pit_evidence.prefix(now)
        prefix["strict_mapping"] = _registry_prefix(registry, now)
    if latest.exists():
        parent_pointer = json.loads(latest.read_bytes())
        m, bodies = read_generation(root / "runs", parent_pointer)
        previous = json.loads(bodies["view.json"])
        ledger = json.loads(bodies["state.json"])
        previous_prefix = json.loads(bodies["prefix.json"])
        if (m["mapping_hash"] != mapping_hash or m["strategy_hash"] != strategy_hash
                or m["source_commit"] != provider.manifest["source_commit"]):
            raise GateError("RUNTIME_CONFIG_OR_SOURCE_DRIFT_BLOCKER")
        check_prefix(previous_prefix, prefix, previous["status"]["cutoff"],
                     previous_decision_at=previous["status"]["updated_at"])
        if previous["status"]["cutoff"] > str(provider.cutoff):
            raise GateError("RUNTIME_TIME_REVERSAL_BLOCKER")
        if previous["status"]["cutoff"] == str(provider.cutoff):
            return {"status": "IDEMPOTENT_NO_CHANGE", "run_id": m["run_id"], "snapshot_id": m["snapshot_id"]}
        portfolio = _portfolio(ledger["portfolio"])
    if ledger is None:
        ledger = {"portfolio": None, "epoch": None, "members": [], "pending": None, "nav": [], "trades": [],
                  "benchmark": [], "benchmark_base": None, "rebalance_count": 0, "last_rebalance_at": None,
                  "holding_metadata": {}, "turnover_notional": "0"}
    view = empty_view(config=config)
    view["strategy"] = strategy
    # Build current series/model FIRST, but an earlier committed intent's
    # targets/weights NEVER use these current predictions.
    series = build_industry_series(provider, min_constituents=minimum, coverage_threshold=coverage,
                                   classification_version=classification)
    models, predictions, fused = current_predictions(series, provider, signal_at=now, config=config)
    selected = (select_mappings(registry, fused.rankings, provider, signal_at=now)
                if execution_policy == "STRICT_TOP5" else
                select_pit_mappings(registry, fused.rankings, provider, pit_evidence, signal_at=now))
    pending = ledger["pending"]
    if pending is not None:
        if (pending["execution_date"] != str(provider.cutoff) or observed_time(pending["persisted_at"]) >= provider.created_at
                or pending["mapping_hash"] != mapping_hash or pending["strategy_hash"] != strategy_hash
                or pending.get("execution_policy", "STRICT_TOP5") != execution_policy):
            raise GateError("PERSISTED_T0_INTENT_INTEGRITY_BLOCKER")
        opens = {}
        for asset in set(pending["members"]) | ({p.asset_id for p in portfolio.positions} if portfolio else set()):
            bar, why = eligible_bar(provider, asset, provider.cutoff)
            if bar is None:
                raise GateError("T1_EXECUTION_BAR_BLOCKER", {"reason": why})
            opens[asset] = Decimal(str(bar["open"]))
        for entry in pending["mapping_entries"]:
            if execution_policy == POLICY_B40_WITH_CASH and entry["mapping_type"] == "PROXY_EXPOSURE":
                actual = next((r for r in pit_evidence.records if r.industry_code == entry["industry_code"]
                    and r.etf_code == entry["etf_code"] and r.evidence_hash == entry["evidence_hash"]), None)
                if (actual is None or actual.available_at > observed_time(pending["persisted_at"])
                        or actual.valid_through < provider.cutoff):
                    raise GateError("T1_MAPPING_CONTINUITY_BLOCKER")
            else:
                actual = next((r for r in registry.entries if r["industry_code"] == entry["industry_code"]
                               and r["etf_code"] == entry["etf_code"]), None)
                if actual is None or not active(actual, provider.cutoff, observed_time(pending["persisted_at"])):
                    raise GateError("T1_MAPPING_CONTINUITY_BLOCKER")
        if portfolio is None:
            portfolio = new_portfolio(now, config)
            ledger["epoch"] = {"epoch_id": "EPOCH_" + run_id, "started_at": now.isoformat(),
                "market_cutoff": str(provider.cutoff), "provider_snapshot_id": provider.manifest["snapshot_id"],
                "mapping_hash": mapping_hash, "strategy_config_hash": strategy_hash, "initial_cash": "10000",
                "code_commit": code_commit, "bookkeeping": "DELAYED_EOD_ACTUAL_PROCESSED_AT"}
        targets = tuple(TargetPosition(r["asset_id"], r["target_weight"]) for r in pending["targets"])
        from datetime import date
        portfolio, fills = rebalance_at_open(portfolio, targets, opens, signal_day=date.fromisoformat(pending["signal_date"]),
            execution_day=provider.cutoff, processed_at=now, calendar=TradingCalendar(provider.sessions),
            batch_id=pending["intent_id"], config=config, lot_size=lot_size)
        market_open = datetime.combine(provider.cutoff, time(9, 30), SHANGHAI).isoformat()
        ledger["trades"].extend({**to_primitive(f), "processed_at": now.isoformat(), "market_execution_at": market_open,
            "execution_price_source": "FINALIZED_T1_RAW_OPEN", "accounting_mode": "AUTHORIZED_DELAYED_EOD",
            "intent_persisted_at": pending["persisted_at"], "provider_snapshot_id": provider.manifest["snapshot_id"],
            "total_cash_impact": str((-1 if f.intent.side.value == "BUY" else 1) * f.price * f.intent.quantity
                                      - f.commission - f.stamp_duty),
            "rebalance_reason": "INITIAL_BUILD" if not ledger["members"] else "EXECUTABLE_ETF_SET_CHANGED",
            **({"accounting_mode": "DELAYED_T1_OPEN_ACCOUNTING", "execution_evidence": "NOT_REALTIME_EXECUTION_EVIDENCE",
                "economic_execution_at": market_open, "evidence_available_at": provider.created_at.isoformat()}
               if execution_policy == POLICY_B40_WITH_CASH else {})} for f in fills)
        ledger["turnover_notional"] = str(Decimal(ledger["turnover_notional"]) +
            sum((f.price * f.intent.quantity for f in fills), Decimal(0)))
        ledger["holding_metadata"].update({r["etf_code"]: {k: r[k] for k in ("etf_name", "industry_code", "industry_name")}
                                         for r in pending["mapping_entries"]})
        ledger["members"] = pending["members"]
        if execution_policy == POLICY_B40_WITH_CASH:
            ledger["execution_slots"] = pending["slots"]
            ledger.setdefault("rebalance_events", []).append({"signal_date": pending["signal_date"],
                "processed_at": now.isoformat(), "previous_members": pending["previous_members"],
                "current_members": pending["members"], "transitions": pending["transitions"],
                "cash_target_weight": pending["cash_target_weight"]})
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
        if execution_policy == "STRICT_TOP5":
            changed = rebalance_decision(ledger["members"], current) is RebalanceStatus.REQUIRED
            if changed:
                allocation = size_targets({r["etf_code"]: r["score"] for r in selected["selected"]})
                if not allocation.targets:
                    raise GateError("ALLOCATION_CAPACITY_BLOCKER")
                ledger["pending"] = {"intent_id": "INTENT_" + run_id, "persisted_at": now.isoformat(),
                    "signal_date": str(provider.cutoff), "execution_date": str(selected["execution_date"]), "members": current,
                    "targets": to_primitive(allocation.targets), "mapping_entries": to_primitive(selected["selected"]),
                    "strategy_hash": strategy_hash, "mapping_hash": mapping_hash,
                    "signal_snapshot_id": provider.manifest["snapshot_id"]}
        else:
            allocation = size_targets({r["industry_code"]: r["score"] for r in selected["slots"]})
            if allocation.status.value != "READY":
                raise GateError("ALLOCATION_CAPACITY_BLOCKER")
            weights = {r.asset_id: r.target_weight for r in allocation.targets}
            slots = [{**r, "target_weight": weights[r["industry_code"]],
                      "cash_retained_weight": weights[r["industry_code"]] if r["etf_code"] is None else 0.0}
                     for r in selected["slots"]]
            cash_weight = sum(r["cash_retained_weight"] for r in slots)
            risk_weight = sum(weights[r["industry_code"]] for r in slots if r["etf_code"])
            if abs(cash_weight + risk_weight - 1) > 1e-9:
                raise GateError("CASH_ACCOUNTING_CONSERVATION_BLOCKER")
            selected["slots"] = slots
            selected["cash_weight"] = cash_weight
            selected["risk_asset_weight"] = risk_weight
            changed = rebalance_decision_v2(ledger["members"], current, execution_policy=execution_policy) is RebalanceStatus.REQUIRED
            previous_slots = ledger.get("execution_slots", [])
            transitions = _slot_transitions(previous_slots, slots)
            ledger["last_signal_slots"] = slots
            ledger["last_signal_date"] = str(provider.cutoff)
            if changed:
                targets = [TargetPosition(r["etf_code"], weights[r["industry_code"]]) for r in slots if r["etf_code"]]
                ledger["pending"] = {"intent_id": "INTENT_" + run_id, "persisted_at": now.isoformat(),
                    "signal_date": str(provider.cutoff), "execution_date": str(selected["execution_date"]), "members": current,
                    "previous_members": list(ledger["members"]), "targets": to_primitive(targets),
                    "mapping_entries": to_primitive(selected["selected"]), "slots": to_primitive(slots),
                    "cash_target_weight": cash_weight, "transitions": transitions,
                    "execution_policy": execution_policy, "strategy_hash": strategy_hash,
                    "mapping_hash": mapping_hash, "signal_snapshot_id": provider.manifest["snapshot_id"]}
    phase = "RUNNING" if portfolio else "WAITING_FOR_T1_OPEN" if ledger["pending"] else (
        "CASH_ONLY_NO_EPOCH" if execution_policy == POLICY_B40_WITH_CASH and selected["status"] == "READY"
        else "MAPPING_ADMISSION_BLOCKED")
    view["status"].update(phase=phase, reason=None if portfolio else phase, snapshot_id=provider.manifest["snapshot_id"],
        source_commit=provider.manifest["source_commit"], source_version=provider.manifest["source_version"], code_commit=code_commit,
        cutoff=str(provider.cutoff), updated_at=now.isoformat(), signal_date=str(provider.cutoff),
        execution_date=ledger["pending"]["execution_date"] if ledger["pending"] else None, epoch=ledger["epoch"],
        mapping_hash=mapping_hash, strategy_hash=strategy_hash,
        industry_level=selected["industry_level"])
    view["mappings"] = {"status": selected["status"], "reason": selected["reason"],
        "entries": to_primitive(selected["selected"]), "diagnostics": selected["diagnostics"],
        "industry_level": selected["industry_level"], "liquidity_sessions": selected["liquidity_sessions"],
        "liquidity_window": selected.get("liquidity_window", []),
        "taxonomy_identity": selected.get("taxonomy_identity")}
    if execution_policy == POLICY_B40_WITH_CASH:
        view["status"]["execution_policy"] = execution_policy
        view["mappings"].update(slots=selected["slots"], cash_weight=selected["cash_weight"],
            risk_asset_weight=selected["risk_asset_weight"], evidence_book_hash=selected["evidence_book_hash"])
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
        adjustment_exact_rows=int(provider.tables["stock_bars"].adj_is_exact.sum()),
        adjustment_rejected_rows=provider.manifest["adjustment_rejected_rows"],
        coverage=latest_audit, source_snapshot=provider.manifest["snapshot_id"], source_schema="1.0.0")
    view["portfolio_summary"]["status"] = phase if portfolio is None else "RUNNING"
    manifest = {"status": "SUCCESSFUL_OBSERVATION", "phase": phase, "snapshot_id": provider.manifest["snapshot_id"],
        "mapping_hash": mapping_hash, "strategy_hash": strategy_hash, "source_commit": provider.manifest["source_commit"],
        "code_commit": code_commit, "parent_run": parent_pointer, "created_at": now.isoformat(),
        "validation_opened": False, "final_oos_read": False}
    pointer = publish_generation(root / "runs", run_id,
        {"view.json": json_bytes(view), "state.json": json_bytes(ledger), "prefix.json": json_bytes(prefix)}, manifest)
    atomic_bytes(latest, json_bytes(pointer))
    return {"status": phase, **pointer, "snapshot_id": provider.manifest["snapshot_id"], "epoch": ledger["epoch"]}

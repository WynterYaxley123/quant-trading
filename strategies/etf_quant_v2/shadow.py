"""Formal V2 target intents and delayed paper ledger, using frozen V1 primitives."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from strategies.etf_quant.domain import PortfolioState, Position, TargetPosition, TradingCalendar
from strategies.etf_quant.portfolio import RebalanceStatus
from strategies.etf_quant.portfolio.partial import rebalance_decision_v2
from strategies.etf_quant.runtime.recovery import abandon_missed_t1
from strategies.etf_quant.runtime.storage import (
    account_lock,
    contained,
    external_root,
    json_bytes,
    publish_account_generation,
    read_generation,
)
from strategies.etf_quant.schemas import to_primitive
from strategies.etf_quant.simulation import mark_to_market, new_portfolio
from strategies.etf_quant.simulation.lots import rebalance_at_open

from .runtime import SHANGHAI, content_hash


def load_state(root: Path) -> dict[str, Any] | None:
    if not (root / "latest.json").exists():
        return None
    if contained(root, "latest.json").stat().st_size > 4096:
        raise ValueError("V2_RUNTIME_SIZE_LIMIT")
    pointer = json.loads(contained(root, "latest.json").read_bytes())
    run_id = pointer.get("run_id")
    if (
        not isinstance(run_id, str)
        or not run_id.replace("_", "").replace("-", "").isalnum()
        or len(run_id) > 96
    ):
        raise ValueError("V2_RUNTIME_POINTER_ERROR")
    for name in ("manifest.json", "state.json", "view.json"):
        if contained(root, "runs/" + run_id + "/" + name).stat().st_size > 4 * 1024 * 1024:
            raise ValueError("V2_RUNTIME_SIZE_LIMIT")
    manifest = json.loads(contained(root, "runs/" + run_id + "/manifest.json").read_bytes())
    if set(manifest["files"]) != {"state.json", "view.json"}:
        raise ValueError("V2_RUNTIME_CLOSED_FILE_SET_REQUIRED")
    _, bodies = read_generation(root / "runs", pointer)
    state = json.loads(bodies["state.json"])
    if (
        state.get("strategy_version") != "ETF_QUANT_V2"
        or state.get("mode") != "SIMULATION_ONLY"
        or state.get("broker_enabled") is not False
        or state.get("real_order_path") is not False
    ):
        raise ValueError("V2_INDEPENDENT_LEDGER_REQUIRED")
    if not isinstance(state.get("signals"), list) or not state["signals"]:
        raise ValueError("V2_EMPTY_SIGNAL_STATE_DENIED")
    return state


def portfolio_from_json(doc: dict[str, Any]) -> PortfolioState:
    if (
        doc.get("initial_cash") != "10000"
        or doc.get("mode") != "SIMULATION_ONLY"
        or doc.get("product") != "ETF_QUANT"
    ):
        raise ValueError("V2_INITIAL_CAPITAL_AND_SIMULATION_REQUIRED")
    return PortfolioState(
        as_of=datetime.fromisoformat(doc["as_of"]),
        cash=Decimal(doc["cash"]),
        initial_cash=Decimal(doc["initial_cash"]),
        realized_pnl=Decimal(doc["realized_pnl"]),
        positions=tuple(
            Position(
                p["asset_id"],
                Decimal(p["quantity"]),
                Decimal(p["average_cost"]),
                Decimal(p["mark_price"]),
            )
            for p in doc["positions"]
        ),
        applied_fill_ids=tuple(doc["applied_fill_ids"]),
        executed_intent_ids=tuple(doc["executed_intent_ids"]),
    )


def temporal_gate(
    now: datetime, calendar: tuple[date, ...], cutoff: date, available_at: datetime
) -> str:
    if now.tzinfo is None or available_at.tzinfo is None:
        raise ValueError("REAL_TIMEZONE_REQUIRED")
    local = now.astimezone(SHANGHAI)
    if calendar != tuple(sorted(set(calendar))):
        raise ValueError("OFFICIAL_UNIQUE_CALENDAR_REQUIRED")
    if local.date() not in calendar:
        return "ARMED_NON_TRADING_DAY"
    if local.time() < time(15, 5):
        return "ARMED_WAITING_FOR_MARKET_CLOSE"
    if cutoff != local.date():
        return "ARMED_WAITING_FOR_FINALIZED_DATA"
    if local.date() <= available_at.astimezone(SHANGHAI).date():
        return "ARMED_WAITING_FOR_POST_FREEZE_SESSION"
    if calendar.index(local.date()) + 1 >= len(calendar):
        return "ARMED_WAITING_FOR_T_PLUS_ONE_CALENDAR"
    return "ELIGIBLE"


def public_view(
    state: dict[str, Any] | None,
    release: dict[str, Any],
    *,
    latest_data_date: str | None,
    armed: bool,
    waiting_reason: str | None = None,
) -> dict[str, Any]:
    latest = state["signals"][-1] if state and state["signals"] else None
    portfolio = portfolio_from_json(state["portfolio"]) if state else None
    pending = state.get("pending") if state else None
    return {
        "strategy_version": "ETF_QUANT_V2",
        "mode": "SIMULATION_ONLY",
        "scientific_status": release["scientific_status"],
        "historical_classification": release["historical_classification"],
        "product_status": release["product_status"],
        "candidate_sha256": release["candidate_sha256"],
        "registry_sha256": release["registry_sha256"],
        "release_sha256": release["release_sha256"],
        "initial_capital": "10000",
        "armed": armed,
        "started": state is not None,
        "waiting_reason": waiting_reason,
        "epoch_count": 1 + len(state.get("terminal_epochs", [])) if state else 0,
        "signal_count": len(state["signals"]) if state else 0,
        "intent_count": len(state["intents"]) if state else 0,
        "fill_count": len(state["fills"]) if state else 0,
        "signal_date": latest["signal_date"] if latest else None,
        "top5": latest["top5"] if latest else [],
        "slots": latest["slots"] if latest else [],
        "cash_weight": latest["cash_weight"] if latest else 1.0,
        "next_accounting_state": "AWAITING_FINALIZED_T_PLUS_ONE"
        if pending
        else "NO_PENDING_INTENT"
        if state
        else "NOT_STARTED",
        "execution_date": pending["execution_date"] if pending else None,
        "balance": str(portfolio.total_equity) if portfolio else "10000",
        "cash": str(portfolio.cash) if portfolio else "10000",
        "holdings": to_primitive(portfolio.positions) if portfolio else [],
        "nav": state["nav"] if state else [],
        "benchmark": {"identity": "CSI_300", "points": state["benchmark"] if state else []},
        "turnover": state["turnover"] if state else None,
        "latest_data_date": latest_data_date,
        "latest_data_time": state.get("snapshot_observed_at") if state else None,
        "broker_enabled": False,
        "real_order_path": False,
    }


def cycle(
    root: Path,
    release: dict[str, Any],
    plan: dict[str, Any],
    *,
    calendar: TradingCalendar,
    now: datetime,
    snapshot_observed_at: datetime,
    code_commit: str,
    registry_entries: list[dict[str, Any]],
    raw_opens: dict[str, Decimal],
    raw_closes: dict[str, Decimal],
    benchmark_close: float | None,
    factual_prefix_sha256: str,
) -> dict[str, Any]:
    """The target intent is persisted at T; T+1 quantities only execute that intent."""
    if now.tzinfo is None or snapshot_observed_at.tzinfo is None or snapshot_observed_at > now:
        raise ValueError("FINALIZED_SNAPSHOT_OBSERVATION_REQUIRED")
    day = now.astimezone(SHANGHAI).date()
    available = datetime.fromisoformat(release["available_at"])
    if (
        temporal_gate(now, calendar.sessions, date.fromisoformat(plan["signal_date"]), available)
        != "ELIGIBLE"
    ):
        raise ValueError("GENUINE_CURRENT_POST_FREEZE_SIGNAL_REQUIRED")
    next_day = calendar.sessions[calendar.sessions.index(day) + 1]
    if (
        len(factual_prefix_sha256) != 64
        or plan["execution_date"] != str(next_day)
        or plan["candidate_sha256"] != release["candidate_sha256"]
        or plan.get("mode") != "SIMULATION_ONLY"
        or plan.get("broker_enabled") is not False
        or plan.get("real_order_path") is not False
    ):
        raise ValueError("CERTIFIED_SIMULATION_PLAN_REQUIRED")
    resolved = root.resolve()
    if any(
        p.name.lower() == "etf-quant-v1" or (p / ".git").exists()
        for p in (resolved, *resolved.parents)
    ):
        raise ValueError("V1_AND_V2_STATE_MUST_BE_DISJOINT")
    root = external_root(root)
    with account_lock(root):
        state = load_state(root)
        if state and any(
            state[k] != release[k]
            for k in ("candidate_sha256", "registry_sha256", "release_sha256")
        ):
            raise ValueError("FORMAL_V2_PROVENANCE_DRIFT")
        if state and state["signals"][-1]["signal_date"] >= str(day):
            if state["signals"][-1]["signal_date"] == str(day):
                return {
                    "status": "ALREADY_PROCESSED",
                    "view": public_view(state, release, latest_data_date=str(day), armed=True),
                }
            raise ValueError("FORWARD_MONOTONIC_SIGNAL_REQUIRED")
        if state is None:
            portfolio = new_portfolio(now)
            state = {
                "strategy_version": "ETF_QUANT_V2",
                "mode": "SIMULATION_ONLY",
                "broker_enabled": False,
                "real_order_path": False,
                "candidate_sha256": release["candidate_sha256"],
                "registry_sha256": release["registry_sha256"],
                "release_sha256": release["release_sha256"],
                "scientific_status": release["scientific_status"],
                "epoch": {
                    "epoch_id": "ETF_QUANT_V2_SHADOW_EPOCH_0001",
                    "created_at": now.isoformat(),
                    "first_signal_date": str(day),
                    "initial_capital": "10000",
                    "code_commit": code_commit,
                },
                "signals": [],
                "intents": [],
                "fills": [],
                "nav": [],
                "benchmark": [],
                "benchmark_base": benchmark_close,
                "pending": None,
                "turnover": 0.0,
            }
        else:
            portfolio = portfolio_from_json(state["portfolio"])
            prior_intent = state["pending"]
            if prior_intent:
                prior_signal_day = date.fromisoformat(prior_intent["signal_date"])
                due = date.fromisoformat(prior_intent["execution_date"])
                if (
                    prior_intent not in state["intents"]
                    or prior_intent.get("fillable") is False
                    or prior_intent.get("epoch_id", state["epoch"]["epoch_id"])
                    != state["epoch"]["epoch_id"]
                    or prior_intent["candidate_sha256"] != release["candidate_sha256"]
                    or due != calendar.sessions[calendar.sessions.index(prior_signal_day) + 1]
                    or datetime.fromisoformat(prior_intent["created_at"])
                    >= datetime.combine(due, time(9, 30), SHANGHAI)
                ):
                    raise ValueError("PERSISTED_V2_INTENT_INTEGRITY_REQUIRED")
            if abandon_missed_t1(state, day=day, now=now.astimezone(SHANGHAI), epoch_key="epoch"):
                state["epoch"] = {
                    "epoch_id": f"ETF_QUANT_V2_SHADOW_EPOCH_{len(state['terminal_epochs']) + 1:04d}",
                    "created_at": now.isoformat(),
                    "first_signal_date": str(day),
                    "initial_capital": "10000",
                    "code_commit": code_commit,
                    "opening_portfolio": to_primitive(portfolio),
                    "continuation": "PRESERVED_ACCOUNT_AFTER_TERMINAL_MISSED_T1",
                }
            pending = state["pending"]
            if pending:
                execution = date.fromisoformat(pending["execution_date"])
                intent_at = datetime.fromisoformat(pending["created_at"])
                if execution != day or intent_at >= datetime.combine(
                    execution, time(9, 30), SHANGHAI
                ):
                    raise ValueError("MISSED_OR_RETROACTIVE_T_PLUS_ONE_DENIED")
                needed = {p.asset_id for p in portfolio.positions} | set(pending["weights"])
                if not needed.issubset(raw_opens):
                    raise ValueError("FINALIZED_T_PLUS_ONE_OPENS_REQUIRED")
                fill_at = datetime.combine(execution, time(9, 30), SHANGHAI)
                portfolio, fills = rebalance_at_open(
                    portfolio,
                    tuple(
                        TargetPosition(code, weight) for code, weight in pending["weights"].items()
                    ),
                    {code: raw_opens[code] for code in needed},
                    signal_day=date.fromisoformat(pending["signal_date"]),
                    execution_day=execution,
                    processed_at=fill_at,
                    calendar=calendar,
                    batch_id=pending["intent_id"],
                    lot_size=release["lot_size"],
                )
                for fill in fills:
                    state["fills"].append(
                        {
                            **to_primitive(fill),
                            "economic_execution_at": fill_at.isoformat(),
                            "accounted_at": now.isoformat(),
                            "target_intent_id": pending["intent_id"],
                        }
                    )
                    state["turnover"] += float(
                        fill.price * fill.intent.quantity / portfolio.initial_cash
                    )
                state["pending"] = None
            required = {p.asset_id for p in portfolio.positions}
            if not required.issubset(raw_closes):
                raise ValueError("FINALIZED_HELD_ETF_CLOSES_REQUIRED")
            portfolio = mark_to_market(
                portfolio, {code: raw_closes[code] for code in required}, as_of=now
            )
            state["nav"].append(
                {
                    "date": str(day),
                    "equity": str(portfolio.total_equity),
                    "normalized_nav": float(portfolio.total_equity / portfolio.initial_cash),
                }
            )
            if benchmark_close is not None and state["benchmark_base"] is not None:
                state["benchmark"].append(
                    {"date": str(day), "normalized_nav": benchmark_close / state["benchmark_base"]}
                )
        allocation = plan["allocation"]
        weights = {r["etf_code"]: r["weight"] for r in allocation["executed"]}
        decision = rebalance_decision_v2(
            tuple(p.asset_id for p in portfolio.positions),
            tuple(weights),
            execution_policy="B40_WITH_CASH",
        )
        if state["pending"] is not None:
            raise ValueError("UNSETTLED_PRIOR_INTENT_REQUIRED")
        by_etf = {r["etf_code"]: r for r in registry_entries}
        slots = [
            {
                **r,
                "mapping_class": by_etf[r["etf_code"]]["mapping_class"],
                "confidence": by_etf[r["etf_code"]]["confidence"],
                "evidence_date": by_etf[r["etf_code"]]["evidence_date"],
                "mapping_available_at": by_etf[r["etf_code"]]["available_at"],
            }
            for r in allocation["executed"]
        ]
        slots.extend(
            {
                **r,
                "etf_code": None,
                "weight": r["weight_forfeited"],
                "mapping_class": "NO_RELIABLE_MAPPING",
                "confidence": None,
                "evidence_date": None,
            }
            for r in allocation["skipped"]
        )
        signal = {
            "signal_id": "V2_SIGNAL_"
            + content_hash({"candidate": release["candidate_sha256"], "day": str(day)})[:24],
            "signal_date": str(day),
            "decision_at": now.isoformat(),
            "code_commit": code_commit,
            "models": plan["models"],
            "top5": plan["rankings"][:5],
            "slots": slots,
            "cash_weight": allocation["cash_weight"],
            "execution_date": str(next_day),
        }
        state["signals"].append(signal)
        if decision is RebalanceStatus.REQUIRED:
            intent = {
                "intent_id": signal["signal_id"] + "_TARGET",
                "signal_date": str(day),
                "execution_date": str(next_day),
                "created_at": now.isoformat(),
                "weights": weights,
                "rule": "TARGET_WEIGHTS_AT_T_CLOSE;LOT_ROUNDED_COST_AWARE_T_PLUS_ONE_OPEN",
                "simulation_only": True,
                "candidate_sha256": release["candidate_sha256"],
                "epoch_id": state["epoch"]["epoch_id"],
            }
            state["intents"].append(intent)
            state["pending"] = intent
        state["portfolio"] = to_primitive(portfolio)
        state["snapshot_observed_at"] = snapshot_observed_at.isoformat()
        state["factual_prefix_sha256"] = factual_prefix_sha256
        view = public_view(state, release, latest_data_date=str(day), armed=True)
        state_bytes = json_bytes(state)
        identifier = (
            "v2_"
            + now.strftime("%Y%m%dT%H%M%S%f")
            + "_"
            + hashlib.sha256(state_bytes).hexdigest()[:12]
        )
        pointer = publish_account_generation(
            root,
            identifier,
            {"state.json": state_bytes, "view.json": json_bytes(view)},
            {
                "strategy_version": "ETF_QUANT_V2",
                "release_sha256": release["release_sha256"],
                "created_at": now.isoformat(),
            },
        )
        return {"status": "STARTED", "view": view, "pointer": pointer}

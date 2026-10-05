"""Compatibility entry point onto production lot-rounded paper accounting."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, time
from decimal import Decimal

from strategies.etf_quant.domain import (
    PortfolioState,
    SimulatedFill,
    TargetPosition,
    TradingCalendar,
)
from strategies.etf_quant.portfolio import RebalanceStatus
from strategies.etf_quant.portfolio.partial import rebalance_decision_v2
from strategies.etf_quant.portfolio.policy import POLICY_B40_WITH_CASH
from strategies.etf_quant.simulation import mark_to_market
from strategies.etf_quant.simulation.lots import rebalance_at_open

from .runtime import SHANGHAI


def settle_t_plus_one(
    state: PortfolioState,
    *,
    signal_at: datetime,
    processed_at: datetime,
    calendar: TradingCalendar,
    weights: Mapping[str, float],
    raw_opens: Mapping[str, Decimal],
    raw_closes: Mapping[str, Decimal],
    finalized: bool,
) -> tuple[PortfolioState, tuple[SimulatedFill, ...]]:
    if signal_at.tzinfo is None or processed_at.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    day = signal_at.astimezone(SHANGHAI).date()
    i = calendar.sessions.index(day)
    if i + 1 >= len(calendar.sessions):
        raise ValueError("OFFICIAL_T_PLUS_ONE_REQUIRED")
    execution = calendar.sessions[i + 1]
    if (
        not finalized
        or processed_at.astimezone(SHANGHAI).date() != execution
        or processed_at.astimezone(SHANGHAI).time() < time(15)
    ):
        raise ValueError("FINALIZED_GENUINE_T_PLUS_ONE_REQUIRED")
    if state.as_of > signal_at or signal_at.astimezone(SHANGHAI).time() < time(15):
        raise ValueError("SIGNAL_CLOSE_AND_MONOTONIC_STATE_REQUIRED")
    target = {k: Decimal(str(v)) for k, v in weights.items()}
    if (
        any(not v.is_finite() or v <= 0 or v > Decimal(".35") for v in target.values())
        or sum(target.values()) > 1
    ):
        raise ValueError("FROZEN_LONG_ONLY_CAP_REQUIRED")
    previous = tuple(p.asset_id for p in state.positions)
    needed = set(previous) | set(target)
    if (
        set(raw_opens) != needed
        or set(raw_closes) != needed
        or any(not v.is_finite() or v <= 0 for v in (*raw_opens.values(), *raw_closes.values()))
    ):
        raise ValueError("COMPLETE_POSITIVE_RAW_PRICES_REQUIRED")
    fill_at = datetime.combine(execution, time(9, 30), SHANGHAI)
    fills: tuple[SimulatedFill, ...] = ()
    decision = rebalance_decision_v2(previous, tuple(target), execution_policy=POLICY_B40_WITH_CASH)
    if decision is RebalanceStatus.REQUIRED:
        state, fills = rebalance_at_open(
            state,
            tuple(TargetPosition(asset, float(weight)) for asset, weight in target.items()),
            dict(raw_opens),
            signal_day=day,
            execution_day=execution,
            processed_at=fill_at,
            calendar=calendar,
            batch_id=f"v2-{day}",
            lot_size=100,
        )
    marks = {p.asset_id: raw_closes[p.asset_id] for p in state.positions}
    return mark_to_market(state, marks, as_of=processed_at), tuple(fills)

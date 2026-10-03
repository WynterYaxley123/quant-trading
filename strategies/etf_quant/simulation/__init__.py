"""Explicit-input accounting primitives, NOT an execution engine/pipeline."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from ..domain import (
    NAVPoint,
    PortfolioState,
    Position,
    Side,
    SimulatedFill,
    SimulatedOrderIntent,
    StrategyConfig,
    TradingCalendar,
    TransactionCost,
    decimal_math,
    decimal_value,
    timestamp,
)

# Fixed arithmetic context, independent of a caller changing global precision.
# No exchange lot/tick/cash-cent rounding is assumed; those contracts are deferred.


def new_portfolio(as_of: datetime, config: StrategyConfig | None = None) -> PortfolioState:
    config = StrategyConfig() if config is None else config
    return PortfolioState(as_of=as_of, cash=config.initial_cash, initial_cash=config.initial_cash)


def validate_next_session(intent: SimulatedOrderIntent, calendar: TradingCalendar) -> None:
    days = calendar.sessions
    if intent.signal_session not in days:
        raise ValueError("unknown signal session")
    i = days.index(intent.signal_session)
    if i + 1 >= len(days) or days[i + 1] != intent.execution_session:
        raise ValueError("execution must be T+1 supplied trading session OPEN")


def price_simulated_fill(
    intent: SimulatedOrderIntent,
    *,
    calendar: TradingCalendar,
    reference_open: Decimal,
    executed_at: datetime,
    fill_id: str,
    costs: TransactionCost | None = None,
) -> SimulatedFill:
    """Produce a SYNTHETIC value from explicit open/quantity/time; no order API.

    Slippage adjusts fill price. It is disclosed separately but never charged
    twice. Commission is based on slipped notional; configured duty is SELL-only.
    """
    validate_next_session(intent, calendar)
    config = TransactionCost() if costs is None else costs
    reference = decimal_value(reference_open, "reference open", positive=True)
    with decimal_math():
        change = config.slippage_bps / 10000
        price = reference * (1 + change if intent.side is Side.BUY else 1 - change)
        notional = price * intent.quantity
        commission = max(config.minimum_commission, notional * config.commission_bps / 10000)
        duty = notional * config.stamp_duty_bps / 10000 if intent.side is Side.SELL else Decimal(0)
        slippage = abs(price - reference) * intent.quantity
    return SimulatedFill(fill_id, intent, executed_at, reference, price, commission, slippage, duty)


def apply_fill(
    state: PortfolioState, fill: SimulatedFill, *, calendar: TradingCalendar
) -> PortfolioState:
    """Pure immutable long-only accounting; reject duplicate/short/cash failure."""
    validate_next_session(fill.intent, calendar)
    if (
        fill.executed_at < state.as_of
        or fill.fill_id in state.applied_fill_ids
        or fill.intent.intent_id in state.executed_intent_ids
    ):
        raise ValueError("out-of-order / duplicate fill")
    positions = {p.asset_id: p for p in state.positions}
    asset, qty = fill.intent.asset_id, fill.intent.quantity
    old = positions.get(asset)
    with decimal_math():
        fees, notional = fill.commission + fill.stamp_duty, fill.price * qty
        realized = state.realized_pnl
        if fill.intent.side is Side.BUY:
            cash = state.cash - notional - fees
            if cash < 0:
                raise ValueError("insufficient simulation cash")
            old_qty = old.quantity if old else Decimal(0)
            basis = old_qty * old.average_cost if old else Decimal(0)
            positions[asset] = Position(
                asset,
                old_qty + qty,
                (basis + notional + fees) / (old_qty + qty),
                fill.reference_open,
            )
        else:
            if old is None or qty > old.quantity:
                raise ValueError("oversell / no shorting")
            cash = state.cash + notional - fees
            if cash < 0:
                raise ValueError("fees exceed available simulation cash")
            realized += notional - fees - qty * old.average_cost
            if qty == old.quantity:
                del positions[asset]
            else:
                positions[asset] = Position(
                    asset, old.quantity - qty, old.average_cost, fill.reference_open
                )
    return replace(
        state,
        cash=cash,
        positions=tuple(positions[c] for c in sorted(positions)),
        realized_pnl=realized,
        as_of=fill.executed_at,
        applied_fill_ids=(*state.applied_fill_ids, fill.fill_id),
        executed_intent_ids=(*state.executed_intent_ids, fill.intent.intent_id),
    )


def mark_to_market(
    state: PortfolioState, prices: Mapping[str, Decimal], *, as_of: datetime
) -> PortfolioState:
    timestamp(as_of)
    if as_of < state.as_of or set(prices) != {p.asset_id for p in state.positions}:
        raise ValueError("complete explicit current marks / monotonic time required")
    return replace(
        state,
        as_of=as_of,
        positions=tuple(
            replace(p, mark_price=decimal_value(prices[p.asset_id], "mark", positive=True))
            for p in state.positions
        ),
    )


def nav_point(state: PortfolioState) -> NAVPoint:
    with decimal_math():
        return NAVPoint(
            state.as_of,
            state.cash,
            state.market_value,
            state.total_equity,
            state.realized_pnl,
            state.unrealized_pnl,
            state.total_equity / state.initial_cash,
        )

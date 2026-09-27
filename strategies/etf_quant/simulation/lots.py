"""Lot-rounded, cost-aware long-only Shadow accounting, never broker orders."""
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR

from ..domain import Side, SimulatedOrderIntent, StrategyConfig, decimal_math
from . import apply_fill, mark_to_market, price_simulated_fill
from ..runtime.storage import GateError


def affordable_units(budget, reference_open, costs, lot_size=100):
    if type(lot_size) is not int or lot_size <= 0:
        raise ValueError("positive integer lot size required")
    if not reference_open.is_finite() or reference_open <= 0 or not budget.is_finite() or budget < 0:
        raise ValueError("finite nonnegative budget and positive raw open required")
    with decimal_math():
        price = reference_open * (1 + costs.slippage_bps / 10000)
        if budget <= costs.minimum_commission:
            return Decimal(0)
        fee_rate = costs.commission_bps / 10000
        upper = min(budget / (price * (1 + fee_rate)), (budget - costs.minimum_commission) / price)
        return max(Decimal(0), (upper / lot_size).to_integral_value(rounding=ROUND_FLOOR) * lot_size)


def rebalance_at_open(state, targets, opens, *, signal_day, execution_day, processed_at: datetime,
                      calendar, batch_id, config=None, lot_size=100):
    """Reference price is T+1 actual OPEN; processed_at is actual delayed bookkeeping.

    Caller must validate a genuinely prior persisted intent. No retrospective
    intent construction is allowed in the runtime. Sells precede buys; fees and
    integer lots constrain cash. Zero-sized targets retain cash, not fake units.
    """
    config = StrategyConfig() if config is None else config
    if (type(lot_size) is not int or lot_size <= 0
            or set(opens) != {t.asset_id for t in targets} | {p.asset_id for p in state.positions}
            or any(not v.is_finite() or v <= 0 for v in opens.values())
            or processed_at.date() != execution_day or state.as_of > processed_at
            or any(p.quantity % lot_size for p in state.positions)):
        raise GateError("SHADOW_EXECUTION_INPUT_BLOCKER")
    marked = mark_to_market(state, {p.asset_id: opens[p.asset_id] for p in state.positions}, as_of=processed_at)
    equity = marked.total_equity
    desired = {t.asset_id: affordable_units(equity * Decimal(str(t.target_weight)), opens[t.asset_id], config.costs, lot_size)
               for t in targets}
    positions = {p.asset_id: p.quantity for p in marked.positions}
    fills, current = [], marked
    for side in (Side.SELL, Side.BUY):
        for asset in sorted(set(desired) | set(positions)):
            old = positions.get(asset, Decimal(0))
            target = desired.get(asset, Decimal(0))
            quantity = max(Decimal(0), old - target if side is Side.SELL else target - old)
            if side is Side.BUY:
                quantity = min(quantity, affordable_units(current.cash, opens[asset], config.costs, lot_size))
            if quantity == 0:
                continue
            intent_id = batch_id + "_" + side.value + "_" + asset
            intent = SimulatedOrderIntent(intent_id, asset, side, quantity, signal_day, execution_day)
            fill = price_simulated_fill(intent, calendar=calendar, reference_open=opens[asset],
                                       executed_at=processed_at, fill_id=intent_id + "_FILL", costs=config.costs)
            current = apply_fill(current, fill, calendar=calendar)
            fills.append(fill)
    return current, tuple(fills)

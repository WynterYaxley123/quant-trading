from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext

import pytest

from strategies.etf_quant.domain import (Side, SimulatedOrderIntent, TradingCalendar, TransactionCost)
from strategies.etf_quant.simulation import (apply_fill, mark_to_market, nav_point, new_portfolio,
                                           price_simulated_fill, validate_next_session)

D = Decimal
CAL = TradingCalendar((date(2026,1,2),date(2026,1,5),date(2026,1,6),date(2026,1,7)))


def at(day,hour=9): return datetime.combine(day,datetime.min.time(),timezone.utc).replace(hour=hour)


def fill(side=Side.BUY,qty='100',price='10',idx=1,key='SYN_BUY',costs=None):
    intent = SimulatedOrderIntent(key,'SYN_ETF_A',side,D(qty),CAL.sessions[idx-1],CAL.sessions[idx])
    return price_simulated_fill(intent,calendar=CAL,reference_open=D(price),executed_at=at(CAL.sessions[idx]),
                                fill_id=key+'_FILL',costs=costs)


def test_transaction_cost_default_per_side_and_no_double_slippage_charge():
    state = new_portfolio(at(CAL.sessions[0],17))
    buy = fill()
    assert buy.price == D('10.005') and buy.commission == D('.30015') and buy.slippage == D('.5')
    assert buy.stamp_duty == 0
    holding = apply_fill(state,buy,calendar=CAL)
    assert state.cash == D('10000') and state.positions == ()  # immutable input
    assert holding.cash == D('8999.19985')
    assert holding.positions[0].quantity == 100 and holding.positions[0].average_cost == D('10.0080015')
    assert holding.market_value == 1000 and holding.total_equity == D('9999.19985')
    assert holding.unrealized_pnl == D('-.80015') and holding.realized_pnl == 0
    sell = fill(Side.SELL,price='11',idx=2,key='SYN_SELL')
    assert sell.price == D('10.9945') and sell.slippage == D('.55') and sell.commission == D('.329835')
    closed = apply_fill(holding,sell,calendar=CAL)
    assert closed.positions == () and closed.cash == D('10098.320015')
    assert closed.realized_pnl == D('98.320015') and closed.unrealized_pnl == 0
    assert nav_point(closed).normalized_nav == closed.cash / 10000


def test_all_cost_components_configuration_driven():
    costs = TransactionCost(D(10),D(20),D(5),D(2))
    buy = fill(qty='1',costs=costs)
    sell = fill(Side.SELL,qty='1',costs=costs)
    assert buy.price == D('10.02') and sell.price == D('9.98')
    assert buy.commission == sell.commission == 2
    assert buy.stamp_duty == 0 and sell.stamp_duty == D('.00499')
    assert buy.slippage == sell.slippage == D('.02')


def test_average_basis_partial_sell_marks_and_pnl_identity():
    zero = TransactionCost(D(0),D(0),D(0),D(0))
    state = apply_fill(new_portfolio(at(CAL.sessions[0],17)),fill(costs=zero),calendar=CAL)
    state = apply_fill(state,fill(qty='100',price='20',idx=2,key='SYN_BUY2',costs=zero),calendar=CAL)
    assert state.positions[0].quantity == 200 and state.positions[0].average_cost == 15
    state = apply_fill(state,fill(Side.SELL,qty='50',price='18',idx=3,key='SYN_SELL',costs=zero),calendar=CAL)
    assert state.positions[0].quantity == 150 and state.positions[0].average_cost == 15
    assert state.realized_pnl == 150
    marked = mark_to_market(state,{'SYN_ETF_A':D(19)},as_of=at(CAL.sessions[3],17))
    assert marked.market_value == 2850 and marked.unrealized_pnl == 600
    assert marked.total_equity == marked.initial_cash+marked.realized_pnl+marked.unrealized_pnl
    with localcontext() as context:
        context.prec = 4
        assert marked.total_equity == 10750 and nav_point(marked).normalized_nav == D('1.075')


def test_next_trading_session_not_natural_day_and_no_same_day_or_late_execution():
    valid = fill().intent
    validate_next_session(valid,CAL)  # explicit Friday -> Monday fixture
    with pytest.raises(ValueError): replace(valid,execution_session=valid.signal_session)
    with pytest.raises(ValueError): validate_next_session(replace(valid,execution_session=CAL.sessions[2]),CAL)
    with pytest.raises(ValueError): replace(valid,mode='LIVE')
    with pytest.raises(ValueError): replace(fill(),executed_at=at(CAL.sessions[2]))
    with pytest.raises(ValueError): replace(valid,quantity=D(0))


def test_duplicate_fill_or_full_intent_and_insufficient_cash_oversell_fail_closed():
    state = new_portfolio(at(CAL.sessions[0],17))
    buy = fill()
    holding = apply_fill(state,buy,calendar=CAL)
    with pytest.raises(ValueError): apply_fill(holding,buy,calendar=CAL)
    with pytest.raises(ValueError): apply_fill(holding,replace(buy,fill_id='DIFFERENT_ID_SAME_FULL_INTENT'),calendar=CAL)
    with pytest.raises(ValueError): apply_fill(state,fill(qty='10000'),calendar=CAL)
    with pytest.raises(ValueError): apply_fill(state,fill(Side.SELL),calendar=CAL)
    with pytest.raises(ValueError): apply_fill(holding,fill(Side.SELL,qty='101',idx=2,key='SELL_TOO_MUCH'),calendar=CAL)
    with pytest.raises(ValueError): mark_to_market(holding,{},as_of=at(CAL.sessions[1],17))
    with pytest.raises(ValueError): mark_to_market(holding,{'SYN_ETF_A':D(0)},as_of=at(CAL.sessions[1],17))
    assert state.cash == 10000 and state.positions == ()


def test_nav_dto_rejects_nonfinite_or_broken_equity_identity():
    point = nav_point(new_portfolio(at(CAL.sessions[0],17)))
    for changes in ({'total_equity':D(1)}, {'cash':D('-1')}, {'realized_pnl':D('NaN')},
                    {'timestamp':point.timestamp.replace(tzinfo=None)}, {'normalized_nav':float('inf')}):
        with pytest.raises(ValueError): replace(point,**changes)

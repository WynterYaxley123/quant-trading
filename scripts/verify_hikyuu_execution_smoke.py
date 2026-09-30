"""Fixed local-data LEVEL A acceptance; never invokes an industry strategy.

Run only in the existing Docker environment. No downloads, parameter selection,
manual trades, forced liquidation, or changes to the smoke system.
"""
from __future__ import annotations

import configparser
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    from src.data.providers import preflight
    from src.backtesting import BacktestRequest, StrategySpec, RESULT_FILES
    from src.backtesting.hikyuu_runner import run_hikyuu_backtest, trades_from_tm
    from src.backtesting.testing import smoke_strategy

    cfg = configparser.ConfigParser()
    assert cfg.read(Path.home() / ".hikyuu/hikyuu.ini"), "Missing local Hikyuu config"
    pf = preflight(cfg.get("hikyuu", "datadir"))
    print(pf.summary(), flush=True)
    data_paths = [Path(pf.db_path), *(Path(p) for p in pf.h5_files.values())]
    def fingerprints():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in data_paths}
    data_before = fingerprints()

    # Capture the actual system created by the runner without altering its rule.
    captured = {}
    original = smoke_strategy.build_smoke_system
    def capture(symbol, config):
        system, tm = original(symbol, config)
        captured[symbol] = (system, tm)
        return system, tm

    req = BacktestRequest(strategy="hikyuu_execution_smoke", framework="hikyuu",
                          start_date="2020-01-01", end_date="2024-12-31",
                          initial_cash=100_000.0)
    spec = StrategySpec(name="hikyuu_execution_smoke",
                        package="src.backtesting.testing.smoke_strategy",
                        path=ROOT / "src/backtesting/testing", version="fixed-smoke-5-20-1000-0.05")
    with patch.object(smoke_strategy, "build_smoke_system", capture):
        result = run_hikyuu_backtest(req, spec, symbols=("sh510300",))
    assert set(captured) == {"sh510300"}
    system, tm = captured["sh510300"]

    import hikyuu as h
    sm = h.StockManager.instance()
    query = h.Query(h.Datetime(20200101), h.Datetime(20241231))
    coverage = {s: len(sm[s].get_kdata(query)) for s in
                ("sh510300", "sh512660", "sz159934", "sz159745")}
    assert all(n > 0 for n in coverage.values())
    stock = sm["sh510300"]
    kd = stock.get_kdata(query)
    def day(d):
        return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
    dates = [day(d) for d in kd.get_datetime_list()]
    assert dates == sorted(set(dates))
    bars = {day(kd[i].datetime): kd[i] for i in range(len(kd))}
    assert all(float(b.volume) > 0 for b in bars.values())
    assert system.get_param("buy_delay") and system.get_param("sell_delay")
    signals = {"BUY": {day(d) for d in system.sg.get_buy_signal()},
               "SELL": {day(d) for d in system.sg.get_sell_signal()}}
    raw = list(tm.get_trade_list())
    all_trades = trades_from_tm(tm, include_init=True)
    assert sum(all_trades.business == "INIT") == 1
    trades = result.trades
    assert len(raw) == len(trades) + 1 and len(trades) > 0
    counts = trades.business.value_counts().to_dict()
    assert set(counts) == {"BUY", "SELL"}
    assert len(trades) == result.metrics.trade_count

    # Independent reconciliation of the engine output; this never creates orders
    # or replaces the TradeManager curve/positions used by BacktestResult.
    cash, quantity = req.initial_cash, 0.0
    ledger = {}
    for t in trades.itertuples(index=False):
        assert t.datetime in bars, "Fill without a real bar"
        b = bars[t.datetime]
        np.testing.assert_allclose(t.price, b.open, rtol=0, atol=1e-8)
        assert b.low <= t.price <= b.high and t.number > 0
        pos = dates.index(t.datetime)
        assert pos > 0 and dates[pos - 1] in signals[t.business], "Fill lacks preceding session signal"
        assert t.cost == 0, "Original TC_Zero placeholder changed"
        sign = 1 if t.business == "BUY" else -1
        cash -= sign * t.price * t.number + t.cost
        quantity += sign * t.number
        np.testing.assert_allclose(t.cash, cash, rtol=0, atol=.011)
        assert cash >= 0 and quantity >= 0
        ledger[t.datetime] = (cash, quantity)

    eq = result.equity_curve
    positions = result.positions
    assert eq.date.tolist() == positions.datetime.tolist() == dates
    assert np.isfinite(eq.equity).all()
    cash, quantity = req.initial_cash, 0.0
    for i, d in enumerate(dates):
        cash, quantity = ledger.get(d, (cash, quantity))
        p = positions.iloc[i]
        np.testing.assert_allclose([p.cash, p.number, p.market_value, eq.equity.iloc[i]],
                                   [cash, quantity, quantity * bars[d].close,
                                    cash + quantity * bars[d].close], rtol=0, atol=.011)
    assert positions.number.nunique() > 1 and positions.cash.nunique() > 1
    assert quantity > 0, "Expected unchanged smoke to retain the actual final open position"
    assert trades.iloc[-1].datetime < dates[-1], "Unexpected terminal forced trade"

    # Prefix invariance: truncating future bars must not change earlier fills.
    prefix_system, prefix_tm = original("sh510300")
    prefix_system.run(stock, h.Query(h.Datetime(20200101), h.Datetime(20230101)))
    import pandas as pd
    pd.testing.assert_frame_equal(
        trades[trades.datetime < "2023-01-01"].reset_index(drop=True),
        trades_from_tm(prefix_tm).reset_index(drop=True))
    assert data_before == fingerprints(), "Local market data changed"

    meta = result.metadata
    assert (meta.run_type, meta.strategy, meta.status) == (
        "execution_smoke", "hikyuu_execution_smoke", "LEVEL_A_SMOKE")
    assert result.metrics.commission is None and meta.commission is None
    assert result.metrics.slippage is None and meta.slippage is None
    assert result.yearly_returns.empty
    result.metadata.run_id += "-" + uuid4().hex[:8]
    out_expected = ROOT / "reports/backtests/hikyuu_execution_smoke" / meta.run_id
    assert not out_expected.exists()
    result.metadata.limitations += (
        "本次验收逐笔确认成交为前一 session 信号后的真实 bar open；现金/份额/市值逐日勾稽通过，截断未来 bar 不改变历史成交。",
        "git_commit/data_snapshot 若 unknown/null 均原样保留；本次报告导出修正尚未提交，源码指纹见 verification.json。",
    )
    output = Path(result.write(str(ROOT / "reports/backtests")))
    assert output == out_expected
    assert all((output / f).is_file() for f in RESULT_FILES)
    assert "THIS IS NOT A SW_SECTOR_ROTATION STRATEGY BACKTEST." in (output / "report.md").read_text()
    verification = {
        "status": "LEVEL A HIKYUU EXECUTION VERIFIED", "preflight": asdict(pf),
        "kdata_bars": coverage, "buy_sell_counts": counts,
        "equity_points": len(eq), "first_bar": dates[0], "last_bar": dates[-1],
        "init_records_excluded": 1, "bar_open_prices_verified": True,
        "previous_session_signals_verified": True, "cash_positions_equity_reconciled": True,
        "prefix_invariance_verified": True, "terminal_open_quantity": quantity,
        "data_files_unchanged": True, "local_data_sha256": data_before,
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [Path(__file__), ROOT / "src/backtesting/hikyuu_runner.py",
                                    ROOT / "src/backtesting/testing/smoke_strategy.py"]},
        "metrics": result.metrics.to_dict(), "metadata": meta.to_dict(),
    }
    (output / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), **verification}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

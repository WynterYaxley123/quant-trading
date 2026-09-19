"""真实 Hikyuu 数据与 LEVEL A 执行链路的集成测试。

标记 ``integration``：需要容器内已初始化 Hikyuu 数据目录
（``scripts/data/init_hikyuu_data.py``）。

运行方式::

    pytest -m integration

**不联网、不修改 HDF5 / stock.db**：只读已存在的本地数据。
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

pytestmark = pytest.mark.integration


def _datadir() -> str | None:
    import configparser

    cfg = os.path.join(os.path.expanduser("~"), ".hikyuu", "hikyuu.ini")
    if not os.path.exists(cfg):
        return None
    p = configparser.ConfigParser()
    p.read(cfg, encoding="utf-8")
    return p.get("hikyuu", "datadir", fallback=None)


@pytest.fixture(scope="module")
def datadir():
    d = _datadir()
    if not d or not os.path.exists(os.path.join(d, "stock.db")):
        pytest.skip("Hikyuu 数据目录未初始化")
    return d


# --- preflight ------------------------------------------------------------


def test_preflight_passes_on_real_data(datadir):
    from src.data.providers import preflight

    rep = preflight(datadir)
    assert rep.db_stock_count > 0
    assert rep.h5_table_count > 0
    assert "SH" in rep.markets


def test_preflight_detects_inconsistency_on_real_data(datadir, tmp_path):
    """在真实数据副本上注入不一致，确认护栏能拦住（防段错误）。"""
    import shutil
    import sqlite3

    from src.data.providers import HikyuuDataIntegrityError, preflight

    copy = str(tmp_path / "hku")
    shutil.copytree(datadir, copy)
    conn = sqlite3.connect(os.path.join(copy, "stock.db"))
    conn.execute(
        "insert into stock(stockid,marketid,code,name,type,valid,startDate,endDate)"
        " values(99999,1,'999999','FAKE',5,1,20200101,99999999)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(HikyuuDataIntegrityError):
        preflight(copy)


# --- 真实 KData -----------------------------------------------------------


def test_real_kdata_loads_via_provider(datadir):
    from src.data.loaders import MarketDataRequest, load_panel
    from src.data.providers import HikyuuProvider

    p = HikyuuProvider()
    assert p.is_available(), "HikyuuProvider 应可用"
    res = load_panel(
        MarketDataRequest(symbols=["sh510300"], start="2024-01-01", end="2024-03-31"), [p]
    )
    assert res.ok
    df = res.panel["sh510300"]
    assert len(df) > 30
    assert (df["close"] > 0).all()
    vals = df["date"].to_numpy()
    assert (vals[1:] >= vals[:-1]).all()


def test_bare_code_resolves_via_market_prefix(datadir):
    """裸 6 位代码必须能解析（自动补 sh/sz 前缀）—— 实测 sm['510300'] 会返回空 Stock。"""
    from src.data.providers import HikyuuProvider

    p = HikyuuProvider()
    res = p.fetch_daily(["510300"], "2024-01-01", "2024-02-01")
    assert "510300" in res
    assert len(res["510300"]) > 10


def test_unknown_symbol_not_faked(datadir):
    from src.data.providers import HikyuuProvider, ProviderUnavailable

    p = HikyuuProvider()
    with pytest.raises(ProviderUnavailable):
        p.fetch_daily(["sh999999"], "2024-01-01", "2024-02-01")


def test_kdata_has_no_nan(datadir):
    from src.data.loaders import MarketDataRequest, load_panel
    from src.data.providers import HikyuuProvider

    res = load_panel(
        MarketDataRequest(symbols=["sh510300", "sz159934"], start="2023-06-01", end="2023-12-31"),
        [HikyuuProvider()],
    )
    for sym, df in res.panel.items():
        for col in ("open", "high", "low", "close", "volume"):
            assert not df[col].isna().any(), f"{sym}.{col} 含 NaN"


# --- LEVEL A 执行链路 -----------------------------------------------------


def test_level_a_smoke_runs_real_backtest(datadir):
    """真实数据 → System → TradeManager → BacktestResult 全链路。"""
    from src.backtesting import BacktestRequest, run_backtest

    req = BacktestRequest(
        strategy="sw_sector_rotation",
        framework="hikyuu",
        start_date="2020-01-01",
        end_date="2024-12-31",
        initial_cash=100_000.0,
    )
    res = run_backtest(req)
    assert res.metadata.status == "LEVEL_A_SMOKE"
    assert res.metadata.framework == "hikyuu"
    assert res.metadata.adjust_mode == "none"
    assert res.metadata.limit_up_down_modeled is False
    # 真实成交
    assert res.metrics.trade_count is not None
    assert res.metrics.trade_count > 0, "5 年区间内均线交叉应产生成交"
    assert len(res.trades) == res.metrics.trade_count
    assert set(res.trades["business"].unique()) <= {"BUY", "SELL"}
    # 净值曲线
    assert len(res.equity_curve) > 100
    assert res.metrics.final_value is not None
    assert res.metrics.final_value > 0
    # 自算回撤有值且为负
    assert res.metrics.max_drawdown is not None
    assert res.metrics.max_drawdown <= 0
    # 未建模项必须明确为 None
    assert res.metrics.slippage is None


def test_level_a_writes_standard_output(datadir, tmp_path):
    from src.backtesting import BacktestRequest, RESULT_FILES, run_backtest

    req = BacktestRequest(
        strategy="sw_sector_rotation", framework="hikyuu",
        start_date="2023-01-01", end_date="2023-12-31", initial_cash=100_000.0,
    )
    res = run_backtest(req)
    out = res.write(str(tmp_path))
    for name in RESULT_FILES:
        assert os.path.exists(os.path.join(out, name)), f"缺少 {name}"
    trades = pd.read_csv(os.path.join(out, "trades.csv"))
    assert len(trades) == len(res.trades)


def test_level_a_limitations_are_recorded(datadir):
    """未建模事项必须写进 metadata，不得让读者误以为已建模。"""
    from src.backtesting import BacktestRequest, run_backtest

    req = BacktestRequest(
        strategy="sw_sector_rotation", framework="hikyuu",
        start_date="2022-01-01", end_date="2022-12-31", initial_cash=100_000.0,
    )
    res = run_backtest(req)
    lim = " ".join(res.metadata.limitations)
    assert "SMOKE" in lim or "非投资策略" in lim
    assert "未复权" in lim
    assert "涨跌停" in lim


def test_short_window_annualized_is_none_not_zero(datadir):
    """样本过短时年化/Sharpe 必须是 None，不得输出 0。"""
    from src.backtesting import BacktestRequest, run_backtest

    req = BacktestRequest(
        strategy="sw_sector_rotation", framework="hikyuu",
        start_date="2024-11-01", end_date="2024-12-31", initial_cash=100_000.0,
    )
    res = run_backtest(req)
    assert res.metrics.annual_return is None
    assert res.metrics.sharpe is None

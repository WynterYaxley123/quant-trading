"""Hikyuu 执行框架 runner。

链路
----
``BacktestRequest``
→ Hikyuu 环境检查
→ Hikyuu 数据 preflight（防段错误）
→ 加载 Hikyuu（``load_hikyuu``）
→ 取真实 KData
→ 构造 System（当前 LEVEL A 用确定性 smoke 规则）
→ ``sys.run(stock, query)``
→ 从 TradeManager 提取交易/净值/持仓
→ ``BacktestResult``

Hikyuu 相关 import **集中在本模块**与
``strategies/<strategy>/src/adapters/hikyuu/``，不污染 factors/model/risk。
"""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any

import pandas as pd

from ..data.providers import HikyuuProvider, preflight
from .result import (
    BacktestMetadata,
    BacktestMetrics,
    BacktestResult,
    now_run_id,
)
from .runner import BacktestRequest, StrategySpec, register_framework
from .testing.smoke_strategy import SMOKE_NOTICE

__all__ = ["run_hikyuu_backtest", "register"]

#: 当前 Hikyuu 数据集中已确认存在的 ETF（用于 LEVEL A）
LEVEL_A_SYMBOLS: tuple[str, ...] = ("sh510300", "sz159934", "sh512660", "sz159745")

#: 框架版本（运行时填充）
_HIKYUU_VERSION = "unknown"


def _git_commit() -> str:
    """取当前 git commit（短），失败返回 ``unknown``。"""
    import subprocess

    # __file__ = <root>/src/backtesting/hikyuu_runner.py → 上溯 3 层为项目根
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _ensure_hikyuu_loaded(config_file: str | None = None):
    """preflight + 加载 Hikyuu，返回 (sm, preflight_report)。"""
    import hikyuu

    global _HIKYUU_VERSION
    _HIKYUU_VERSION = getattr(hikyuu, "__version__", "unknown")

    sm = hikyuu.StockManager.instance()
    if len(sm) == 0:
        # 先做结构一致性检查 —— 不一致会导致 reload 段错误（实测 exit 139）
        cfg = config_file or os.path.join(
            os.path.expanduser("~"), ".hikyuu", "hikyuu.ini"
        )
        import configparser

        dest = None
        if os.path.exists(cfg):
            p = configparser.ConfigParser()
            p.read(cfg, encoding="utf-8")
            dest = p.get("hikyuu", "datadir", fallback=None)
        report = None
        if dest:
            report = preflight(dest)  # 不一致时抛 HikyuuDataIntegrityError
        if config_file:
            hikyuu.load_hikyuu(config_file=config_file)
        else:
            hikyuu.load_hikyuu()
        sm = hikyuu.StockManager.instance()
        return sm, report
    return sm, None


def _to_hikyuu_dt(d: date):
    import hikyuu

    return hikyuu.Datetime(int(d.strftime("%Y%m%d")))


# --- TradeManager → 标准表 -------------------------------------------------


def trades_from_tm(tm, *, include_init: bool = False) -> pd.DataFrame:
    """从 ``TradeManager`` 提取成交记录。

    实测字段（Hikyuu 2.8.2 ``TradeRecord``）：
    ``datetime`` / ``stock`` / ``business`` / ``real_price``（成交价）/
    ``plan_price`` / ``number`` / ``cash`` / ``cost``（``cost.total``）/
    ``part`` / ``stoploss`` / ``goal_price`` / ``remark``。

    注意：

    - 成交价字段是 ``real_price``，**不是** ``price``。
    - 第一条记录通常是 ``BUSINESS.INIT``（初始资金建账，``number=0``），
      默认过滤掉，不计入成交。
    """
    recs = tm.get_trade_list()
    rows: list[dict] = []
    cols = [
        "datetime",
        "symbol",
        "business",
        "price",
        "number",
        "amount",
        "cash",
        "cost",
    ]
    for t in recs:
        biz_name = _business_name(getattr(t, "business", None))
        if not include_init and biz_name == "INIT":
            continue
        cost = getattr(t, "cost", None)
        total_cost = None
        if cost is not None:
            try:
                total_cost = float(cost.total)
            except Exception:  # noqa: BLE001
                total_cost = None
        d = t.datetime
        number = float(getattr(t, "number", 0.0) or 0.0)
        price = float(getattr(t, "real_price", 0.0) or 0.0)
        rows.append(
            {
                "datetime": f"{int(d.year):04d}-{int(d.month):02d}-{int(d.day):02d}",
                "symbol": str(t.stock),
                "business": biz_name,
                "price": price,
                "number": number,
                "amount": price * number,
                "cash": float(getattr(t, "cash", 0.0) or 0.0),
                "cost": total_cost,
            }
        )
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def _business_name(biz: Any) -> str:
    """把 Hikyuu BUSINESS 枚举转成可读字符串。"""
    if biz is None:
        return "UNKNOWN"
    try:
        import hikyuu

        B = hikyuu.BUSINESS
        for attr in ("INIT", "BUY", "SELL", "LIQUIDATION"):
            v = getattr(B, attr, None)
            if v is not None and biz == v:
                return attr
    except Exception:  # noqa: BLE001
        pass
    return str(biz)


def equity_curve_from_tm(tm, dates=None) -> pd.DataFrame:
    """从 ``TradeManager`` 提取资金曲线。

    实测签名：``tm.get_funds_curve(dates: DatetimeList, ktype='DAY') -> list[float]``
    —— 接受 ``DatetimeList``，**不接受** ``Query``。

    :param dates: 交易日序列（``DatetimeList``）；None 时使用
        ``tm.get_funds_list()`` 的日期（若不支持则退化为空表，
        不伪造日期）。
    """
    dl = dates
    if dl is None:
        try:
            dl = tm.get_funds_list()  # 部分版本提供
        except Exception:  # noqa: BLE001
            dl = None
    if dl is None:
        return pd.DataFrame(columns=["date", "equity"])

    values = [float(v) for v in tm.get_funds_curve(dl)]
    dates_out = list(dl)
    n = min(len(values), len(dates_out))
    return pd.DataFrame(
        {
            "date": [
                f"{int(d.year):04d}-{int(d.month):02d}-{int(d.day):02d}"
                for d in dates_out[:n]
            ],
            "equity": values[:n],
        }
    )


def _query_all(tm):
    import hikyuu

    return hikyuu.Query(tm.first_datetime, tm.last_datetime)


def _closing_dates(stk, start, end):
    """取标的在区间内的交易日（``DatetimeList``），用于资金曲线。"""
    import hikyuu

    q = hikyuu.Query(_to_hikyuu_dt(start), _to_hikyuu_dt(end))
    kd = stk.get_kdata(q)
    return kd.get_datetime_list() if len(kd) else None


def positions_from_tm(tm) -> pd.DataFrame:
    """历史持仓记录。"""
    try:
        plist = tm.get_history_position_list()
    except Exception:  # noqa: BLE001
        plist = []
    rows: list[dict] = []
    for p in plist:
        d = getattr(p, "datetime", None)
        rows.append(
            {
                "datetime": (
                    f"{int(d.year):04d}-{int(d.month):02d}-{int(d.day):02d}" if d else ""
                ),
                "symbol": str(getattr(p, "stock", "")),
                "number": float(getattr(p, "number", 0.0) or 0.0),
                "price": float(getattr(p, "price", 0.0) or 0.0),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["datetime", "symbol", "number", "price"])
    return pd.DataFrame(rows)


# --- 主链路 ---------------------------------------------------------------


def run_hikyuu_backtest(
    request: BacktestRequest,
    spec: StrategySpec,
    *,
    symbols: tuple[str, ...] | None = None,
    config_file: str | None = None,
) -> BacktestResult:
    """执行一次 Hikyuu 回测（当前为 LEVEL A smoke 链路）。

    :param symbols: 交易标的（Hikyuu 形式，如 ``sh510300``）；
        None 时使用 :data:`LEVEL_A_SYMBOLS`。
    """
    import hikyuu

    from .testing.smoke_strategy import SmokeConfig, build_smoke_system

    t0 = time.time()
    run_id = now_run_id()
    syms = symbols or LEVEL_A_SYMBOLS
    limitations = [SMOKE_NOTICE]

    sm, pf_report = _ensure_hikyuu_loaded(config_file)

    # --- 取真实 KData ---
    provider = HikyuuProvider()
    start_s, end_s = request.start.isoformat(), request.end.isoformat()
    fetched = provider.fetch_daily(list(syms), start_s, end_s)
    if not fetched:
        raise RuntimeError(
            f"未取到任何行情数据（symbols={list(syms)}, {start_s}..{end_s}）。"
            f"preflight={pf_report.summary() if pf_report else 'n/a'}"
        )

    # --- 对每个标的跑最小系统，取第一个有成交的作为主结果 ---
    chosen: str | None = None
    tm_best = None
    sys_best = None
    best_trades = -1
    sym_dates: dict[str, Any] = {}
    per_symbol: dict[str, Any] = {}
    for sym in syms:
        if sym not in fetched:
            per_symbol[sym] = {"status": "no_data"}
            continue
        # 注意：不能写 ``sym in sm`` —— 实测 StockManager.__contains__ 恒返回
        # False（Hikyuu 2.8.2），必须直接索引再检查 valid。
        try:
            stk = sm[sym]
        except Exception:  # noqa: BLE001
            per_symbol[sym] = {"status": "lookup_failed"}
            continue
        if stk is None or not getattr(stk, "valid", False):
            per_symbol[sym] = {"status": "invalid_stock"}
            continue
        q = hikyuu.Query(_to_hikyuu_dt(request.start), _to_hikyuu_dt(request.end))
        kd = stk.get_kdata(q)
        if len(kd) == 0:
            per_symbol[sym] = {"status": "empty_kdata"}
            continue
        cfg = SmokeConfig(init_cash=request.initial_cash)
        sys_obj, tm = build_smoke_system(sym, cfg)
        sys_obj.run(stk, q)
        n_trades = len(trades_from_tm(tm))
        per_symbol[sym] = {"status": "ran", "kdata_bars": len(kd), "trades": n_trades}
        # 记录每只标的的交易日，供资金曲线使用
        sym_dates[sym] = kd.get_datetime_list()
        if tm_best is None or n_trades > best_trades:
            chosen, tm_best, sys_best = sym, tm, sys_obj
            best_trades = n_trades

    if tm_best is None or sys_best is None:
        raise RuntimeError(f"所有标的均未能运行 Hikyuu 系统: {per_symbol}")
    assert chosen is not None  # 与 tm_best 同时赋值

    if chosen != syms[0]:
        limitations.append(
            f"多标的中选择 {chosen} 作为主结果（成交数最多）；"
            f"其余标的仅记录状态，未做组合级资金分配。"
        )
    if best_trades == 0:
        limitations.append(
            "选定标的在区间内未产生任何买卖成交（均线未交叉或区间过短）；"
            "trade_count=0 是真实结果，未伪造交易。"
        )

    # --- 提取结果 ---
    trades = trades_from_tm(tm_best)
    equity = equity_curve_from_tm(tm_best, sym_dates.get(chosen))
    positions = positions_from_tm(tm_best)

    final_value = float(equity["equity"].iloc[-1]) if len(equity) else None
    total_return = (
        final_value / request.initial_cash - 1.0
        if final_value is not None and request.initial_cash
        else None
    )
    # 最大回撤：从资金曲线自行计算（透明、可追溯）。
    # 不使用 tm.get_max_pull_back()：实测在未平仓状态下返回 0.0，
    # 与资金曲线的真实回撤不一致；也不使用 get_performance()，其
    # 指标在部分日期参数下返回全 0。自行计算避免这两类不可靠来源。
    max_dd = _max_drawdown(equity)
    ann_ret, vol, sharpe = _annualized(equity, request.initial_cash)

    metrics = BacktestMetrics(
        initial_cash=float(request.initial_cash),
        final_value=final_value,
        total_return=total_return,
        annual_return=ann_ret,
        max_drawdown=max_dd,
        volatility=vol,
        sharpe=sharpe,
        trade_count=int(len(trades)),
        commission=_sum_cost(trades),
        slippage=None,  # cost_func 为 crtTM 默认（TC_Zero），未单独建模滑点
        execution_time=time.time() - t0,
    )

    limitations.extend(
        [
            "复权口径：未复权（见 docs/data/market_data_policy.md）",
            "未建模涨跌停",
            "未建模停牌",
            "未做组合级资金分配（单标的运行）",
            f"框架默认交易成本（crtTM 默认 TC_Zero，即零成本）",
        ]
    )

    meta = BacktestMetadata(
        strategy=request.strategy,
        strategy_version=spec.version,
        framework="hikyuu",
        framework_version=_HIKYUU_VERSION,
        git_commit=_git_commit(),
        run_id=run_id,
        start_date=start_s,
        end_date=end_s,
        data_source="hikyuu:pytdx-hdf5",
        data_snapshot=None,
        initial_cash=float(request.initial_cash),
        commission=_sum_cost(trades),
        slippage=None,
        status="LEVEL_A_SMOKE",
        adjust_mode="none",
        limit_up_down_modeled=False,
        suspension_modeled=False,
        symbols=(chosen,),
        data_coverage={k: str(v) for k, v in (pf_report.last_dates.items() if pf_report else {})},
        limitations=tuple(limitations),
    )

    return BacktestResult(
        metadata=meta,
        metrics=metrics,
        trades=trades,
        positions=positions,
        equity_curve=equity,
        yearly_returns=pd.DataFrame(columns=["year", "return"]),
    )


def _sum_cost(trades: pd.DataFrame) -> float | None:
    if trades.empty or "cost" not in trades.columns:
        return None
    s = trades["cost"].dropna()
    return float(s.sum()) if len(s) else None


def _max_drawdown(equity: pd.DataFrame) -> float | None:
    """从资金曲线计算最大回撤（负数，如 -0.0812 表示 -8.12%）。

    公式：``min(equity / cummax(equity) - 1)``。
    数据不足（< 2 点）时返回 None，**不返回 0**。
    """
    if equity.empty or "equity" not in equity.columns or len(equity) < 2:
        return None
    import numpy as np

    a = equity["equity"].to_numpy(dtype=float)
    peak = np.maximum.accumulate(a)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peak > 0, a / peak - 1.0, 0.0)
    return float(dd.min())


def _annualized(
    equity: pd.DataFrame, initial_cash: float
) -> tuple[float | None, float | None, float | None]:
    """按日频资金曲线计算 (年化收益, 年化波动率, Sharpe)。

    - 交易日按每年 252 天折算。
    - 区间 < 60 个交易日时**不计算**（返回 ``(None, None, None)``），
      因为样本过短的年化数字没有意义，输出它会误导读者。
    - 无风险利率按 0 处理（明确记录，不做隐式假设）。
    """
    if equity.empty or len(equity) < 60:
        return None, None, None
    import numpy as np

    a = equity["equity"].to_numpy(dtype=float)
    if a[0] <= 0:
        return None, None, None
    rets = a[1:] / a[:-1] - 1.0
    rets = rets[np.isfinite(rets)]
    if len(rets) < 2:
        return None, None, None
    vol = float(rets.std(ddof=1) * np.sqrt(252))
    n_years = len(rets) / 252.0
    total = a[-1] / a[0]
    if total <= 0 or n_years <= 0:
        ann = None
    else:
        ann = float(total ** (1.0 / n_years) - 1.0)
    sharpe = float(rets.mean() / rets.std(ddof=1) * np.sqrt(252)) if rets.std(ddof=1) > 0 else None
    return ann, vol, sharpe


# --- 注册 -----------------------------------------------------------------


def register() -> None:
    """把 hikyuu 框架注册进 runner（供 ``run_backtest`` 调用）。"""
    register_framework("hikyuu", lambda req, spec: run_hikyuu_backtest(req, spec))


register()

"""LEVEL A 执行冒烟测试组件。

⚠️ **这不是投资策略，也不是正式策略。**

目的：验证 Hikyuu 执行引擎本身（KData → System → 订单 → TradeManager →
净值/交易记录）能否在**真实行情**上跑通。

它使用确定性的极简规则（固定均线交叉 + 固定手数 + 固定止损），
不对收益做任何优化，也**不得**被当作策略绩效证据。

正式策略（如 ``strategies/sw_sector_rotation``）需要申万行业数据，
本轮尚未初始化，因此不在此处出现。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SmokeConfig", "build_smoke_system", "SMOKE_NOTICE"]


#: 出现在任何 smoke 输出中的醒目声明
SMOKE_NOTICE = (
    "HIKYUU EXECUTION SMOKE TEST —— 非投资策略，仅用于验证执行链路。"
    "规则为固定均线交叉的确定性测试，未做任何参数优化，"
    "其收益数字不构成策略有效性的任何证据。"
)


@dataclass(frozen=True)
class SmokeConfig:
    """smoke 系统的确定性参数（刻意保守、固定，不做调参）。"""

    #: 快线周期
    fast_n: int = 5
    #: 慢线周期
    slow_n: int = 20
    #: 每次买入股数（ETF 以「份」计）
    buy_count: int = 1000
    #: 固定止损百分比（0.05 = 5%）
    stop_loss_pct: float = 0.05
    #: 初始资金
    init_cash: float = 100_000.0


def build_smoke_system(symbol: str, config: SmokeConfig | None = None):
    """构造一个最小可运行的 Hikyuu ``System``。

    需要 Hikyuu 已加载数据（调用方负责，且应先跑 preflight）。

    返回 ``(system, trade_manager)``。
    """
    import hikyuu

    cfg = config or SmokeConfig()

    tm = hikyuu.crtTM(init_cash=cfg.init_cash)
    # 双均线金叉买入 / 死叉卖出（确定性、无调参）
    sg = hikyuu.SG_Cross(hikyuu.MA(hikyuu.CLOSE(), cfg.fast_n),
                         hikyuu.MA(hikyuu.CLOSE(), cfg.slow_n))
    mm = hikyuu.MM_FixedCount(cfg.buy_count)
    st = hikyuu.ST_FixedPercent(cfg.stop_loss_pct)

    sys = hikyuu.SYS_Simple(tm=tm, sg=sg, mm=mm, st=st)
    sys.name = f"smoke-{symbol}"
    return sys, tm

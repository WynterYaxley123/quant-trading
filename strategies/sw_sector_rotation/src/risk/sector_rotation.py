"""行业风险过滤器 v2（生产版）。

迁移来源
--------
Legacy china-market-data v5 ``scripts/quant/risk_filter_v2.py``（生产版）。
**不迁移** ``self_improver/modules/risk_filter.py``（实验版，阈值与生产版
不一致，属 legacy 缺陷之一）。

五个风险指标
------------
1. **Market Breadth** —— 行业 close > MA20 的比例。红灯：< 0.4
2. **New High / New Low** —— 20 日新高 / 新低行业数比，0.5% 容差。红灯：< 1.0
3. **Cross-Sectional Volatility** —— 行业 5 日平均收益的横截面标准差。
   红灯：> 历史均值 + 1.5 × 标准差
4. **Volume Concentration** —— Top5 行业成交额 / 全部行业成交额。红灯：> 0.35
5. **Average Correlation** —— 过去 20 日行业收益相关性均值。红灯：< 0.2

与 Risk 状态解耦（重要设计决定）
--------------------------------
Legacy 会把所有行业分数统一乘以 ``confidence``，但这**不改变横截面排序**，
因此它对 ranking 毫无作用。迁移版本只输出 :class:`RiskState`，**不得直接
修改 ranking**。

未来如何根据 RiskState 调整总仓位（降仓 / 提现金 / 减少 Top N / 切宽基 /
停止开仓）留给 ChatGPT 后续研究，接口见
:func:`strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping.apply_risk_budget`。

对角线排除（HARD GUARDRAIL）
-----------------------------
相关性均值必须排除相关矩阵对角线。legacy 用
``np.triu(ones, k=1)`` 再取 ``[~mask]``，语义正确（下三角，不含对角线）。
本实现用更直白的写法并加**显式单元测试**，防止未来改动引入对角线污染。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

__all__ = [
    "RISK_THRESHOLDS",
    "RiskState",
    "compute_offdiag_correlation_mean",
    "compute_risk_state",
]

#: 全部阈值集中一处，便于审计与配置覆盖。
RISK_THRESHOLDS = {
    "breadth_red_below": 0.4,
    "nh_nl_red_below": 1.0,
    "cross_vol_sigma": 1.5,
    "volume_concentration_red_above": 0.35,
    "correlation_red_below": 0.2,
    "new_high_tolerance": 0.995,
    "new_low_tolerance": 1.005,
    "min_sectors": 10,
    "min_history": 25,
    "corr_lookback_days": 20,
}

_CONFIDENCE_MAP = {0: 1.0, 1: 1.0, 2: 0.85, 3: 0.70, 4: 0.70, 5: 0.70}


@dataclass(frozen=True)
class RiskState:
    """风险状态输出。**只描述状态，不修改 ranking。**

    Attributes
    ----------
    red_lights:
        红灯数量 0-5。
    confidence:
        风险置信度系数，供下游（未来）决定仓位规模。
        **注意**：直接用它缩放行业分数不会改变横截面排序。
    details:
        每项指标的红绿状态。
    metrics:
        指标原始数值，便于诊断。
    """

    red_lights: int
    confidence: float
    details: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "red_lights": self.red_lights,
            "confidence": self.confidence,
            "details": dict(self.details),
            "metrics": dict(self.metrics),
        }


def compute_offdiag_correlation_mean(corr_matrix: pd.DataFrame) -> float:
    """相关矩阵的**非对角**均值。

    显式排除对角线（k=1 的上三角 mask，取反后为下三角、不含对角线）。
    矩阵退化（< 2 个变量）或全 NaN 时返回 0.0。
    """
    values = np.asarray(corr_matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        return 0.0
    n = values.shape[0]
    upper = np.triu(np.ones((n, n), dtype=bool), k=1)
    off = values[upper]
    off = off[~np.isnan(off)]
    if off.size == 0:
        return 0.0
    return float(off.mean())


def _aligned_closes(
    prices: Mapping[str, pd.DataFrame], lookback_days: int
) -> dict[str, pd.Series]:
    end = max(p.index.max() for p in prices.values())
    start = end - pd.Timedelta(days=lookback_days * 2)
    out = {}
    for name, df in prices.items():
        mask = (df.index >= start) & (df.index <= end)
        out[name] = df.loc[mask, "close"]
    return out


def compute_risk_state(
    prices: Mapping[str, pd.DataFrame],
    *,
    thresholds: Mapping[str, float] | None = None,
    historical_cross_vols: list[float] | None = None,
) -> RiskState:
    """计算风险状态。

    参数
    ----
    prices:
        ``{sector: DataFrame(close, volume, amount)}``，index 为 DatetimeIndex。
    thresholds:
        覆盖默认阈值。
    historical_cross_vols:
        历史截面波动率序列，用于动态阈值。为 ``None`` 时阈值退化为
        ``cross_vol_mean = 0.01, cross_vol_std = 0.005``（legacy 兜底值）。

    返回
    ----
    :class:`RiskState`。行业数不足时返回 ``red_lights=0, confidence=1.0``
    并附 error 说明（与 legacy 行为一致：数据不足不误报红灯）。
    """
    th = dict(RISK_THRESHOLDS)
    if thresholds:
        th.update(dict(thresholds))

    names = list(prices.keys())
    if len(names) < th["min_sectors"]:
        return RiskState(
            red_lights=0,
            confidence=1.0,
            details={},
            metrics={"error": "insufficient data", "n_sectors": len(names)},
        )

    closes = _aligned_closes(prices, 60)

    # 1. 市场广度
    above = 0
    total = 0
    for c in closes.values():
        if len(c) < th["min_history"]:
            continue
        ma20 = c.rolling(20).mean().iloc[-1]
        last = c.iloc[-1]
        if pd.notna(ma20) and pd.notna(last) and ma20 > 0:
            if last > ma20:
                above += 1
            total += 1
    market_breadth = above / max(total, 1)

    # 2. 新高新低
    new_highs = new_lows = 0
    for c in closes.values():
        if len(c) < th["min_history"]:
            continue
        c20 = c.iloc[-20:]
        hi, lo, last = c20.max(), c20.min(), c.iloc[-1]
        if pd.isna(last) or pd.isna(hi) or pd.isna(lo):
            continue
        if last >= hi * th["new_high_tolerance"]:
            new_highs += 1
        elif last <= lo * th["new_low_tolerance"]:
            new_lows += 1
    nh_nl_ratio = new_highs / max(new_lows, 1)

    # 3. 截面波动率
    rets_5d = []
    for c in closes.values():
        if len(c) < 10:
            continue
        r = c.pct_change().dropna()
        if len(r) >= 5:
            rets_5d.append(float(r.iloc[-5:].mean()))
    cross_vol = float(np.std(rets_5d)) if len(rets_5d) > 5 else 0.0

    if historical_cross_vols:
        cv_mean = float(np.mean(historical_cross_vols))
        cv_std = float(np.std(historical_cross_vols))
    else:
        cv_mean, cv_std = 0.01, 0.005

    # 4. 成交集中度
    latest_amounts = []
    for df in prices.values():
        col = df["amount"] if "amount" in df.columns else None
        if col is None or len(col) == 0:
            continue
        last = col.iloc[-1]
        if pd.notna(last) and last > 0:
            latest_amounts.append(float(last))
    if latest_amounts:
        latest_amounts.sort(reverse=True)
        top5 = sum(latest_amounts[:5])
        vol_conc = top5 / max(sum(latest_amounts), 1.0)
    else:
        vol_conc = 0.0

    # 5. 相关性（排除对角线）
    ret_frames = {}
    for name, c in closes.items():
        r = c.pct_change().dropna()
        if len(r) >= th["corr_lookback_days"]:
            ret_frames[name] = r.iloc[-int(th["corr_lookback_days"]):]
    if len(ret_frames) >= th["min_sectors"]:
        corr_matrix = pd.DataFrame(ret_frames).corr()
        avg_corr = compute_offdiag_correlation_mean(corr_matrix)
    else:
        avg_corr = 0.0

    # 红绿灯判定
    details = {}
    red = 0
    checks = [
        ("market_breadth", market_breadth < th["breadth_red_below"]),
        ("new_highs_lows", nh_nl_ratio < th["nh_nl_red_below"]),
        ("cross_sectional_vol", cross_vol > cv_mean + th["cross_vol_sigma"] * cv_std),
        ("volume_concentration", vol_conc > th["volume_concentration_red_above"]),
        ("correlation_collapse", avg_corr < th["correlation_red_below"]),
    ]
    for key, is_red in checks:
        details[key] = "red" if is_red else "green"
        red += int(is_red)

    return RiskState(
        red_lights=red,
        confidence=_CONFIDENCE_MAP.get(red, 0.70),
        details=details,
        metrics={
            "market_breadth": round(market_breadth, 4),
            "new_high_low_ratio": round(nh_nl_ratio, 4),
            "cross_sectional_vol": round(cross_vol, 6),
            "cross_vol_mean": round(cv_mean, 6),
            "cross_vol_std": round(cv_std, 6),
            "volume_concentration": round(vol_conc, 4),
            "avg_correlation": round(avg_corr, 4),
            "above_ma20_count": above,
            "total_sectors": total,
            "new_highs": new_highs,
            "new_lows": new_lows,
        },
    )

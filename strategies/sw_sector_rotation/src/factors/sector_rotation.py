"""行业横截面因子族（SW Sector Rotation Core）。

迁移自 Legacy china-market-data v5 ``scripts/quant/predict.py::build_features``。

设计约束
--------
1. **纯函数**：输入统一 OHLCVA DataFrame（canonical market frame），
   输出因子 DataFrame。不做任何网络 I/O、不依赖 Hikyuu。
2. 全部因子只使用 **<= 当前行** 的价格，天然无未来信息。
3. 只迁移经过源码确认、且 legacy 正式模型实际使用的因子。
   被消融的动量族（m5/m20/m60/accel）与量比（vr5/vr20）**不迁移**。

Canonical market frame
----------------------
必须含列：``open, high, low, close, volume, amount``，
index 为升序 ``DatetimeIndex``。可用 :func:`validate_market_frame` 校验。

因子清单
--------
MA 位置（deviation）
    ``d5/d10/d20/d60/d120`` = (close - MA_n) / MA_n
区间位置（range position / MAPP 稳位置）
    ``p5/p10/p20/p60/p120`` = (close - min_n) / (max_n - min_n)，clip 到 [0,1]
趋势排列
    ``align`` = (MA5>MA10)*3 + (MA10>MA20)*2 + (MA20>MA60)*1，归一化 /6
波动率
    ``v5`` / ``v20`` = 日收益滚动标准差；``vc`` = v5 / (v20 + eps)
反转
    ``rev5`` / ``rev10`` = -滚动平均收益
RSI
    ``rsi`` = 14 日 RSI
回撤
    ``dd20`` / ``dd60`` = close / 滚动最高 - 1
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

__all__ = [
    "CANONICAL_COLUMNS",
    "MA_WINDOWS",
    "RANGE_WINDOWS",
    "MA_FEATURES",
    "VOL_FEATURES",
    "REV_FEATURES",
    "DD_FEATURES",
    "RSI_FEATURE",
    "RSRS_FEATURE",
    "TRAIN_FEATURES_PRICE",
    "ALL_FEATURES_PRICE",
    "validate_market_frame",
    "compute_ma_features",
    "compute_volatility_features",
    "compute_reversal_features",
    "compute_drawdown_features",
    "compute_rsi_feature",
    "compute_all_price_features",
]

CANONICAL_COLUMNS = ("open", "high", "low", "close", "volume", "amount")

MA_WINDOWS = (5, 10, 20, 60, 120)
RANGE_WINDOWS = (5, 10, 20, 60, 120)
_ALIGN_WEIGHTS = ((5, 10, 3), (10, 20, 2), (20, 60, 1))

_EPS = 1e-10

MA_FEATURES = [f"d{m}" for m in MA_WINDOWS] + [f"p{m}" for m in RANGE_WINDOWS] + ["align"]
VOL_FEATURES = ["v5", "v20", "vc"]
REV_FEATURES = ["rev5", "rev10"]
DD_FEATURES = ["dd20", "dd60"]
RSI_FEATURE = "rsi"
RSRS_FEATURE = "rsrs"

#: 价格类训练特征（不含 rsrs，rsrs 单独计算；不含 ext/funda）。
TRAIN_FEATURES_PRICE = MA_FEATURES + VOL_FEATURES + REV_FEATURES + DD_FEATURES + [RSI_FEATURE]

#: 全部价格特征（含 rsrs），供推理与诊断使用。
ALL_FEATURES_PRICE = TRAIN_FEATURES_PRICE + [RSRS_FEATURE]


def validate_market_frame(frame: pd.DataFrame) -> None:
    """校验 canonical market frame 的结构。

    要求：含全部 :data:`CANONICAL_COLUMNS`，index 为 ``DatetimeIndex``
    且严格升序（允许重复日期被拒绝）。
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"需要 DataFrame, 收到 {type(frame).__name__}")
    missing = [c for c in CANONICAL_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"market frame 缺少列: {missing}")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("market frame index 必须是 DatetimeIndex")
    if len(frame.index) and not frame.index.is_monotonic_increasing:
        raise ValueError("market frame index 必须升序排列")


# ---------------------------------------------------------------------------
# 各因子组
# ---------------------------------------------------------------------------


def compute_ma_features(frame: pd.DataFrame) -> pd.DataFrame:
    """MA 位置因子 + 区间位置因子。

    ``d{n}``: 价格相对 n 日均线的偏离度，反映趋势强度与超买超卖。
    ``p{n}``: 价格在 n 日高低区间中的相对位置（MAPP 稳位置），
              0 = 区间最低，1 = 区间最高。
    """
    c = frame["close"]
    out = pd.DataFrame(index=frame.index)
    for m in MA_WINDOWS:
        mv = c.rolling(m).mean()
        out[f"d{m}"] = (c - mv) / mv
    for m in RANGE_WINDOWS:
        hi = c.rolling(m).max()
        lo = c.rolling(m).min()
        out[f"p{m}"] = ((c - lo) / (hi - lo + _EPS)).clip(0.0, 1.0)
    return out


def compute_align_feature(frame: pd.DataFrame) -> pd.Series:
    """多头排列得分，归一化到 [0, 1]。

    权重 MA5>MA10 (3) / MA10>MA20 (2) / MA20>MA60 (1)，总分 6。
    完全多头排列 = 1.0，完全空头排列 = 0.0。
    """
    c = frame["close"]
    mas = {m: c.rolling(m).mean() for m in (5, 10, 20, 60)}
    score = sum(
        (mas[fast] > mas[slow]).astype(float) * w for fast, slow, w in _ALIGN_WEIGHTS
    )
    return score / 6.0


def compute_volatility_features(frame: pd.DataFrame) -> pd.DataFrame:
    """波动率因子。

    ``v5`` / ``v20``: 日收益的滚动标准差。
    ``vc``: 短期波动 / 中期波动，> 1 表示波动放大。
    """
    r = frame["close"].pct_change()
    out = pd.DataFrame(index=frame.index)
    out["v5"] = r.rolling(5).std()
    out["v20"] = r.rolling(20).std()
    out["vc"] = out["v5"] / (out["v20"] + _EPS)
    return out


def compute_reversal_features(frame: pd.DataFrame) -> pd.DataFrame:
    """反转因子：过去平均收益取负。"""
    r = frame["close"].pct_change()
    out = pd.DataFrame(index=frame.index)
    for p in (5, 10):
        out[f"rev{p}"] = -r.rolling(p).mean()
    return out


def compute_drawdown_features(frame: pd.DataFrame) -> pd.DataFrame:
    """回撤因子：相对过去 n 日最高点的回撤（<= 0）。"""
    c = frame["close"]
    out = pd.DataFrame(index=frame.index)
    out["dd20"] = c / c.rolling(20).max() - 1.0
    out["dd60"] = c / c.rolling(60).max() - 1.0
    return out


def compute_rsi_feature(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI（0-100），legacy 使用 14 日简单平均的改进版。"""
    r = frame["close"].pct_change()
    gains = r.clip(lower=0)
    losses = (-r).clip(lower=0)
    rs = gains.rolling(period).mean() / (losses.rolling(period).mean() + _EPS)
    return 100.0 - 100.0 / (1.0 + rs)


def compute_all_price_features(
    frame: pd.DataFrame,
    *,
    include_rsrs: bool = True,
    rsrs_n: int = 18,
    rsrs_m: int = 600,
) -> pd.DataFrame:
    """组装全部价格因子。

    ``include_rsrs=True`` 时额外计算 RSRS（需要 high/low 列）。
    RSRS 的 z-score 使用**严格滞后**窗口，不使用当前值，详见
    :mod:`strategies.sw_sector_rotation.src.factors.rsrs`。
    """
    validate_market_frame(frame)
    out = pd.concat(
        [
            compute_ma_features(frame),
            compute_volatility_features(frame),
            compute_reversal_features(frame),
            compute_drawdown_features(frame),
        ],
        axis=1,
    )
    out["align"] = compute_align_feature(frame)
    out[RSI_FEATURE] = compute_rsi_feature(frame)

    if include_rsrs:
        from strategies.sw_sector_rotation.src.factors.rsrs import compute_rsrs

        out[RSRS_FEATURE] = compute_rsrs(
            frame["close"], frame["high"], frame["low"], n=rsrs_n, m=rsrs_m
        )
    # 列顺序稳定，便于测试与序列化
    ordered = [c for c in ALL_FEATURES_PRICE if c in out.columns]
    return out[ordered]

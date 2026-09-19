"""RSRS（阻力支撑相对强度）因子。

算法来源
--------
Legacy china-market-data v5 ``scripts/quant/rsrs_factor.py``，
JoinQuant 标准 RSRS 实现，A 股已验证有效。

算法步骤
--------
1. 对每个交易日 t，取 ``[t-n+1, t]`` 的 high/low 序列做 OLS：
   ``low = alpha + beta * high``
2. 记录 ``beta_t``（斜率）与 ``R2_t``（拟合优度）。
3. 对 beta 序列做滚动 z-score，窗口为 ``[t-m, t)`` —— **严格不含 t 自身**，
   避免用当前值标准化当前值造成的前视偏差：
   ``rsrs_raw_t = (beta_t - mean(beta[t-m:t])) / std(beta[t-m:t])``
4. 右侧修正：``rsrs_t = rsrs_raw_t * beta_t * R2_t``

默认参数 ``n = 18``（回归窗口）、``m = 600``（标准化窗口，约 2.5 年交易日）。

与 legacy 的差异
----------------
legacy 用逐日 Python 循环；本实现改为逐窗口 numpy OLS，
数值结果一致但显著更快。z-score 语义与 legacy **完全相同**（均为 [t-m, t)）。

本模块是纯函数，无 I/O，无全局状态。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["compute_rsrs", "rolling_ols_beta_r2"]

_EPS = 1e-10


def rolling_ols_beta_r2(
    high: np.ndarray, low: np.ndarray, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """滚动 OLS 回归 ``low = alpha + beta * high``，返回 (beta, r2) 序列。

    位置 ``t < n-1`` 为 NaN。``var(high) ~ 0`` 时 beta/r2 记为 NaN。
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n_points = len(high)
    beta = np.full(n_points, np.nan)
    r2 = np.full(n_points, np.nan)
    if n <= 1 or n_points < n:
        return beta, r2

    for t in range(n - 1, n_points):
        h = high[t - n + 1 : t + 1]
        l = low[t - n + 1 : t + 1]
        h_mean = h.mean()
        l_mean = l.mean()
        h_d = h - h_mean
        l_d = l - l_mean
        var = float(np.dot(h_d, h_d))
        if var <= _EPS:
            continue
        b = float(np.dot(h_d, l_d)) / var
        a = l_mean - b * h_mean
        l_pred = a + b * h
        ss_res = float(np.sum((l - l_pred) ** 2))
        ss_tot = float(np.sum(l_d**2))
        beta[t] = b
        r2[t] = 1.0 - ss_res / ss_tot if ss_tot > _EPS else 0.0
    return beta, r2


def compute_rsrs(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    n: int = 18,
    m: int = 600,
) -> pd.Series:
    """计算 RSRS 修正值序列，index 与输入的公共索引对齐。

    参数
    ----
    close, high, low:
        收盘 / 最高 / 最低价序列。
    n:
        滚动 OLS 回归窗口，默认 18。
    m:
        z-score 标准化窗口，默认 600。

    返回
    ----
    ``pd.Series``，前 ``m-1`` 个位置（以及数据不足处）为 NaN。
    """
    idx = close.index.intersection(high.index).intersection(low.index)
    close = close.loc[idx]
    high = high.loc[idx].astype(float)
    low = low.loc[idx].astype(float)

    n_points = len(idx)
    if n_points < n + 10:
        return pd.Series(np.nan, index=idx, dtype=float)

    beta_arr, r2_arr = rolling_ols_beta_r2(high.values, low.values, n)
    beta_s = pd.Series(beta_arr, index=idx)
    r2_s = pd.Series(r2_arr, index=idx)

    # z-score：窗口 [t-m, t)，严格不含 t 自身
    rsrs_raw = pd.Series(np.nan, index=idx, dtype=float)
    for t in range(m, n_points):
        window = beta_s.iloc[t - m : t].dropna()
        if len(window) <= m * 0.5:
            continue
        mu = float(window.mean())
        sigma = float(window.std())
        if sigma <= _EPS:
            continue
        b_t = beta_s.iloc[t]
        if pd.notna(b_t):
            rsrs_raw.iloc[t] = (float(b_t) - mu) / sigma

    rsrs = pd.Series(np.nan, index=idx, dtype=float)
    for t in range(m, n_points):
        b_t = beta_s.iloc[t]
        r2_t = r2_s.iloc[t]
        raw = rsrs_raw.iloc[t]
        if pd.notna(b_t) and pd.notna(r2_t) and pd.notna(raw):
            rsrs.iloc[t] = float(raw) * float(b_t) * float(r2_t)
    return rsrs

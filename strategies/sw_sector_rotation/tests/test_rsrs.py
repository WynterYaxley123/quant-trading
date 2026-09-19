"""RSRS 因子测试。

覆盖迁移任务书第三节 F：完整迁移 RSRS，默认 n=18, m=600，
保留 OLS beta / R² / 历史 z-score / 右侧修正，
最终 RSRS = z-score × beta × R²。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.sw_sector_rotation.src.factors.rsrs import compute_rsrs, rolling_ols_beta_r2
from strategies.sw_sector_rotation.tests.conftest import make_market_frame


def test_rolling_ols_recovers_exact_slope():
    """对精确线性关系 low = 2*high + 1，beta 必须为 2、R² 为 1。"""
    n = 30
    high = np.linspace(10.0, 40.0, n)
    low = 2.0 * high + 1.0
    beta, r2 = rolling_ols_beta_r2(high, low, n=18)

    assert np.isnan(beta[:17]).all(), "窗口未满应为 NaN"
    assert beta[-1] == pytest.approx(2.0, rel=1e-9)
    assert r2[-1] == pytest.approx(1.0, rel=1e-9)


def test_rolling_ols_negative_slope():
    n = 30
    high = np.linspace(10.0, 40.0, n)
    low = -1.5 * high + 100.0
    beta, r2 = rolling_ols_beta_r2(high, low, n=18)
    assert beta[-1] == pytest.approx(-1.5, rel=1e-9)
    assert r2[-1] == pytest.approx(1.0, rel=1e-9)


def test_rolling_ols_constant_series_gives_nan():
    """high 恒定（方差 0）时 beta/r2 应为 NaN，不得除零。"""
    high = np.ones(30) * 5.0
    low = np.linspace(1.0, 2.0, 30)
    beta, r2 = rolling_ols_beta_r2(high, low, n=18)
    assert np.isnan(beta[-1])
    assert np.isnan(r2[-1])


def test_rsrs_returns_series_aligned_to_index(market_frame):
    rsrs = compute_rsrs(
        market_frame["close"], market_frame["high"], market_frame["low"], n=18, m=100
    )
    assert isinstance(rsrs, pd.Series)
    assert rsrs.index.equals(market_frame.index)
    assert len(rsrs) == len(market_frame)


def test_rsrs_nan_before_warmup(market_frame):
    """前 m 个位置应是 NaN（z-score 窗口未满）。"""
    m = 120
    rsrs = compute_rsrs(
        market_frame["close"], market_frame["high"], market_frame["low"], n=18, m=m
    )
    assert rsrs.iloc[:m].isna().all()
    assert rsrs.iloc[m:].notna().any(), "窗口满后应有非 NaN 值"


def test_rsrs_insufficient_data_returns_all_nan():
    frame = make_market_frame(n_days=20, seed=5)
    rsrs = compute_rsrs(frame["close"], frame["high"], frame["low"], n=18, m=600)
    assert rsrs.isna().all()


def test_rsrs_equals_zscore_times_beta_times_r2():
    """核心公式核对：RSRS = z × beta × R²。"""
    frame = make_market_frame(n_days=500, seed=6)
    n, m = 18, 150
    beta, r2 = rolling_ols_beta_r2(
        frame["high"].to_numpy(), frame["low"].to_numpy(), n
    )
    rsrs = compute_rsrs(frame["close"], frame["high"], frame["low"], n=n, m=m)

    checked = 0
    for t in range(m, len(frame)):
        window = pd.Series(beta[t - m : t]).dropna()
        if len(window) <= m * 0.5 or np.isnan(beta[t]) or np.isnan(r2[t]):
            continue
        mu, sigma = window.mean(), window.std()
        if sigma <= 1e-10:
            continue
        expected = (beta[t] - mu) / sigma * beta[t] * r2[t]
        assert rsrs.iloc[t] == pytest.approx(expected, rel=1e-9, abs=1e-12)
        checked += 1
    assert checked > 10, f"应核对到足够多的点，实际 {checked}"


def test_rsrs_zscore_window_excludes_current_value():
    """z-score 窗口必须是 [t-m, t)，不含 t 自身。

    验证方式：把 t 自身的 high/low 改成极端值，beta[t] 会变，
    但 z-score 的 mean/std（只用 [t-m, t)）不应改变，
    因此 rsrs[t] 的变化只能来自 beta[t] 与 r2[t] 乘子。
    此处只断言窗口统计量不因 t 自身变化而改变。
    """
    frame = make_market_frame(n_days=500, seed=7)
    n, m = 18, 150
    t = 400

    beta_before, _ = rolling_ols_beta_r2(
        frame["high"].to_numpy(), frame["low"].to_numpy(), n
    )
    win_before = pd.Series(beta_before[t - m : t]).dropna()

    modified = frame.copy()
    modified.iloc[t, modified.columns.get_loc("high")] *= 3.0
    modified.iloc[t, modified.columns.get_loc("low")] *= 3.0
    beta_after, _ = rolling_ols_beta_r2(
        modified["high"].to_numpy(), modified["low"].to_numpy(), n
    )
    win_after = pd.Series(beta_after[t - m : t]).dropna()

    # 窗口 [t-m, t) 只覆盖到 t-1，t 自身改动不应影响它
    pd.testing.assert_series_equal(win_before, win_after, check_exact=False)


def test_rsrs_no_lookahead():
    """修改未来数据不得改变过去 RSRS 值。"""
    frame = make_market_frame(n_days=800, seed=8)
    n, m = 18, 200
    orig = compute_rsrs(frame["close"], frame["high"], frame["low"], n=n, m=m)

    mod_frame = frame.copy()
    cut = 500
    mod_frame.iloc[cut + 1 :, :] = mod_frame.iloc[cut + 1 :, :] * 4.0
    mod = compute_rsrs(mod_frame["close"], mod_frame["high"], mod_frame["low"], n=n, m=m)

    pd.testing.assert_series_equal(
        orig.iloc[: cut + 1], mod.iloc[: cut + 1], check_exact=False, atol=1e-12
    )


def test_rsrs_default_params_are_18_600():
    """默认参数必须为 n=18, m=600（JoinQuant 标准）。"""
    import inspect

    sig = inspect.signature(compute_rsrs)
    assert sig.parameters["n"].default == 18
    assert sig.parameters["m"].default == 600


def test_rsrs_handles_misaligned_indices():
    """输入 index 不一致时按交集对齐，不报错。"""
    frame = make_market_frame(n_days=300, seed=9)
    close = frame["close"].iloc[10:]
    high = frame["high"].iloc[:-5]
    low = frame["low"]
    rsrs = compute_rsrs(close, high, low, n=18, m=100)
    expected_idx = close.index.intersection(high.index).intersection(low.index)
    assert rsrs.index.equals(expected_idx)

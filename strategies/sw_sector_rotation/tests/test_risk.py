"""风险过滤器 v2 测试。

覆盖迁移任务书第四节/第五节：
- 五指标迁移（breadth / new high-low / cross vol / volume concentration / correlation）
- correlation 必须排除对角线
- RiskState 与 ranking 解耦
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.sw_sector_rotation.src.risk.sector_rotation import (
    RISK_THRESHOLDS,
    RiskState,
    compute_offdiag_correlation_mean,
    compute_risk_state,
)
from strategies.sw_sector_rotation.tests.conftest import make_market_frame, make_sector_panel


# ---------------------------------------------------------------------------
# RiskState 结构
# ---------------------------------------------------------------------------


def test_risk_state_dataclass_shape(sector_panel):
    state = compute_risk_state(sector_panel)
    assert isinstance(state, RiskState)
    assert 0 <= state.red_lights <= 5
    assert state.confidence in (1.0, 0.85, 0.70)
    assert set(state.details) == {
        "market_breadth",
        "new_highs_lows",
        "cross_sectional_vol",
        "volume_concentration",
        "correlation_collapse",
    }
    for v in state.details.values():
        assert v in ("red", "green")
    d = state.as_dict()
    assert d["red_lights"] == state.red_lights


def test_insufficient_sectors_returns_neutral():
    """行业数 < 10 时不误报红灯。"""
    panel = make_sector_panel(n_sectors=5)
    state = compute_risk_state(panel)
    assert state.red_lights == 0
    assert state.confidence == 1.0
    assert state.metrics.get("error") == "insufficient data"


def test_confidence_mapping(sector_panel):
    """红灯数 → 置信度映射。"""
    state = compute_risk_state(sector_panel)
    expected = {0: 1.0, 1: 1.0, 2: 0.85, 3: 0.70, 4: 0.70, 5: 0.70}[state.red_lights]
    assert state.confidence == expected


# ---------------------------------------------------------------------------
# 指标 1: market breadth
# ---------------------------------------------------------------------------


def test_market_breadth_all_below_ma20_is_red():
    """全部行业跌破 MA20 时 breadth=0 → 红灯。"""
    n, days = 12, 300
    frames = {}
    for i in range(n):
        # 先涨后暴跌，确保收盘价低于 MA20
        close = np.concatenate(
            [np.linspace(100, 150, days - 30), np.linspace(150, 60, 30)]
        )
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.details["market_breadth"] == "red"
    assert state.metrics["market_breadth"] == pytest.approx(0.0)


def test_market_breadth_all_above_ma20_is_green():
    """全部行业在 MA20 上方时 breadth=1 → 绿灯。"""
    panel = make_sector_panel(n_sectors=12, n_days=300, seed=99)
    # 构造持续上涨
    frames = {}
    for i in range(12):
        close = np.linspace(100, 200, 300)
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(300) * 1e6,
                "amount": np.ones(300) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=300),
        )
    state = compute_risk_state(frames)
    assert state.details["market_breadth"] == "green"
    assert state.metrics["market_breadth"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 指标 2: new high / low
# ---------------------------------------------------------------------------


def test_new_high_low_ratio_red_when_more_lows():
    """多数行业创新低时 ratio < 1 → 红灯。"""
    days = 300
    frames = {}
    for i in range(12):
        close = np.concatenate(
            [np.linspace(50, 200, days - 40), np.linspace(200, 80, 40)]
        )
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.005,
                "low": close * 0.995,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.details["new_highs_lows"] == "red"
    assert state.metrics["new_high_low_ratio"] < 1.0


# ---------------------------------------------------------------------------
# 指标 4: volume concentration
# ---------------------------------------------------------------------------


def test_volume_concentration_red_when_top5_dominates():
    """Top5 行业成交额占比 > 0.35 → 红灯。"""
    days = 300
    frames = {}
    for i in range(12):
        close = np.linspace(100, 120, days)
        # 前 5 个行业成交额极大
        scale = 1e10 if i < 5 else 1e6
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * scale,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.metrics["volume_concentration"] > 0.35
    assert state.details["volume_concentration"] == "red"


def test_volume_concentration_green_when_evenly_distributed():
    """行业数足够多时等权分布的 Top5 占比 < 0.35 → 绿灯。

    注意：12 个行业等权时 Top5 占比恒为 5/12 ≈ 0.417 > 0.35，
    因此必须用更多行业（20 个 → 5/20 = 0.25）才能得到绿灯。
    """
    days = 300
    n_sectors = 20
    frames = {}
    for i in range(n_sectors):
        close = np.linspace(100, 120, days)
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.metrics["volume_concentration"] == pytest.approx(5 / 20, abs=1e-4)
    assert state.details["volume_concentration"] == "green"


def test_volume_concentration_math_is_exact():
    """验证占比计算本身：20 个等权行业的 Top5 占比必须恰为 0.25。"""
    days = 200
    frames = {}
    for i in range(20):
        close = np.linspace(100, 110, days)
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.metrics["volume_concentration"] == pytest.approx(0.25, abs=1e-4)


# ---------------------------------------------------------------------------
# 指标 5: correlation（对角线排除）
# ---------------------------------------------------------------------------


def test_correlation_excludes_diagonal_explicit():
    """非对角均值：3x3 矩阵非对角为 0.5,0.3,0.1 → 0.3。"""
    corr = pd.DataFrame([[1.0, 0.5, 0.3], [0.5, 1.0, 0.1], [0.3, 0.1, 1.0]])
    assert compute_offdiag_correlation_mean(corr) == pytest.approx(0.3)


def test_correlation_identity_matrix_is_zero():
    """单位阵非对角全 0。"""
    assert compute_offdiag_correlation_mean(pd.DataFrame(np.eye(5))) == 0.0


def test_correlation_not_including_diagonal_regression():
    """回归测试：如果实现错误地把对角线算进去，结果会偏高。

    全 0.5 的非对角 + 全 1 对角线 → 正确值 0.5；
    错误实现（含对角线）会得到 (6*0.5 + 3*1.0)/9 = 0.667。
    """
    corr = pd.DataFrame(np.full((3, 3), 0.5))
    np.fill_diagonal(corr.values, 1.0)
    val = compute_offdiag_correlation_mean(corr)
    assert val == pytest.approx(0.5), f"对角线未排除, 得到 {val}"
    assert val != pytest.approx(0.6667, abs=0.01)


def test_correlation_handles_nan():
    """含 NaN 的非对角元素应被忽略。"""
    corr = pd.DataFrame(
        [[1.0, 0.4, np.nan], [0.4, 1.0, 0.2], [np.nan, 0.2, 1.0]]
    )
    assert compute_offdiag_correlation_mean(corr) == pytest.approx(0.3)


def test_correlation_degenerate_inputs():
    assert compute_offdiag_correlation_mean(pd.DataFrame([[1.0]])) == 0.0
    assert compute_offdiag_correlation_mean(pd.DataFrame()) == 0.0
    assert compute_offdiag_correlation_mean(pd.DataFrame(np.array([]))) == 0.0


def test_correlation_collapse_red_when_low():
    """行业收益几乎不相关时 avg_corr 低 → 红灯。"""
    days = 300
    rng = np.random.default_rng(123)
    frames = {}
    for i in range(12):
        # 独立噪声 → 相关性接近 0
        rets = rng.normal(0, 0.01, days)
        close = 100 * np.cumprod(1 + rets)
        frames[f"S{i:02d}"] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(days) * 1e6,
                "amount": np.ones(days) * 1e8,
            },
            index=pd.bdate_range("2023-01-02", periods=days),
        )
    state = compute_risk_state(frames)
    assert state.metrics["avg_correlation"] < 0.2
    assert state.details["correlation_collapse"] == "red"


# ---------------------------------------------------------------------------
# 指标 3: cross-sectional volatility
# ---------------------------------------------------------------------------


def test_cross_sectional_vol_uses_dynamic_threshold():
    """阈值 = 历史均值 + 1.5σ，可由调用方注入。"""
    panel = make_sector_panel(n_sectors=12, n_days=300)
    low_hist = [0.001] * 20
    state_low = compute_risk_state(panel, historical_cross_vols=low_hist)
    high_hist = [0.5] * 20
    state_high = compute_risk_state(panel, historical_cross_vols=high_hist)
    # 历史波动大 → 阈值高 → 更不容易红灯
    assert state_low.metrics["cross_vol_mean"] < state_high.metrics["cross_vol_mean"]


def test_thresholds_overridable():
    """阈值可通过参数覆盖。"""
    panel = make_sector_panel(n_sectors=12, n_days=300)
    strict = compute_risk_state(
        panel, thresholds={"volume_concentration_red_above": 0.99}
    )
    loose = compute_risk_state(
        panel, thresholds={"volume_concentration_red_above": 0.0}
    )
    assert loose.red_lights >= strict.red_lights
    assert loose.details["volume_concentration"] == "red"


# ---------------------------------------------------------------------------
# 解耦：RiskState 不得修改 ranking
# ---------------------------------------------------------------------------


def test_risk_state_does_not_touch_ranking():
    """RiskState 只输出状态；核心不提供用 confidence 缩放 ranking 的路径。"""
    from pathlib import Path

    import strategies.sw_sector_rotation.src.risk.sector_rotation as mod

    src_text = Path(mod.__file__).read_text(encoding="utf-8")
    assert "confidence" in src_text  # 有置信度输出
    # 不得存在把分数乘以 confidence 的"统一缩放"逻辑
    assert "score * confidence" not in src_text
    assert "confidence *" not in src_text.replace("confidence_map", "")

    panel = make_sector_panel(n_sectors=12, n_days=300)
    state = compute_risk_state(panel)
    assert not hasattr(state, "scores")
    assert not hasattr(state, "ranking")


def test_risk_thresholds_constant_values():
    assert RISK_THRESHOLDS["breadth_red_below"] == 0.4
    assert RISK_THRESHOLDS["nh_nl_red_below"] == 1.0
    assert RISK_THRESHOLDS["cross_vol_sigma"] == 1.5
    assert RISK_THRESHOLDS["volume_concentration_red_above"] == 0.35
    assert RISK_THRESHOLDS["correlation_red_below"] == 0.2
    assert RISK_THRESHOLDS["new_high_tolerance"] == 0.995
    assert RISK_THRESHOLDS["new_low_tolerance"] == 1.005

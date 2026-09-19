"""因子族测试：MA/MAPP、波动率、反转、回撤、RSI。

覆盖迁移任务书第三节 B/C/D/E 的因子清单。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.sw_sector_rotation.src.factors.sector_rotation import (
    ALL_FEATURES_PRICE,
    MA_FEATURES,
    MA_WINDOWS,
    RANGE_WINDOWS,
    TRAIN_FEATURES_PRICE,
    compute_align_feature,
    compute_all_price_features,
    compute_drawdown_features,
    compute_ma_features,
    compute_reversal_features,
    compute_rsi_feature,
    compute_volatility_features,
    validate_market_frame,
)
from strategies.sw_sector_rotation.tests.conftest import make_market_frame


# ---------------------------------------------------------------------------
# 结构校验
# ---------------------------------------------------------------------------


def test_validate_market_frame_ok(market_frame):
    validate_market_frame(market_frame)


def test_validate_market_frame_missing_column(market_frame):
    bad = market_frame.drop(columns=["amount"])
    with pytest.raises(ValueError, match="缺少列"):
        validate_market_frame(bad)


def test_validate_market_frame_requires_datetime_index(market_frame):
    bad = market_frame.copy()
    bad.index = range(len(bad))
    with pytest.raises(TypeError, match="DatetimeIndex"):
        validate_market_frame(bad)


def test_validate_market_frame_requires_sorted(market_frame):
    bad = market_frame.iloc[::-1]
    with pytest.raises(ValueError, match="升序"):
        validate_market_frame(bad)


# ---------------------------------------------------------------------------
# MA / MAPP 因子族
# ---------------------------------------------------------------------------


def test_ma_deviation_formula(market_frame):
    """d_n = (close - MA_n) / MA_n，手工核对最后一个点。"""
    out = compute_ma_features(market_frame)
    for m in MA_WINDOWS:
        ma = market_frame["close"].rolling(m).mean()
        expected = (market_frame["close"] - ma) / ma
        pd.testing.assert_series_equal(
            out[f"d{m}"], expected, check_names=False, atol=1e-12
        )


def test_range_position_formula_and_bounds(market_frame):
    """p_n = (close - min_n) / (max_n - min_n)，必须落在 [0, 1]。"""
    out = compute_ma_features(market_frame)
    for m in RANGE_WINDOWS:
        lo = market_frame["close"].rolling(m).min()
        hi = market_frame["close"].rolling(m).max()
        expected = ((market_frame["close"] - lo) / (hi - lo + 1e-10)).clip(0, 1)
        pd.testing.assert_series_equal(
            out[f"p{m}"], expected, check_names=False, atol=1e-12
        )
        valid = out[f"p{m}"].dropna()
        assert valid.min() >= 0.0
        assert valid.max() <= 1.0


def test_ma_feature_columns_present(market_frame):
    out = compute_ma_features(market_frame)
    for col in MA_FEATURES:
        if col == "align":
            continue
        assert col in out.columns, f"缺少 {col}"
    assert len(out) == len(market_frame)


def test_align_scores_and_weights(market_frame):
    """align = 3/2/1 加权归一化，值域 [0, 1]。"""
    align = compute_align_feature(market_frame)
    valid = align.dropna()
    assert valid.min() >= 0.0
    assert valid.max() <= 1.0

    # 构造严格多头排列：MA5 > MA10 > MA20 > MA60
    n = 200
    rising = pd.DataFrame(
        {
            "open": np.arange(n) + 100.0,
            "high": np.arange(n) + 101.0,
            "low": np.arange(n) + 99.0,
            "close": np.arange(n) + 100.0,
            "volume": np.ones(n) * 1e6,
            "amount": np.ones(n) * 1e8,
        },
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    a_up = compute_align_feature(rising).iloc[-1]
    assert a_up == pytest.approx(1.0), "严格多头排列应为 1.0"

    falling = rising.iloc[::-1].copy()
    falling.index = pd.bdate_range("2023-01-02", periods=n)
    a_down = compute_align_feature(falling).iloc[-1]
    assert a_down == pytest.approx(0.0), "严格空头排列应为 0.0"


# ---------------------------------------------------------------------------
# 波动率
# ---------------------------------------------------------------------------


def test_volatility_formula(market_frame):
    out = compute_volatility_features(market_frame)
    r = market_frame["close"].pct_change()
    pd.testing.assert_series_equal(
        out["v5"], r.rolling(5).std(), check_names=False, atol=1e-12
    )
    pd.testing.assert_series_equal(
        out["v20"], r.rolling(20).std(), check_names=False, atol=1e-12
    )
    expected_vc = out["v5"] / (out["v20"] + 1e-10)
    pd.testing.assert_series_equal(out["vc"], expected_vc, check_names=False, atol=1e-12)


def test_volatility_non_negative(market_frame):
    out = compute_volatility_features(market_frame)
    assert (out["v5"].dropna() >= 0).all()
    assert (out["v20"].dropna() >= 0).all()
    assert (out["vc"].dropna() >= 0).all()


# ---------------------------------------------------------------------------
# 反转 / RSI / 回撤
# ---------------------------------------------------------------------------


def test_reversal_is_negative_mean_return(market_frame):
    out = compute_reversal_features(market_frame)
    r = market_frame["close"].pct_change()
    for p in (5, 10):
        expected = -r.rolling(p).mean()
        pd.testing.assert_series_equal(
            out[f"rev{p}"], expected, check_names=False, atol=1e-12
        )


def test_rsi_bounds(market_frame):
    rsi = compute_rsi_feature(market_frame).dropna()
    assert rsi.min() >= -1e-9
    assert rsi.max() <= 100 + 1e-9


def test_rsi_extremes():
    """单调上涨 RSI→100，单调下跌 RSI→0。"""
    n = 80
    up = pd.DataFrame(
        {"close": np.arange(n) + 100.0},
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    rsi_up = compute_rsi_feature(up).iloc[-1]
    assert rsi_up > 99.0

    down = pd.DataFrame(
        {"close": np.arange(n, 0, -1) + 0.0},
        index=pd.bdate_range("2023-01-02", periods=n),
    )
    rsi_down = compute_rsi_feature(down).iloc[-1]
    assert rsi_down < 1.0


def test_drawdown_non_positive(market_frame):
    out = compute_drawdown_features(market_frame)
    for col in ("dd20", "dd60"):
        valid = out[col].dropna()
        assert (valid <= 1e-12).all(), f"{col} 应 <= 0"
    # 回撤公式核对
    c = market_frame["close"]
    pd.testing.assert_series_equal(
        out["dd20"], c / c.rolling(20).max() - 1.0, check_names=False, atol=1e-12
    )


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------


def test_all_price_features_complete(market_frame):
    out = compute_all_price_features(market_frame, include_rsrs=True)
    for col in ALL_FEATURES_PRICE:
        assert col in out.columns, f"缺少 {col}"
    assert list(out.columns) == list(ALL_FEATURES_PRICE)
    assert len(out) == len(market_frame)


def test_all_price_features_without_rsrs(market_frame):
    out = compute_all_price_features(market_frame, include_rsrs=False)
    assert "rsrs" not in out.columns
    for col in TRAIN_FEATURES_PRICE:
        assert col in out.columns


def test_no_ablation_factors_present(market_frame):
    """已消融因子不得出现在输出中。"""
    out = compute_all_price_features(market_frame)
    for banned in ("m5", "m20", "m60", "accel", "vr5", "vr20", "flow"):
        assert banned not in out.columns, f"消融因子 {banned} 不应存在"


def test_factors_do_not_use_future_data(market_frame):
    """截断输入后，前段因子值必须一致（无未来信息）。"""
    cut = 250
    f_full = compute_all_price_features(market_frame, include_rsrs=False)
    f_part = compute_all_price_features(
        market_frame.iloc[:cut], include_rsrs=False
    )
    pd.testing.assert_frame_equal(
        f_full.iloc[:cut], f_part, check_exact=False, atol=1e-12
    )

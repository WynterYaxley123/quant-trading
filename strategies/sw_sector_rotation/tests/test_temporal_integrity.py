"""时点完整性（防未来数据泄露）测试。

对应迁移任务书第 15 节的 13 项 HARD GUARDRAILS。这些测试是未来
ChatGPT 修改策略时**不得破坏**的安全边界。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    ALLOWED_TRAIN_GROUPS,
    FORBIDDEN_TRAIN_FEATURES,
    as_of_truncate,
    assert_no_lookahead,
    inference_rows,
    make_forward_label,
    non_overlapping_periods,
    temporal_boundaries,
    trading_calendar,
    training_window,
    validate_train_features,
)
from strategies.sw_sector_rotation.tests.conftest import make_market_frame

# ---------------------------------------------------------------------------
# 1. 未来价格变化不能改变过去日期的因子
# ---------------------------------------------------------------------------


def test_future_prices_do_not_affect_past_factors():
    """修改 as_of 之后的未来价格，过去日期的因子值必须完全不变。"""
    from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features

    frame = make_market_frame(n_days=300, seed=1)
    cut_pos = 200
    cut_date = frame.index[cut_pos]

    modified = frame.copy()
    # 把 cutoff 之后的价格全部乘 10（剧烈改动）
    modified.iloc[cut_pos + 1 :, :] = modified.iloc[cut_pos + 1 :, :] * 10.0

    f_orig = compute_all_price_features(frame, include_rsrs=False)
    f_mod = compute_all_price_features(modified, include_rsrs=False)

    past = slice(None, cut_date)
    pd.testing.assert_frame_equal(f_orig.loc[past], f_mod.loc[past], check_exact=False, atol=1e-12)


# ---------------------------------------------------------------------------
# 2. 推理允许最新无标签行
# ---------------------------------------------------------------------------


def test_inference_allows_latest_unlabelled_row():
    """推理：最新一行允许标签为空。"""
    frame = make_market_frame(n_days=120, seed=2)
    labels = make_forward_label(frame["close"], 10)
    df = frame.copy()
    df["fwd10"] = labels
    assert pd.isna(df["fwd10"].iloc[-1])

    rows = inference_rows(df, df.index[-1], require_label=False)
    assert df.index[-1] in rows.index
    assert len(rows) == len(df)


# ---------------------------------------------------------------------------
# 3. 训练必须要求完整 forward label
# ---------------------------------------------------------------------------


def test_training_requires_realized_label():
    """训练：缺少 forward label 的最新行必须被排除。"""
    frame = make_market_frame(n_days=120, seed=3)
    df = frame.copy()
    df["fwd10"] = make_forward_label(frame["close"], 10)

    rows = inference_rows(df, df.index[-1], require_label=True, label_column="fwd10")
    assert len(rows) == len(df) - 10  # 最后 10 行没有已实现标签
    assert not rows["fwd10"].isna().any()


# ---------------------------------------------------------------------------
# 4. forward label 必须 purge
# ---------------------------------------------------------------------------


def test_forward_label_purge():
    """label_cutoff 的 fwd 日收益必须在 pred_date 当天已完全实现。"""
    frame = make_market_frame(n_days=300, seed=4)
    cal = trading_calendar(frame.index)
    fwd = 20
    pred_date = cal[200]

    b = temporal_boundaries(cal, pred_date, fwd, train_months=6)
    assert b is not None

    pred_pos = cal.get_loc(pred_date)
    cutoff_pos = cal.get_loc(b.label_cutoff)
    # 核心断言：cutoff 的实现日 <= pred_date
    assert cutoff_pos + fwd == pred_pos
    assert b.label_cutoff + pd.tseries.offsets.BDay(0) == b.label_cutoff
    # realized_end 落在 pred_date 之后（未来）
    assert b.realized_end > pred_date
    # train_start < label_cutoff
    assert b.train_start < b.label_cutoff


# ---------------------------------------------------------------------------
# 5. rolling window 真实限制 train_months
# ---------------------------------------------------------------------------


def test_rolling_window_respects_train_months():
    """训练窗口确实被 train_months 限制，且上限为 label_cutoff。"""
    frame = make_market_frame(n_days=600, seed=5)
    cal = trading_calendar(frame.index)
    pred_date = cal[400]

    b6 = temporal_boundaries(cal, pred_date, 20, train_months=6)
    b12 = temporal_boundaries(cal, pred_date, 20, train_months=12)
    assert b6 is not None and b12 is not None
    # 12 个月窗口起点更早（窗口更长）
    assert b12.train_start < b6.train_start

    all_dates = list(cal)
    w6 = training_window(all_dates, b6, min_observations=1)
    assert w6, "6 个月窗口应有训练日期"
    assert w6[-1] <= b6.label_cutoff
    assert w6[0] >= b6.train_start
    # 窗口内日期数远小于全部交易日（确实被限制）
    assert len(w6) < len(all_dates)


# ---------------------------------------------------------------------------
# 6. as_of 之后的价格不可见
# ---------------------------------------------------------------------------


def test_as_of_truncation_hides_future():
    frame = make_market_frame(n_days=200, seed=6)
    as_of = frame.index[150]
    truncated = as_of_truncate(frame, as_of)
    assert truncated.index.max() == as_of
    assert (truncated.index <= as_of).all()

    assert_no_lookahead(truncated, as_of)  # 不抛异常即通过

    with pytest.raises(ValueError, match="未来数据泄露"):
        assert_no_lookahead(frame, as_of)


# ---------------------------------------------------------------------------
# 7. 历史模式禁止实时资金流
# ---------------------------------------------------------------------------


def test_flow_forbidden_in_training():
    """fundamentals 与 flow 默认不得进入 TRAIN_FEATS。"""
    from strategies.sw_sector_rotation.src.factors.sector_rotation import TRAIN_FEATURES_PRICE

    validate_train_features(TRAIN_FEATURES_PRICE)  # 不抛异常

    for bad in ("flow_net", "flow_pct"):
        with pytest.raises(ValueError, match="禁止进入训练"):
            validate_train_features(list(TRAIN_FEATURES_PRICE) + [bad])


# ---------------------------------------------------------------------------
# 8. fundamentals 默认不进训练
# ---------------------------------------------------------------------------


def test_fundamentals_not_in_train_features():
    from strategies.sw_sector_rotation.src.strategy import SWSectorRotationCore

    core = SWSectorRotationCore()
    for col in ("profit_growth", "roe", "pb_inv"):
        assert col not in core.feature_names

    # 配置层面禁止开启
    from strategies.sw_sector_rotation.src.strategy import (
        SWSectorRotationConfig,
    )

    with pytest.raises(ValueError, match="include_fundamentals"):
        SWSectorRotationConfig(include_fundamentals=True)


# ---------------------------------------------------------------------------
# 9. 宏观发布时间之前不可见
# ---------------------------------------------------------------------------


def test_macro_not_visible_before_publication():
    from strategies.sw_sector_rotation.src.factors.macro_pit import (
        macro_available_at,
        publication_date,
    )

    macro_raw = pd.DataFrame(
        {
            "pmi_mfg": [50.0, 51.0, 52.0],
            "m2_yoy": [8.0, 8.5, 9.0],
            "cpi_yoy": [1.0, 1.2, 1.4],
            "lpr_1y": [3.45, 3.45, 3.40],
        },
        index=pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
    )

    # 2026-01-31 之前看不到 1 月 PMI（当月最后一天才发布）
    snap = macro_available_at("2026-01-30", macro_raw)
    assert "macro_pmi_mfg" not in snap

    # 2026-02-01 能看到 1 月 PMI
    snap = macro_available_at("2026-02-01", macro_raw)
    assert snap["macro_pmi_mfg"] == 50.0

    # M2 要等次月 12 日
    assert "macro_m2_yoy" not in macro_available_at("2026-02-10", macro_raw)
    assert macro_available_at("2026-02-12", macro_raw)["macro_m2_yoy"] == 8.0

    # CPI 次月 10 日
    assert "macro_cpi_yoy" not in macro_available_at("2026-02-09", macro_raw)
    assert macro_available_at("2026-02-10", macro_raw)["macro_cpi_yoy"] == 1.0

    # 发布日期规则本身
    assert publication_date("pmi_mfg", "2026-01-01") == pd.Timestamp("2026-01-31")
    assert publication_date("m2_yoy", "2026-01-01") == pd.Timestamp("2026-02-12")
    assert publication_date("cpi_yoy", "2026-01-01") == pd.Timestamp("2026-02-10")
    assert publication_date("lpr_1y", "2026-01-01") == pd.Timestamp("2026-01-20")


def test_parse_month_reimplemented():
    """legacy 缺失的 _parse_month 已重新实现并覆盖多种输入。"""
    from strategies.sw_sector_rotation.src.factors.macro_pit import parse_month

    assert parse_month("2026-05") == pd.Timestamp("2026-05-01")
    assert parse_month("2026/5") == pd.Timestamp("2026-05-01")
    assert parse_month("202605") == pd.Timestamp("2026-05-01")
    assert parse_month("2026-05-17") == pd.Timestamp("2026-05-01")
    assert parse_month(pd.Timestamp("2026-05-17")) == pd.Timestamp("2026-05-01")

    for bad in (None, "", "not-a-month"):
        with pytest.raises(ValueError):
            parse_month(bad)


# ---------------------------------------------------------------------------
# 10. prediction date 与 realized return 正确对齐
# ---------------------------------------------------------------------------


def test_prediction_date_aligned_with_realized_return():
    """pred_date / label_cutoff / realized_end 三者的对齐关系。

    语义区分（与 legacy ``temporal_boundaries`` 一致）：
    - ``label_cutoff`` = pred_pos - fwd：**训练标签**的最后可用日期。
      其 forward label 在 pred_date 当天已实现，即
      ``cal[cutoff_pos + fwd] == pred_date``。
    - ``realized_end`` = pred_pos + fwd：**本次预测**的目标实现日，
      位于 pred_date 之后，用于事后计算这次预测的已实现收益。
    """
    frame = make_market_frame(n_days=200, seed=10)
    fwd = 10
    labels = make_forward_label(frame["close"], fwd)
    cal = trading_calendar(frame.index)
    pos = 100
    pred_date = cal[pos]

    b = temporal_boundaries(cal, pred_date, fwd, train_months=6)
    assert b is not None

    cutoff_pos = cal.get_loc(b.label_cutoff)

    # 训练标签边界：cutoff 的 fwd 日收益恰好在 pred_date 实现
    assert cal[cutoff_pos + fwd] == pred_date
    assert cutoff_pos + fwd == pos

    # 本次预测的目标实现日落在 pred_date 之后
    assert b.realized_end == cal[pos + fwd]
    assert b.realized_end > pred_date

    # 手工核对：label[cutoff] 应等于 close[pred]/close[cutoff]-1
    manual = frame["close"].iloc[pos] / frame["close"].iloc[cutoff_pos] - 1.0
    assert labels.iloc[cutoff_pos] == pytest.approx(manual)


# ---------------------------------------------------------------------------
# 11. overlapping windows 不得用于正式 Sharpe/DD
# ---------------------------------------------------------------------------


def test_non_overlapping_periods():
    dates = pd.bdate_range("2024-01-01", periods=50)
    fwd = 10
    picked = non_overlapping_periods(dates, fwd)
    assert picked, "应挑出至少一个评估点"
    positions = [dates.get_loc(d) for d in picked]
    gaps = np.diff(positions)
    assert (gaps >= fwd).all(), f"相邻评估点间隔必须 >= {fwd}，实际 {gaps}"


# ---------------------------------------------------------------------------
# 12. RSRS z-score 窗口不得使用当前/未来值
# ---------------------------------------------------------------------------


def test_rsrs_zscore_excludes_current_and_future():
    """修改 t 之后的数据不得改变 t 及之前的 RSRS 值。"""
    from strategies.sw_sector_rotation.src.factors.rsrs import compute_rsrs

    frame = make_market_frame(n_days=900, seed=12)
    n, m = 18, 200
    orig = compute_rsrs(frame["close"], frame["high"], frame["low"], n=n, m=m)

    modified = frame.copy()
    cut = 600
    modified.iloc[cut + 1 :, :] = modified.iloc[cut + 1 :, :] * 5.0
    mod = compute_rsrs(modified["close"], modified["high"], modified["low"], n=n, m=m)

    pd.testing.assert_series_equal(
        orig.iloc[: cut + 1], mod.iloc[: cut + 1], check_exact=False, atol=1e-12
    )


def test_rsrs_zscore_uses_strictly_lagged_window():
    """RSRS 的 z-score 窗口为 [t-m, t)，不含 t 自身。"""
    from strategies.sw_sector_rotation.src.factors.rsrs import compute_rsrs, rolling_ols_beta_r2

    frame = make_market_frame(n_days=400, seed=13)
    n, m = 18, 100
    beta, r2 = rolling_ols_beta_r2(frame["high"].to_numpy(), frame["low"].to_numpy(), n)
    rsrs = compute_rsrs(frame["close"], frame["high"], frame["low"], n=n, m=m)

    t = 300
    window = pd.Series(beta[t - m : t]).dropna()
    mu, sigma = window.mean(), window.std()
    if sigma > 1e-10 and not np.isnan(beta[t]) and not np.isnan(r2[t]):
        expected = (beta[t] - mu) / sigma * beta[t] * r2[t]
        assert rsrs.iloc[t] == pytest.approx(expected, rel=1e-9, abs=1e-12)


# ---------------------------------------------------------------------------
# 13. 风险相关性计算必须排除对角线
# ---------------------------------------------------------------------------


def test_correlation_excludes_diagonal():
    from strategies.sw_sector_rotation.src.risk.sector_rotation import (
        compute_offdiag_correlation_mean,
    )

    corr = pd.DataFrame([[1.0, 0.5, 0.3], [0.5, 1.0, 0.1], [0.3, 0.1, 1.0]])
    # 非对角元素: 0.5, 0.3, 0.1 → 均值 0.3
    assert compute_offdiag_correlation_mean(corr) == pytest.approx(0.3)

    # 全 1 的对角线必须被排除：非对角为 0 时结果应为 0
    identity = pd.DataFrame(np.eye(4))
    assert compute_offdiag_correlation_mean(identity) == pytest.approx(0.0)

    # 若把对角线也算进去，均值会明显偏高，验证不是那种实现
    corr2 = pd.DataFrame(np.full((3, 3), 0.5))
    np.fill_diagonal(corr2.values, 1.0)
    assert compute_offdiag_correlation_mean(corr2) == pytest.approx(0.5)


def test_offdiag_returns_zero_for_degenerate_input():
    from strategies.sw_sector_rotation.src.risk.sector_rotation import (
        compute_offdiag_correlation_mean,
    )

    assert compute_offdiag_correlation_mean(pd.DataFrame([[1.0]])) == 0.0
    assert compute_offdiag_correlation_mean(pd.DataFrame()) == 0.0


# ---------------------------------------------------------------------------
# 附加：常量一致性
# ---------------------------------------------------------------------------


def test_train_groups_constant():
    assert set(ALLOWED_TRAIN_GROUPS) == {"ma", "vol", "rev", "dd", "macro"}
    assert "flow_net" in FORBIDDEN_TRAIN_FEATURES
    assert "profit_growth" in FORBIDDEN_TRAIN_FEATURES
    assert "roe" in FORBIDDEN_TRAIN_FEATURES

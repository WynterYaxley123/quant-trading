"""Ridge 模型测试。

覆盖迁移任务书第三节 K/L：
- 三周期 10/40/120，独立训练
- 初始超参 alpha=0.01 / train_months=6 / top_n=5
- 至少 30 个有效训练日期才允许训练
- sklearn 不存在 → NumPyRidge 兼容实现
- intercept 不做 L2 惩罚
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategies.hikyuu.sw_sector_rotation.model import (
    DEFAULT_ALPHA,
    DEFAULT_TRAIN_MONTHS,
    DEFAULT_TOP_N,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
    CrossSectionalRidgeModel,
    NumPyRidge,
)
from tests.conftest import make_named_panel


# ---------------------------------------------------------------------------
# NumPyRidge 数学正确性
# ---------------------------------------------------------------------------


def test_ridge_intercept_not_penalized():
    """intercept 不做 L2 惩罚：alpha → ∞ 时 coef→0 但 intercept 保留均值。"""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = 5.0 + X @ np.array([1.0, -2.0, 0.5]) + rng.normal(0, 0.01, 200)

    big_alpha = NumPyRidge(alpha=1e6).fit(X, y)
    assert np.allclose(big_alpha.coef_, 0.0, atol=1e-3), "大 alpha 应把系数压到 0"
    assert big_alpha.intercept_ == pytest.approx(y.mean(), abs=1e-3), (
        "intercept 不应被惩罚，必须保留 y 均值"
    )


def test_ridge_matches_closed_form():
    """与闭式解 (X^T X + aI)^-1 X^T y 逐元素一致。"""
    rng = np.random.default_rng(1)
    X = rng.normal(size=(100, 4))
    y = rng.normal(size=100)
    alpha = 0.7

    m = NumPyRidge(alpha=alpha).fit(X, y)

    Xm, ym = X.mean(axis=0), y.mean()
    Xc, yc = X - Xm, y - ym
    w = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(4), Xc.T @ yc)
    b = ym - Xm @ w

    assert np.allclose(m.coef_, w, atol=1e-10)
    assert m.intercept_ == pytest.approx(b, abs=1e-10)


def test_ridge_zero_alpha_is_ols():
    """alpha=0 时退化为普通最小二乘。"""
    rng = np.random.default_rng(2)
    X = rng.normal(size=(80, 3))
    y = rng.normal(size=80)
    m = NumPyRidge(alpha=0.0).fit(X, y)
    ols, *_ = np.linalg.lstsq(
        np.hstack([X, np.ones((len(X), 1))]), y, rcond=None
    )
    assert np.allclose(m.coef_, ols[:3], atol=1e-8)
    assert m.intercept_ == pytest.approx(ols[3], abs=1e-8)


def test_ridge_predict_shape_and_1d_input():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(50, 3))
    y = rng.normal(size=50)
    m = NumPyRidge().fit(X, y)

    assert m.predict(X).shape == (50,)
    assert m.predict(X[0]).shape == (1,)


def test_ridge_predict_before_fit_raises():
    with pytest.raises(RuntimeError, match="尚未 fit"):
        NumPyRidge().predict(np.zeros((1, 2)))


def test_ridge_feature_mismatch_raises():
    rng = np.random.default_rng(4)
    m = NumPyRidge().fit(rng.normal(size=(30, 3)), rng.normal(size=30))
    with pytest.raises(ValueError, match="特征数不匹配"):
        m.predict(np.zeros((1, 5)))


def test_ridge_negative_alpha_rejected():
    with pytest.raises(ValueError, match="alpha"):
        NumPyRidge(alpha=-1.0)


def test_ridge_singular_matrix_falls_back():
    """完全共线（奇异）时不得崩溃，应退到伪逆。"""
    x = np.linspace(0, 1, 40)
    X = np.column_stack([x, x, x])  # 完全共线
    y = 2.0 * x
    m = NumPyRidge(alpha=0.0).fit(X, y)
    pred = m.predict(X)
    assert np.all(np.isfinite(pred))
    assert np.allclose(pred, y, atol=1e-6)


def test_ridge_recovers_known_linear_relation():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(500, 4))
    true_w = np.array([1.5, -0.5, 2.0, 0.0])
    y = 3.0 + X @ true_w
    m = NumPyRidge(alpha=1e-8).fit(X, y)
    assert np.allclose(m.coef_, true_w, atol=1e-4)
    assert m.intercept_ == pytest.approx(3.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 初始超参
# ---------------------------------------------------------------------------


def test_initial_defaults_match_legacy():
    assert DEFAULT_ALPHA == 0.01
    assert DEFAULT_TRAIN_MONTHS == 6
    assert DEFAULT_TOP_N == 5
    assert FORWARD_WINDOWS == {"short": 10, "medium": 40, "long": 120}
    assert FUSION_WEIGHTS == {"short": 0.25, "medium": 0.50, "long": 0.25}
    assert MIN_TRAIN_DATES == 30


# ---------------------------------------------------------------------------
# 横截面模型
# ---------------------------------------------------------------------------


def _panel_with_factors(panel: dict) -> tuple[dict, list[str]]:
    from src.factors.sector_rotation import compute_all_price_features
    from src.common.temporal_integrity import make_forward_label

    out = {}
    feats = None
    for name, frame in panel.items():
        f = compute_all_price_features(frame, include_rsrs=False)
        for w in (10, 40, 120):
            f[f"fwd{w}"] = make_forward_label(frame["close"], w)
        out[name] = f
        if feats is None:
            feats = [c for c in f.columns if not c.startswith("fwd")]
    return out, feats


def test_fit_requires_min_train_dates():
    """有效训练日期 < 30 时不得训练。"""
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=5, n_days=200))
    model = CrossSectionalRidgeModel()
    dates = list(panel["ALPHA"].index[:MIN_TRAIN_DATES - 1])
    assert model.fit_period("short", panel, feats, dates) is None
    assert "short" not in model.models


def test_fit_period_trains_and_predicts_ranking():
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=8, n_days=400))
    model = CrossSectionalRidgeModel()
    cal = list(panel["ALPHA"].index)
    train_dates = cal[100:300]

    m = model.fit_period("short", panel, feats, train_dates)
    assert m is not None
    assert m.coef_.shape == (len(feats),)

    result = model.predict_period("short", panel, feats, cal[350])
    assert result.scores, "应有行业分数"
    assert len(result.rankings) == len(result.scores)
    ranks = [r["rank"] for r in result.rankings]
    assert ranks == sorted(ranks), "排名必须升序"
    scores = [r["score"] for r in result.rankings]
    assert scores == sorted(scores, reverse=True), "分数必须降序"
    assert result.forward_days == 10


def test_predict_period_before_fit_raises():
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=5, n_days=300))
    model = CrossSectionalRidgeModel()
    with pytest.raises(RuntimeError, match="尚未训练"):
        model.predict_period("medium", panel, feats, panel["ALPHA"].index[-1])


def test_three_periods_independent_models():
    """三周期各自独立训练，模型互不相同。"""
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=6, n_days=500))
    model = CrossSectionalRidgeModel()
    cal = list(panel["ALPHA"].index)
    train_dates = cal[150:400]

    for period in ("short", "medium", "long"):
        assert model.fit_period(period, panel, feats, train_dates) is not None
    assert set(model.models) == {"short", "medium", "long"}
    coefs = [model.models[p].coef_ for p in model.models]
    assert not np.allclose(coefs[0], coefs[2]), "不同周期系数应不同"


def test_different_horizons_produce_different_labels():
    """不同周期的标签确实不同（10/40/120）。"""
    panel, _ = _panel_with_factors(make_named_panel(n_sectors=3, n_days=300))
    f = panel["ALPHA"]
    a, b, c = f["fwd10"].dropna(), f["fwd40"].dropna(), f["fwd120"].dropna()
    assert len(a) > len(b) > len(c), "更长周期应有更少已实现标签"
    assert not np.allclose(a.iloc[: len(c)], c)


def test_fuse_periods_returns_common_sectors():
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=6, n_days=500))
    model = CrossSectionalRidgeModel()
    cal = list(panel["ALPHA"].index)
    train_dates = cal[150:400]
    pred_date = cal[450]

    results = {}
    for period in ("short", "medium", "long"):
        if model.fit_period(period, panel, feats, train_dates):
            results[period] = model.predict_period(period, panel, feats, pred_date)

    fused = model.fuse_periods(results)
    assert fused, "融合结果不应为空"
    assert len(fused) == len(panel), "所有行业都应有融合分"
    vals = [v for _, v in fused]
    assert vals == sorted(vals, reverse=True)


def test_top_n_selection():
    model = CrossSectionalRidgeModel(top_n=3)
    ranked = [("A", 3.0), ("B", 2.0), ("C", 1.0), ("D", 0.0)]
    assert len(model.top_n_sectors(ranked)) == 3
    assert model.top_n_sectors(ranked)[0][0] == "A"


def test_missing_labels_are_dropped_from_training():
    """含 NaN 标签的样本不得进入训练。"""
    panel, feats = _panel_with_factors(make_named_panel(n_sectors=5, n_days=300))
    model = CrossSectionalRidgeModel()
    cal = list(panel["ALPHA"].index)
    # 包含最后 50 天（fwd40 尚未实现）
    train_dates = cal[100:]
    m = model.fit_period("medium", panel, feats, train_dates)
    assert m is not None
    # 训练时 NaN 行被 dropna 掉，模型仍可训练
    assert np.all(np.isfinite(m.coef_))

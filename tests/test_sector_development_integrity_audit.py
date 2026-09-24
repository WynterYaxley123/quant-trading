"""Offline correctness checks for the Development-only integrity audit."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.sector_development_baseline import EXPECTED_FEATURES, evaluate_date
from research.sector_development_integrity_audit import (
    endpoint, independent_metrics, label_from_bars, ordered_top,
)
from strategies.sw_sector_rotation.src.model.model import CrossSectionalRidgeModel


def test_label_uses_same_sector_forward_close_and_exact_calendar_endpoint():
    calendar = pd.bdate_range("2025-01-01", periods=5)
    frames = {
        "A": pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 15.0]}, index=calendar),
        "B": pd.DataFrame({"close": [20.0, 18.0, 16.0, 14.0, 10.0]}, index=calendar),
    }
    assert endpoint(calendar, calendar[1], 2) == calendar[3]
    end_a, start_a, finish_a, y_a = label_from_bars(frames, calendar, "A", calendar[1], 2)
    end_b, start_b, finish_b, y_b = label_from_bars(frames, calendar, "B", calendar[1], 2)
    assert end_a == end_b == calendar[3]
    assert (start_a, finish_a, y_a) == pytest.approx((11.0, 13.0, 13 / 11 - 1))
    assert (start_b, finish_b, y_b) == pytest.approx((18.0, 14.0, 14 / 18 - 1))
    assert y_a != pytest.approx(start_a / finish_a - 1)
    assert y_b != pytest.approx(start_b / finish_b - 1)


def test_stacked_x_and_y_keep_sector_and_date_identity():
    dates = pd.bdate_range("2025-01-01", periods=3)
    panel = {
        "B": pd.DataFrame({"d5": [30.0, 40.0, 50.0],
                           "fwd10": [300.0, 400.0, 500.0]}, index=dates),
        "A": pd.DataFrame({"d5": [1.0, 2.0, 3.0],
                           "fwd10": [10.0, 20.0, 30.0]}, index=dates),
    }
    model = CrossSectionalRidgeModel(min_train_dates=1)
    actual = model.fit_period("short", panel, ["d5"], [dates[0], dates[2]])
    expected_x = np.array([[1.0], [3.0], [30.0], [50.0]])
    expected_y = np.array([10.0, 30.0, 300.0, 500.0])
    assert actual is not None
    np.testing.assert_allclose(actual.predict(expected_x),
                               model.models["short"].predict(expected_x))
    # The exact sector-major/date-order pair reproduces the fitted parameters.
    from strategies.sw_sector_rotation.src.model.model import NumPyRidge
    independent = NumPyRidge(alpha=model.alpha).fit(expected_x, expected_y)
    np.testing.assert_allclose(actual.coef_, independent.coef_, atol=1e-12, rtol=0)
    assert actual.intercept_ == pytest.approx(independent.intercept_)
    assert model.training_coverage["short"]["samples_by_date"] == {
        str(dates[0].date()): 2, str(dates[2].date()): 2}


def test_frozen_feature_order_is_explicit_and_predict_rejects_reorder():
    assert EXPECTED_FEATURES == (
        "d5", "d10", "d20", "d60", "d120", "p5", "p10", "p20", "p60",
        "p120", "align", "v5", "v20", "vc", "rev5", "rev10", "dd20",
        "dd60", "rsi")
    dates = pd.bdate_range("2025-01-01", periods=2)
    panel = {"A": pd.DataFrame({"d5": [1.0, 2.0], "d10": [3.0, 4.0],
                                 "fwd10": [0.1, 0.2]}, index=dates)}
    model = CrossSectionalRidgeModel(min_train_dates=1)
    assert model.fit_period("short", panel, ["d5", "d10"], [dates[0]]) is not None
    with pytest.raises(ValueError, match="schema/order"):
        model.predict_period("short", panel, ["d10", "d5"], dates[1])


def test_descending_rank_fused_top5_and_spread_direction():
    scores = {"B": 0.4, "A": 0.4, "C": 0.1, "D": 0.0, "E": -0.1, "F": -0.2}
    assert ordered_top(scores) == ["A", "B", "C", "D", "E"]
    metrics = independent_metrics(
        np.array([0.0, 1.0, 2.0]), np.array([0.3, 0.2, 0.1]),
        np.array([0.1, 0.2]),
    )
    assert metrics["Top5_minus_universe"] == pytest.approx(0.15 - 0.2)
    assert metrics["IC"] == pytest.approx(-1.0)


def test_registered_40_day_spread_is_top5_minus_universe_not_inverse():
    codes = [f"{i:06d}" for i in range(124)]
    scores = {code: float(i) for i, code in enumerate(codes)}
    fused = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    labels = {code: -float(i) / 1000 for i, code in enumerate(codes)}
    rows = evaluate_date(1, "2025-04-02", codes, {40: scores}, fused, {40: labels})
    values = {row["metric"]: row["value"] for row in rows}
    expected_top = np.mean([labels[code] for code, _ in fused[:5]])
    expected_universe = np.mean(list(labels.values()))
    assert values["Top5_minus_universe_40"] == pytest.approx(expected_top - expected_universe)
    assert values["Top5_minus_universe_40"] < 0

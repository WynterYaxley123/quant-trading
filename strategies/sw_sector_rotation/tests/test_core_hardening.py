"""Deterministic correctness regressions; no market-data or execution engine use."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from strategies.sw_sector_rotation import SWSectorRotationConfig, SWSectorRotationCore
from strategies.sw_sector_rotation.src.adapters.hikyuu.sector_rotation import (
    SectorWeightTarget,
    build_stock_selector_input,
    ranked_sectors_to_targets,
)
from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    make_forward_label,
    signal_timing,
    temporal_boundaries,
    validate_execution_date,
)
from strategies.sw_sector_rotation.src.factors.macro_pit import add_macro_features
from strategies.sw_sector_rotation.src.factors.sector_rotation import validate_market_frame
from strategies.sw_sector_rotation.src.model.model import CrossSectionalRidgeModel, NumPyRidge
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors, sector_scores_to_weights
from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import (
    match_etfs_for_sectors,
    normalize_scores_to_weights,
    passthrough_sector_weights,
)
from strategies.sw_sector_rotation.src.risk.sector_rotation import compute_risk_state
from strategies.sw_sector_rotation.tests.conftest import (
    make_market_frame,
    make_named_panel,
    make_sector_panel,
)


@pytest.mark.parametrize("horizon", [10, 40, 120])
def test_calendar_labels_and_purge_with_missing_sector_dates(horizon):
    cal = pd.bdate_range("2023-01-02", periods=400)
    close = pd.Series(np.arange(400, dtype=float) + 100, index=cal)
    # Missing dates used to move the endpoint beyond the calendar-based cutoff.
    sparse = close.drop(cal[81:86])
    labels = make_forward_label(sparse, horizon, calendar=cal)
    origin, end = cal[80], cal[80 + horizon]
    assert labels.loc[origin] == pytest.approx(close.loc[end] / close.loc[origin] - 1)
    b = temporal_boundaries(cal, end, horizon)
    assert b.label_cutoff == origin
    missing_endpoint = make_forward_label(close.drop(end), horizon, calendar=cal)
    assert pd.isna(missing_endpoint.loc[origin])
    visible = sparse.loc[:end]
    known = make_forward_label(visible, horizon, calendar=cal[cal <= end])
    assert known.loc[origin] == labels.loc[origin]
    assert known.loc[known.index > b.label_cutoff].isna().all()


@pytest.mark.parametrize("horizon", [10, 40, 120])
def test_latest_prediction_does_not_require_future_calendar(horizon):
    cal = pd.bdate_range("2023-01-02", periods=300)
    b = temporal_boundaries(cal, cal[-1], horizon)
    assert b is not None and b.realized_end is None
    assert b.label_cutoff == cal[-1 - horizon]
    assert b.as_dict()["realized_end"] is None


def test_after_close_execution_contract_skips_non_sessions():
    cal = pd.to_datetime(["2024-02-08", "2024-02-19", "2024-02-20"])
    timing = signal_timing(cal, cal[0], 2)
    assert timing["decision_time"] == "after_close"
    assert timing["earliest_execution_date"] == cal[1]
    assert timing["label_start"] == cal[0] and timing["label_end"] == cal[2]
    assert timing["execution_date"] is timing["holding_end"] is timing["rebalance_cadence"] is None
    validate_execution_date(cal[0], cal[1])
    for bad in (cal[0], cal[0] - pd.Timedelta(days=1), pd.NaT):
        with pytest.raises(ValueError):
            validate_execution_date(cal[0], bad)
    assert signal_timing(cal, cal[-1], 2)["earliest_execution_date"] is None


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_invalid_horizon_rejected(bad):
    close = pd.Series([100.0, 101.0], index=pd.bdate_range("2024-01-01", periods=2))
    with pytest.raises(ValueError):
        make_forward_label(close, bad)
    with pytest.raises(ValueError):
        temporal_boundaries(close.index, close.index[-1], bad)


def test_core_ranking_unchanged_by_future_prices_and_calendar():
    panel = make_named_panel(n_sectors=3, n_days=480)
    cal = panel["ALPHA"].index
    signal = cal[390]
    core = SWSectorRotationCore()
    result = core.run(panel, cal, signal)
    visible = {s: f.loc[:signal] for s, f in panel.items()}
    truncated = SWSectorRotationCore().run(visible, cal[cal <= signal], signal)
    altered = {s: f.copy() for s, f in panel.items()}
    for frame in altered.values():
        frame.loc[frame.index > signal, :] = np.nan
    changed = SWSectorRotationCore().run(altered, cal, signal)
    assert result["status"] == "RANKING_READY"
    assert result["fused_ranking"] == truncated["fused_ranking"] == changed["fused_ranking"]
    for p in ("short", "medium", "long"):
        assert result["periods"][p]["scores"] == truncated["periods"][p]["scores"]
        assert (
            result["periods"][p]["train_dates"][-1]
            <= result["periods"][p]["boundaries"].label_cutoff
        )
    assert result["target_definition"] == "absolute_close_to_close_forward_return"
    assert result["holding_period"] is result["rebalance_cadence"] is None
    assert result["risk_budget_status"] == "NOT_IMPLEMENTED"


def test_build_panel_requires_calendar_for_unequal_dates():
    panel = make_named_panel(n_sectors=2, n_days=150)
    panel["BETA"] = panel["BETA"].iloc[1:]
    with pytest.raises(ValueError, match="公共交易日历"):
        SWSectorRotationCore().build_panel(panel)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_ridge_rejects_nonfinite_fit_and_predict(bad):
    X = np.arange(80, dtype=float).reshape(40, 2)
    y = np.arange(40, dtype=float)
    broken = X.copy()
    broken[0, 0] = bad
    with pytest.raises(ValueError):
        NumPyRidge().fit(broken, y)
    by = y.copy()
    by[0] = bad
    with pytest.raises(ValueError):
        NumPyRidge().fit(X, by)
    model = NumPyRidge().fit(X, y)
    with pytest.raises(ValueError):
        model.predict(broken)
    with pytest.raises(ValueError):
        NumPyRidge(alpha=bad)


@pytest.mark.parametrize("alpha", [0.0, 0.01])
def test_ridge_constant_features_and_underdetermined_system(alpha):
    X = np.ones((4, 7))
    y = np.arange(4, dtype=float)
    m = NumPyRidge(alpha=alpha).fit(X, y)
    np.testing.assert_allclose(m.coef_, 0.0, atol=1e-12)
    np.testing.assert_allclose(m.predict(X), y.mean())
    rng = np.random.default_rng(21)
    X = rng.normal(size=(4, 7))
    m = NumPyRidge(alpha=alpha).fit(X, y)
    assert np.isfinite(m.predict(X)).all()


def test_ridge_ill_conditioned_matches_augmented_reference():
    rng = np.random.default_rng(11)
    x = rng.normal(size=80)
    X = np.column_stack((x, x + 1e-9 * rng.normal(size=80), np.ones(80)))
    y = x * 2 + 3
    model = NumPyRidge().fit(X, y)
    A = np.vstack((X - X.mean(0), np.sqrt(0.01) * np.eye(3)))
    expected = np.linalg.lstsq(A, np.r_[y - y.mean(), np.zeros(3)], rcond=None)[0]
    np.testing.assert_allclose(model.coef_, expected, atol=1e-12)


def test_ridge_extreme_values_fail_without_stale_state():
    model = NumPyRidge().fit(np.arange(20.0).reshape(10, 2), np.arange(10.0))
    with pytest.raises(ValueError):
        model.fit(np.full((10, 2), 1e308), np.arange(10.0))
    with pytest.raises(RuntimeError, match="尚未 fit"):
        model.predict([[1.0, 2.0]])


@pytest.mark.parametrize("X,y", [([], []), ([[1.0]], [[1.0]]), ([[1.0, 2.0]], [1.0, 2.0])])
def test_ridge_invalid_shapes_fail_explicitly(X, y):
    with pytest.raises(ValueError):
        NumPyRidge().fit(X, y)


def _model_panel():
    cal = pd.bdate_range("2024-01-02", periods=65)
    rng = np.random.default_rng(33)
    panel = {}
    for name in ("A", "B", "C"):
        x = rng.normal(size=(65, 2))
        panel[name] = pd.DataFrame(
            {
                "x": x[:, 0],
                "z": x[:, 1],
                "fwd10": x[:, 0] * 0.1,
                "fwd40": x[:, 1] * 0.2,
                "fwd120": x[:, 0] - x[:, 1],
            },
            index=cal,
        )
    return panel, cal


def test_feature_order_guard_and_dataframe_column_selection():
    panel, cal = _model_panel()
    model = CrossSectionalRidgeModel()
    model.fit_period("short", panel, ["x", "z"], list(cal[:50]))
    expected = model.predict_period("short", panel, ["x", "z"], cal[-1]).scores
    reordered = {s: f.loc[:, list(reversed(f.columns))] for s, f in panel.items()}
    assert model.predict_period("short", reordered, ["x", "z"], cal[-1]).scores == expected
    with pytest.raises(ValueError, match="schema/order"):
        model.predict_period("short", panel, ["z", "x"], cal[-1])
    with pytest.raises(ValueError, match="缺少 feature"):
        model.predict_period("short", {"A": panel["A"].drop(columns="x")}, ["x", "z"], cal[-1])


@pytest.mark.parametrize("features", [["x", "x"], ["fwd10"], ["sector_code"], ["flow_net"], []])
def test_bad_feature_schema_rejected(features):
    panel, cal = _model_panel()
    with pytest.raises(ValueError):
        CrossSectionalRidgeModel().fit_period("short", panel, features, list(cal[:50]))


def test_training_coverage_counts_actual_rows_and_dates():
    panel, cal = _model_panel()
    panel["B"] = panel["B"].drop(cal[0])
    panel["C"].loc[cal[1], "x"] = np.nan
    model = CrossSectionalRidgeModel()
    with pytest.warns(RuntimeWarning, match="coverage"):
        model.fit_period("short", panel, ["x", "z"], list(cal[:50]))
    c = model.training_coverage["short"]
    assert c["n_train_samples"] == 148 and c["n_train_dates"] == 50
    assert c["samples_by_date"][str(cal[0].date())] == 2
    assert c["dropped_nan_rows"]["C"] == 1
    # Thirty nominal dates / many sector samples cannot hide only 29 usable dates.
    for f in panel.values():
        f.loc[cal[29:50], "x"] = np.nan
    with pytest.warns(RuntimeWarning, match="coverage"):
        assert model.fit_period("short", panel, ["x", "z"], list(cal[:50])) is None
    assert "short" not in model.models


def test_prediction_rejects_stale_sector_and_reports_missing_features():
    panel, cal = _model_panel()
    model = CrossSectionalRidgeModel()
    model.fit_period("short", panel, ["x", "z"], list(cal[:50]))
    panel["A"] = panel["A"].iloc[:-1]
    panel["B"].loc[cal[-1], "z"] = np.nan
    with pytest.warns(RuntimeWarning, match="推理排除"):
        result = model.predict_period("short", panel, ["x", "z"], cal[-1])
    assert set(result.scores) == {"C"}
    assert result.excluded_sectors == {"A": "missing_signal_date", "B": "incomplete_features"}
    assert result.n_train_samples == 150 and result.n_train_dates == 50


def test_model_infinity_is_not_treated_as_missing():
    panel, cal = _model_panel()
    panel["A"].loc[cal[0], "fwd10"] = np.inf
    with pytest.raises(ValueError, match="Inf"):
        CrossSectionalRidgeModel().fit_period("short", panel, ["x", "z"], list(cal[:50]))


def test_entire_missing_sector_is_reported_at_inference():
    panel, cal = _model_panel()
    model = CrossSectionalRidgeModel()
    model.fit_period("short", panel, ["x", "z"], list(cal[:50]))
    del panel["B"]
    with pytest.warns(RuntimeWarning, match="missing_sector"):
        result = model.predict_period("short", panel, ["x", "z"], cal[-1])
    assert result.excluded_sectors == {"B": "missing_sector"}


def test_unavailable_boundaries_cannot_reuse_previous_model():
    core = SWSectorRotationCore()
    panel, cal = _model_panel()
    core.model.fit_period("short", panel, ["x", "z"], list(cal[:50]))
    assert core.run_period("short", panel, cal, cal[0]) is None
    assert "short" not in core.model.models
    with pytest.raises(RuntimeError, match="尚未训练"):
        core.model.predict_period("short", panel, ["x", "z"], cal[-1])


def test_core_missing_horizons_is_not_ready_and_has_no_targets():
    panel = make_named_panel(n_sectors=3, n_days=140)
    cal = panel["ALPHA"].index
    with pytest.warns(RuntimeWarning, match="horizon unavailable"):
        out = SWSectorRotationCore().run(panel, cal, cal[-1], etf_mapping={})
    assert out["status"] == "NOT_READY" and out["unavailable_horizons"]
    assert out["fused_ranking"] == out["top_sectors"] == out["etf_candidates"] == []
    assert out["mapping_status"] == "requires_validation"


def _trained_results():
    panel, cal = _model_panel()
    model = CrossSectionalRidgeModel()
    results = {}
    for period in model.forward_windows:
        model.fit_period(period, panel, ["x", "z"], list(cal[:50]))
        results[period] = model.predict_period(period, panel, ["x", "z"], cal[-1])
    return model, results


def test_unavailable_horizon_cannot_silently_change_fusion_weights():
    model, results = _trained_results()
    results.pop("long")
    with pytest.warns(RuntimeWarning, match="horizon unavailable"):
        assert model.fuse_periods(results) == []


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_horizon_score_never_becomes_zero(bad):
    model, results = _trained_results()
    results["short"].scores["A"] = bad
    with pytest.raises(ValueError, match="NaN/Inf"):
        model.fuse_periods(results)


def test_fusion_rejects_mixed_dates_and_stabilizes_ties():
    model, results = _trained_results()
    for r in results.values():
        r.scores = {"C": 1.0, "B": 1.0, "A": 1.0}
    assert model.fuse_periods(results) == [("A", 0.0), ("B", 0.0), ("C", 0.0)]
    results["long"].predict_date += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="dates"):
        model.fuse_periods(results)


def test_core_defaults_load_package_configuration():
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parents[1] / "config/sw_sector_rotation.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    core = SWSectorRotationCore()
    assert (
        core.model.fusion_weights
        == cfg["model"]["fusion_weights"]
        == {"short": 0.25, "medium": 0.5, "long": 0.25}
    )
    assert core.model.alpha == cfg["model"]["alpha"] == 0.01
    assert core.model.forward_windows == cfg["model"]["horizons"]


def test_historical_flow_rejected_and_inference_updates_fusion(monkeypatch):
    core = SWSectorRotationCore(SWSectorRotationConfig(flow_posthoc_enabled=True))
    panel = make_named_panel(n_sectors=3, n_days=400)
    cal = panel["ALPHA"].index
    with pytest.raises(ValueError, match="live_flow"):
        core.run(panel, cal, cal[-1], live_flow={"ALPHA": 1.0})
    captured = {}
    original = core.model.fuse_periods

    def capture(results):
        captured.update(results)
        return original(results)

    monkeypatch.setattr(core.model, "fuse_periods", capture)
    out = core.run(panel, cal, cal[-1], mode="inference", live_flow={"ALPHA": 1.0})
    assert out["flow_posthoc_applied"]
    for p, r in out["periods"].items():
        assert captured[p].scores == r["scores"]


def test_missing_mapping_is_visible_and_empty_etf_set_is_not_sector_trade():
    with pytest.warns(RuntimeWarning, match="missing ETF mapping: A"):
        assert match_etfs_for_sectors([("A", 1.0)], {}) == []
    assert ranked_sectors_to_targets([("A", 1.0)], []) == []


def test_duplicate_mapping_keeps_max_score_and_direct_relation():
    mapping = {"A": {"code": "E", "relation": "proxy"}, "B": {"code": "E", "relation": "direct"}}
    out = match_etfs_for_sectors([("A", 2.0), ("B", 1.0)], mapping)
    assert len(out) == 1 and out[0]["score"] == 2.0 and out[0]["relation"] == "direct"
    assert out[0]["sectors"] == ["A", "B"]


@pytest.mark.parametrize(
    "entry", [{"code": ""}, [{"code": "E1"}, {"code": "E2"}], {"code": "E", "relation": "typo"}]
)
def test_unsupported_mapping_fails_explicitly(entry):
    with pytest.raises(ValueError):
        match_etfs_for_sectors([("A", 1.0)], {"A": entry})


@pytest.mark.parametrize(
    "candidates",
    [
        [{"etf_code": "E"}, {"etf_code": "E"}],
        [{"weight": 1.0}],
        [{"etf_code": "E", "weight": -1.0}],
        [{"etf_code": "E", "weight": np.nan}],
        [{"etf_code": "E", "weight": 0.0}],
        [{"etf_code": "E", "weight": 0.2}, {"etf_code": "F"}],
    ],
)
def test_invalid_etf_candidates_cannot_reach_selector(candidates):
    with pytest.raises(ValueError):
        ranked_sectors_to_targets([], candidates)


def test_selector_requires_unique_targets_and_complete_resolver():
    with pytest.raises(ValueError, match="duplicate"):
        build_stock_selector_input([SectorWeightTarget("E", 0.5), SectorWeightTarget("E", 0.5)])
    with pytest.raises(ValueError, match="resolver"):
        build_stock_selector_input([SectorWeightTarget("E", 1.0)], {})


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_invalid_scores_never_produce_rank_or_weight(bad):
    for func, arg in (
        (rank_sectors, {"A": bad}),
        (sector_scores_to_weights, [("A", bad)]),
        (normalize_scores_to_weights, {"A": bad}),
    ):
        with pytest.raises(ValueError):
            func(arg)


@pytest.mark.parametrize("weights", [{"A": -1.0, "B": 2.0}, {"A": np.inf}, {"A": 0.0}])
def test_invalid_passthrough_weights_fail(weights):
    with pytest.raises(ValueError):
        passthrough_sector_weights({"sector_weights": weights}, list(weights))


def test_risk_as_of_is_independent_of_future_prices_and_rankings():
    panel = make_sector_panel(n_days=160)
    day = next(iter(panel.values())).index[130]
    original = deepcopy(panel)
    ranking = rank_sectors({k: float(i) for i, k in enumerate(panel)})
    saved = list(ranking)
    before = compute_risk_state(panel, as_of=day)
    for f in panel.values():
        f.loc[f.index > day, :] = np.nan
    assert compute_risk_state(panel, as_of=day).as_dict() == before.as_dict()
    assert ranking == saved
    assert SWSectorRotationCore().evaluate_risk(original, as_of=day).as_dict() == before.as_dict()


def test_stale_risk_and_insufficient_data_have_explicit_status():
    panel = make_sector_panel(n_days=50)
    panel["Sector00"] = panel["Sector00"].iloc[:-1]
    assert compute_risk_state(panel).status == "INSUFFICIENT_DATA"
    assert compute_risk_state({}).status == "INSUFFICIENT_DATA"


@pytest.mark.parametrize("kind", ["duplicate_date", "nan", "inf", "zero_close"])
def test_factor_input_invalidity_is_not_silently_filled(kind):
    f = make_market_frame(n_days=30)
    if kind == "duplicate_date":
        f = pd.concat([f, f.iloc[-1:]])
    else:
        f.iloc[0, f.columns.get_loc("close")] = {"nan": np.nan, "inf": np.inf, "zero_close": 0.0}[
            kind
        ]
    with pytest.raises(ValueError):
        validate_market_frame(f)


def test_macro_unpublished_values_stay_missing_even_for_unsorted_queries():
    raw = pd.DataFrame({"m2_yoy": [8.0]}, index=pd.to_datetime(["2024-01-01"]))
    features = pd.DataFrame({"x": [1.0, 2.0]}, index=pd.to_datetime(["2024-02-12", "2024-02-01"]))
    out = add_macro_features(features, raw)
    assert out.loc["2024-02-12", "macro_m2_yoy"] == 8.0
    assert pd.isna(out.loc["2024-02-01", "macro_m2_yoy"])
    with pytest.raises(ValueError, match="macro_enabled"):
        SWSectorRotationConfig(macro_enabled=True)

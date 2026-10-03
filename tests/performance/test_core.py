"""Business-output equality and algorithmic structure; no timing gates."""

from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from benchmarks import fixtures, reference
from research.development_panel import DevelopmentPanel
from strategies.etf_quant.mapping.liquidity import LiquidityLookup, assess_liquidity
from strategies.etf_quant.runtime.industry import build_industry_series
from strategies.etf_quant.runtime.prediction import TrainingInputs, training_rows
from strategies.etf_quant.runtime.prefix import SourcePrefixIndex, source_prefix
from strategies.etf_quant.runtime.shadow import check_prefix
from strategies.etf_quant.runtime.storage import GateError
from strategies.sw_sector_rotation.src.model import model as sw_model
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationCore


@pytest.mark.parametrize("scale", [5, 20])
def test_industry_reference_equivalence_with_snapshot_changes_and_invalid_bars(scale):
    p = fixtures.industry(24, scale)
    changed = p.tables["industry_membership"].copy()
    changed["as_of_date"] = p.sessions[12]
    changed = changed.iloc[1:]  # complete replacement removes a constituent
    p.tables["industry_membership"] = pd.concat([p.tables["industry_membership"], changed])
    p.tables["stock_bars"].loc[15, "volume"] = 0
    actual = build_industry_series(p, classification_version="SYNTHETIC")
    expected = reference.build_industry_series(p, classification_version="SYNTHETIC")
    pd.testing.assert_frame_equal(actual.closes, expected.closes, check_exact=True)
    assert actual.audit == expected.audit and actual.universe == expected.universe


@pytest.mark.parametrize(
    "fault",
    ["valid", "missing_amount", "zero_amount", "duplicate", "missing_bar", "veto", "short_history"],
)
def test_liquidity_reference_equivalence_and_no_full_scans_after_indexing(fault):
    p = fixtures.liquidity(4)
    frame = p.tables["etf_bars"]
    target = frame.index[(frame.symbol == "510000.SH") & (frame.trade_date == p.sessions[-10])][0]
    if fault == "missing_amount":
        frame.loc[target, "amount"] = None
    if fault == "zero_amount":
        frame.loc[target, "amount"] = 0
    if fault == "duplicate":
        p.tables["etf_bars"] = pd.concat([frame, frame.loc[[target]]])
    if fault == "missing_bar":
        p.tables["etf_bars"] = frame.drop(target)
    if fault == "veto":
        p.tables["trading_status"].loc[30, "is_trading"] = False
    if fault == "short_history":
        p.tables["instruments"].loc[0, "list_date"] = p.sessions[-10]
    window = p.sessions[-20:]
    expected = [reference.assess_liquidity(p, f"{510000 + i}.SH", window) for i in range(4)]
    lookup = LiquidityLookup.build(p.tables)
    with patch.object(pd.DataFrame, "to_dict", side_effect=AssertionError("table rescan")):
        actual = [assess_liquidity(p, f"{510000 + i}.SH", window, lookup=lookup) for i in range(4)]
    assert actual == expected


def test_prefix_reference_equivalence_tampering_reorder_and_content_cache():
    p = fixtures.industry(30, 5)
    cache = SourcePrefixIndex()
    expected = reference.source_prefix(p)
    assert source_prefix(p, index=cache) == expected
    with patch(
        "strategies.etf_quant.runtime.prefix.digest",
        wraps=__import__("strategies.etf_quant.runtime.prefix", fromlist=["digest"]).digest,
    ) as hashing:
        assert source_prefix(p, index=cache) == expected
        assert hashing.call_count == len(p.tables)  # cryptographic content auth, zero row rehashes
    for frame in p.tables.values():
        frame["fetched_at"] = "irrelevant observation"
    assert source_prefix(p, index=cache) == expected
    p.tables = {name: frame.iloc[::-1].copy() for name, frame in p.tables.items()}
    assert source_prefix(p, index=cache) == expected
    returned = source_prefix(p, index=cache)
    returned["stock_bars"].clear()
    assert source_prefix(p, index=cache) == expected  # caller cannot poison cache
    p.tables["stock_bars"].iloc[0, p.tables["stock_bars"].columns.get_loc("adj_close")] += 0.1
    changed = source_prefix(p, index=cache)
    assert changed == reference.source_prefix(p) and changed != expected
    with pytest.raises(GateError, match="HISTORICAL_REVISION"):
        check_prefix(expected, changed, str(p.cutoff))


def test_prediction_rows_and_raw_targets_equal_for_every_horizon():
    series, provider, features, config = fixtures.prediction()
    features[series.universe[0]].iloc[210, 0] = np.nan
    inputs = TrainingInputs.build(series, series.universe, features, config.horizons)
    for spec in config.horizons:
        expected = reference.training_rows(series, provider, spec, series.universe, features)
        with patch(
            "pandas.core.indexing._LocIndexer.__getitem__",
            side_effect=AssertionError("per-row projection"),
        ):
            actual = training_rows(series, provider, spec, series.universe, features, inputs=inputs)
        assert actual == expected


def test_training_assembly_preserves_row_identities_feature_order_and_coefficients(monkeypatch):
    frames, cal = fixtures.market()
    core = SWSectorRotationCore()
    panel = core.build_panel(frames, include_rsrs=False, calendar=cal.tolist())
    panel["0"].loc[cal[350], core.feature_names[0]] = np.nan
    dates = list(cal[300:421])

    class CaptureRidge(sw_model.NumPyRidge):
        def fit(self, x, y):
            self.training_x = np.asarray(x).copy()
            self.training_y = np.asarray(y).copy()
            return super().fit(x, y)

    monkeypatch.setattr(reference, "NumPyRidge", CaptureRidge)
    monkeypatch.setattr(sw_model, "NumPyRidge", CaptureRidge)
    old, new = sw_model.CrossSectionalRidgeModel(), sw_model.CrossSectionalRidgeModel()
    expected = reference.fit_period_reference(old, "medium", panel, core.feature_names, dates)
    actual = new.fit_period("medium", panel, core.feature_names, dates)
    assert expected is not None and actual is not None
    np.testing.assert_array_equal(expected.training_x, actual.training_x)
    np.testing.assert_array_equal(expected.training_y, actual.training_y)
    np.testing.assert_array_equal(expected.coef_, actual.coef_)
    assert old.training_coverage == new.training_coverage


@pytest.mark.parametrize("offset", [0, 30, 80])
def test_development_panel_equivalence_maturity_and_no_future_leakage(offset):
    frames, cal = fixtures.market()
    core = SWSectorRotationCore()
    cache = DevelopmentPanel(frames, cal[499])
    start, end = cal[offset], cal[399 + offset]
    visible = {c: f.loc[start:end] for c, f in frames.items()}
    expected = core.build_panel(
        visible, include_rsrs=False, calendar=cal[offset : 400 + offset].tolist()
    )
    actual = cache.visible(start, end, (10, 40, 120))
    for code in frames:
        pd.testing.assert_frame_equal(actual[code], expected[code], atol=1e-12, rtol=1e-12)
        for horizon in (10, 40, 120):
            assert actual[code][f"fwd{horizon}"].iloc[-horizon:].isna().all()
    changed = deepcopy(frames)
    for frame in changed.values():
        frame.loc[cal[500] :, "close"] *= 3
    other = DevelopmentPanel(changed, cal[499]).visible(start, end, (10, 40, 120))
    for code in frames:
        pd.testing.assert_frame_equal(actual[code], other[code], check_exact=True)

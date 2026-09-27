from datetime import date
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.config import FACTORS_19
from strategies.etf_quant.domain import Horizon, ModelPrediction
from strategies.etf_quant.factors import FACTOR_REGISTRY, compute_price_factors
from strategies.etf_quant.models.fusion import cross_sectional_zscore, fuse_predictions
from strategies.etf_quant.portfolio import AllocationStatus, RebalanceStatus, rebalance_decision, size_targets


def frame():
    rng = np.random.default_rng(73)
    close = 100 * np.cumprod(1 + rng.normal(.0001, .01, 250))
    return pd.DataFrame(dict(open=close, high=close * 1.01, low=close * .99, close=close,
                             volume=np.ones(250), amount=close), index=pd.bdate_range('2020-01-01', periods=250))


def predictions(vectors):
    return {h: tuple(ModelPrediction(h, date(2026, 1, 2), code, float(v))
                     for code, v in zip('ABCDEFG', values)) for h, values in zip(Horizon, vectors)}


def test_factor_registry_formulas_and_no_future_or_mutation():
    market = frame()
    original = market.copy(deep=True)
    factors = compute_price_factors(market)
    assert tuple(FACTOR_REGISTRY) == tuple(factors.columns) == FACTORS_19
    pd.testing.assert_frame_equal(market, original)
    pd.testing.assert_frame_equal(factors.iloc[:150], compute_price_factors(market.iloc[:150]))
    close, returns = market.close, market.close.pct_change(fill_method=None)
    for n in (5, 10, 20, 60, 120):
        np.testing.assert_allclose(factors[f'd{n}'], (close-close.rolling(n).mean())/close.rolling(n).mean(), equal_nan=True)
        np.testing.assert_allclose(factors[f'p{n}'], ((close-close.rolling(n).min()) /
            (close.rolling(n).max()-close.rolling(n).min()+1e-10)).clip(0, 1), equal_nan=True)
    for n in (5, 20): np.testing.assert_allclose(factors[f'v{n}'], returns.rolling(n).std(ddof=1), equal_nan=True)
    np.testing.assert_allclose(factors.vc, factors.v5/(factors.v20+1e-10), equal_nan=True)
    for n in (5, 10): np.testing.assert_allclose(factors[f'rev{n}'], -returns.rolling(n).mean(), equal_nan=True)
    for n in (20, 60): np.testing.assert_allclose(factors[f'dd{n}'], close/close.rolling(n).max()-1, equal_nan=True)
    ma = {n: close.rolling(n).mean() for n in (5, 10, 20, 60)}
    np.testing.assert_allclose(factors['align'], ((ma[5]>ma[10])*3+(ma[10]>ma[20])*2+(ma[20]>ma[60]))/6)
    rs = returns.clip(lower=0).rolling(14).mean()/((-returns).clip(lower=0).rolling(14).mean()+1e-10)
    np.testing.assert_allclose(factors.rsi, 100-100/(1+rs), equal_nan=True)
    assert factors.d120.iloc[:119].isna().all() and factors['align'].iloc[0] == 0


@pytest.mark.parametrize('defect', ['missing', 'nan', 'duplicate', 'reverse', 'timezone', 'negative'])
def test_factor_input_guard(defect):
    market = frame()
    if defect == 'missing': market = market.drop(columns='volume')
    if defect == 'nan': market.iloc[5, 0] = np.nan
    if defect == 'duplicate': market.index = [market.index[0]] * len(market)
    if defect == 'reverse': market = market.iloc[::-1]
    if defect == 'timezone': market.index = market.index.tz_localize('UTC')
    if defect == 'negative': market.iloc[0, 3] = -1
    with pytest.raises(ValueError): compute_price_factors(market)


def test_zscore_population_std_constant_and_extreme_finite():
    x = np.array([1., 2., 9., 4., 5.])
    np.testing.assert_allclose(cross_sectional_zscore(x), (x-x.mean())/x.std(ddof=0))
    np.testing.assert_array_equal(cross_sectional_zscore([2.] * 5), np.zeros(5))
    assert np.isfinite(cross_sectional_zscore([-1e308, 1e308, 0, 0, 0])).all()
    with pytest.raises(ValueError): cross_sectional_zscore([1, np.nan])


def test_fusion_standardizes_each_horizon_not_raw_sum():
    vectors = [[1000, 10, 4, 3, 2, 1, 0], [0, 1, 2, 3, 4, 5, 6], [1, 0, 3, 2, 5, 4, 6]]
    p = predictions(vectors)
    fused = fuse_predictions(p)
    expected = sum(w * cross_sectional_zscore(v) for w, v in zip((.25, .5, .25), vectors))
    scores = {r.industry_code:r.score for r in fused.rankings}
    np.testing.assert_allclose([scores[c] for c in 'ABCDEFG'], expected)
    raw = sum(w * np.array(v) for w, v in zip((.25, .5, .25), vectors))
    assert not np.allclose([scores[c] for c in 'ABCDEFG'], raw)
    scaled = dict(p)
    scaled[Horizon.H10] = tuple(replace(p, prediction=p.prediction*100+1234) for p in scaled[Horizon.H10])
    changed = fuse_predictions(scaled)
    np.testing.assert_allclose([r.score for r in changed.rankings], [r.score for r in fused.rankings], atol=1e-12)
    assert len(fused.top5) == 5
    assert [(r.industry_code,r.score) for r in fused.rankings] == sorted(scores.items(), key=lambda x:(-x[1],x[0]))


def test_top5_ties_are_sector_code_ascending_and_input_order_independent():
    p = predictions([[0]*7]*3)
    first = fuse_predictions(p)
    second = fuse_predictions({h:tuple(reversed(v)) for h,v in p.items()})
    assert first == second
    assert [r.industry_code for r in first.top5] == list('ABCDE')


def test_fused_dto_cannot_mislabel_horizon_date_or_universe():
    result = fuse_predictions(predictions([[0]*7]*3))
    original = result.horizon_zscores
    h, rows = original[0]
    for wrong in (rows[:-1], (*rows[:-1], rows[0]),
                  tuple(replace(p, signal_date=date(2026,1,3)) for p in rows),
                  tuple(replace(p, horizon=Horizon.H40) for p in rows)):
        with pytest.raises(ValueError):
            replace(result, horizon_zscores=((h,wrong), *original[1:]))


@pytest.mark.parametrize('defect', ['horizon', 'date', 'coverage', 'duplicate', 'small'])
def test_fusion_no_partial_universe_or_date_mix(defect):
    p = predictions([[1,2,3,4,5,6,7]]*3)
    if defect == 'horizon': del p[Horizon.H10]
    if defect == 'date': p[Horizon.H40] = tuple(replace(v, signal_date=date(2026,1,3)) for v in p[Horizon.H40])
    if defect == 'coverage': p[Horizon.H120] = p[Horizon.H120][1:]
    if defect == 'duplicate': p[Horizon.H10] = (*p[Horizon.H10],p[Horizon.H10][0])
    if defect == 'small': p = {h:v[:4] for h,v in p.items()}
    with pytest.raises(ValueError): fuse_predictions(p)


def weights(scores, **kw):
    result = size_targets(scores, **kw)
    assert result.status is AllocationStatus.READY
    return {r.asset_id:r.target_weight for r in result.targets}


def test_softmax_matches_definition_when_no_cap_binds():
    vals = np.array([.1,.2,.3,.4,.5])
    w = weights(dict(zip('ABCDE',vals)))
    np.testing.assert_allclose([w[c] for c in 'ABCDE'], np.exp(vals-vals.max())/np.exp(vals-vals.max()).sum())


@pytest.mark.parametrize('scores', [dict(zip('ABCDE',[100,0,0,0,0])),
    dict(zip('ABCDE',[1000,999,-1000,-1100,-1200])), dict(zip('ABCDE',[1e308,0,-1e308,-1e308,-1e308])),
    dict(zip('ABCDE',[-10,-10,-10,-10,-10]))])
def test_cap_redistribution_normalization_extremes_and_determinism(scores):
    w = weights(scores)
    assert w == weights(dict(reversed(list(scores.items()))))
    assert sum(w.values()) == pytest.approx(1, abs=1e-12)
    assert all(0 <= v <= .35 for v in w.values())
    if scores['A'] == 100:
        assert w['A'] == .35
        assert all(w[c] == pytest.approx(.65/4) for c in 'BCDE')


@pytest.mark.parametrize('n,status', [(0,AllocationStatus.EMPTY),(1,AllocationStatus.INFEASIBLE),
    (2,AllocationStatus.INFEASIBLE),(3,AllocationStatus.INSUFFICIENT_ASSETS),(4,AllocationStatus.INSUFFICIENT_ASSETS)])
def test_insufficient_no_fabricated_allocation(n,status):
    result = size_targets({c:1 for c in 'ABCDE'[:n]})
    assert result.status is status and result.targets == () and result.unallocated_weight == 1
    assert size_targets(dict.fromkeys('ABCDE',1),max_weight=.1).status is AllocationStatus.INFEASIBLE


def test_infeasible_cap_is_not_hidden_by_normalization_tolerance():
    scores = dict.fromkeys('ABCDE',0)
    assert size_targets(scores,max_weight=.2-1e-13).status is AllocationStatus.INFEASIBLE
    assert weights(scores,max_weight=.2) == dict.fromkeys('ABCDE',.2)


def test_rebalance_only_member_set_not_weights_or_order():
    before = tuple('ABCDE')
    assert rebalance_decision(before,tuple('EDCBA')) is RebalanceStatus.NO_REBALANCE
    assert rebalance_decision(before,tuple('ABCDF')) is RebalanceStatus.REQUIRED
    assert rebalance_decision((),before) is RebalanceStatus.REQUIRED
    old = weights(dict.fromkeys(before,0))
    new = weights(dict(zip(before,[2,1,0,-1,-2])))
    assert old != new and rebalance_decision(tuple(old),tuple(new)) is RebalanceStatus.NO_REBALANCE
    with pytest.raises(ValueError): rebalance_decision(before,tuple('ABCDD'))

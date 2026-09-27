from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant import StrategyConfig
from strategies.etf_quant.domain import Horizon, TradingCalendar
from strategies.etf_quant.models import NumPyRidge, TrainingObservation, fit_horizon, predict_industries
from strategies.etf_quant.schemas import to_primitive


def training(spec, n_dates=30):
    # Synthetic business-date fixture, not an exchange calendar/data provider.
    cal = TradingCalendar(tuple(d.date() for d in pd.bdate_range('2023-01-02',periods=450)))
    signal = datetime.combine(cal.sessions[420],datetime.min.time(),timezone.utc).replace(hour=17)
    cutoff_i = 420-int(spec.horizon)
    rng = np.random.default_rng(56+int(spec.horizon))
    rows = []
    for i in range(cutoff_i-n_dates+1,cutoff_i+1):
        end = cal.sessions[i+int(spec.horizon)]
        for j,code in enumerate('ABCDE'):
            features = tuple(rng.normal(size=len(spec.factor_names)))
            raw = float(features[0]*.1+j*.01+i*.0001)
            available = datetime.combine(end,datetime.min.time(),timezone.utc).replace(hour=16)
            rows.append(TrainingObservation(spec.horizon,code,cal.sessions[i],end,available,spec.factor_names,features,raw))
    return cal,signal,rows


def test_numpy_ridge_established_objective_intercept_determinism():
    rng = np.random.default_rng(901)
    X,y = rng.normal(size=(100,4)),rng.normal(size=100)+12
    a = NumPyRidge(.01).fit(X,y)
    b = NumPyRidge(.01).fit(X,y)
    xc,yc = X-X.mean(axis=0),y-y.mean()
    expected = np.linalg.solve(xc.T@xc+.01*np.eye(4),xc.T@yc)
    np.testing.assert_allclose(a.coef_,expected,atol=1e-12)
    assert a.intercept_ == pytest.approx(float(y.mean()-X.mean(axis=0)@expected))
    np.testing.assert_array_equal(a.coef_,b.coef_)
    assert a.intercept_ == b.intercept_
    big = NumPyRidge(1e10).fit(X,y)
    np.testing.assert_allclose(big.coef_,np.zeros(4),atol=1e-7)
    assert big.intercept_ == pytest.approx(y.mean(),abs=1e-7)
    no_intercept = NumPyRidge(.01,False).fit(X,y)
    np.testing.assert_allclose(no_intercept.coef_,np.linalg.solve(X.T@X+.01*np.eye(4),X.T@y),atol=1e-12)
    assert no_intercept.intercept_ == 0


def test_ridge_zero_alpha_collinear_and_failed_refit_invalidates():
    x = np.linspace(0,1,40)
    X = np.column_stack((x,x))
    model = NumPyRidge(0).fit(X,2*x+3)
    np.testing.assert_allclose(model.predict(X),2*x+3,atol=1e-12)
    with pytest.raises(ValueError): model.fit([[np.nan,0]],[1])
    with pytest.raises(RuntimeError): model.predict(X)
    with pytest.raises(ValueError): NumPyRidge(float('inf'))
    with pytest.raises(ValueError): NumPyRidge(-1)


@pytest.mark.parametrize('h',list(Horizon))
def test_horizon_metadata_excess_target_feature_order_and_window(h):
    spec = next(s for s in StrategyConfig().horizons if s.horizon is h)
    cal,signal,rows = training(spec)
    model = fit_horizon(spec,rows,calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))
    raw = np.array([r.raw_forward_return for r in rows]).reshape(30,5)
    target = (raw-raw.mean(axis=1,keepdims=True)).ravel()
    expected = NumPyRidge(.01).fit([r.features for r in rows],target)
    np.testing.assert_array_equal(model.coefficients,expected.coef_)
    assert model.intercept == expected.intercept_
    assert model.training.training_day_count == 30 and model.training.sample_count == 150
    assert model.training.label_cutoff == cal.sessions[420-int(h)]
    assert model.training.window_start == (pd.Timestamp(model.training.label_cutoff)-pd.DateOffset(months=6)).date()
    assert model.training.training_start == rows[0].observation_date
    assert model.training.training_end == rows[-1].observation_date
    assert model.training.target_identity == 'SAME_DATE_CROSS_SECTIONAL_EXCESS_FORWARD_RETURN'
    assert tuple(n for n,_ in model.named_coefficients) == spec.factor_names
    repeated = fit_horizon(spec,list(reversed(rows)),calendar=cal,signal_at=signal,industry_universe=tuple('EDCBA'))
    assert repeated == model
    values = predict_industries(model,{c:rows[j].features for j,c in enumerate('ABCDE')},
        factor_names=spec.factor_names,signal_date=signal.date())
    assert all(p.horizon is h and p.signal_date == signal.date() for p in values)
    assert len(to_primitive(model)['coefficients']) == len(spec.factor_names)
    with pytest.raises(ValueError): predict_industries(model,{'A':rows[0].features},
        factor_names=tuple(reversed(spec.factor_names)),signal_date=signal.date())


def test_independent_horizons_no_shared_state():
    models = []
    for spec in StrategyConfig().horizons:
        cal,signal,rows = training(spec)
        models.append(fit_horizon(spec,rows,calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE')))
    assert len({id(m) for m in models}) == 3
    assert len(models[0].coefficients) == 5 and len(models[1].coefficients) == len(models[2].coefficients) == 19
    assert models[1].coefficients != models[2].coefficients
    old = tuple(models)
    spec = StrategyConfig().horizons[0]
    cal,signal,rows = training(spec)
    changed = fit_horizon(spec,[replace(r,raw_forward_return=r.raw_forward_return*2) for r in rows],
        calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))
    assert changed.coefficients != models[0].coefficients and tuple(models) == old


def test_fitted_model_and_training_dto_guards():
    spec = StrategyConfig().horizons[0]
    cal,signal,rows = training(spec)
    model = fit_horizon(spec,rows,calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))
    for changes in ({'coefficients':model.coefficients[:-1]}, {'coefficients':list(model.coefficients)},
                    {'intercept':np.nan}, {'coefficients':(np.inf,*model.coefficients[1:])},
                    {'spec':StrategyConfig().horizons[1]}):
        with pytest.raises(ValueError): replace(model,**changes)
    for changes in ({'training_day_count':29}, {'sample_count':1}, {'training_end':signal.date()},
                    {'window_start':model.training.training_start}, {'feature_preprocessing':'SCALED'}):
        with pytest.raises(ValueError): replace(model.training,**changes)


@pytest.mark.parametrize('defect',['few_dates','unknown_available','future_available','bad_end','early_available',
                                  'feature_order','missing_sector','duplicate','nan','wrong_horizon'])
def test_training_safeguards(defect):
    spec = StrategyConfig().horizons[0]
    cal,signal,rows = training(spec,29 if defect=='few_dates' else 30)
    if defect=='unknown_available': rows[0] = replace(rows[0],available_at=None)
    if defect=='future_available': rows[0] = replace(rows[0],available_at=signal+pd.Timedelta(days=1))
    if defect=='bad_end': rows[0] = replace(rows[0],label_end=rows[0].observation_date)
    if defect=='early_available': rows[0] = replace(rows[0],available_at=signal-pd.Timedelta(days=1000))
    if defect=='feature_order': rows[0] = replace(rows[0],factor_names=tuple(reversed(spec.factor_names)))
    if defect=='missing_sector': rows = rows[1:]
    if defect=='duplicate': rows.append(rows[0])
    if defect=='nan': rows[0] = replace(rows[0],raw_forward_return=np.nan)
    if defect=='wrong_horizon': rows[0] = replace(rows[0],horizon=Horizon.H40)
    with pytest.raises(ValueError): fit_horizon(spec,rows,calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))


def test_unmatured_and_outside_window_values_cannot_influence_fit():
    spec = StrategyConfig().horizons[0]
    cal,signal,rows = training(spec)
    clean = fit_horizon(spec,rows,calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))
    future = replace(rows[0],observation_date=signal.date(),label_end=None,available_at=None,
                     features=tuple(np.nan for _ in spec.factor_names),raw_forward_return=np.nan)
    ancient = replace(future,observation_date=cal.sessions[0])
    result = fit_horizon(spec,[future,ancient,*rows],calendar=cal,signal_at=signal,industry_universe=tuple('ABCDE'))
    assert result == clean

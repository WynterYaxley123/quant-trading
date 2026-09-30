"""Synthetic conformance to the successful Source-C engineering path."""
from dataclasses import replace
from datetime import timedelta
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.domain import StrategyConfig
from strategies.etf_quant.runtime.industry import build_industry_series
from strategies.etf_quant.runtime import model_inputs
from strategies.etf_quant.runtime.prediction import (current_predictions, model_features,
    model_readiness_reference, training_rows)
from strategies.etf_quant.runtime.storage import GateError, digest
from test_exports_industry import industry_provider, make_export, ExportProvider, IDENTITY, NOW

def audit_module(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source(n=500):
    p = industry_provider(n)
    return p, build_industry_series(p, classification_version="SWCLASS2021")


def test_production_scores_match_successful_engineering_fit_math():
    p, s = source()
    models, predictions, fused = current_predictions(s, p, signal_at=p.created_at+timedelta(minutes=1))
    reference = model_readiness_reference(s, p)
    for h, model in models.items():
        r = reference["horizons"][str(int(h))]
        assert r["unique_valid_dates"] == model.training.training_day_count
        assert r["valid_observations"] == model.training.sample_count
        np.testing.assert_allclose(model.coefficients, list(r["coefficients"].values()), rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose([q.prediction for q in predictions[h]], list(r["raw_predictions"].values()))
    assert [r.industry_code for r in fused.rankings] == [r["industry_code"] for r in reference["ranking"]]


def test_partial_taxonomy_and_retired_nonadmitted_row_do_not_veto_model_dates():
    p, s = source()
    admitted = s.universe
    closes = s.closes.copy(); closes["9999"] = np.nan  # explicitly nonadmitted synthetic historical code
    s = replace(s, closes=closes, universe=(*admitted, "9999"))
    p.model_input_contract = {"industries": list(admitted)}
    r = model_readiness_reference(s, p)
    assert all(m["status"] == "PASS" and m["valid_sectors"] == 5 for m in r["horizons"].values())
    assert "9999" not in r["universe"]
    del p.model_input_contract
    with pytest.raises(GateError, match="WARMUP"):
        model_readiness_reference(s, p)


def test_partial_admitted_cross_section_is_still_rejected_as_a_whole_date():
    p, s = source()
    spec = StrategyConfig().horizons[0]
    universe, features = model_features(s, p)
    before, count = training_rows(s, p, spec, universe, features)
    day = s.closes.index[-1-int(spec.horizon)]
    features[universe[0]].loc[day, spec.factor_names[0]] = np.nan
    after, result = training_rows(s, p, spec, universe, features)
    assert result["unique_valid_dates"] == count["unique_valid_dates"]-1
    assert len(after) == len(before)-len(universe)
    assert all(r.observation_date != day.date() for r in after)


@pytest.mark.parametrize("h", [10,40,120])
@pytest.mark.parametrize("dates,ready", [(29,False),(30,True)])
def test_date_sector_observations_maturity_and_minimum_unique_dates(h, dates, ready):
    p, s = source(h+dates)
    spec = next(x for x in StrategyConfig().horizons if int(x.horizon)==h)
    universe = s.universe
    features = {c:pd.DataFrame(1.,index=s.closes.index,columns=spec.factor_names) for c in universe}
    rows, result = training_rows(s, p, spec, universe, features)
    assert len(rows)==dates*len(universe)
    assert result["unique_valid_dates"]==dates and (result["status"]=="PASS") is ready
    assert max(r.label_end for r in rows)==p.cutoff
    assert all(r.label_end<=p.cutoff and r.available_at==p.created_at for r in rows)


def test_per_sector_min_constituents_and_recursive_isolation_match_reference():
    p = industry_provider(4)
    bars = p.tables["stock_bars"]
    p.tables["stock_bars"] = bars.loc[~(bars.symbol.isin(["SYN_0_0","SYN_0_1"]) & (bars.trade_date==p.sessions[1]))]
    s = build_industry_series(p,classification_version="SWCLASS2021")
    assert np.isnan(s.closes.iloc[1:,0]).all()
    assert np.isfinite(s.closes.iloc[:,1:]).all().all()
    reference = audit_module("audit_etf_quant_readiness.py")
    state = {}
    code=s.universe[0]
    for i,d in enumerate(p.sessions):
        rows=[]
        for symbol in sorted(p.tables["industry_membership"].query("symbol.str.startswith('SYN_0_')",engine="python").symbol):
            current=p.tables["stock_bars"].query("symbol==@symbol and trade_date==@d")
            previous_day=p.sessions[i-1] if i else None
            previous=p.tables["stock_bars"].loc[(p.tables["stock_bars"].symbol==symbol) &
                (p.tables["stock_bars"].trade_date==previous_day)] if i else current.iloc[:0]
            rows.append({"symbol":symbol,"bar_valid":str(not current.empty),"adj_is_exact":"True",
                "adj_close":str(current.iloc[0].adj_close) if not current.empty else "",
                "prev_adj_close":str(previous.iloc[0].adj_close) if not previous.empty else "",
                "return_valid":str(not current.empty and not previous.empty)})
        r=reference.advance_source_c(state,d,code,rows)
        assert r["source_c_valid"] is bool(np.isfinite(s.closes.loc[pd.Timestamp(d),code]))


def test_complete_membership_snapshot_replaces_removed_constituents():
    p=industry_provider(3)
    first=p.tables["industry_membership"]
    second=first.loc[first.symbol!='SYN_0_0'].copy();second['as_of_date']=p.sessions[1]
    p.tables['industry_membership']=pd.concat([first,second],ignore_index=True)
    s=build_industry_series(p,classification_version='SWCLASS2021')
    row=next(r for r in s.audit if r['trade_date']==str(p.sessions[1]) and r['industry_code']==s.universe[0])
    assert row['eligible_members']==row['valid_constituents']==5
    assert row['coverage']==1 and row['status']=='VALID'


def test_unknown_historical_publication_does_not_veto_asof_bootstrap():
    p=industry_provider(3)
    seed=p.tables['industry_membership'].copy();seed['as_of_date']=p.sessions[0]-timedelta(days=1)
    p.tables['industry_membership']['as_of_date']=p.sessions[1]
    p.model_membership_seed=seed
    p.model_input_contract={'warmup_start':str(p.sessions[0])}
    s=build_industry_series(p,classification_version='SWCLASS2021')
    assert np.isfinite(s.closes).all().all()
    assert all(r['available_at'] is None and r['source_published_at'] is None for r in s.audit)
    assert s.quality_flag=='HISTORICAL_MEMBERSHIP_PIT_UNPROVEN'


def test_fixed_classification_cannot_replace_approved_source_c_asof_contract(tmp_path):
    doc=json.loads(model_inputs.CONTRACT_PATH.read_bytes())
    doc['classification_mode']='MODEL_FIXED_CLASSIFICATION'
    path=tmp_path/'SYNTHETIC.json';path.write_text(json.dumps(doc))
    with pytest.raises(GateError,match='MODEL_INPUT_CONTRACT'):
        model_inputs.load_model_contract(path)


def test_model_readiness_does_not_lower_execution_pit_gate(tmp_path):
    from test_formal_shadow import setup, run
    p,reg,book,contract=setup(tmp_path)
    future=replace(contract,available_from=(p.created_at+timedelta(hours=2)).isoformat())
    root=tmp_path/'SYNTHETIC_FORMAL'
    assert run(p,reg,book,future,root)['status']=='WAITING_FOR_PIT_EVIDENCE'
    assert not root.exists()


def test_bootstrap_bytes_guard_and_null_publication_are_preserved(tmp_path,monkeypatch):
    path,_=make_export(tmp_path)
    p=ExportProvider(path,expected_identity=IDENTITY,now=NOW)
    m=json.loads((path/'manifest.json').read_bytes())
    contract={'reference_snapshot_id':path.name,'reference_manifest_sha256':digest((path/'manifest.json').read_bytes()),
        'reference_membership_sha256':m['files']['industry_membership.csv'],'warmup_start':'2026-09-24'}
    monkeypatch.setattr(model_inputs,'load_model_contract',lambda:contract)
    model_inputs.bind_model_inputs(p,path)
    assert p.model_membership_seed.iloc[0].as_of_date==p.cutoff
    (path/'industry_membership.csv').write_bytes(b'SYNTHETIC_TAMPER')
    with pytest.raises(GateError,match='MODEL_REFERENCE_HASH'):
        model_inputs.bind_model_inputs(p,path)

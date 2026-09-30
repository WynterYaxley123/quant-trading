"""Synthetic factual warehouse cases; no online observations or strategy change."""
from datetime import date
import hashlib
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/"services/cnequity-sidecar"))
    return tuple(importlib.import_module(n) for n in ("finalization","expected_bars","source_compatibility"))


def settings(tmp_path):
    lake=tmp_path/"lake";lake.mkdir()
    return {"paths":{"lake_root":str(lake),"export_root":str(tmp_path/"exports")},
            "export":{"start":"2026-09-24","cutoff":"2026-09-24","etf_symbols":[],"calendar_end":"2026-10-08"}}


def export(m,cfg,day,ident):
    folder=Path(cfg["paths"]["export_root"])/(ident*64);folder.mkdir(parents=True)
    names=("trading_calendar","stock_bars","industry_membership","etf_bars","instruments","trading_status","benchmark_csi300")
    files={}
    for name in names:
        leaf=folder/(name+".csv");leaf.write_bytes(b"SYNTHETIC\n")
        files[leaf.name]=m.checksum(leaf)
    (folder/"manifest.json").write_text(json.dumps({"snapshot_id":folder.name,"data_cutoff":str(day),
        "source_commit":m.PIN,"files":files}))
    return {"snapshot_id":folder.name}


def days():return [date(2026,9,24),date(2026,9,28),date(2026,9,29),date(2026,9,30)]


def test_complete_session_is_published_and_later_incomplete_day_cannot_retract_it(modules,tmp_path):
    m,*_=modules;cfg=settings(tmp_path);journal=m.SessionJournal(cfg,days()[0],days())
    journal.publish(days()[1],export(m,cfg,days()[1],"a"),"SYNTHETIC_COMPLETE")
    before=(journal.root/"latest.json").read_bytes()
    restarted=m.SessionJournal(cfg,days()[0],days())
    assert restarted.cutoff==days()[1] and (journal.root/"latest.json").read_bytes()==before
    assert not (journal.root/"sessions"/(str(days()[2])+".json")).exists()


def test_incomplete_prior_session_cannot_be_skipped(modules,tmp_path):
    m,*_=modules;cfg=settings(tmp_path);journal=m.SessionJournal(cfg,days()[0],days())
    with pytest.raises(m.GateError,match="CONTINUITY"):
        journal.publish(days()[2],export(m,cfg,days()[2],"a"),"SYNTHETIC_COMPLETE_LATER")
    assert journal.latest is None


@pytest.mark.parametrize("phase",["fetch","stage","derive","before_export","export_before_receipt","receipt_before_cursor","after_publish"])
def test_restart_at_each_publication_boundary(modules,tmp_path,phase):
    m,*_=modules;cfg=settings(tmp_path);journal=m.SessionJournal(cfg,days()[0],days())
    result=export(m,cfg,days()[1],"a")
    if phase in ("receipt_before_cursor","after_publish"):
        journal.publish(days()[1],result,"SYNTHETIC_OWN_RUN")
        if phase=="receipt_before_cursor":(journal.root/"latest.json").unlink()
    restart=m.SessionJournal(cfg,days()[0],days())
    expected=days()[1] if phase in ("receipt_before_cursor","after_publish") else days()[0]
    assert restart.cutoff==expected
    assert len(list((journal.root/"sessions").glob("*.json")))==int(expected==days()[1]) if (journal.root/"sessions").exists() else expected==days()[0]


@pytest.mark.parametrize("leaf",["manifest.json","stock_bars.csv"])
def test_committed_byte_corruption_fails_closed(modules,tmp_path,leaf):
    m,*_=modules;cfg=settings(tmp_path);j=m.SessionJournal(cfg,days()[0],days())
    r=export(m,cfg,days()[1],"a");j.publish(days()[1],r,"SYNTHETIC_RUN")
    (Path(cfg["paths"]["export_root"])/r["snapshot_id"]/leaf).write_bytes(b"SYNTHETIC_CORRUPTION")
    with pytest.raises(m.GateError,match="HASH|BYTES"):m.SessionJournal(cfg,days()[0],days())


def test_scope_drift_or_cursor_without_receipt_is_not_success(modules,tmp_path):
    m,*_=modules;cfg=settings(tmp_path);m.SessionJournal(cfg,days()[0],days())
    with pytest.raises(m.GateError,match="CURSOR_AHEAD"):m.SessionJournal(cfg,days()[1],days())
    cfg["export"]["etf_symbols"]=["SYNTHETIC"]
    with pytest.raises(m.GateError,match="SCOPE_DRIFT"):m.SessionJournal(cfg,days()[0],days())


def test_export_committed_before_receipt_recovers_only_matching_prepared_evidence(modules,tmp_path):
    m,*_=modules;cfg=settings(tmp_path);j=m.SessionJournal(cfg,days()[0],days())
    j.prepare(days()[1],"SYNTHETIC_COMPLETE_RUN","SYNTHETIC_LAKE_FINGERPRINT")
    r=export(m,cfg,days()[1],"a")
    leaf=Path(cfg["paths"]["export_root"])/r["snapshot_id"]/"manifest.json"
    doc=json.loads(leaf.read_bytes());doc.update(lake_fingerprint_sha256="SYNTHETIC_LAKE_FINGERPRINT",
        created_at="9999-01-01T00:00:00+00:00");leaf.write_text(json.dumps(doc))
    resumed=m.SessionJournal(cfg,days()[0],days())
    assert resumed.cutoff==days()[1] and resumed.latest["source_run_id"]=="SYNTHETIC_COMPLETE_RUN"
    again=m.SessionJournal(cfg,days()[0],days())
    assert again.latest==resumed.latest and len(list((j.root/"sessions").glob("*.json")))==1


def test_failed_batches_empty_never_substitutes_for_complete_stage_receipts(modules):
    m,*_=modules
    assert m.admission([], ["daily_bars","audit"])
    assert m.admission([{"dataset":"daily_bars","stage":"fetch","status":"success"}], ["daily_bars"])


def test_105_of_106_is_provider_missing_then_exact_recovery_passes(modules):
    _,m,_=modules;expected={str(i) for i in range(106)}
    summary,missing=m.classify(expected,expected-{"105"})
    assert summary["missing_count"]==1 and missing==["105"] and summary["reason_code"]=="PROVIDER_MISSING"
    summary,_=m.classify(expected,expected)
    assert summary["missing_count"]==0


def test_explicit_expected_no_bar_is_accepted_but_unknown_absence_is_not(modules):
    _,m,_=modules
    assert m.classify({"HALTED"},set(),{"HALTED"})[0]["missing_count"]==0
    assert m.classify({"UNKNOWN"},set())[0]["missing_count"]==1
    assert m.classify(set(),set())[0]["expected_count"]==0  # calendar supplied no session obligations


def test_bj_correction_requires_official_active_identity_and_byte_verified_prior_catalogue(modules):
    *_,m=modules
    rows=[{"symbol":"920001.BJ","delist_date":date(2026,9,28)},
          {"symbol":"920002.BJ","delist_date":date(2026,9,27)},
          {"symbol":"600001.SH","delist_date":date(2026,9,28)}]
    baseline={"920001.BJ":{"delist_date":""}}
    assert m.correction_symbols(rows,{"920001.BJ"},baseline)=={"920001.BJ"}
    assert not m.correction_symbols(rows,set(),baseline)
    assert not m.correction_symbols(rows,{"920001.BJ"},{"920001.BJ":{"delist_date":"2026-09-28"}})

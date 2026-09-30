"""Synthetic pinned-upstream job receipts, never an online data test."""
from contextlib import nullcontext
from datetime import date, datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def forward(tmp_path,monkeypatch):
    events=[]
    def module(name,**attrs):
        m=ModuleType(name)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules,name,m)
        return m
    module("runner",verify_install=lambda root:events.append("VERIFY_PIN"))
    module("proxy_policy",proxy_policy=lambda p:nullcontext())
    module("export_streaming",export_lake_streaming=lambda *a,**k:(events.append("EXPORT") or {"snapshot_id":"a"*64}))
    dates=[date(2026,9,25),date(2026,9,28),date(2026,9,29)]
    package=module("cnequity",load=lambda *a,**k:SimpleNamespace(to_dicts=lambda:
        [{"trade_date":d,"is_trading":True} for d in dates]))
    package.__path__=[]
    module("cnequity.config",load_config=lambda p:SimpleNamespace(data_root=tmp_path/"lake"))
    job_status={"status":"success"}
    class Engine:
        def __init__(self,cfg):pass
        def run_job(self,name,**kw):
            events.append((name,kw))
            return {"run_id":"SYNTHETIC_"+str(kw["trade_date"]),"status":job_status["status"]}
    module("cnequity.orchestrator.engine",JobEngine=Engine)
    steps=module("cnequity.steps")
    package.steps=steps
    from strategies.etf_quant.runtime.exports import SHANGHAI
    module("cnequity.domain.market_time",SHANGHAI_TZ=SHANGHAI)
    spec=importlib.util.spec_from_file_location("synthetic_forward",ROOT/"services/cnequity-sidecar/forward.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    config=tmp_path/"export.toml"
    config.write_text('[paths]\nlake_root="'+(tmp_path/"lake").as_posix()+'"\n[export]\ncutoff="2026-09-24"\n')
    return m,events,job_status,config


def test_forward_preserves_upstream_all_gates_and_exports_after_all_sessions(forward,tmp_path):
    m,events,status,config=forward
    result=m.forward(tmp_path,tmp_path/"source.toml",config,date(2026,9,29),date(2026,9,24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"))
    assert result["status"]=="REFRESH_EXPORTED" and events[0]=="VERIFY_PIN" and events[-1]=="EXPORT"
    jobs=[r for r in events if isinstance(r,tuple)]
    assert len(jobs)==3 and all(r[1]["steps"]==m.STEPS for r in jobs)
    assert {"compact","audit","derive_adj_factors","trading_status_derive"}<=set(m.STEPS)
    assert all("backfill" not in r[1] for r in jobs)


def test_upstream_failure_never_exports_or_invents_cutoff(forward,tmp_path):
    m,events,status,config=forward;status["status"]="failed"
    result=m.forward(tmp_path,tmp_path/"source.toml",config,date(2026,9,29),date(2026,9,24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"))
    assert result["status"]=="WAITING_FOR_DATA" and "EXPORT" not in events
    assert len(result["receipts"])==1 and "snapshot_id" not in result


@pytest.mark.parametrize("target",[date(2026,9,30),date(2026,10,1)])
def test_unfinalized_current_or_future_session_never_fetches(forward,tmp_path,target):
    m,events,status,config=forward
    result=m.forward(tmp_path,tmp_path/"source.toml",config,target,date(2026,9,24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"))
    assert result["status"]=="WAITING_FOR_MARKET_CLOSE" and events==["VERIFY_PIN"]


def test_missing_official_calendar_fails_closed(forward,tmp_path):
    m,events,status,config=forward
    result=m.forward(tmp_path,tmp_path/"source.toml",config,date(2026,10,1),date(2026,9,29),
        now=datetime.fromisoformat("2026-10-02T16:00:00+08:00"))
    assert result["status"]=="WAITING_FOR_DATA" and events==["VERIFY_PIN"]

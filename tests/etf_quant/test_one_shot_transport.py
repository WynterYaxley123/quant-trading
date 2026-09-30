"""Offline, synthetic filesystem/process tests for the single transport entry."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO/"services/etf-quant-runner"))
    spec = importlib.util.spec_from_file_location("synthetic_oneshot", REPO/"services/etf-quant-runner/one_shot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.transport, "committed_code", lambda: "d"*40)
    monkeypatch.setattr(module, "certified_inputs", lambda c: {module.CANDIDATE:"a"*64})
    return module


def config(tmp_path, module, cutoff="2026-09-30"):
    snapshot = tmp_path/"snapshot"
    snapshot.mkdir()
    (snapshot/"trading_calendar.csv").write_text("trade_date,is_trading\n2026-09-29,true\n2026-09-30,true\n2026-10-01,false\n")
    module.transport.verify_snapshot_files = lambda p: {"data_cutoff": cutoff}
    return {"snapshot": str(snapshot), "runtime_root": str(tmp_path/"FORMAL"),
        "control_root": str(tmp_path/"CONTROL"), "sidecar_root": str(tmp_path/"SIDECAR")}


@pytest.mark.parametrize("now,status", [
    ("2026-09-30T06:00:00+00:00","WAITING_FOR_MARKET_CLOSE"),
    ("2026-10-01T10:00:00+00:00","READY_NO_SIGNAL"),
    ("2026-10-02T10:00:00+00:00","WAITING_FOR_DATA"),
])
def test_no_docker_or_epoch_for_waiting_session(tmp_path, runner, monkeypatch, now, status):
    cfg = config(tmp_path, runner)
    calls = []
    def call(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="integration/etf-quant-v1-shadow-autonomous-final")
    monkeypatch.setattr(runner.transport,"call",call)
    result = runner.run_once(cfg, now=datetime.fromisoformat(now))
    assert result["status"] == status
    assert not Path(cfg["runtime_root"]).exists()
    assert len(calls) == 1  # Branch gate only; no source or Docker command.


def test_same_date_is_idempotent_before_refresh(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner, cutoff="2026-09-24")
    root = Path(cfg["runtime_root"])
    state = {"shadow_epoch":{"candidate_hash":"a"*64}, "formal_signal":{"signal_date":"2026-09-30"}}
    pointer = runner.transport.storage.publish_generation(root/"runs", "SYNTHETIC_001",
        {"state.json":runner.transport.storage.json_bytes(state)}, {"status":"SUCCESSFUL_OBSERVATION"})
    (root/"latest.json").write_bytes(runner.transport.storage.json_bytes(pointer))
    calls = []
    monkeypatch.setattr(runner.transport,"call",lambda argv,**kw: (calls.append(argv) or
        SimpleNamespace(returncode=0,stdout="integration/etf-quant-v1-shadow-autonomous-final")))
    before = (root/"latest.json").read_bytes()
    assert runner.run_once(cfg,now=datetime.fromisoformat("2026-09-30T10:00:00+00:00"))["status"] == "ALREADY_PROCESSED"
    assert len(calls)==1 and (root/"latest.json").read_bytes()==before


def test_refresh_failure_waits_without_partial_epoch(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner, cutoff="2026-09-24")
    cfg.update(source_config=str(tmp_path/"source.toml"), export_config=str(tmp_path/"export.toml"))
    for k in ("source_config","export_config"): Path(cfg[k]).write_text("# SYNTHETIC")
    calls=[]
    def call(argv,**kw):
        calls.append(argv)
        return SimpleNamespace(returncode=0,stdout=("integration/etf-quant-v1-shadow-autonomous-final" if len(calls)==1
            else json.dumps({"status":"WAITING_FOR_DATA","exception_class":"ReadTimeout"})))
    monkeypatch.setattr(runner.transport,"call",call)
    result=runner.run_once(cfg,now=datetime.fromisoformat("2026-09-30T06:00:00+00:00"))
    assert result["status"]=="WAITING_FOR_DATA" and len(calls)==2
    assert not Path(cfg["runtime_root"]).exists()
    assert len(list((Path(cfg["control_root"])/"refreshes").iterdir()))==1


def test_uncertified_hash_blocks_before_any_refresh(tmp_path, runner, monkeypatch):
    cfg=config(tmp_path,runner)
    def fail(c): raise runner.transport.GateError("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER")
    monkeypatch.setattr(runner,"certified_inputs",fail)
    monkeypatch.setattr(runner.transport,"call",lambda *a,**kw:
        SimpleNamespace(returncode=0,stdout="integration/etf-quant-v1-shadow-autonomous-final"))
    with pytest.raises(runner.transport.GateError,match="CERTIFIED_INPUT_HASH"):
        runner.run_once(cfg)
    assert not Path(cfg["runtime_root"]).exists()


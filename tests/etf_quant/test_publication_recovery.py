"""Crash-boundary tests for committed evidence; all state and prices are synthetic."""

import json
import subprocess
import sys

import pytest
from test_formal_shadow import run, setup
from test_shadow import advance, read

from strategies.etf_quant.runtime import storage


@pytest.mark.parametrize("phase", ["signal", "fill"])
@pytest.mark.parametrize("after_pointer", [False, True])
def test_v1_crash_restart_never_duplicates_epoch_intent_fill_nav(
    tmp_path, monkeypatch, phase, after_pointer
):
    p, reg, book, contract = setup(tmp_path)
    root = tmp_path / "SYNTHETIC_CRASH_V1"
    if phase == "fill":
        run(p, reg, book, contract, root)
        q = advance(p)
        import pandas as pd

        for name in ("etf_bars", "trading_status"):
            old = p.tables[name].loc[p.tables[name].trade_date == p.cutoff].copy()
            old["trade_date"] = q.cutoff
            q.tables[name] = pd.concat([p.tables[name], old], ignore_index=True)
        p = q
    original = storage.atomic_bytes

    def crash(path, payload, **kwargs):
        if path == root / "latest.json":
            if after_pointer:
                original(path, payload, **kwargs)
            raise SystemExit("SYNTHETIC_PROCESS_DEATH")
        return original(path, payload, **kwargs)

    monkeypatch.setattr(storage, "atomic_bytes", crash)
    with pytest.raises(SystemExit, match="PROCESS_DEATH"):
        run(p, reg, book, contract, root)
    assert (root / ".publication.json").exists()
    monkeypatch.setattr(storage, "atomic_bytes", original)
    assert run(p, reg, book, contract, root)["status"] == "ALREADY_PROCESSED"
    _, state = read(root)
    before = (root / "latest.json").read_bytes()
    assert run(p, reg, book, contract, root)["status"] == "ALREADY_PROCESSED"
    assert (root / "latest.json").read_bytes() == before
    assert len(list((root / "runs").iterdir())) == (2 if phase == "fill" else 1)
    assert len(state["nav"]) == (1 if phase == "fill" else 0)
    assert bool(state["trades"]) == (phase == "fill")
    assert state["shadow_epoch"]["initial_cash"] == "10000"
    assert not (root / ".publication.json").exists()


def test_os_releases_account_mutex_on_real_process_death(tmp_path):
    code = """
import os, sys
from pathlib import Path
from strategies.etf_quant.runtime.storage import account_lock
with account_lock(Path(sys.argv[1])):
    os._exit(86)
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=False)
    assert result.returncode == 86
    with storage.account_lock(tmp_path):
        with pytest.raises(storage.GateError, match="CONCURRENT"):
            with storage.account_lock(tmp_path):
                pytest.fail("second owner acquired the account mutex")


@pytest.mark.parametrize("mutation", ["oversize", "escape", "hash", "parent", "symlink"])
def test_recovery_rejects_unknown_or_tampered_publication(tmp_path, monkeypatch, mutation):
    root = tmp_path / "account"
    root.mkdir()
    original = storage.atomic_bytes

    def fail(path, payload, **kwargs):
        if path == root / "latest.json":
            raise SystemExit()
        return original(path, payload, **kwargs)

    monkeypatch.setattr(storage, "atomic_bytes", fail)
    with pytest.raises(SystemExit):
        storage.publish_account_generation(root, "SYNTHETIC", {"state.json": b"{}"}, {})
    monkeypatch.setattr(storage, "atomic_bytes", original)
    journal = root / ".publication.json"
    value = json.loads(journal.read_bytes())
    if mutation == "oversize":
        journal.write_bytes(b" " * 4097)
    elif mutation == "escape":
        value["pointer"]["run_id"] = "../outside"
    elif mutation == "hash":
        (root / "runs/SYNTHETIC/state.json").write_bytes(b"tampered")
    elif mutation == "parent":
        (root / "latest.json").write_bytes(b"{}")
    else:
        (root / "runs").rename(tmp_path / "outside")
        (root / "runs").symlink_to(tmp_path / "outside", target_is_directory=True)
    if mutation in ("escape",):
        journal.write_bytes(storage.json_bytes(value))
    before = (root / "latest.json").read_bytes() if (root / "latest.json").exists() else None
    with pytest.raises(storage.GateError):
        with storage.account_lock(root):
            pytest.fail("tampered publication was accepted")
    assert (
        (root / "latest.json").read_bytes() if (root / "latest.json").exists() else None
    ) == before
    assert journal.exists()


def test_crash_before_generation_can_retry_without_business_records(tmp_path, monkeypatch):
    def fail(*args):
        raise SystemExit()

    with pytest.raises(SystemExit):
        storage.publish_account_generation(
            tmp_path, "SYNTHETIC", {"state.json": b"{}"}, {}, publisher=fail
        )
    with storage.account_lock(tmp_path):
        assert not (tmp_path / "latest.json").exists()
        storage.publish_account_generation(tmp_path, "SYNTHETIC", {"state.json": b"{}"}, {})
    assert len(list((tmp_path / "runs").iterdir())) == 1

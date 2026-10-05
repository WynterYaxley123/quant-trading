"""Synthetic transport regression only; never uses Docker daemon or a real lake."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "transport_under_test", REPO / "services/etf-quant-runner/run.py"
)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
s = transport.storage


def test_real_transport_process_death_releases_guard_and_recovers_owned_lock(tmp_path):
    code = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import run as transport
with transport.transport_lock(Path(sys.argv[2])):
    os._exit(86)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(REPO / "services/etf-quant-runner"), str(tmp_path)],
        check=False,
    )
    assert result.returncode == 86
    assert (tmp_path / ".transport.lock").exists()
    with transport.transport_lock(tmp_path):
        assert (
            json.loads((tmp_path / "last_lock_recovery.json").read_bytes())["reason_code"]
            == "OS_PROVEN_DEAD_OWNER"
        )
    assert not (tmp_path / ".transport.lock").exists()


def test_mixed_native_stderr_does_not_destroy_structured_receipt():
    result = transport.call(
        [
            sys.executable,
            "-c",
            'import os; os.write(2,bytes([0x97,0x98])); print(\'{"status":"SYNTHETIC"}\')',
        ]
    )
    assert transport.result_json(result) == {"status": "SYNTHETIC"}
    assert result.stderr == r"\x97\x98" and result.returncode == 0


def test_non_utf8_structured_stdout_still_blocks():
    with pytest.raises(s.GateError, match="CHILD_ENCODING"):
        transport.call([sys.executable, "-c", "import os; os.write(1,bytes([0x97]))"])


def generation(root, run="SYNTHETIC_TEST_001"):
    pointer = s.publish_generation(
        root / "runs",
        run,
        {
            "view.json": b'{"synthetic":true}',
            "state.json": b'{"synthetic":true}',
            "prefix.json": b"{}",
        },
        {"status": "SUCCESSFUL_OBSERVATION"},
    )
    s.atomic_bytes(root / "latest.json", s.json_bytes(pointer))
    return pointer


def test_verified_transport_publishes_only_complete_immutable_run(tmp_path):
    copied, runtime = tmp_path / "copied", tmp_path / "public"
    runtime.mkdir()
    pointer = generation(copied)
    assert transport.publish_copied_runtime(copied, runtime) == 1
    assert json.loads((runtime / "latest.json").read_bytes()) == pointer
    assert s.read_generation(runtime / "runs", pointer) == s.read_generation(
        copied / "runs", pointer
    )
    before = (runtime / "latest.json").read_bytes()
    assert transport.publish_copied_runtime(copied, runtime) == 1
    assert (runtime / "latest.json").read_bytes() == before
    assert len(list((runtime / "runs").iterdir())) == 1


@pytest.mark.parametrize("file", ["view.json", "state.json", "prefix.json", "manifest.json"])
def test_tampered_copy_cannot_advance_public_account(tmp_path, file):
    copied, runtime = tmp_path / "copied", tmp_path / "public"
    generation(runtime, "SYNTHETIC_PREVIOUS")
    before = (runtime / "latest.json").read_bytes()
    pointer = generation(copied)
    (copied / "runs" / pointer["run_id"] / file).write_bytes(b"SYNTHETIC_CORRUPTION")
    with pytest.raises(s.GateError):
        transport.publish_copied_runtime(copied, runtime)
    assert (runtime / "latest.json").read_bytes() == before
    assert not (runtime / "runs" / pointer["run_id"]).exists()


def test_all_copied_plans_validate_before_any_pointer_moves(tmp_path):
    copied, runtime = tmp_path / "copied", tmp_path / "public"
    generation(runtime, "SYNTHETIC_PREVIOUS")
    before = (runtime / "latest.json").read_bytes()
    pointer = generation(copied)
    failure = transport.record_failure(copied, "SYNTHETIC_ERROR")
    (copied / "failures" / failure["run_id"] / "failure.json").write_bytes(b"BROKEN")
    with pytest.raises(s.GateError):
        transport.publish_copied_runtime(copied, runtime)
    assert (runtime / "latest.json").read_bytes() == before
    assert not (runtime / "runs" / pointer["run_id"]).exists()


def test_failure_report_keeps_successful_account(tmp_path):
    generation(tmp_path)
    before = (tmp_path / "latest.json").read_bytes()
    result = transport.record_failure(tmp_path, "SYNTHETIC_INPUT_BLOCKER")
    assert result["status"] == "BLOCKED" and (tmp_path / "latest.json").read_bytes() == before
    pointer = json.loads((tmp_path / "last_attempt.json").read_bytes())
    manifest, files = s.read_generation(tmp_path / "failures", pointer)
    assert manifest["status"] == "FAILED"
    failure = json.loads(files["failure.json"])
    assert failure["validation_opened"] is False and failure["final_oos_read"] is False


def test_transport_lock_no_stale_stealing(tmp_path):
    with transport.transport_lock(tmp_path):
        with pytest.raises(s.GateError, match="CONCURRENT"):
            with transport.transport_lock(tmp_path):
                pass
    assert not (tmp_path / ".transport.lock").exists()


def test_proven_dead_owned_transport_lock_recovers_without_touching_unknown_lock(
    tmp_path, monkeypatch
):
    path = tmp_path / ".transport.lock"
    path.write_text(json.dumps({"pid": 123456, "created_at": "SYNTHETIC"}))
    monkeypatch.setattr(transport, "process_owner", lambda pid: "DEAD")
    with transport.transport_lock(tmp_path):
        assert json.loads(path.read_bytes())["scope"] == "ETF_QUANT_TRANSPORT_V1"
    assert (
        json.loads((tmp_path / "last_lock_recovery.json").read_bytes())["reason_code"]
        == "OS_PROVEN_DEAD_OWNER"
    )
    path.write_text(json.dumps({"pid": 123456, "unknown": "SYNTHETIC"}))
    with pytest.raises(s.GateError, match="CONCURRENT"):
        with transport.transport_lock(tmp_path):
            pass
    assert path.exists()


@pytest.mark.parametrize("state", ["ALIVE", "UNKNOWN"])
def test_transport_lock_never_recovers_active_or_uninspectable_owner(tmp_path, monkeypatch, state):
    path = tmp_path / ".transport.lock"
    path.write_text(json.dumps({"pid": 123456, "created_at": "SYNTHETIC"}))
    monkeypatch.setattr(transport, "process_owner", lambda pid: state)
    before = path.read_bytes()
    with pytest.raises(s.GateError, match="CONCURRENT"):
        with transport.transport_lock(tmp_path):
            pass
    assert path.read_bytes() == before


def test_external_profile_required_and_safe_child_errors(tmp_path):
    with pytest.raises(s.GateError):
        transport.external_file("relative.json")
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "secret.json").write_bytes(b"SYNTHETIC_NOT_CREDENTIALS")
    with pytest.raises(s.GateError):
        transport.external_file(root / "secret.json")
    with pytest.raises(s.GateError, match="CHILD_RESPONSE"):
        transport.result_json(SimpleNamespace(stdout="D:/private/synthetic", returncode=1))


@pytest.mark.parametrize(
    "branch,status,main",
    [("main", "", "b" * 40), ("main", " M file", "a" * 40), ("unmerged-feature", "", "a" * 40)],
)
def test_dirty_or_wrong_branch_blocks_transport(monkeypatch, branch, status, main):
    replies = iter([branch, "a" * 40, status, main])
    monkeypatch.setattr(
        transport, "call", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=next(replies))
    )
    with pytest.raises(s.GateError, match="CLEAN_COMMITTED"):
        transport.committed_code()


@pytest.mark.parametrize("branch", ["main", "", "release/etf-quant-v2-finalization"])
def test_clean_exact_fetched_main_allows_formal_delivery(monkeypatch, branch):
    replies = iter([branch, "a" * 40, "", "a" * 40])
    monkeypatch.setattr(
        transport, "call", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=next(replies))
    )
    assert transport.committed_code() == "a" * 40


def test_source_identity_mismatch_before_market_parsing(tmp_path):
    folder = tmp_path / ("a" * 64)
    folder.mkdir()
    (folder / "manifest.json").write_bytes(
        s.json_bytes({"snapshot_id": folder.name, "provider": "WRONG_SOURCE"})
    )
    with pytest.raises(s.GateError, match="SOURCE_POLICY"):
        transport.verify_snapshot_files(folder)


def test_smoke_failure_import_is_genuine_metadata_not_fake_nav(tmp_path):
    report = {
        "status": "NETWORK_METADATA_SMOKE_BLOCKED",
        "source_commit": transport.POLICY["source_commit"],
        "tls_verification": "STRICT_UPSTREAM_SSL_CONTEXT",
        "pit_evidence": False,
        "market_data_initialization": False,
        "exception_class": "RemoteProtocolError",
        "completed_at": "2026-01-01T00:00:00+00:00",
    }
    path = tmp_path / "smoke.json"
    path.write_bytes(s.json_bytes(report))
    runtime = s.external_root(tmp_path / "runtime")
    assert (
        transport.import_smoke_failure(path, runtime)["blocker"] == "CNEQUITY_RUNTIME_SMOKE_BLOCKED"
    )
    assert not (runtime / "latest.json").exists() and not (runtime / "runs").exists()
    report["source_commit"] = "b" * 40
    path.write_bytes(s.json_bytes(report))
    with pytest.raises(s.GateError, match="UNVERIFIED"):
        transport.import_smoke_failure(path, runtime)

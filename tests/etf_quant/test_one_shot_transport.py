"""Offline, synthetic filesystem/process tests for the single transport entry."""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_version_dispatch_rejects_unknown_version_without_business_state(tmp_path, runner):
    with pytest.raises(runner.transport.GateError, match="UNKNOWN_STRATEGY_VERSION"):
        runner.run_once({"strategy_version": "UNKNOWN", "control_root": str(tmp_path / "CONTROL")})
    assert not (tmp_path / "FORMAL").exists()


def test_v2_transport_denies_clock_override(tmp_path, runner):
    with pytest.raises(runner.transport.GateError, match="CLOCK_OVERRIDE"):
        runner.run_once(
            {"strategy_version": "ETF_QUANT_V2", "control_root": str(tmp_path / "CONTROL")},
            now=datetime.fromisoformat("2026-10-08T12:00:00+00:00"),
        )


def test_v2_cannot_use_legacy_integration_authority_before_merge(tmp_path, runner, monkeypatch):
    monkeypatch.setattr(
        runner.transport,
        "call",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="e" * 40),
    )
    with pytest.raises(runner.transport.GateError, match="V2_MERGED_MAIN_REQUIRED"):
        runner.run_once(
            {"strategy_version": "ETF_QUANT_V2", "control_root": str(tmp_path / "CONTROL")}
        )


def test_docker_refresh_uses_readonly_pin_and_owned_lake(tmp_path, runner):
    from docker_refresh import refresh_command

    cfg = {
        k: str(tmp_path / k)
        for k in ("docker_source_root", "sidecar_root", "export_root", "snapshot")
    }
    for path in cfg.values():
        Path(path).mkdir()
    for k in ("source_config", "export_config"):
        p = tmp_path / (k + ".toml")
        p.write_text("SYNTHETIC")
        cfg[k] = str(p)
    cfg["operational_lake_root"] = str(tmp_path / "forward-source-lake")
    command = refresh_command(cfg, "2026-10-08", "2026-09-30")
    assert (
        "--docker-source" in command
        and "/cnequity" in command
        and "PYTHONPATH=/workspace:/cnequity/src" in command
    )
    assert any("/cnequity,readonly" in part for part in command)
    cfg["operational_lake_root"] = str(tmp_path / "canonical-lake")
    with pytest.raises(runner.transport.GateError, match="OWNED_FORWARD"):
        refresh_command(cfg, "2026-10-08", "2026-09-30")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "services/etf-quant-runner"))
    spec = importlib.util.spec_from_file_location(
        "synthetic_oneshot", REPO / "services/etf-quant-runner/one_shot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.transport, "committed_code", lambda: "d" * 40)
    monkeypatch.setattr(module, "certified_inputs", lambda c: {module.CANDIDATE: "a" * 64})
    monkeypatch.setattr(
        module,
        "certified_implementation",
        lambda: json.loads(
            (REPO / "reports/engineering/etf-quant-v2-console-integrity.json").read_bytes()
        )["implementation_integrity"]["files"],
    )
    return module


def config(tmp_path, module, cutoff="2026-09-30"):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "trading_calendar.csv").write_text(
        "trade_date,is_trading\n2026-09-29,true\n2026-09-30,true\n2026-10-01,false\n"
    )
    module.transport.verify_snapshot_files = lambda p: {"data_cutoff": cutoff}
    return {
        "snapshot": str(snapshot),
        "runtime_root": str(tmp_path / "FORMAL"),
        "control_root": str(tmp_path / "CONTROL"),
        "sidecar_root": str(tmp_path / "SIDECAR"),
    }


@pytest.mark.parametrize("version", ["ETF_QUANT_V1", "ETF_QUANT_V2"])
def test_restart_recovers_in_docker_before_holiday_without_host_account_lock(
    tmp_path, runner, monkeypatch, version
):
    cfg = config(tmp_path, runner)
    cfg.update(strategy_version=version, developer_image="synthetic-recovery-image")
    root = Path(cfg["runtime_root"])
    root.mkdir()
    storage = runner.transport.storage
    original_atomic = storage.atomic_bytes

    def crash(path, raw):
        if path.name == "latest.json":
            raise RuntimeError("synthetic crash after generation")
        original_atomic(path, raw)

    monkeypatch.setattr(storage, "atomic_bytes", crash)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        storage.publish_account_generation(
            root, "SYNTHETIC_RECOVERY", {"state.json": b'{"signals":1}'}, {}
        )
    monkeypatch.setattr(storage, "atomic_bytes", original_atomic)
    expected = json.loads((root / ".publication.json").read_bytes())["pointer"]
    monkeypatch.setattr(
        storage, "account_lock", lambda *args: pytest.fail("host account lock is unsafe")
    )
    calls = []

    def call(argv, **kwargs):
        calls.append(argv)
        assert argv[:6] == ["docker", "run", "--rm", "--network", "none", "--mount"]
        assert any("target=/workspace,readonly" in arg for arg in argv)
        assert any("target=/shadow" in arg and "readonly" not in arg for arg in argv)
        assert argv[-5:-1] == ["synthetic-recovery-image", "python", "-B", "-c"]
        # Exercise the exact stdlib worker with synthetic mounts in this Linux
        # test container. No provider, model or formal runner is invoked.
        worker = argv[-1].replace("/workspace", REPO.as_posix()).replace("/shadow", root.as_posix())
        return subprocess.run([sys.executable, "-B", "-c", worker], check=False)

    def holiday(*args, **kwargs):
        assert not (root / ".publication.json").exists()
        assert json.loads((root / "latest.json").read_bytes()) == expected
        return {"status": "ARMED_NON_TRADING_DAY"}

    monkeypatch.setattr(runner.transport, "call", call)
    monkeypatch.setattr(runner, "_run_once", holiday)
    monkeypatch.setattr(runner, "_run_v2", holiday)
    runner.run_once(cfg)
    before = (root / "latest.json").read_bytes()
    runner.run_once(cfg)
    assert len(calls) == 1 and (root / "latest.json").read_bytes() == before
    assert len(list((root / "runs").iterdir())) == 1


def test_recovery_failure_does_not_reach_signal_or_fill_decisions(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner)
    root = Path(cfg["runtime_root"])
    root.mkdir()
    (root / ".publication.json").write_text("SYNTHETIC_BAD_JOURNAL")
    monkeypatch.setattr(
        runner.transport, "call", lambda *args, **kwargs: SimpleNamespace(returncode=1)
    )
    monkeypatch.setattr(runner, "_run_once", lambda *args, **kwargs: pytest.fail("unsafe decision"))
    with pytest.raises(runner.transport.GateError, match="PUBLICATION_RECOVERY_BLOCKER"):
        runner.run_once(cfg)
    assert not (root / "latest.json").exists()
    assert (root / ".publication.json").read_text() == "SYNTHETIC_BAD_JOURNAL"


def test_recovery_worker_respects_linux_account_publication_mutex(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner)
    root = Path(cfg["runtime_root"])
    root.mkdir()
    (root / ".publication.json").write_text("SYNTHETIC_PENDING")

    def call(argv, **kwargs):
        worker = argv[-1].replace("/workspace", REPO.as_posix()).replace("/shadow", root.as_posix())
        result = subprocess.run(
            [sys.executable, "-B", "-c", worker], capture_output=True, check=False
        )
        assert b"CONCURRENT_OR_INTERRUPTED_RUN_BLOCKER" in result.stderr
        return result

    monkeypatch.setattr(runner.transport, "call", call)
    with runner.transport.storage.process_lock(root / ".cycle.guard"):
        with pytest.raises(runner.transport.GateError, match="PUBLICATION_RECOVERY_BLOCKER"):
            runner.recover_runtime(cfg)
    assert (root / ".publication.json").read_text() == "SYNTHETIC_PENDING"


@pytest.mark.parametrize(
    "now,status",
    [
        ("2026-09-30T06:00:00+00:00", "WAITING_FOR_MARKET_CLOSE"),
        ("2026-10-01T10:00:00+00:00", "READY_NO_SIGNAL"),
        ("2026-10-02T10:00:00+00:00", "BLOCKED_DATA_INTEGRITY"),
    ],
)
def test_no_docker_or_epoch_for_waiting_session(tmp_path, runner, monkeypatch, now, status):
    cfg = config(tmp_path, runner)
    calls = []

    def call(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(
            returncode=0, stdout="integration/etf-quant-v1-shadow-autonomous-final"
        )

    monkeypatch.setattr(runner.transport, "call", call)
    result = runner.run_once(cfg, now=datetime.fromisoformat(now))
    assert result["status"] == status
    assert not Path(cfg["runtime_root"]).exists()
    assert len(calls) == 1  # Branch gate only; no source or Docker command.


def test_same_date_is_idempotent_before_refresh(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner, cutoff="2026-09-24")
    root = Path(cfg["runtime_root"])
    state = {
        "shadow_epoch": {"candidate_hash": "a" * 64},
        "formal_signal": {"signal_date": "2026-09-30"},
    }
    pointer = runner.transport.storage.publish_generation(
        root / "runs",
        "SYNTHETIC_001",
        {"state.json": runner.transport.storage.json_bytes(state)},
        {"status": "SUCCESSFUL_OBSERVATION"},
    )
    (root / "latest.json").write_bytes(runner.transport.storage.json_bytes(pointer))
    calls = []
    monkeypatch.setattr(
        runner.transport,
        "call",
        lambda argv, **kw: (
            calls.append(argv)
            or SimpleNamespace(
                returncode=0, stdout="integration/etf-quant-v1-shadow-autonomous-final"
            )
        ),
    )
    before = (root / "latest.json").read_bytes()
    assert (
        runner.run_once(cfg, now=datetime.fromisoformat("2026-09-30T10:00:00+00:00"))["status"]
        == "ALREADY_PROCESSED"
    )
    assert len(calls) == 1 and (root / "latest.json").read_bytes() == before


def test_refresh_failure_waits_without_partial_epoch(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner, cutoff="2026-09-24")
    cfg.update(
        source_config=str(tmp_path / "source.toml"), export_config=str(tmp_path / "export.toml")
    )
    for k in ("source_config", "export_config"):
        Path(cfg[k]).write_text("# SYNTHETIC")
    calls = []

    def call(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "integration/etf-quant-v1-shadow-autonomous-final"
                if len(calls) == 1
                else json.dumps({"status": "WAITING_FOR_DATA", "exception_class": "ReadTimeout"})
            ),
        )

    monkeypatch.setattr(runner.transport, "call", call)
    result = runner.run_once(cfg, now=datetime.fromisoformat("2026-09-30T06:00:00+00:00"))
    assert result["status"] == "WAITING_FOR_PROVIDER_DATA" and len(calls) == 2
    assert not Path(cfg["runtime_root"]).exists()
    assert len(list((Path(cfg["control_root"]) / "refreshes").iterdir())) == 1


def test_uncertified_hash_blocks_before_any_refresh(tmp_path, runner, monkeypatch):
    cfg = config(tmp_path, runner)

    def fail(c):
        raise runner.transport.GateError("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER")

    monkeypatch.setattr(runner, "certified_inputs", fail)
    monkeypatch.setattr(
        runner.transport,
        "call",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="integration/etf-quant-v1-shadow-autonomous-final"
        ),
    )
    with pytest.raises(runner.transport.GateError, match="CERTIFIED_INPUT_HASH"):
        runner.run_once(cfg)
    assert not Path(cfg["runtime_root"]).exists()


def test_formal_docker_transport_preserves_immutable_snapshot_hash_directory(
    tmp_path, runner, monkeypatch
):
    cfg = config(tmp_path, runner)
    original = Path(cfg["snapshot"])
    snapshot = tmp_path / ("a" * 64)
    original.rename(snapshot)
    cfg["snapshot"] = str(snapshot)
    cfg.update(
        profile=str(tmp_path / "profile.json"),
        evidence_root=str(tmp_path / "evidence"),
        pit_source_root=str(tmp_path / "pit-sources"),
        pit_evidence=str(tmp_path / "pit-book.json"),
        docker_executable="SYNTHETIC_DOCKER",
        model_reference_snapshot=str(tmp_path / ("b" * 64)),
    )
    Path(cfg["profile"]).write_text(
        json.dumps({"mode": "SIMULATION_ONLY", "provider_identity": runner.transport.POLICY})
    )
    Path(cfg["pit_evidence"]).write_text("{}")
    Path(cfg["evidence_root"]).mkdir()
    Path(cfg["pit_source_root"]).mkdir()
    Path(cfg["model_reference_snapshot"]).mkdir()
    calls = []

    def call(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(
            returncode=0,
            stdout="integration/etf-quant-v1-shadow-autonomous-final"
            if argv[0] == "git"
            else json.dumps({"status": "STARTED", "shadow_epoch_created": True}),
        )

    monkeypatch.setattr(runner.transport, "call", call)
    result = runner.run_once(cfg, now=datetime.fromisoformat("2026-09-30T14:00:00+00:00"))
    assert result["status"] == "STARTED" and result["shadow_start_gate"] == "STARTED"
    command = calls[-1]
    assert command[command.index("--network") + 1] == "none"
    target = command[command.index("--snapshot") + 1]
    assert Path(target).name == snapshot.name and target == "/snapshot/" + snapshot.name
    assert any(
        "source=" + str(snapshot) in str(a) and "target=" + target + ",readonly" in str(a)
        for a in command
    )
    model_target = command[command.index("--model-reference-snapshot") + 1]
    assert model_target == "/model-reference/" + "b" * 64
    assert any("target=" + model_target + ",readonly" in str(a) for a in command)


def test_partial_finalization_is_adopted_despite_next_session_failure_and_resume_uses_it(
    tmp_path, runner, monkeypatch
):
    cfg = config(tmp_path, runner, cutoff="2026-09-24")
    cfg.update(
        source_config=str(tmp_path / "source.toml"),
        export_config=str(tmp_path / "export.toml"),
        export_root=str(tmp_path / "exports"),
    )
    for k in ("source_config", "export_config"):
        Path(cfg[k]).write_text("# SYNTHETIC")
    admitted = Path(cfg["export_root"]) / ("f" * 64)
    admitted.mkdir(parents=True)
    (admitted / "manifest.json").write_bytes(b"SYNTHETIC_MANIFEST")
    (admitted / "trading_calendar.csv").write_bytes(
        (Path(cfg["snapshot"]) / "trading_calendar.csv").read_bytes()
    )
    monkeypatch.setattr(
        runner.transport,
        "verify_snapshot_files",
        lambda p: {"data_cutoff": "2026-09-28" if p == admitted else "2026-09-24"},
    )
    calls = []

    def call(argv, **kw):
        calls.append(argv)
        if argv[0] == "git":
            return SimpleNamespace(
                returncode=0, stdout="integration/etf-quant-v1-shadow-autonomous-final"
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "WAITING_FOR_PROVIDER_DATA",
                    "latest_finalized": {
                        "snapshot_id": admitted.name,
                        "manifest_sha256": runner.checksum(admitted / "manifest.json"),
                    },
                }
            ),
        )

    monkeypatch.setattr(runner.transport, "call", call)
    r = runner.run_once(cfg, now=datetime.fromisoformat("2026-09-30T12:00:00+00:00"))
    assert r["data_cutoff"] == "2026-09-28" and r["status"] == "WAITING_FOR_PROVIDER_DATA"
    assert r["shadow_runtime_armed"] is True and not Path(cfg["runtime_root"]).exists()
    pointer = Path(cfg["control_root"]) / "latest_export.json"
    before = pointer.read_bytes()
    runner.run_once(cfg, now=datetime.fromisoformat("2026-09-30T12:01:00+00:00"))
    assert str(calls[-1][-1]) == "2026-09-28" and pointer.read_bytes() == before


@pytest.mark.parametrize("empty", [False, True])
def test_v2_same_signal_returns_before_provider_or_model(tmp_path, runner, monkeypatch, empty):
    cfg = config(tmp_path, runner)
    cfg["strategy_version"] = "ETF_QUANT_V2"
    (Path(cfg["snapshot"]) / "trading_calendar.csv").write_text(
        "trade_date,is_trading\n2026-09-30,true\n2026-10-08,true\n2026-10-09,true\n"
    )
    monkeypatch.setattr(runner, "refresh_command", lambda *a: ["SYNTHETIC_PROVIDER"])
    release = json.loads((REPO / "strategies/etf_quant_v2/config/release.json").read_bytes())
    state = {
        "strategy_version": "ETF_QUANT_V2",
        "mode": "SIMULATION_ONLY",
        "broker_enabled": False,
        "real_order_path": False,
        "portfolio": {"initial_cash": "10000"},
        "signals": [] if empty else [{"signal_date": "2026-10-08"}],
        **{k: release[k] for k in ("candidate_sha256", "registry_sha256", "release_sha256")},
    }
    root = Path(cfg["runtime_root"])
    pointer = runner.transport.storage.publish_generation(
        root / "runs",
        "SYNTHETIC_V2_001",
        {
            "state.json": runner.transport.storage.json_bytes(state),
            "view.json": runner.transport.storage.json_bytes({"signal_count": 1}),
        },
        {"strategy_version": "ETF_QUANT_V2"},
    )
    (root / "latest.json").write_bytes(runner.transport.storage.json_bytes(pointer))
    before = (root / "latest.json").read_bytes()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat("2026-10-08T08:00:00+00:00").astimezone(tz)

    monkeypatch.setattr(runner, "datetime", Clock)

    def call(argv, **kwargs):
        if argv[0] == "git":
            return SimpleNamespace(returncode=0, stdout="d" * 40)
        pytest.fail("a committed V2 signal must not call a provider or model")

    monkeypatch.setattr(runner.transport, "call", call)
    if empty:
        with pytest.raises(runner.transport.GateError, match="EMPTY_SIGNAL"):
            runner.run_once(cfg)
        assert (root / "latest.json").read_bytes() == before
        return
    result = runner.run_once(cfg)
    assert result["status"] == "ALREADY_PROCESSED"
    assert result["strategy_version"] == "ETF_QUANT_V2"
    assert result["view"]["signal_count"] == 1
    assert (root / "latest.json").read_bytes() == before


def test_two_versions_continue_after_one_failure_and_reject_aliases(tmp_path, runner, monkeypatch):
    configs = [
        {
            "strategy_version": version,
            "control_root": str(tmp_path / version / "control"),
            "runtime_root": str(tmp_path / version / "shadow"),
        }
        for version in ("ETF_QUANT_V1", "ETF_QUANT_V2")
    ]
    calls = []

    def run(config):
        calls.append(config["strategy_version"])
        if config["strategy_version"] == "ETF_QUANT_V1":
            raise runner.transport.GateError("SYNTHETIC_PROVIDER_BLOCKER")
        return {"status": "ARMED_NON_TRADING_DAY"}

    monkeypatch.setattr(runner, "run_once", run)
    result = runner.run_versions(configs)
    assert calls == ["ETF_QUANT_V1", "ETF_QUANT_V2"]
    assert result["status"] == "BLOCKED_VERSION"
    assert result["results"][1]["status"] == "ARMED_NON_TRADING_DAY"
    configs[1]["runtime_root"] = configs[0]["runtime_root"]
    calls.clear()
    with pytest.raises(runner.transport.GateError, match="DISJOINT"):
        runner.run_versions(configs)
    assert calls == []


@pytest.mark.parametrize("namespace", ["runtime_root", "nested_control"])
def test_v2_container_control_cannot_alias_account_or_nested_host_control(
    tmp_path, runner, monkeypatch, namespace
):
    configs = [
        {
            "strategy_version": version,
            "control_root": str(tmp_path / version / "control"),
            "runtime_root": str(tmp_path / version / "account"),
        }
        for version in ("ETF_QUANT_V1", "ETF_QUANT_V2")
    ]
    configs[1]["v2_control_root"] = (
        configs[1]["runtime_root"]
        if namespace == "runtime_root"
        else str(Path(configs[1]["control_root"]) / "nested")
    )
    monkeypatch.setattr(runner, "observe_once", lambda *args: pytest.fail("unsafe roots invoked"))
    with pytest.raises(runner.transport.GateError, match="DISJOINT"):
        runner.run_versions(configs)

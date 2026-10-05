"""Synthetic host wake configuration, retry, metadata and Git update boundaries."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "scheduled_wake", REPO / "services/etf-quant-runner/scheduled_wake.py"
)
assert spec is not None and spec.loader is not None
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)


@pytest.fixture
def deployment(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").mkdir()
    log = tmp_path / "logs"
    log.mkdir()
    configs = []
    for version in ("V1", "V2"):
        value = {"strategy_version": "ETF_QUANT_" + version}
        for field in ("runtime_root", "control_root"):
            root = tmp_path / (version + field)
            root.mkdir()
            value[field] = str(root)
        if version == "V2":
            value["v2_control_root"] = value["control_root"]
        path = tmp_path / (version + ".json")
        path.write_text(json.dumps(value))
        configs.append(str(path))
    config = dict(
        checkout=str(repo),
        transport_python=sys.executable,
        git_executable=sys.executable,
        configs=configs,
        log_root=str(log),
    )
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(config))
    return repo, path, config


def test_wake_has_one_authoritative_entry_with_literal_argument_paths(deployment):
    repo, path, config = deployment
    parsed = scheduler.deployment(path, repo)
    argv = scheduler.command(parsed)
    assert argv == [
        sys.executable,
        "-B",
        str(repo / "services/etf-quant-runner/one_shot.py"),
        "--config",
        config["configs"][0],
        "--config",
        config["configs"][1],
    ]


@pytest.mark.parametrize(
    "mutation", ["overlap", "version", "within_repo", "oversize", "other_checkout"]
)
def test_unsafe_or_incomplete_scheduler_configuration_fails_before_wake(deployment, mutation):
    repo, path, config = deployment
    v2_path = Path(config["configs"][1])
    value = json.loads(v2_path.read_text())
    if mutation == "overlap":
        value["v2_control_root"] = value["runtime_root"]
    elif mutation == "version":
        value["strategy_version"] = "ETF_QUANT_V1"
    elif mutation == "within_repo":
        path = repo / "deployment.json"
        path.write_text(json.dumps(config))
    elif mutation == "oversize":
        path.write_bytes(b" " * (scheduler.MAX_CONFIG + 1))
    else:
        config["checkout"] = str(repo.parent)
        path.write_text(json.dumps(config))
    v2_path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        scheduler.deployment(path, repo)


def test_wait_provider_retry_and_duplicate_wakes_only_call_canonical_runner(
    deployment, monkeypatch
):
    _, _, config = deployment
    calls = []
    monkeypatch.setattr(
        scheduler, "git", lambda cfg, *args: "a" * 40 if args[0] == "rev-parse" else ""
    )

    def execute(argv, checkout, **kwargs):
        calls.append(argv)
        status = ["WAITING_FOR_PROVIDER_DATA", "STARTED", "ALREADY_PROCESSED"][len(calls) - 1]
        rows = [
            {
                "strategy_version": "ETF_QUANT_" + version,
                "status": status,
                "data_cutoff": "2026-10-08",
                "view": {
                    "signal_count": int(len(calls) > 1),
                    "intent_count": int(len(calls) > 1),
                    "fill_count": 0,
                },
            }
            for version in ("V1", "V2")
        ]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"results": rows}).encode())

    monkeypatch.setattr(scheduler, "execute", execute)
    first, second, third = [scheduler.wake(config) for _ in range(3)]
    assert [r["decision"] for r in first["results"]] == ["WAIT", "WAIT"]
    assert [r["decision"] for r in second["results"]] == ["SIGNAL", "SIGNAL"]
    assert [r["decision"] for r in third["results"]] == ["NOOP", "NOOP"]
    assert all(call == scheduler.command(config) for call in calls)
    assert second["results"][0]["counts"] == third["results"][0]["counts"]


def test_dirty_checkout_and_dry_run_never_invoke_runner(deployment, monkeypatch):
    _, _, config = deployment
    monkeypatch.setattr(scheduler, "execute", lambda *args, **kwargs: pytest.fail("runner invoked"))
    monkeypatch.setattr(scheduler, "git", lambda *args: "dirty")
    with pytest.raises(ValueError, match="CLEAN_OPERATIONAL"):
        scheduler.wake(config)
    calls = []

    def clean(cfg, *args):
        calls.append(args)
        return "a" * 40 if args[0] == "rev-parse" else ""

    monkeypatch.setattr(scheduler, "git", clean)
    assert scheduler.wake(config, dry_run=True)["runner_invoked"] is False
    assert not any(args[0] in ("fetch", "merge") for args in calls)


def test_runner_failure_logs_both_versions_without_private_payload(deployment, monkeypatch):
    _, _, config = deployment
    monkeypatch.setattr(
        scheduler, "git", lambda cfg, *args: "a" * 40 if args[0] == "rev-parse" else ""
    )
    rows = [
        {"strategy_version": "ETF_QUANT_V1", "status": "BLOCKED_INTEGRITY", "secret": "PRIVATE"},
        {
            "strategy_version": "ETF_QUANT_V2",
            "status": "WAITING_FOR_DATA",
            "view": {"holdings": ["PRIVATE"]},
        },
    ]
    monkeypatch.setattr(
        scheduler,
        "execute",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout=json.dumps({"results": rows}).encode()
        ),
    )
    result = scheduler.wake(config)
    assert result["status"] == "ERROR" and len(result["results"]) == 2
    assert "PRIVATE" not in json.dumps(result)


def test_accounting_metadata_and_armed_wait_remain_visible_without_payload():
    result = scheduler.summary(
        {
            "strategy_version": "ETF_QUANT_V1",
            "status": "STARTED",
            "lifecycle_state": "SHADOW_RUNNING",
            "data_cutoff": "2026-10-09",
            "run_id": "SYNTHETIC_T1",
            "signal_id": "SYNTHETIC_SIGNAL",
            "shadow_epoch": {"epoch_id": "SYNTHETIC_EPOCH", "private": "OMIT"},
            "fill_count": 2,
        }
    )
    assert result["accounting_state"] == "SHADOW_RUNNING"
    assert result["state_identity"] == "SYNTHETIC_T1"
    assert result["latest_data_date"] == "2026-10-09" and result["counts"]["fill_count"] == 2
    assert result["signal_identity"] == "SYNTHETIC_SIGNAL"
    assert result["epoch_identity"] == "SYNTHETIC_EPOCH" and "OMIT" not in json.dumps(result)
    assert scheduler.summary({"status": "ARMED_WAITING_FOR_FINALIZED_DATA"})["decision"] == "WAIT"


def test_real_git_fast_forward_preserves_dirty_or_divergent_checkout(tmp_path):
    git_executable = "git"
    upstream, checkout = tmp_path / "upstream", tmp_path / "operations"
    environment = dict(scheduler.os.environ)
    environment.pop("GIT_DIR", None)
    environment.pop("GIT_WORK_TREE", None)

    def run(*args, cwd=tmp_path):
        return subprocess.run(
            [git_executable, *args], cwd=cwd, env=environment, check=True, capture_output=True
        )

    run("init", "-b", "main", str(upstream))
    run("-C", str(upstream), "config", "user.email", "synthetic@example.invalid")
    run("-C", str(upstream), "config", "user.name", "Synthetic fixture")
    (upstream / "source.txt").write_text("first")
    run("-C", str(upstream), "add", ".")
    run("-C", str(upstream), "commit", "-m", "synthetic initial")
    run("clone", str(upstream), str(checkout))
    config = {"checkout": str(checkout), "git_executable": git_executable}
    (upstream / "source.txt").write_text("second")
    run("-C", str(upstream), "commit", "-am", "synthetic update")
    scheduler.git(config, "fetch", "origin", "--prune")
    scheduler.git(config, "merge", "--ff-only", "origin/main")
    assert (checkout / "source.txt").read_text() == "second"
    (checkout / "source.txt").write_text("owned local change")
    with pytest.raises(ValueError, match="CLEAN_OPERATIONAL"):
        scheduler.wake(config)
    assert (checkout / "source.txt").read_text() == "owned local change"
    run("-C", str(checkout), "config", "user.email", "synthetic@example.invalid")
    run("-C", str(checkout), "config", "user.name", "Synthetic fixture")
    run("-C", str(checkout), "commit", "-am", "synthetic owned branch change")
    local_head = scheduler.git(config, "rev-parse", "HEAD")
    (upstream / "source.txt").write_text("third upstream")
    run("-C", str(upstream), "commit", "-am", "synthetic upstream divergence")
    with pytest.raises(ValueError, match="SCHEDULER_GIT_GATE_FAILED"):
        scheduler.wake(config)
    assert scheduler.git(config, "rev-parse", "HEAD") == local_head
    assert (checkout / "source.txt").read_text() == "owned local change"

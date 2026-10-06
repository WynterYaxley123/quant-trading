"""Synthetic source/state isolation and fixed external dependency regressions."""

import importlib.util
import json
from pathlib import Path

import pytest

from scripts.engineering.integrity_delta import build

ROOT = Path(__file__).resolve().parents[1]


def test_source_transition_preserves_every_superseded_delta_change():
    previous_path = "reports/engineering/v8-integrity.json"
    previous = json.loads((ROOT / previous_path).read_text())["implementation_integrity"]
    result = build(
        ROOT,
        previous["parent_manifest_path"],
        "reports/engineering/deployment-source-integrity.json",
        "HEAD",
        "Synthetic transition regression",
        "docs/engineering/deployment-source-boundary.md",
        previous_path,
    )["implementation_integrity"]
    assert set(previous["files"]).issubset(result["files"])
    assert previous_path in result["files"]


spec = importlib.util.spec_from_file_location(
    "deployment_check", ROOT / "scripts/operations/verify_deployment.py"
)
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "services/etf-quant-runner").mkdir(parents=True)
    (source / "services/etf-quant-runner/scheduled_wake.py").touch()
    deployment = tmp_path / "deployment"
    result = {
        "mode": "SIMULATION_ONLY",
        "broker_enabled": False,
        "real_order_path": False,
        "source_repository": str(source),
        "deployment_root": str(deployment),
    }
    for role in tool.ROLES:
        target = deployment / role
        target.mkdir(parents=True)
        result[role] = str(target)
    monkeypatch.setattr(
        tool, "git_value", lambda root, *args: "" if args[0] == "status" else "a" * 40
    )
    return result


def test_read_only_verifier_does_not_open_or_modify_business_files(settings):
    state = Path(settings["runtime_root"]) / "ledger.json"
    state.write_bytes(b"SYNTHETIC_SENTINEL_DO_NOT_PARSE")
    result = tool.verify(settings, {"commit": "a" * 40})
    assert result["status"] == "PASS"
    assert result["business_events_created"] is False
    assert state.read_bytes() == b"SYNTHETIC_SENTINEL_DO_NOT_PARSE"
    assert all(
        value not in str(result)
        for value in settings.values()
        if isinstance(value, str) and value.startswith("/")
    )


def test_provider_drift_overlap_escape_and_execution_switch_fail_closed(settings, monkeypatch):
    with pytest.raises(ValueError, match="PIN_MISMATCH"):
        tool.verify(settings, {"commit": "b" * 40})
    for change in (
        {"broker_enabled": True},
        {"runtime_root": settings["data_root"]},
        {"control_root": settings["source_repository"]},
        {"unexpected_secret": "SYNTHETIC"},
    ):
        with pytest.raises(ValueError):
            tool.verify(settings | change, {"commit": "a" * 40})
    monkeypatch.setattr(tool, "git_value", lambda *args: "a" * 40)
    with pytest.raises(ValueError, match="SOURCE_DIRTY"):
        tool.verify(settings, {"commit": "a" * 40})


def test_environment_expansion_and_symlink_escape_are_validated(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("DEPLOYMENT_ROOT", settings["deployment_root"])
    assert tool.directory("${DEPLOYMENT_ROOT}/data_root") == Path(settings["data_root"])
    with pytest.raises(ValueError):
        tool.directory("${MISSING_REQUIRED_ROOT}/data")
    link = Path(settings["deployment_root"]) / "escape"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="CONTAINMENT"):
        tool.verify(settings | {"control_root": str(link)}, {"commit": "a" * 40})

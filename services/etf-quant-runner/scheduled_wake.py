"""External scheduler transport: update owned main checkout, wake one_shot, log metadata.

Standard library only. No calendar, prices, model, allocation or accounting logic.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
MAX_CONFIG = 64 * 1024


def external(path: str, *, directory: bool = False) -> Path:
    """Deployment configuration and logs must resolve outside every Git checkout."""
    value = Path(path)
    if not value.is_absolute():
        raise ValueError("ABSOLUTE_EXTERNAL_PATH_REQUIRED")
    value = value.resolve(strict=True)
    if any((parent / ".git").exists() for parent in (value, *value.parents)):
        raise ValueError("EXTERNAL_DEPLOYMENT_PATH_REQUIRED")
    if value.is_dir() != directory:
        raise ValueError("DEPLOYMENT_PATH_TYPE_INVALID")
    return value


def read_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_CONFIG + 1)
    value = json.loads(raw)
    if len(raw) > MAX_CONFIG or not isinstance(value, dict):
        raise ValueError("BOUNDED_CONFIG_REQUIRED")
    return value


def deployment(path: Path, repo: Path = REPO) -> dict[str, Any]:
    config = read_config(external(str(path)))
    if set(config) != {"checkout", "transport_python", "git_executable", "configs", "log_root"}:
        raise ValueError("DEPLOYMENT_SCHEMA_INVALID")
    checkout = Path(config["checkout"]).resolve(strict=True)
    if checkout != repo.resolve() or not (checkout / ".git").exists():
        raise ValueError("SCHEDULER_CHECKOUT_BINDING_REQUIRED")
    for key in ("transport_python", "git_executable"):
        executable = Path(config[key])
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("EXPLICIT_EXECUTABLE_REQUIRED")
    paths = config["configs"]
    if not isinstance(paths, list) or len(paths) != 2:
        raise ValueError("BOTH_VERSION_CONFIGS_REQUIRED")
    versions: set[str] = set()
    owned: list[Path] = []
    for name in paths:
        value = read_config(external(name))
        version = value.get("strategy_version")
        if version not in ("ETF_QUANT_V1", "ETF_QUANT_V2") or version in versions:
            raise ValueError("DISTINCT_STRATEGY_VERSIONS_REQUIRED")
        versions.add(version)
        roots = [external(value[key], directory=True) for key in ("runtime_root", "control_root")]
        if version == "ETF_QUANT_V2":
            roots.append(external(value["v2_control_root"], directory=True))
        for i, left in enumerate(roots):
            for j, right in enumerate(roots[:i]):
                if version == "ETF_QUANT_V2" and i == 2 and j == 1 and left == right:
                    continue  # The host/container control alias is explicitly supported.
                if left.is_relative_to(right) or right.is_relative_to(left):
                    raise ValueError("ACCOUNT_CONTROL_ISOLATION_REQUIRED")
        if any(a.is_relative_to(b) or b.is_relative_to(a) for a in roots for b in owned):
            raise ValueError("V1_V2_ISOLATION_REQUIRED")
        owned.extend(roots)
    external(config["log_root"], directory=True)
    return config


def command(config: dict[str, Any]) -> list[str]:
    """Only the canonical runner receives the two external version configurations."""
    return [
        config["transport_python"],
        "-B",
        str(Path(config["checkout"]) / "services/etf-quant-runner/one_shot.py"),
        *[arg for name in config["configs"] for arg in ("--config", name)],
    ]


def execute(argv: list[str], checkout: str, *, timeout: int = 120) -> subprocess.CompletedProcess:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    environment.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(
            argv,
            cwd=checkout,
            env=environment,
            stdout=output,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        output.seek(0)
        body = output.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise ValueError("BOUNDED_RUNNER_RESPONSE_REQUIRED")
    return subprocess.CompletedProcess(argv, result.returncode, body)


def git(config: dict[str, Any], *args: str) -> str:
    result = execute([config["git_executable"], "--no-optional-locks", *args], config["checkout"])
    if result.returncode:
        raise ValueError("SCHEDULER_GIT_GATE_FAILED")
    return result.stdout.decode("utf-8").strip()


def summary(result: dict[str, Any]) -> dict[str, Any]:
    """Keep operational identities/counts; never copy portfolio payloads or stderr."""
    view = result.get("view", {})
    status = result["status"]
    decision = (
        "ERROR"
        if status.startswith("BLOCKED")
        else "NOOP"
        if status in ("ALREADY_PROCESSED", "READY_NO_SIGNAL", "ARMED_NON_TRADING_DAY")
        else "WAIT"
        if "WAITING" in status
        else "SIGNAL"
        if status == "STARTED"
        else "NOOP"
    )
    counts = {
        key: result.get(key, view.get(key))
        for key in ("epoch_count", "signal_count", "intent_count", "fill_count")
    }
    return {
        "strategy_version": result.get("strategy_version"),
        "runner_status": status,
        "decision": decision,
        "reason_code": result.get("reason_code", result.get("blocker")),
        "latest_data_date": result.get("data_cutoff", view.get("latest_data_date")),
        "signal_date": view.get("signal_date"),
        "state_identity": result.get("pointer", result.get("run_id")),
        "signal_identity": result.get("signal_id"),
        "epoch_identity": result.get("shadow_epoch", {}).get("epoch_id"),
        "accounting_state": result.get("lifecycle_state", view.get("next_accounting_state")),
        "counts": counts,
    }


def wake(config: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    if git(config, "status", "--porcelain"):
        raise ValueError("CLEAN_OPERATIONAL_CHECKOUT_REQUIRED")
    if not dry_run:
        git(config, "fetch", "origin", "--prune")
        # This checkout belongs exclusively to this deployment. Never reset,
        # switch, clean, stash, rewrite history or update another checkout.
        git(config, "merge", "--ff-only", "origin/main")
    head = git(config, "rev-parse", "HEAD")
    if head != git(config, "rev-parse", "origin/main"):
        raise ValueError("MERGED_MAIN_REQUIRED")
    if dry_run:
        return {"status": "DRY_RUN", "code_commit": head, "runner_invoked": False}
    result = execute(command(config), config["checkout"], timeout=10800)
    if len(result.stdout) > 4 * 1024 * 1024:
        raise ValueError("BOUNDED_RUNNER_RESPONSE_REQUIRED")
    value = json.loads(result.stdout)
    observations = value.get("results", [value])
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("BOTH_VERSION_RECEIPTS_REQUIRED")
    return {
        "status": "ERROR" if result.returncode else "OBSERVED",
        "code_commit": head,
        "runner_exit_code": result.returncode,
        "results": [summary(item) for item in observations],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config: dict[str, Any] | None = None
    try:
        config = deployment(args.deployment)
        receipt = wake(config, dry_run=args.dry_run)
    except Exception as error:
        receipt = {
            "status": "ERROR",
            "reason_code": str(error)
            if isinstance(error, ValueError) and str(error).isupper()
            else "SCHEDULER_TRANSPORT_FAILURE",
            "exception_class": type(error).__name__,
        }
    receipt["observed_at"] = datetime.now(timezone.utc).isoformat()
    body = json.dumps(receipt, sort_keys=True, allow_nan=False)
    if config is not None:
        try:
            root = external(config["log_root"], directory=True)
            name = (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "_" + uuid4().hex + ".json"
            )
            with (root / name).open("x", encoding="utf-8") as stream:
                stream.write(body + "\n")
        except (OSError, ValueError):
            receipt = {"status": "ERROR", "reason_code": "SCHEDULER_LOG_FAILURE"}
            body = json.dumps(receipt)
    sys.stdout.write(body + "\n")
    return 3 if receipt["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())

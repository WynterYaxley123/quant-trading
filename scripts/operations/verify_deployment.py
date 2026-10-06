"""Read-only deployment boundary and external source pin verification.

This tool never starts a runner, opens market records or writes deployment state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("data_root", "runtime_root", "control_root", "provider_source_root")


def directory(value: object) -> Path:
    """Resolve an existing absolute directory, rejecting unresolved variables."""
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("DIRECTORY_REQUIRED")

    def substitute(match: re.Match[str]) -> str:
        replacement = os.environ.get(match[1])
        if not replacement:
            raise ValueError("ENVIRONMENT_VARIABLE_REQUIRED")
        return replacement

    expanded = re.sub(r"\$\{([A-Z][A-Z0-9_]*)\}", substitute, value)
    if "$" in expanded:
        raise ValueError("UNRESOLVED_VARIABLE")
    path = Path(expanded)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("ABSOLUTE_LITERAL_PATH_REQUIRED")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("DIRECTORY_REQUIRED")
    return resolved


def git_value(root: Path, *args: str) -> str:
    """Use argv-only local Git reads; never emit subprocess stderr or credentials."""
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise ValueError("GIT_VERIFICATION_BLOCKED")
    return result.stdout.strip()


def verify(settings: dict[str, object], pin: dict[str, object]) -> dict[str, object]:
    """Validate ownership boundaries without reading any market or ledger payload."""
    expected = {
        "mode",
        "broker_enabled",
        "real_order_path",
        "source_repository",
        "deployment_root",
        *ROLES,
    }
    if set(settings) != expected:
        raise ValueError("CONFIG_FIELDS_MISMATCH")
    if (
        settings["mode"] != "SIMULATION_ONLY"
        or settings["broker_enabled"] is not False
        or settings["real_order_path"] is not False
    ):
        raise ValueError("SIMULATION_ONLY_REQUIRED")
    source = directory(settings["source_repository"])
    deployment = directory(settings["deployment_root"])
    if source.is_relative_to(deployment) or deployment.is_relative_to(source):
        raise ValueError("SOURCE_STATE_BOUNDARY_REQUIRED")
    roots = {role: directory(settings[role]) for role in ROLES}
    if any(root == deployment or not root.is_relative_to(deployment) for root in roots.values()):
        raise ValueError("DEPLOYMENT_CONTAINMENT_REQUIRED")
    values = list(roots.values())
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(values)
        for b in values[i + 1 :]
    ):
        raise ValueError("DISJOINT_ROOTS_REQUIRED")
    if not (source / "services/etf-quant-runner/scheduled_wake.py").is_file():
        raise ValueError("CANONICAL_SOURCE_REQUIRED")
    provider = roots["provider_source_root"]
    if git_value(provider, "rev-parse", "HEAD") != pin["commit"]:
        raise ValueError("PROVIDER_PIN_MISMATCH")
    if git_value(provider, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("PROVIDER_SOURCE_DIRTY")
    return {
        "status": "PASS",
        "mode": "READ_ONLY",
        "source_commit": git_value(source, "rev-parse", "HEAD"),
        "provider_commit": pin["commit"],
        "boundaries": {role: True for role in ROLES},
        "business_events_created": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", required=True, type=Path, help="External deployment JSON; no secrets needed"
    )
    args = parser.parse_args()
    try:
        if args.config.stat().st_size > 64 * 1024:
            raise ValueError("CONFIG_TOO_LARGE")
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        pin = json.loads((ROOT / "config/deployment/cnequity.pin.json").read_text())
        result = verify(config, pin)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Do not disclose private paths, config values or subprocess diagnostics.
        print(json.dumps({"status": "BLOCKED", "mode": "READ_ONLY"}))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

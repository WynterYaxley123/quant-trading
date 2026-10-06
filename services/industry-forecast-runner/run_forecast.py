"""Docker-only SWL2 forecast invocation; public facts remain in read-only mounts."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.implementation import verify_implementation
from strategies.etf_quant.runtime.storage import digest, external_root, json_bytes, process_lock
from strategies.swl2_ridge import ledger
from strategies.swl2_ridge.adapter import prediction
from strategies.swl2_ridge.engine import HORIZONS, first_session, mature, publication_gate
from strategies.swl2_ridge.engine import publish as publish_forecast
from strategies.swl2_ridge.facts import external_read, load
from strategies.swl2_ridge.metrics import aggregate
from strategies.swl2_ridge.registry import ROOT, families, resolve, verify_model

TRANSITION = "config/research/swl2-industry-forecast-transition.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def merged_source() -> tuple[str, str, str]:
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("CLEAN_MERGED_SOURCE_REQUIRED")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"], cwd=ROOT, check=False
    ).returncode:
        raise ValueError("MERGED_MAIN_SOURCE_REQUIRED")
    transition_commit = git(
        "log", "origin/main", "--first-parent", "--diff-filter=A", "--format=%H", "--", TRANSITION
    ).splitlines()
    if len(transition_commit) != 1:
        raise ValueError("UNIQUE_MERGED_TRANSITION_REQUIRED")
    merge_commit = transition_commit[0]
    merged_at = git("show", "-s", "--format=%cI", merge_commit)
    verify_implementation(ROOT)
    return commit, merge_commit, merged_at


def _invoke(
    family: dict[str, Any],
    config: dict[str, Any],
    *,
    now: datetime,
    source_commit: str,
    merge_commit: str,
    merge_at: str,
    dry_run: bool,
    preflight: bool,
) -> dict[str, Any]:
    model_hash = verify_model(family)
    root = Path(config["runtime_root"])
    if not root.is_absolute() or root.name != "industry-forecast":
        raise ValueError("EXPLICIT_INDUSTRY_FORECAST_ROOT_REQUIRED")
    root = root / family["family_id"]
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise ValueError("EXTERNAL_FORECAST_RUNTIME_REQUIRED")
    if not dry_run and not preflight:
        ledger.recover(root)
    state = ledger.read(root)
    binding = (
        state["binding"]
        if state
        else {
            "schema_version": 1,
            "family_id": family["family_id"],
            "source_commit": source_commit,
            "merge_commit": merge_commit,
            "merge_at": merge_at,
            "freeze_at": now.isoformat(),
            "model_contract_hash": model_hash,
        }
    )
    if (
        binding["source_commit"] != source_commit
        or binding["model_contract_hash"] != model_hash
        or binding["merge_commit"] != merge_commit
    ):
        raise ValueError("MODEL_OR_SOURCE_BINDING_MISMATCH")
    inputs = load(family, config["families"][family["family_id"]], now)
    first = first_session(binding, tuple(inputs["calendar"]))
    if preflight or dry_run:
        try:
            publication_gate(binding, inputs, now)
            status = "ELIGIBLE_DRY_RUN"
        except ValueError as error:
            status = str(error)
        return {
            "family_id": family["family_id"],
            "status": status,
            "first_forward_signal_date": first,
            "read_only": True,
            "data_cutoff": str(inputs["cutoff"]),
            "events_created": 0,
        }
    if not state:
        binding = ledger.initialize(root, binding)
    existing = {
        e["body"]["signal_date"]
        for e in (state["events"] if state else [])
        if e["body"]["kind"] == "FORECAST"
    }
    status = "NOOP_ALREADY_PUBLISHED"
    try:
        day = publication_gate(binding, inputs, now)
    except ValueError as error:
        status = str(error)
    else:
        if str(day) not in existing:
            codes = sorted(family["industry_codes"])
            inputs["provenance"]["signal_levels_hash"] = digest(
                json_bytes(inputs["closes"].loc[str(day), codes].to_dict())
            )
            status = publish_forecast(
                root, family, binding, inputs, prediction(family, inputs, now), now
            )
    evaluations = mature(root, inputs, now)
    return {
        "family_id": family["family_id"],
        "status": status,
        "first_forward_signal_date": first,
        "metrics": [aggregate(evaluations, h) for h in HORIZONS],
    }


def invoke(
    family: dict[str, Any],
    config: dict[str, Any],
    *,
    now: datetime,
    source_commit: str,
    merge_commit: str,
    merge_at: str,
    dry_run: bool,
    preflight: bool,
) -> dict[str, Any]:
    """Serialize genuine retries before factual loading or fitting, with no dry-run writes."""
    arguments: dict[str, Any] = dict(
        now=now,
        source_commit=source_commit,
        merge_commit=merge_commit,
        merge_at=merge_at,
        dry_run=dry_run,
        preflight=preflight,
    )
    if dry_run or preflight:
        return _invoke(family, config, **arguments)
    base = Path(config["runtime_root"])
    if not base.is_absolute() or base.name != "industry-forecast":
        raise ValueError("EXPLICIT_INDUSTRY_FORECAST_ROOT_REQUIRED")
    namespace = external_root(ledger.checked_namespace(base / family["family_id"]))
    with process_lock(namespace / ".runner.guard"):
        return _invoke(family, config, **arguments)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--family", choices=("swl2-ridge-v1", "swl2-ridge-v2"))
    selection.add_argument("--all-swl2", action="store_true")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--read-only-preflight", action="store_true")
    args = parser.parse_args()
    if not Path("/.dockerenv").exists():
        raise ValueError("DOCKER_QUANTITATIVE_EXECUTION_REQUIRED")
    try:
        source, merge, merged_at = merged_source()
        config = json.loads(external_read(str(args.config)).read_bytes())
        selected = families() if args.all_swl2 else [resolve(args.family)]
        result = [
            invoke(
                f,
                config,
                now=datetime.now(timezone.utc),
                source_commit=source,
                merge_commit=merge,
                merge_at=merged_at,
                dry_run=args.dry_run,
                preflight=args.read_only_preflight,
            )
            for f in selected
        ]
        print(json.dumps({"results": result}, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": str(error)
                    if isinstance(error, ValueError)
                    else "FORECAST_INPUT_UNAVAILABLE",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

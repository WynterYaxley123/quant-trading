"""Docker-only manual integration entrypoint; no automatic clock overrides."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from ..domain import StrategyConfig, TransactionCost
from ..mapping.registry import load_registry
from .exports import ExportProvider
from .shadow import daily_cycle
from .storage import GateError, json_bytes
from .view import public_strategy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("describe", "verify-export", "cycle"))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--commit")
    args = parser.parse_args()
    if args.command == "describe":
        print(json_bytes(public_strategy()).decode())
        return 0
    if not args.profile or not args.snapshot:
        raise GateError("EXPLICIT_PROFILE_AND_SNAPSHOT_REQUIRED")
    profile = json.loads(args.profile.read_bytes())
    identity = profile["provider_identity"]
    if not identity or profile.get("mode") != "SIMULATION_ONLY":
        raise GateError("PROFILE_IDENTITY_BLOCKER")
    now = datetime.now(timezone.utc)
    provider = ExportProvider(args.snapshot, expected_identity=identity, now=now)
    if args.command == "verify-export":
        result = {"status": "EXPORT_VERIFIED", "snapshot_id": provider.manifest["snapshot_id"],
            "row_counts": {k: len(v) for k, v in provider.tables.items()},
            "adjustment_exact_rows": int(provider.tables["stock_bars"].adj_is_exact.sum()),
            "adjustment_rejected_rows": 0, "available_at": None, "source_published_at": None}
    else:
        if args.runtime is None or args.registry is None:
            raise GateError("EXPLICIT_RUNTIME_AND_REGISTRY_REQUIRED")
        registry = load_registry(args.registry, evidence_root=args.evidence_root)
        costs = TransactionCost(**profile.get("costs", {}))
        config = StrategyConfig(costs=costs)
        result = daily_cycle(provider, registry, args.runtime, now=now, code_commit=args.commit, config=config,
            lot_size=profile.get("lot_size", 100), min_constituents=profile.get("min_valid_constituents", 5),
            coverage_threshold=profile.get("min_constituent_coverage_ratio", .8),
            classification_version=profile.get("classification_version"))
    print(json_bytes(result).decode())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(json_bytes({"status": "BLOCKED", "blocker": error.code, "details": error.details}).decode())
        raise SystemExit(2)

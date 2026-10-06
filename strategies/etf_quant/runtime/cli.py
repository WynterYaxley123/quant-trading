"""Docker-only manual integration entrypoint; no automatic clock overrides."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ..domain import StrategyConfig, TransactionCost
from ..mapping.pit import load_pit_evidence
from ..mapping.registry import load_registry
from .exports import ExportProvider
from .formal import load_formal_contract
from .model_inputs import bind_model_inputs
from .oneshot import one_shot
from .shadow import daily_cycle
from .storage import GateError, json_bytes
from .view import public_strategy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("describe", "verify-export", "cycle", "one-shot"))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--commit")
    parser.add_argument(
        "--execution-policy", choices=("STRICT_TOP5", "B40_WITH_CASH"), default="STRICT_TOP5"
    )
    parser.add_argument("--pit-evidence", type=Path)
    parser.add_argument("--pit-source-root", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--pit-registry", type=Path)
    parser.add_argument("--model-reference-snapshot", type=Path)
    args = parser.parse_args()
    if args.command in ("cycle", "one-shot"):
        raise GateError("SWL2_ETF_PRODUCTIZATION_RETIRED_LEGACY_READ_ONLY")
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
        result = {
            "status": "EXPORT_VERIFIED",
            "snapshot_id": provider.manifest["snapshot_id"],
            "row_counts": {k: len(v) for k, v in provider.tables.items()},
            "adjustment_exact_rows": int(provider.tables["stock_bars"].adj_is_exact.sum()),
            "adjustment_rejected_rows": provider.manifest["adjustment_rejected_rows"],
            "available_at": None,
            "source_published_at": None,
        }
    else:
        if args.runtime is None or args.registry is None:
            raise GateError("EXPLICIT_RUNTIME_AND_REGISTRY_REQUIRED")
        registry = load_registry(args.registry, evidence_root=args.evidence_root)
        if args.execution_policy == "B40_WITH_CASH" and (
            args.pit_evidence is None or args.pit_source_root is None
        ):
            raise GateError("EXPLICIT_PIT_EVIDENCE_REQUIRED")
        if args.execution_policy == "STRICT_TOP5" and (
            args.pit_evidence is not None or args.pit_source_root is not None
        ):
            raise GateError("STRICT_PATH_PIT_EVIDENCE_FORBIDDEN")
        pit_evidence = (
            load_pit_evidence(args.pit_evidence, source_root=args.pit_source_root)
            if args.execution_policy == "B40_WITH_CASH"
            else None
        )
        costs = TransactionCost(**profile.get("costs", {}))
        config = StrategyConfig(costs=costs)
        formal = args.command == "one-shot"
        if formal and args.model_reference_snapshot is None:
            raise GateError("EXPLICIT_MODEL_REFERENCE_REQUIRED")
        if args.model_reference_snapshot is not None:
            bind_model_inputs(provider, args.model_reference_snapshot)
        if formal and (
            args.candidate is None
            or args.pit_registry is None
            or args.execution_policy != "B40_WITH_CASH"
        ):
            raise GateError("EXPLICIT_FORMAL_CERTIFICATION_REQUIRED")
        contract = (
            load_formal_contract(args.candidate, args.pit_registry, registry, pit_evidence)
            if formal
            else None
        )
        kwargs = (
            {"formal_contract": contract} if formal else {"execution_policy": args.execution_policy}
        )
        result = (one_shot if formal else daily_cycle)(
            provider,
            registry,
            args.runtime,
            now=now,
            code_commit=args.commit,
            config=config,
            lot_size=profile.get("lot_size", 100),
            min_constituents=profile.get("min_valid_constituents", 5),
            coverage_threshold=profile.get("min_constituent_coverage_ratio", 0.8),
            classification_version=profile.get("classification_version"),
            pit_evidence=pit_evidence,
            **kwargs,
        )
    print(json_bytes(result).decode())
    return 2 if result.get("status") == "BLOCKED_INTEGRITY" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(
            json_bytes(
                {"status": "BLOCKED", "blocker": error.code, "details": error.details}
            ).decode()
        )
        raise SystemExit(2)
    except Exception as error:
        print(
            json_bytes(
                {
                    "status": "BLOCKED",
                    "blocker": "RUNTIME_INPUT_BLOCKER",
                    "exception_class": type(error).__name__,
                }
            ).decode()
        )
        raise SystemExit(2)

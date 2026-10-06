"""Explicit-input V2 forward signal preparation; no broker or automatic launch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from strategies.etf_quant.portfolio.policy import (
    POLICY_B40_WITH_CASH,
    BenchmarkExposureVector,
    IndustryCandidate,
    evaluate_policy,
)

from .mapping import select_mappings
from .model import SHANGHAI, FrozenSpecification, Observation, predict_forecast


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def prepare_signal(
    spec: FrozenSpecification,
    observations: Sequence[Observation],
    current_factors: Mapping[str, tuple[float, ...]],
    *,
    calendar: Sequence[date],
    signal_at: datetime,
    snapshot_available_at: datetime,
    finalized: bool,
    mapping_pools: Mapping[str, Sequence[IndustryCandidate]],
    exposure_vectors: dict[str, BenchmarkExposureVector],
    mapping_available_at: datetime,
    allow_unvalidated_research: bool = False,
) -> dict[str, Any]:
    """Fit coefficients from mature facts, then reuse frozen V1 execution functions."""
    if any(t.tzinfo is None for t in (signal_at, snapshot_available_at, mapping_available_at)):
        raise ValueError("FORWARD_TIMEZONE_REQUIRED")
    day = signal_at.astimezone(SHANGHAI).date()
    sessions = tuple(calendar)
    if (
        not finalized
        or sessions != tuple(sorted(set(sessions)))
        or day not in sessions
        or signal_at.astimezone(SHANGHAI).time() < time(15)
        or day <= spec.frozen_at.astimezone(SHANGHAI).date()
        or snapshot_available_at > signal_at
        or mapping_available_at > signal_at
        or (not spec.validated and not allow_unvalidated_research)
    ):
        raise ValueError("GENUINE_FINALIZED_FORWARD_DATE_REQUIRED")
    positions = {session: i for i, session in enumerate(sessions)}
    index = positions[day]
    if index + 1 >= len(sessions):
        raise ValueError("OFFICIAL_T_PLUS_ONE_SESSION_REQUIRED")
    result = predict_forecast(
        spec,
        observations,
        current_factors,
        calendar=calendar,
        signal_at=signal_at,
        snapshot_available_at=snapshot_available_at,
        finalized=finalized,
        allow_unvalidated_research=allow_unvalidated_research,
    )
    ranked, model_records = result["rankings"], result["models"]
    # Caller obtains pools through the existing admitted mapping/evidence boundary.
    # Scores are injected only after fitting; proxies never rescale those scores.
    top = ranked[:5]
    pools = {
        code: tuple(
            IndustryCandidate(**(vars(c) | {"final_score": score}))
            for c in mapping_pools.get(code, ())
        )
        for code, score in top
    }
    chosen = select_mappings(top, pools)
    allocation = evaluate_policy(POLICY_B40_WITH_CASH, list(chosen), exposure_vectors, cap=0.35)
    return {
        "product": "ETF_QUANT_V2",
        "candidate_sha256": spec.candidate_sha256,
        "signal_date": str(day),
        "execution_date": str(sessions[index + 1]),
        "models": model_records,
        "rankings": ranked,
        "allocation": allocation.as_dict(),
        "accounting": "WAIT_FOR_GENUINE_FINALIZED_T_PLUS_ONE_RAW_OPEN",
        "mode": "SIMULATION_ONLY",
        "validation_accepted": spec.validated and not spec.final_oos_authorized,
        "historical_final_oos_accepted": spec.validated and spec.final_oos_authorized,
        "broker_enabled": False,
        "real_order_path": False,
    }


def publish_forward_plan(
    root: Path, plan: dict[str, Any], *, authorization: bool, frozen_at: datetime, now: datetime
) -> Path:
    """Explicit future human launch gate, independent immutable V2 namespace."""
    from strategies.swl2_ridge.retirement import guard_legacy_write

    guard_legacy_write(root)
    resolved = root.resolve()
    if not authorization:
        raise ValueError("EXPLICIT_FUTURE_SHADOW_LAUNCH_AUTHORIZATION_REQUIRED")
    if any(
        (p / ".git").exists() or p.name.lower() == "etf-quant-v1"
        for p in (resolved, *resolved.parents)
    ):
        raise ValueError("INDEPENDENT_EXTERNAL_V2_NAMESPACE_REQUIRED")
    if resolved.name != "etf-quant-v2" or now.tzinfo is None or frozen_at.tzinfo is None:
        raise ValueError("INDEPENDENT_EXTERNAL_V2_NAMESPACE_REQUIRED")
    signal_day = date.fromisoformat(plan["signal_date"])
    if (
        signal_day <= frozen_at.astimezone(SHANGHAI).date()
        or signal_day > now.astimezone(SHANGHAI).date()
    ):
        raise ValueError("RETROACTIVE_OR_FUTURE_EPOCH_DENIED")
    if (
        plan.get("product") != "ETF_QUANT_V2"
        or plan.get("broker_enabled")
        or plan.get("real_order_path")
        or plan.get("mode") != "SIMULATION_ONLY"
    ):
        raise ValueError("SIMULATION_ONLY_V2_REQUIRED")
    resolved.mkdir(parents=True, exist_ok=True)
    # One lock covers uniqueness and publication, so competing callers cannot
    # create two generations for one date. A crash leaves a closed gate.
    lock = resolved / ".publish.lock"
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        existing = sorted(resolved.glob("*/plan.json"))
        if (
            existing
            and max(date.fromisoformat(json.loads(p.read_text())["signal_date"]) for p in existing)
            >= signal_day
        ):
            raise ValueError("STRICTLY_FORWARD_UNIQUE_SIGNAL_REQUIRED")
        generation = resolved / (str(signal_day) + "_" + content_hash(plan)[:12])
        generation.mkdir()
        descriptor = os.open(generation / "plan.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n")
    finally:
        lock.unlink()
    return generation


def load_candidate(path: Path) -> dict[str, Any]:
    from strategies.etf_quant.runtime.implementation import verify_implementation

    repository = Path(__file__).resolve().parents[2]
    certified = verify_implementation(repository)
    name = "strategies/etf_quant_v2/config/candidate.json"
    if (
        path.resolve() != (repository / name).resolve()
        or certified.get(name) != hashlib.sha256(path.read_bytes()).hexdigest()
    ):
        raise ValueError("CERTIFIED_V2_CANDIDATE_PATH_REQUIRED")
    doc = json.loads(path.read_text())
    body = {k: v for k, v in doc.items() if k != "candidate_sha256"}
    if doc.get("candidate_sha256") != content_hash(body) or doc.get("product") != "ETF_QUANT_V2":
        raise ValueError("V2_CANDIDATE_INTEGRITY_ERROR")
    if doc.get("final_oos_opened") or doc.get("shadow_started") or doc.get("broker_enabled"):
        raise ValueError("V2_RESEARCH_SAFETY_CONTRACT_ERROR")
    return doc


def main() -> None:
    print(json.dumps({"status": "SWL2_ETF_PRODUCTIZATION_RETIRED", "role": "LEGACY_READ_ONLY"}))
    return

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--authorize-future-shadow", action="store_true")
    parser.add_argument("--authorize-unvalidated-research", action="store_true")
    args = parser.parse_args()
    candidate = load_candidate(args.candidate)
    if not args.readiness_only:
        if not args.authorize_future_shadow or args.input is None or args.runtime_root is None:
            raise ValueError("EXPLICIT_FUTURE_LAUNCH_AND_FACT_INPUTS_REQUIRED")
        from .inputs import plan_from_inputs

        plan = plan_from_inputs(
            candidate,
            json.loads(args.input.read_text()),
            allow_unvalidated_research=args.authorize_unvalidated_research,
        )
        publish_forward_plan(
            args.runtime_root,
            plan,
            authorization=True,
            frozen_at=datetime.fromisoformat(candidate["frozen_at"]),
            now=datetime.now(SHANGHAI),
        )
        print(
            json.dumps(
                {
                    "product": "ETF_QUANT_V2",
                    "signal_date": plan["signal_date"],
                    "mode": "SIMULATION_ONLY",
                }
            )
        )
        return
    print(
        json.dumps(
            {
                "product": "ETF_QUANT_V2",
                "candidate_sha256": candidate["candidate_sha256"],
                "shadow_ready": True,
                "validation_accepted": candidate["validation_accepted"],
                "research_status": candidate["research_status"],
                "shadow_started": False,
                "next_start": "NEXT_GENUINE_FINALIZED_SESSION_AFTER_CANDIDATE_FREEZE",
                "epoch": 0,
                "signal": 0,
                "intent": 0,
                "fill": 0,
                "broker_enabled": False,
                "real_order_path": False,
                "final_oos_opened": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

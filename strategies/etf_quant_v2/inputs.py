"""Explicit normalized facts and admitted mapping inputs for a future V2 one-shot."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from strategies.etf_quant.portfolio.policy import BenchmarkExposureVector, IndustryCandidate

from .runtime import FrozenSpecification, Observation, prepare_signal


def plan_from_inputs(
    candidate: dict[str, Any], facts: dict[str, Any], *, allow_unvalidated_research: bool = False
) -> dict[str, Any]:
    if facts.get("candidate_sha256") != candidate["candidate_sha256"]:
        raise ValueError("INPUT_CANDIDATE_PIN_REQUIRED")
    mode = candidate["evidence_mode"]
    records = facts["observations"]
    if mode == "HIGH_CONFIDENCE" and any(r["evidence_tier"] not in ("A", "B") for r in records):
        raise ValueError("HIGH_CONFIDENCE_EVIDENCE_REQUIRED")
    selected = candidate["specification"]
    spec = FrozenSpecification(
        selected["identifier"],
        tuple(selected["horizons"]),
        tuple(selected["fusion"]),
        selected["alpha"],
        selected["training_months"],
        selected["scaling"],
        candidate["candidate_sha256"],
        datetime.fromisoformat(candidate["frozen_at"]),
        date.fromisoformat(candidate["final_oos_start"]),
        date.fromisoformat(candidate["final_oos_end"]),
        candidate["validation_accepted"],
    )
    observations = [
        Observation(
            r["industry"],
            date.fromisoformat(r["day"]),
            tuple(r["factors"]),
            {int(h): v for h, v in r["returns"].items()},
            {int(h): date.fromisoformat(v) for h, v in r["label_end"].items()},
            datetime.fromisoformat(r["observed_at"]),
            r["evidence_tier"],
        )
        for r in records
    ]
    pools = {
        code: tuple(IndustryCandidate(**r) for r in rows)
        for code, rows in facts["mapping_pools"].items()
    }
    vectors = {code: BenchmarkExposureVector(**r) for code, r in facts["exposure_vectors"].items()}
    return prepare_signal(
        spec,
        observations,
        {k: tuple(v) for k, v in facts["current_factors"].items()},
        calendar=tuple(date.fromisoformat(d) for d in facts["calendar"]),
        signal_at=datetime.fromisoformat(facts["signal_at"]),
        snapshot_available_at=datetime.fromisoformat(facts["snapshot_available_at"]),
        finalized=facts["finalized"] is True,
        mapping_pools=pools,
        exposure_vectors=vectors,
        mapping_available_at=datetime.fromisoformat(facts["mapping_available_at"]),
        allow_unvalidated_research=allow_unvalidated_research,
    )

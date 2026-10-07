"""Result-free proof of outcome chronology and the closed V1 lineage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.swl1_ridge_v1.protocol import HORIZONS, digest

V1_ARTIFACTS = (
    "config/research/swl1-ridge-v1-protocol.json",
    "config/research/swl1-ridge-v1-candidate.json",
    "config/research/swl1-ridge-v1-universe.json",
    "reports/research/swl1_ridge_v1/development.json",
    "reports/research/swl1_ridge_v1/validation.json",
    "reports/research/swl1_ridge_v1/status.json",
)


def v1_lineage(repository: Path, evidence: Path) -> dict[str, Any]:
    """Inspect lineage/consumption metadata, never another generation's OOS."""
    hashes = {name: digest((repository / name).read_bytes()) for name in V1_ARTIFACTS}
    protocol = json.loads((repository / V1_ARTIFACTS[0]).read_bytes())
    validation = json.loads((repository / V1_ARTIFACTS[4]).read_bytes())
    status = json.loads((repository / V1_ARTIFACTS[5]).read_bytes())
    failures = []
    if (
        status.get("scientific_status") != "FAILED_VALIDATION"
        or status.get("final_oos_opened") is not False
        or status.get("validation_passed") is not False
        or validation.get("passed") is not False
        or status.get("protocol_hash") != hashes[V1_ARTIFACTS[0]]
        or status.get("candidate_hash") != hashes[V1_ARTIFACTS[1]]
        or validation.get("lineage", {}).get("candidate_hash") != hashes[V1_ARTIFACTS[1]]
        or validation.get("lineage", {}).get("protocol_hash") != hashes[V1_ARTIFACTS[0]]
    ):
        failures.append("V1_CLOSED_LINEAGE_NOT_PROVEN")
    for name, expected in protocol["implementation_hashes"].items():
        if digest((repository / name).read_bytes()) != expected:
            failures.append("V1_IMPLEMENTATION_DRIFT")
    # Check existence only: if an OOS object exists, do not inspect its content.
    if any(
        (evidence / "lifecycle" / name).exists()
        for name in ("final_oos.claim.json", "final_oos.result.json", "final_oos_seal.json")
    ) or any(
        (repository / "reports/research/swl1_ridge_v1" / name).exists()
        for name in ("final_oos.json", "final_oos_seal.json")
    ):
        failures.append("V1_FINAL_OOS_CONSUMPTION_DETECTED")
    for phase in ("development", "validation"):
        claim = evidence / "lifecycle" / f"{phase}.claim.json"
        result = evidence / "lifecycle" / f"{phase}.result.json"
        if not claim.is_file() or not result.is_file():
            failures.append("V1_PRIVATE_PHASE_WITNESS_MISSING")
            continue
        lineage = json.loads(claim.read_bytes())
        recorded = json.loads(result.read_bytes())
        if (
            lineage.get("protocol_hash") != hashes[V1_ARTIFACTS[0]]
            or lineage.get("phase") != phase
            or lineage.get("consumed") is not True
            or recorded.get("lineage") != {k: v for k, v in lineage.items() if k != "consumed"}
        ):
            failures.append("V1_PRIVATE_PHASE_LINEAGE_MISMATCH")
        if (
            phase == "validation"
            and result.read_bytes() != (repository / V1_ARTIFACTS[4]).read_bytes()
        ):
            failures.append("V1_VALIDATION_PUBLIC_PRIVATE_MISMATCH")
    return {
        "passed": not failures,
        "reason_codes": sorted(set(failures)),
        "artifact_hashes": hashes,
    }


def chronology_proof(
    v1: dict[str, Any],
    dates: list[str],
    split: dict[str, Any] | None,
    lineage: dict[str, Any],
) -> dict[str, Any]:
    """V2 target is (t,t+h]; an endpoint t may equal V1's last seen maturity."""
    failures = list(lineage["reason_codes"])
    v1_indices = v1["split"]["indices"]
    seen = max(
        i + max(HORIZONS) for phase in ("development", "validation") for i in v1_indices[phase]
    )
    last_signal = max(v1_indices["validation"])
    if dates[last_signal] != v1["split"]["ranges"]["validation"]["end"] or seen >= len(dates):
        failures.append("V1_SIGNAL_SPINE_MISMATCH")
    checked = 0
    first = None
    target_first = None
    if split is None:
        failures.append("INSUFFICIENT_ELIGIBLE_VALIDATION_SIGNALS")
    else:
        validation = split["indices"]["validation"]
        first = validation[0]
        target_first = first + 1
        if first - max(split["indices"]["development"]) - 1 != 120:
            failures.append("EXACT_120_SESSION_PURGE_NOT_PROVEN")
        for signal in validation:
            for horizon in HORIZONS:
                checked += 1
                if signal + 1 <= seen or signal + horizon >= len(dates):
                    failures.append("V2_OUTCOME_OVERLAPS_SEEN_OR_IMMATURE")
    planned = v1_indices.get("final_oos", [])
    return {
        "passed": not failures,
        "reason_codes": sorted(set(failures)),
        "v1_last_validation_signal": dates[last_signal],
        "v1_max_horizon": max(HORIZONS),
        "v1_last_consumed_label_maturity_session": dates[seen] if seen < len(dates) else None,
        "v1_consumed_prefix_end_index": seen,
        "v2_validation_first_signal": dates[first] if first is not None else None,
        "v2_validation_first_outcome_session": dates[target_first]
        if target_first is not None
        else None,
        "target_convention": "Outcome returns on exchange sessions t+1 through t+h; endpoint t may equal seen maturity.",
        "outcome_intervals_checked": checked,
        "v1_planned_oos_opened": False if lineage["passed"] else None,
        "v1_planned_oos_consumed": False if lineage["passed"] else None,
        "v1_planned_oos_repurposed_as_v2_validation": bool(
            split and split["indices"]["validation"] == planned and not failures
        ),
        "v1_lineage": lineage,
    }

"""Discover independent levels without altering frozen SWL2 family definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.storage import contained, digest
from strategies.swl2_ridge.registry import ROOT
from strategies.swl2_ridge.registry import families as swl2_families

REGISTRY = "config/research/industry-forecast-families.json"


def document(root: Path, reference: dict[str, str]) -> dict[str, Any]:
    raw = contained(root, reference["path"]).read_bytes()
    if digest(raw) != reference["sha256"]:
        raise ValueError("FAMILY_REFERENCE_HASH_MISMATCH")
    result: dict[str, Any] = json.loads(raw)
    return result


def families(root: Path = ROOT) -> list[dict[str, Any]]:
    registry = json.loads(contained(root, REGISTRY).read_bytes())
    document(root, registry["swl2_registry_reference"])
    result = swl2_families(root)
    for reference in registry["additional_families"]:
        family = document(root, reference)
        artifacts = {
            key: document(root, family[key])
            for key in (
                "protocol_reference",
                "candidate_reference",
                "taxonomy_reference",
                "frozen_universe_reference",
                "validation_reference",
                "status_reference",
            )
        }
        protocol, candidate, taxonomy, universe, validation, status = (
            artifacts[key]
            for key in (
                "protocol_reference",
                "candidate_reference",
                "taxonomy_reference",
                "frozen_universe_reference",
                "validation_reference",
                "status_reference",
            )
        )
        if (
            family["family_id"] != "swl1_ridge_v1"
            or family["industry_level"] != 1
            or family["display_name"] != "SWL1-Ridge-V1"
            or family["generation"] != 1
            or family["etf_productization_status"] != "NOT_STARTED"
            or family["scientific_status"] != status["scientific_status"]
            or family["forward_eligible"] is not False
            or status["forward_eligible"] is not False
            or validation["passed"] is not False
            or status["final_oos_opened"] is not False
            or candidate["protocol_hash"] != family["protocol_reference"]["sha256"]
            or validation["lineage"]["candidate_hash"] != family["candidate_reference"]["sha256"]
            or status["candidate_hash"] != family["candidate_reference"]["sha256"]
            or family["model_contract_hash"] != family["candidate_reference"]["sha256"]
            or status["protocol_hash"] != family["protocol_reference"]["sha256"]
            or validation["lineage"]["protocol_hash"] != family["protocol_reference"]["sha256"]
            or candidate["model_universe_hash"] != family["frozen_universe_reference"]["sha256"]
            or protocol["model_universe_hash"] != family["frozen_universe_reference"]["sha256"]
            or protocol["taxonomy_hash"] != family["taxonomy_reference"]["sha256"]
            or protocol["model_universe"] != universe["industries"]
            or family["industry_codes"] != universe["industries"]
        ):
            raise ValueError("CLOSED_RESEARCH_FAMILY_CONTRACT_MISMATCH")
        current = sorted(r["industry_code"] for r in taxonomy["industries"])
        codes = family["industry_codes"]
        if codes != sorted(set(codes)) or not set(codes).issubset(current):
            raise ValueError("FIXED_UNIVERSE_REQUIRED")
        family.update(
            taxonomy_scope=taxonomy["classification_version"],
            taxonomy_universe_size=len(current),
            model_universe_size=len(codes),
            model_universe_hash=digest(json.dumps(codes, separators=(",", ":")).encode()),
            taxonomy_only_industries=sorted(set(current) - set(codes)),
            taxonomy_only_status="NOT_IN_FROZEN_MODEL_UNIVERSE",
        )
        result.append(family)
    return result


def resolve(identifier: str, root: Path = ROOT, *, require_forward: bool = False) -> dict[str, Any]:
    for family in families(root):
        if identifier.replace("-", "_") == family["family_id"]:
            if require_forward and family.get("forward_eligible") is False:
                raise ValueError("RESEARCH_FAMILY_FORWARD_INELIGIBLE")
            return family
    raise ValueError("UNKNOWN_RESEARCH_FAMILY")

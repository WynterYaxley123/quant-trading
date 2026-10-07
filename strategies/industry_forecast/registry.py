"""Discover independent levels without altering frozen SWL2 family definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.storage import contained, digest
from strategies.swl2_ridge.registry import ROOT
from strategies.swl2_ridge.registry import families as swl2_families

REGISTRY = "config/research/industry-forecast-families.json"


def validate_v2(family: dict[str, Any], artifacts: dict[str, Any]) -> None:
    """A closed/pending Level-1 generation never gains forward from Validation alone."""
    protocol, status, universe = (
        artifacts[key]
        for key in ("protocol_reference", "status_reference", "frozen_universe_reference")
    )
    candidate, validation, development = (
        artifacts.get(key)
        for key in ("candidate_reference", "validation_reference", "development_reference")
    )
    protocol_hash = family["protocol_reference"]["sha256"]
    allowed = {
        "NO_DEVELOPMENT_CANDIDATE",
        "FAILED_VALIDATION",
        "AWAITING_PROSPECTIVE_FINAL_OOS",
        "VALIDATION_INTERVAL_NOT_UNSEEN",
        "NOT_RESEARCHABLE_WITH_CURRENT_DATA",
    }
    valid = (
        family["display_name"] == "SWL1-Ridge-V2"
        and family["generation"] == 2
        and family["industry_level"] == 1
        and family["current_role"] == "INDUSTRY_FORECAST_RESEARCH"
        and family["etf_productization_status"] == "NOT_STARTED"
        and family["scientific_status"] in allowed
        and family["scientific_status"] == status["scientific_status"]
        and family["forward_eligible"] is False
        and status["forward_eligible"] is False
        and status["final_oos_opened"] is False
        and status["final_oos_consumed"] is False
        and protocol["family_id"] == "swl1_ridge_v2"
        and status["protocol_hash"] == protocol_hash
        and protocol["model_universe_hash"] == family["frozen_universe_reference"]["sha256"]
        and protocol["model_universe"] == universe["industries"] == family["industry_codes"]
        and protocol["primary_series"] == "RECONSTRUCTED_SWL1_EQUAL_WEIGHT"
        and protocol["final_oos_mode"] == "PROSPECTIVE_ONLY"
        and status["public_preregistration_anchor"]["external_merge_witness"]["protocol_hash"]
        == protocol_hash
        and status["public_preregistration_anchor"]["external_merge_witness"]["merged"] is True
        and status["public_preregistration_anchor"]["external_merge_witness"][
            "exact_remote_bytes_verified"
        ]
        is True
        and status["public_preregistration_anchor"]["external_merge_witness"][
            "factual_performance_before_remote_anchor"
        ]
        is False
        and status["validation_reopened"] is False
        and status["validation_informed_revision"] is False
        and status["formal_forward_forecasts_created"] == 0
        and status["live_scheduler_enabled"] is False
        and status["live_deployment_promoted"] is False
    )
    if development:
        valid &= development["protocol_hash"] == protocol_hash
        valid &= len(development["leaderboard"]) == len(protocol["specifications"]) == 16
    if candidate:
        checksum = family["candidate_reference"]["sha256"]
        valid &= (
            candidate["protocol_hash"] == protocol_hash and status.get("candidate_hash") == checksum
        )
        valid &= family["model_contract_hash"] == checksum
        valid &= candidate["model_universe_hash"] == family["frozen_universe_reference"]["sha256"]
        valid &= candidate["implementation_hashes"] == protocol["implementation_hashes"]
    else:
        valid &= (
            status.get("candidate_hash") is None and family["model_contract_hash"] == protocol_hash
        )
    if status["scientific_status"] in {"FAILED_VALIDATION", "AWAITING_PROSPECTIVE_FINAL_OOS"}:
        valid &= candidate is not None and validation is not None and development is not None
        if validation:
            valid &= validation["lineage"]["protocol_hash"] == protocol_hash
            valid &= (
                validation["lineage"]["candidate_hash"] == family["candidate_reference"]["sha256"]
            )
            valid &= validation["passed"] is (
                status["scientific_status"] == "AWAITING_PROSPECTIVE_FINAL_OOS"
            )
            valid &= (
                status["validation_opened"] is True
                and status["validation_passed"] is validation["passed"]
            )
    else:
        valid &= candidate is None and validation is None and status["validation_opened"] is False
        if status["scientific_status"] == "NO_DEVELOPMENT_CANDIDATE":
            valid &= development is not None and not any(
                row["admitted"] for row in development["leaderboard"]
            )
    if not valid:
        raise ValueError("CLOSED_RESEARCH_FAMILY_CONTRACT_MISMATCH")


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
                "development_reference",
            )
            if family.get(key) is not None
        }
        protocol, taxonomy, universe, status = (
            artifacts[key]
            for key in (
                "protocol_reference",
                "taxonomy_reference",
                "frozen_universe_reference",
                "status_reference",
            )
        )
        candidate = artifacts.get("candidate_reference")
        validation = artifacts.get("validation_reference")
        if family["family_id"] == "swl1_ridge_v2":
            validate_v2(family, artifacts)
        elif (
            candidate is None
            or validation is None
            or family["family_id"] != "swl1_ridge_v1"
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
        if family["family_id"] == "swl1_ridge_v2":
            family.update(
                protocol_hash=family["protocol_reference"]["sha256"],
                candidate_hash=status.get("candidate_hash"),
                validation_status="PASS"
                if status.get("validation_passed") is True
                else "FAIL"
                if status.get("validation_opened")
                else "NOT_OPENED",
                final_oos_status="PROSPECTIVE_NOT_OPENED",
                membership_confidence=protocol["membership_confidence"],
                primary_series=protocol["primary_series"],
                research_evidence={
                    "ranges": protocol["split"]["ranges"],
                    "development": artifacts.get("development_reference"),
                    "validation": validation,
                    "selected_spec": candidate["spec"] if candidate else None,
                    "anchor": status["public_preregistration_anchor"]["external_merge_witness"],
                },
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

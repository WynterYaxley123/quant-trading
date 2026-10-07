"""One public naming authority; historical identities and artifacts retain their bytes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.storage import contained, digest

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "config/research/swl2-ridge-families.json"
SWL2_RIDGE_V1 = "swl2_ridge_v1"
SWL2_RIDGE_V2 = "swl2_ridge_v2"


def universe_metadata(family: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    """Resolve pinned identities; taxonomy inventory never enlarges a fitted universe."""
    documents = {}
    for key in ("frozen_universe_reference", "taxonomy_reference"):
        reference = family[key]
        body = contained(root, reference["path"]).read_bytes()
        if digest(body) != reference["sha256"]:
            raise ValueError("FROZEN_UNIVERSE_REFERENCE_MISMATCH")
        documents[key] = json.loads(body)
    universe = documents["frozen_universe_reference"]
    codes = universe["industries"]
    if codes != sorted(set(codes)) or codes != family["industry_codes"]:
        raise ValueError("FROZEN_MODEL_UNIVERSE_MISMATCH")
    if family["generation"] == 2 and (
        universe["source_metadata_sha256"]
        != family["frozen_model_reference"]["warmup_metadata_sha256"]
        or universe["warmup_panel_sha256"]
        != family["frozen_model_reference"]["warmup_panel_sha256"]
    ):
        raise ValueError("FROZEN_WARMUP_UNIVERSE_MISMATCH")
    taxonomy = documents["taxonomy_reference"]
    taxonomy_codes = sorted(
        row["industry_code"]
        for row in taxonomy["industries"]
        if row.get("vintage") == taxonomy["classification_version"]
    )
    if taxonomy["taxonomy_identity"] != family["taxonomy_identity"] or not set(codes).issubset(
        taxonomy_codes
    ):
        raise ValueError("FROZEN_UNIVERSE_TAXONOMY_MISMATCH")
    return {
        "taxonomy_scope": taxonomy["classification_version"],
        "taxonomy_universe_size": len(taxonomy_codes),
        "legacy_taxonomy_identity_count": len(taxonomy["industries"]) - len(taxonomy_codes),
        "model_universe_size": len(codes),
        "model_universe_hash": digest(json.dumps(codes, separators=(",", ":")).encode()),
        "taxonomy_only_industries": sorted(set(taxonomy_codes) - set(codes)),
        "taxonomy_only_status": "NOT_IN_FROZEN_MODEL_UNIVERSE",
    }


def families(root: Path = ROOT) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads(contained(root, REGISTRY).read_bytes())["families"]
    if [f["family_id"] for f in result] != [SWL2_RIDGE_V1, SWL2_RIDGE_V2]:
        raise ValueError("CANONICAL_FAMILY_REGISTRY_REQUIRED")
    for generation, family in enumerate(result, 1):
        if (
            family["display_name"] != f"SWL2-Ridge-V{generation}"
            or family["generation"] != generation
            or family["industry_level"] != 2
            or family["current_role"] != "INDUSTRY_FORECAST_RESEARCH"
            or family["etf_productization_status"] != "RETIRED"
            or family["legacy_identity"] != f"ETF_QUANT_V{generation}"
        ):
            raise ValueError("FAMILY_NAMING_CONTRACT_REQUIRED")
        family.update(universe_metadata(family, root))
    return result


def resolve(identifier: str, root: Path = ROOT) -> dict[str, Any]:
    for family in families(root):
        if identifier in (family["family_id"], family["family_id"].replace("_", "-")):
            return family
    raise ValueError("UNKNOWN_RESEARCH_FAMILY")


def verify_model(family: dict[str, Any], root: Path = ROOT) -> str:
    universe_metadata(family, root)
    pins = family["frozen_model_reference"]["files"]
    for name, expected in pins.items():
        if digest(contained(root, name).read_bytes()) != expected:
            raise ValueError("FROZEN_MODEL_HASH_MISMATCH")
    contract_hash = digest(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode())
    if contract_hash != family["model_contract_hash"]:
        raise ValueError("FROZEN_MODEL_CONTRACT_MISMATCH")
    return contract_hash

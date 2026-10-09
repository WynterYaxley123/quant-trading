"""Stricter review preflight around the existing admission contract, without promotion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .contracts import Proof, SyntheticAuthority, hash_id, instant, require
from .source_admission import Source, SourceRegistry, Tier, admit

RIGHTS = (
    "dataset_access",
    "local_storage",
    "internal_research",
    "automated_processing",
    "derived_data",
    "backtesting",
    "commercial_use",
    "public_redisplay",
    "redistribution",
    "retention",
    "revision_access",
)
RIGHT_STATES = frozenset(
    {
        "PERMITTED",
        "PROHIBITED",
        "CONDITIONAL",
        "NOT_ESTABLISHED",
        "REQUIRES_OWNER_ACCEPTANCE",
        "REQUIRES_PROVIDER_CONFIRMATION",
    }
)
REQUIRED_RIGHTS = frozenset(
    {
        "dataset_access",
        "local_storage",
        "internal_research",
        "automated_processing",
        "derived_data",
        "retention",
        "revision_access",
    }
)
QUALITY_CHECKS = frozenset(
    {
        "sessions",
        "identifiers",
        "membership_intervals",
        "duplicates",
        "adjustment",
        "corporate_actions",
        "lifecycle",
        "suspension",
        "coverage",
        "independent_reconciliation",
    }
)


@dataclass(frozen=True)
class Qualification:
    state: str
    reason: str
    existing_admission_state: str
    source_digest: str
    production_admission: bool = False


def synthetic_preflight(
    source: Source,
    authority: SyntheticAuthority,
    proofs: tuple[Proof, ...],
    *,
    now: str,
    required_tier: Tier = "A",
) -> Qualification:
    """Authenticated test domain only; a successful review cannot promote a real source."""
    require(
        all(p.purpose in {"metadata", "rights", "pit", "quality"} for p in proofs),
        "QUALIFICATION_PURPOSE_INVALID",
    )
    base = tuple(p for p in proofs if p.purpose != "quality")
    admission = admit(source, authority, base, required_tier=required_tier)
    if admission.state != "SOURCE_ADMITTED":
        return Qualification("SOURCE_BLOCKED", admission.reason, admission.state, source.digest)
    claims: dict[str, dict[str, Any]] = {}
    for proof in proofs:
        require(proof.purpose not in claims, "DUPLICATE_PROOF")
        value = authority.verify(proof, proof.purpose)
        require(value.get("source_digest") == source.digest, "SOURCE_IDENTITY_MISMATCH")
        claims[proof.purpose] = value
    rights = claims["rights"]
    scope = rights.get("scope")
    require(isinstance(scope, dict) and set(scope) == set(RIGHTS), "RIGHTS_SCOPE_INCOMPLETE")
    scope = cast(dict[str, Any], scope)
    require(
        all(isinstance(v, str) and v in RIGHT_STATES for v in scope.values()),
        "RIGHTS_STATE_INVALID",
    )
    require(all(scope[k] == "PERMITTED" for k in REQUIRED_RIGHTS), "RIGHTS_SCOPE_BLOCKED")
    require(rights.get("basis") == "DATASET_SPECIFIC_GRANT", "DATASET_GRANT_REQUIRED")
    require(
        rights.get("conflicts") == [] and rights.get("conditions_satisfied") is True,
        "RIGHTS_CONFLICT_OR_CONDITION",
    )
    require(
        instant(rights.get("valid_from", ""))
        <= instant(now)
        < instant(rights.get("valid_until", "")),
        "RIGHTS_EXPIRED_OR_NOT_EFFECTIVE",
    )
    require(
        rights.get("contract_hash") == source.data_contract_hash, "RIGHTS_CONTRACT_SCOPE_MISMATCH"
    )
    pit = claims["pit"]
    require(
        pit.get("taxonomy_identity") == source.taxonomy_identity
        and pit.get("membership_identity") == source.membership_identity,
        "PIT_TAXONOMY_MISMATCH",
    )
    published = instant(pit.get("published_at", ""))
    observed = instant(pit.get("observed_at", ""))
    ingested = instant(pit.get("ingested_at", ""))
    signal = instant(pit.get("signal_at", ""))
    require(
        published <= observed <= ingested <= signal <= instant(now), "PIT_NOT_AVAILABLE_AT_SIGNAL"
    )
    require(instant(pit.get("revised_at", "")) <= signal, "PIT_REVISION_AFTER_SIGNAL")
    snapshot_hash = pit.get("snapshot_hash", "")
    require(isinstance(snapshot_hash, str), "PIT_SNAPSHOT_INCOMPLETE")
    hash_id(snapshot_hash)
    require(pit.get("receipt_scope") == "FULL_REQUIRED_UNIVERSE", "PIT_SNAPSHOT_INCOMPLETE")
    quality = claims.get("quality", {})
    require(
        quality.get("revision_identity") == source.revision_identity, "QUALITY_REVISION_MISMATCH"
    )
    require(
        quality.get("assessment_scope") == "AUTHORIZED_BLIND_NUMERIC_QA"
        and quality.get("performance_fields") == [],
        "QUALITY_SCOPE_INVALID",
    )
    require(quality.get("checks") == dict.fromkeys(QUALITY_CHECKS, "PASS"), "QUALITY_INCOMPLETE")
    origin = claims["metadata"].get("upstream_origin")
    require(isinstance(origin, str) and bool(origin), "SOURCE_ORIGIN_REQUIRED")
    require(
        quality.get("independent_origin") not in {None, "", origin}, "INDEPENDENT_SOURCE_REQUIRED"
    )
    require(
        quality.get("method_equivalence") == "VERIFIED" and bool(quality.get("evidence_reference")),
        "QUALITY_METHOD_NOT_EQUIVALENT",
    )
    # Same existing registry revalidates proofs. No alternative registry/store exists.
    SourceRegistry(authority).register(source, base, required_tier=required_tier)
    return Qualification(
        "QUALIFIED_SYNTHETIC_ONLY",
        "PRODUCTION_IDENTITY_NOT_ESTABLISHED",
        admission.state,
        source.digest,
    )


def real_registry_preflight(contract: dict[str, Any]) -> dict[str, Any]:
    """Exercise PR34 with NO minted factual/rights/PIT proofs; never real promotion."""
    source = Source(**contract)
    result = SourceRegistry(SyntheticAuthority(synthetic_only=True)).register(
        source, (), required_tier="A"
    )
    require(result.state != "SOURCE_ADMITTED", "UNAUTHORIZED_SOURCE_PROMOTION")
    return {
        "source_digest": source.digest,
        "existing_registry_state": result.state,
        "existing_registry_reason": result.reason,
        "real_sources_admitted": 0,
        "production_identity": "SIGNATURE_AUTHORITY_NOT_ESTABLISHED",
        "proofs_supplied": 0,
    }


def main() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / "reports/research/swl1_source_qualification/source-inventory.json"
    require(path.is_file() and not path.is_symlink(), "QUALIFICATION_REPORT_REQUIRED")
    require(path.stat().st_size <= 128 * 1024, "QUALIFICATION_REPORT_SIZE")
    inventory = json.loads(path.read_bytes())
    checks = [
        dict(source_id=s["source_id"], **real_registry_preflight(s["source_contract"]))
        for s in inventory["sources"]
        if s.get("source_contract")
    ]
    print(
        json.dumps(
            {"scope": "READ_ONLY_NO_PROMOTION", "preflight": checks, "real_sources_admitted": 0},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Factual admission, without performance fields or self-asserted verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .contracts import Proof, SyntheticAuthority, canonical, hash_id, identity, require, sha

Tier = Literal["A", "B", "C", "D"]
Kind = Literal["OFFICIAL_TAXONOMY", "OFFICIAL_INDEX_PRICE_SERIES", "RECONSTRUCTED_INDUSTRY_RETURN"]


@dataclass(frozen=True)
class Source:
    source_id: str
    source_hash: str
    data_contract_hash: str
    taxonomy_identity: str
    membership_identity: str
    kind: Kind
    tier: Tier
    revision_identity: str

    def __post_init__(self) -> None:
        for value in (self.source_id, self.taxonomy_identity, self.membership_identity):
            identity(value)
        for value in (self.source_hash, self.data_contract_hash, self.revision_identity):
            hash_id(value)
        require(self.tier in {"A", "B", "C", "D"}, "PIT_TIER_INVALID")
        require(
            self.kind
            in {
                "OFFICIAL_TAXONOMY",
                "OFFICIAL_INDEX_PRICE_SERIES",
                "RECONSTRUCTED_INDUSTRY_RETURN",
            },
            "SOURCE_KIND_INVALID",
        )

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))


@dataclass(frozen=True)
class Admission:
    source: Source
    state: str
    reason: str
    proofs: tuple[str, ...]


def admit(
    source: Source,
    authority: SyntheticAuthority,
    proofs: tuple[Proof, ...],
    *,
    required_tier: Tier,
) -> Admission:
    """Every proof must bind this generation; missing evidence yields a closed state."""
    verified = {}
    for proof in proofs:
        require(proof.purpose in {"metadata", "rights", "pit"}, "ADMISSION_PURPOSE_INVALID")
        require(proof.purpose not in verified, "DUPLICATE_PROOF")
        claims = authority.verify(proof, proof.purpose)
        require(claims.get("source_digest") == source.digest, "SOURCE_IDENTITY_MISMATCH")
        verified[proof.purpose] = claims
    hashes = tuple(proof.digest for proof in proofs)
    if "metadata" not in verified or not verified["metadata"].get("identity_reference"):
        return Admission(source, "SOURCE_UNREVIEWED", "SOURCE_METADATA_UNVERIFIED", hashes)
    if "rights" not in verified:
        return Admission(source, "SOURCE_BLOCKED", "BLOCKED_UNVERIFIED_RIGHTS", hashes)
    rights = verified["rights"]
    if rights.get("research_use") != "PERMITTED" or not rights.get("evidence_reference"):
        return Admission(source, "SOURCE_BLOCKED", "BLOCKED_UNVERIFIED_RIGHTS", hashes)
    if rights.get("redistribution") not in {"PERMITTED", "PROHIBITED", "UNKNOWN"}:
        return Admission(source, "SOURCE_REJECTED", "RIGHTS_SCOPE_INVALID", hashes)
    if "pit" not in verified:
        return Admission(source, "SOURCE_RIGHTS_VERIFIED", "PIT_EVIDENCE_INSUFFICIENT", hashes)
    pit = verified["pit"]
    if pit.get("tier") != source.tier or "ABCD".index(source.tier) > "ABCD".index(required_tier):
        return Admission(source, "SOURCE_BLOCKED", "PIT_EVIDENCE_INSUFFICIENT", hashes)
    if source.tier == "D" or pit.get("availability_basis") not in {
        "CONTEMPORANEOUS_RECEIPT",
        "VERIFIED_EFFECTIVE_DATED_RECONSTRUCTION",
        "RECONSTRUCTED_PROVENANCE",
    }:
        return Admission(source, "SOURCE_BLOCKED", "AVAILABILITY_NOT_VERIFIED", hashes)
    basis_by_tier = {
        "A": "CONTEMPORANEOUS_RECEIPT",
        "B": "VERIFIED_EFFECTIVE_DATED_RECONSTRUCTION",
        "C": "RECONSTRUCTED_PROVENANCE",
    }
    if pit["availability_basis"] != basis_by_tier.get(source.tier):
        return Admission(source, "SOURCE_BLOCKED", "AVAILABILITY_NOT_VERIFIED", hashes)
    return Admission(source, "SOURCE_ADMITTED", "SYNTHETIC_ONLY", hashes)


class SourceRegistry:
    """No replacing a generation; a revision needs a new source admission."""

    def __init__(self, authority: SyntheticAuthority) -> None:
        self._authority = authority
        self._sources: dict[str, Admission] = {}
        self._quarantined: set[str] = set()

    def register(
        self, source: Source, proofs: tuple[Proof, ...], *, required_tier: Tier
    ) -> Admission:
        admission = admit(source, self._authority, proofs, required_tier=required_tier)
        key = admission.source.digest
        require(
            key not in self._sources or self._sources[key] == admission,
            "SOURCE_TRANSITION_REQUIRED",
        )
        self._sources[key] = admission
        return admission

    def get(self, digest: str) -> Admission:
        require(digest not in self._quarantined, "FACT_REVISION_QUARANTINED")
        require(digest in self._sources, "SOURCE_NOT_REGISTERED")
        result = self._sources[digest]
        require(result.state == "SOURCE_ADMITTED", result.reason)
        return result

    def revision(self, original: Source, revised: Source) -> str:
        require(original.digest in self._sources, "SOURCE_NOT_REGISTERED")
        require(original.digest != revised.digest, "REVISION_IDENTITY_REQUIRED")
        self._quarantined.add(original.digest)
        return "SOURCE_TRANSITION_REQUIRED"

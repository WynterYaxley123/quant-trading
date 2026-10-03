"""Production STRICT mapping evidence: mechanical constituent-set containment.

The runtime's STRICT admission channel is the separate ``VERIFIED_MAPPING_REGISTRY_V1``
(``config/verified_mappings_v1.json``): per-ETF official fund documents verified
against an external evidence root. Nothing here changes that channel, the frozen
Strict definition, or any runtime selector.

What the production PIT evidence registry lacked was the *other* half of the
strict contract, stated in the mapping contract as the constituent-set
containment condition: a benchmark proves STRICT for a target Shenwan L2 when
every official constituent carries an official classification and every one of
them sits inside the target L2, on a complete official weight vector with zero
unmapped weight. Exposure equal to 100% is not sufficient on its own -- one
zero-weight constituent classified outside the target would hold exposure at
100% while breaking containment -- so the proof is checked per constituent.

The derivation is additive and mechanical: it consumes the same evidence the
exposure derivation already produced and emits the schema's own
``B40MappingEvidence`` record with ``mapping_type="STRICT_MAPPING"`` only when
every condition holds and the decision instant is not earlier than the evidence's
production availability. Otherwise the record is ``REJECTED`` with the first
failing reason; it is never silently relabelled as a proxy mapping, and no
observation is invented.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from .schema import (
    REJECTION_CLASSIFICATION_INCOMPLETE,
    REJECTION_NO_OFFICIAL_WEIGHT,
    REJECTION_NOT_YET_AVAILABLE,
    WEIGHT_COMPLETE,
    B40MappingEvidence,
    EvidenceError,
    parse_instant,
)

#: The mechanical strict condition this module proves, named for provenance
#: records. It states an evidence fact, not a new mapping contract.
CONTAINMENT_IDENTITY = "PRODUCTION_STRICT_CONSTITUENT_CONTAINMENT_V1"

#: One constituent classified outside the target L2 breaks strict containment.
REJECTION_CONTAINMENT = "CONSTITUENT_SET_NOT_CONTAINED_IN_TARGET_L2"


@dataclass(frozen=True)
class ContainmentProof:
    """The per-constituent verdict for one (benchmark, target L2) pair."""

    target_l2_code: str
    constituent_count: int
    classified_count: int
    unclassified: tuple[str, ...]
    out_of_bounds: tuple[str, ...]

    @property
    def proven(self) -> bool:
        return self.constituent_count > 0 and not self.unclassified and not self.out_of_bounds

    @property
    def reason(self) -> str | None:
        if not self.constituent_count:
            return REJECTION_NO_OFFICIAL_WEIGHT
        if self.unclassified:
            return REJECTION_CLASSIFICATION_INCOMPLETE
        if self.out_of_bounds:
            return REJECTION_CONTAINMENT
        return None

    def as_dict(self) -> dict:
        return {
            "target_l2_code": self.target_l2_code,
            "constituent_count": self.constituent_count,
            "classified_count": self.classified_count,
            "unclassified_count": len(self.unclassified),
            "out_of_bounds_count": len(self.out_of_bounds),
        }


def prove_constituent_containment(
    *, constituents: Iterable[str], stock_to_l2: Mapping[str, str], target_l2_code: str
) -> ContainmentProof:
    """Prove the benchmark constituent set is contained in the target L2 set.

    Every constituent security must carry a classification and every
    classification must equal the target code. One missing row or one
    out-of-bounds row rejects the proof outright; nothing is redistributed and
    nothing is guessed, so a gap can only ever fail closed.
    """
    if not isinstance(target_l2_code, str) or not target_l2_code:
        raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "target_l2_code"})
    codes = list(constituents)
    unclassified: list[str] = []
    out_of_bounds: list[str] = []
    for code in codes:
        l2 = stock_to_l2.get(code)
        if l2 is None:
            unclassified.append(code)
        elif l2 != target_l2_code:
            out_of_bounds.append(code)
    return ContainmentProof(
        target_l2_code=target_l2_code,
        constituent_count=len(codes),
        classified_count=len(codes) - len(unclassified),
        unclassified=tuple(sorted(unclassified)),
        out_of_bounds=tuple(sorted(out_of_bounds)),
    )


def derive_strict_mapping_evidence(
    *,
    benchmark_code: str,
    target_l2_code: str,
    target_l2_name: str,
    etf_code: str,
    etf_name: str,
    constituents: Sequence[str],
    stock_to_l2: Mapping[str, str],
    target_l2_exposure: float,
    target_is_largest: bool,
    unmapped_weight: float,
    weight_quality: str,
    production_available_at: str,
    input_package_hashes: Sequence[str],
    available_from: str,
    decision_at: datetime | None = None,
) -> B40MappingEvidence:
    """Derive one STRICT mapping evidence record, or a rejected one with a reason.

    The conditions mirror the frozen strict semantics and are all mechanical:
    complete official weight set, zero unmapped weight, per-constituent
    containment in the target L2, and -- when ``decision_at`` is supplied -- PIT
    availability (``production_available_at <= decision_at``). A record failing
    any condition is returned ``REJECTED`` carrying the first failing reason in
    the rejection chain. Only facts supplied by the caller are asserted here;
    this function invents no exposure, no dominance and no timestamp.
    """
    proof = prove_constituent_containment(
        constituents=constituents, stock_to_l2=stock_to_l2, target_l2_code=target_l2_code
    )
    available = parse_instant(production_available_at, "production_available_at")
    started = parse_instant(available_from, "available_from")
    production_available = max(available, started)
    hashes = tuple(sorted({str(value) for value in input_package_hashes}))
    reasons: list[str] = []
    if weight_quality != WEIGHT_COMPLETE:
        reasons.append(REJECTION_NO_OFFICIAL_WEIGHT)
    if unmapped_weight != 0.0:
        reasons.append(REJECTION_CLASSIFICATION_INCOMPLETE)
    if proof.reason is not None:
        reasons.append(proof.reason)
    if decision_at is not None and production_available > decision_at:
        reasons.append(REJECTION_NOT_YET_AVAILABLE)
    admitted = not reasons
    return B40MappingEvidence(
        target_l2_code=target_l2_code,
        target_l2_name=target_l2_name,
        etf_code=etf_code,
        etf_name=etf_name,
        benchmark_code=benchmark_code,
        target_l2_exposure=float(target_l2_exposure),
        target_is_largest=bool(target_is_largest),
        dominance_margin=float(target_l2_exposure),
        mapping_type="STRICT_MAPPING",
        admission_status="ADMITTED" if admitted else "REJECTED",
        rejection_reason=None if admitted else "|".join(reasons),
        production_available_at=production_available.isoformat(),
        input_package_hashes=hashes,
    )


__all__ = [
    "CONTAINMENT_IDENTITY",
    "ContainmentProof",
    "REJECTION_CONTAINMENT",
    "derive_strict_mapping_evidence",
    "prove_constituent_containment",
]

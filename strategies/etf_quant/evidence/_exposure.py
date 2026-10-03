"""PIT evidence exposure contracts; public facade: schema.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.industry_level import default_taxonomy
from ._classification import ClassificationSnapshot
from ._validation import (
    AVAILABILITY_FORWARD_ONLY,
    AVAILABILITY_STATES,
    B40_MIN_TARGET_EXPOSURE,
    CLASSIFICATION_CONFLICT,
    CLASSIFICATION_OFFICIAL,
    REJECTION_BELOW_THRESHOLD,
    REJECTION_CLASSIFICATION_CONFLICT,
    REJECTION_CLASSIFICATION_INCOMPLETE,
    REJECTION_NO_OFFICIAL_WEIGHT,
    REJECTION_NOT_LARGEST,
    WEIGHT_COMPLETE,
    EvidenceError,
    parse_day,
    parse_instant,
    require_sha256,
    require_text,
    sha256_json,
)
from ._weights import WeightVector


@dataclass(frozen=True)
class BenchmarkL2Exposure:
    benchmark_code: str
    benchmark_effective_date: str
    benchmark_evidence_available_at: str
    classification_snapshot_id: str
    classification_evidence_available_at: str
    derived_at: str
    l2_weights: tuple[tuple[str, float], ...]
    unmapped_weight: float
    weight_sum: float
    input_package_hashes: tuple[str, ...]
    derivation_code_hash: str
    availability_semantics: str = AVAILABILITY_FORWARD_ONLY
    note: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.benchmark_code, "benchmark_code")
        parse_day(self.benchmark_effective_date, "benchmark_effective_date")
        parse_instant(self.benchmark_evidence_available_at, "benchmark_evidence_available_at")
        parse_instant(
            self.classification_evidence_available_at, "classification_evidence_available_at"
        )
        derived = parse_instant(self.derived_at, "derived_at")
        require_sha256(self.derivation_code_hash, "derivation_code_hash")
        if not isinstance(self.input_package_hashes, tuple) or not self.input_package_hashes:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"reason": "NO_INPUT_HASHES"})
        for value in self.input_package_hashes:
            require_sha256(value, "input_package_hashes")
        if self.availability_semantics not in AVAILABILITY_STATES:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "availability_semantics"})
        if self.unmapped_weight < 0.0:
            raise EvidenceError("EVIDENCE_WEIGHT_BLOCKER", {"field": "unmapped_weight"})
        if derived < parse_instant(
            self.benchmark_evidence_available_at, "benchmark_evidence_available_at"
        ):
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "DERIVED_BEFORE_INPUT"})
        if derived < parse_instant(
            self.classification_evidence_available_at, "classification_evidence_available_at"
        ):
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER", {"reason": "DERIVED_BEFORE_CLASSIFICATION"}
            )

    @property
    def production_available_at(self) -> datetime:
        """The earliest instant this derivation could honestly have been used.

        It is the maximum over every input, never the minimum, and never the date
        the data merely describes.
        """
        return max(
            parse_instant(self.benchmark_evidence_available_at, "benchmark_evidence_available_at"),
            parse_instant(
                self.classification_evidence_available_at, "classification_evidence_available_at"
            ),
            parse_instant(self.derived_at, "derived_at"),
        )

    @property
    def l2_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _weight in self.l2_weights)

    @property
    def largest_l2(self) -> tuple[str, float] | None:
        ranked = self.ranked_l2
        return ranked[0] if ranked else None

    @property
    def second_l2(self) -> tuple[str, float] | None:
        ranked = self.ranked_l2
        return ranked[1] if len(ranked) > 1 else None

    @property
    def ranked_l2(self) -> list[tuple[str, float]]:
        return sorted(self.l2_weights, key=lambda kv: (-kv[1], kv[0]))

    def exposure(self, l2_code: str) -> float:
        return float(dict(self.l2_weights).get(l2_code, 0.0))

    def dominance_margin_for(self, l2_code: str) -> float:
        others = [(code, w) for code, w in self.ranked_l2 if code != l2_code]
        second = max((w for _code, w in others), default=0.0)
        return round(self.exposure(l2_code) - second, 6)

    def is_largest(self, l2_code: str) -> bool:
        largest = self.largest_l2
        return bool(largest and largest[0] == l2_code)

    def as_dict(self) -> dict:
        largest, second = self.largest_l2, self.second_l2
        return {
            "benchmark_code": self.benchmark_code,
            "benchmark_effective_date": self.benchmark_effective_date,
            "benchmark_evidence_available_at": self.benchmark_evidence_available_at,
            "classification_snapshot_id": self.classification_snapshot_id,
            "classification_evidence_available_at": self.classification_evidence_available_at,
            "derived_at": self.derived_at,
            "production_available_at": self.production_available_at.isoformat(),
            "availability_semantics": self.availability_semantics,
            "l2_weights": [[code, weight] for code, weight in self.l2_weights],
            "largest_l2_code": largest[0] if largest else None,
            "largest_l2_weight": largest[1] if largest else None,
            "second_l2_code": second[0] if second else None,
            "second_l2_weight": second[1] if second else None,
            "dominance_margin": round((largest[1] - second[1]), 6)
            if largest and second
            else (largest[1] if largest else None),
            "unmapped_weight": self.unmapped_weight,
            "weight_sum": self.weight_sum,
            "input_package_hashes": list(self.input_package_hashes),
            "derivation_code_hash": self.derivation_code_hash,
            "note": list(self.note),
        }


def derive_l2_exposure(
    *,
    weights: WeightVector,
    snapshot: ClassificationSnapshot,
    derived_at: str,
    derivation_code_hash: str,
    availability_semantics: str = AVAILABILITY_FORWARD_ONLY,
) -> BenchmarkL2Exposure:
    """Attribute a verified official weight vector onto Shenwan L2 industries.

    Fails closed on the two things this layer exists to catch: a constituent with
    no classification row, and a constituent whose classification is a recorded
    conflict. Neither is redistributed and neither is guessed.
    """
    rows = snapshot.by_security
    missing = [row.security_code for row in weights.rows if row.security_code not in rows]
    if missing:
        raise EvidenceError(
            REJECTION_CLASSIFICATION_INCOMPLETE,
            {
                "benchmark_code": weights.benchmark_code,
                "missing_count": len(missing),
                "sample": sorted(missing)[:10],
            },
        )
    conflicted = [
        row.security_code
        for row in weights.rows
        if rows[row.security_code].classification_quality == CLASSIFICATION_CONFLICT
    ]
    if conflicted:
        raise EvidenceError(
            REJECTION_CLASSIFICATION_CONFLICT,
            {
                "benchmark_code": weights.benchmark_code,
                "conflict_count": len(conflicted),
                "sample": sorted(conflicted)[:10],
            },
        )
    unusable = [
        row.security_code
        for row in weights.rows
        if rows[row.security_code].classification_quality != CLASSIFICATION_OFFICIAL
    ]
    if unusable:
        raise EvidenceError(
            REJECTION_CLASSIFICATION_INCOMPLETE,
            {
                "benchmark_code": weights.benchmark_code,
                "unusable_count": len(unusable),
                "sample": sorted(unusable)[:10],
            },
        )
    if (
        weights.recompute_quality()[0] != WEIGHT_COMPLETE
        or weights.weight_quality != WEIGHT_COMPLETE
    ):
        raise EvidenceError(
            REJECTION_NO_OFFICIAL_WEIGHT,
            {
                "benchmark_code": weights.benchmark_code,
                "weight_sum": weights.weight_sum,
                "counted": weights.constituent_count,
                "declared": weights.declared_constituent_count,
            },
        )
    totals: dict[str, float] = {}
    for row in weights.rows:
        code = rows[row.security_code].shenwan_l2_code
        totals[code] = totals.get(code, 0.0) + float(row.weight_pct)
    return BenchmarkL2Exposure(
        benchmark_code=weights.benchmark_code,
        benchmark_effective_date=weights.constituent_effective_date,
        benchmark_evidence_available_at=weights.evidence_available_at,
        classification_snapshot_id=snapshot.snapshot_id,
        classification_evidence_available_at=snapshot.evidence_available_at,
        derived_at=derived_at,
        l2_weights=tuple((code, round(weight, 6)) for code, weight in sorted(totals.items())),
        unmapped_weight=0.0,
        weight_sum=weights.weight_sum,
        input_package_hashes=tuple(
            sorted({sha256_json(weights.as_dict()), sha256_json(snapshot.as_dict())})
        ),
        derivation_code_hash=derivation_code_hash,
        availability_semantics=availability_semantics,
        note=tuple(weights.notes),
    )


@dataclass(frozen=True)
class B40MappingEvidence:
    target_l2_code: str
    target_l2_name: str
    etf_code: str
    etf_name: str
    benchmark_code: str
    target_l2_exposure: float
    target_is_largest: bool
    dominance_margin: float
    mapping_type: str
    admission_status: str
    production_available_at: str
    input_package_hashes: tuple[str, ...]
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        taxonomy = default_taxonomy()
        taxonomy.assert_level(self.target_l2_code)
        if self.mapping_type not in ("PROXY_EXPOSURE", "STRICT_MAPPING"):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "mapping_type"})
        if self.admission_status not in ("ADMITTED", "REJECTED", "CASH_FAIL_CLOSED"):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "admission_status"})
        if not isinstance(self.target_is_largest, bool):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "target_is_largest"})
        if isinstance(self.target_l2_exposure, bool) or not isinstance(
            self.target_l2_exposure, (int, float)
        ):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "target_l2_exposure"})
        parse_instant(self.production_available_at, "production_available_at")
        if not isinstance(self.input_package_hashes, tuple) or not self.input_package_hashes:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"reason": "NO_INPUT_HASHES"})
        if self.admission_status == "ADMITTED" and self.rejection_reason is not None:
            raise EvidenceError(
                "EVIDENCE_SCHEMA_BLOCKER", {"reason": "ADMITTED_WITH_REJECTION_REASON"}
            )
        if self.admission_status != "ADMITTED" and not self.rejection_reason:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"reason": "REJECTED_WITHOUT_REASON"})

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.production_available_at, "production_available_at")

    @property
    def passes_b40(self) -> bool:
        """The frozen B40 predicate, restated over evidence rather than asserted."""
        return (
            self.admission_status == "ADMITTED"
            and float(self.target_l2_exposure) >= B40_MIN_TARGET_EXPOSURE
            and self.target_is_largest is True
        )

    def as_dict(self) -> dict:
        return {
            "target_l2_code": self.target_l2_code,
            "target_l2_name": self.target_l2_name,
            "etf_code": self.etf_code,
            "etf_name": self.etf_name,
            "benchmark_code": self.benchmark_code,
            "target_l2_exposure": round(float(self.target_l2_exposure), 6),
            "target_is_largest": self.target_is_largest,
            "dominance_margin": round(float(self.dominance_margin), 6),
            "mapping_type": self.mapping_type,
            "admission_status": self.admission_status,
            "rejection_reason": self.rejection_reason,
            "production_available_at": self.production_available_at,
            "input_package_hashes": list(self.input_package_hashes),
        }


def decide_b40_mapping(
    *,
    exposure: BenchmarkL2Exposure,
    target_l2_code: str,
    etf_code: str,
    etf_name: str,
    available_from: datetime,
) -> B40MappingEvidence:
    """Apply the frozen B40 rule to one (benchmark, target industry) pair."""
    target_exposure = exposure.exposure(target_l2_code)
    largest = exposure.is_largest(target_l2_code)
    margin = exposure.dominance_margin_for(target_l2_code)
    production_available_at = max(exposure.production_available_at, available_from).isoformat()
    reasons = []
    if target_exposure < B40_MIN_TARGET_EXPOSURE:
        reasons.append(REJECTION_BELOW_THRESHOLD)
    if not largest:
        reasons.append(REJECTION_NOT_LARGEST)
    return B40MappingEvidence(
        target_l2_code=target_l2_code,
        target_l2_name=default_taxonomy().name_of(target_l2_code),
        etf_code=etf_code,
        etf_name=etf_name,
        benchmark_code=exposure.benchmark_code,
        target_l2_exposure=target_exposure,
        target_is_largest=largest,
        dominance_margin=margin,
        mapping_type="PROXY_EXPOSURE",
        admission_status="ADMITTED" if not reasons else "REJECTED",
        rejection_reason=None if not reasons else "|".join(reasons),
        production_available_at=production_available_at,
        input_package_hashes=tuple(sorted({sha256_json(exposure.as_dict())})),
    )

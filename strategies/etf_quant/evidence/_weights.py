"""PIT evidence weights contracts; public facade: schema.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._sources import PinnedSource
from ._validation import (
    WEIGHT_COMPLETE,
    WEIGHT_INCOMPLETE,
    WEIGHT_QUALITY_STATES,
    WEIGHT_SUM_BAND,
    EvidenceError,
    optional_day,
    optional_instant,
    parse_day,
    parse_instant,
    require_text,
)


@dataclass(frozen=True)
class ConstituentRow:
    security_code: str
    weight_pct: float
    security_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.security_code, str) or not self.security_code:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "security_code"})
        if isinstance(self.weight_pct, bool) or not isinstance(self.weight_pct, (int, float)):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "weight_pct"})
        if not 0.0 <= float(self.weight_pct) <= 100.0:
            raise EvidenceError(
                "EVIDENCE_WEIGHT_BLOCKER", {"field": "weight_pct", "value": self.weight_pct}
            )

    def as_dict(self) -> dict:
        return {"security_code": self.security_code, "weight_pct": float(self.weight_pct)}


@dataclass(frozen=True)
class WeightVector:
    """One benchmark's official constituent weight vector, as of one official date."""

    benchmark_code: str
    benchmark_name: str
    provider: str
    weight_source_type: str
    constituent_effective_date: str
    evidence_observed_at: str
    evidence_available_at: str
    declared_constituent_count: int
    rows: tuple[ConstituentRow, ...]
    valid_from: str
    valid_to: str | None = None
    source_publication_at: str | None = None
    weight_quality: str = WEIGHT_INCOMPLETE
    notes: tuple[str, ...] = ()
    sources: tuple[PinnedSource, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.benchmark_code, "benchmark_code")
        require_text(self.benchmark_name, "benchmark_name")
        require_text(self.provider, "provider")
        for name in ("evidence_observed_at", "evidence_available_at", "valid_from"):
            parse_instant(
                self.evidence_observed_at, "evidence_observed_at"
            ) if name == "evidence_observed_at" else None
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        available = parse_instant(self.evidence_available_at, "evidence_available_at")
        published = optional_instant(self.source_publication_at, "source_publication_at")
        effective = parse_day(self.constituent_effective_date, "constituent_effective_date")
        valid_from = parse_day(self.valid_from, "valid_from")
        valid_to = optional_day(self.valid_to, "valid_to")
        if published is not None and published > observed:
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER", {"reason": "PUBLICATION_AFTER_OBSERVATION"}
            )
        if available < observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        if effective > available.date():
            # The data describes a date the system could not yet have seen.
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER", {"reason": "EFFECTIVE_DATE_AFTER_AVAILABILITY"}
            )
        if valid_to is not None and valid_to <= valid_from:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "EMPTY_VALIDITY"})
        if type(self.declared_constituent_count) is not int or self.declared_constituent_count <= 0:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "declared_constituent_count"})
        if not isinstance(self.rows, tuple) or not self.rows:
            raise EvidenceError("EVIDENCE_WEIGHT_BLOCKER", {"reason": "NO_CONSTITUENTS"})
        codes = [row.security_code for row in self.rows]
        if len(set(codes)) != len(codes):
            raise EvidenceError("EVIDENCE_WEIGHT_BLOCKER", {"reason": "DUPLICATE_SECURITY"})
        if self.weight_quality not in WEIGHT_QUALITY_STATES:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "weight_quality"})
        if not isinstance(self.sources, tuple) or not self.sources:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"reason": "NO_PINNED_SOURCE"})
        if len({source.source_sha256 for source in self.sources}) != len(self.sources):
            raise EvidenceError(
                "EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"reason": "DUPLICATE_PINNED_SOURCE"}
            )

    @property
    def constituent_count(self) -> int:
        return len(self.rows)

    @property
    def weight_sum(self) -> float:
        return round(sum(float(row.weight_pct) for row in self.rows), 6)

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.evidence_available_at, "evidence_available_at")

    @property
    def observed_at(self) -> datetime:
        return parse_instant(self.evidence_observed_at, "evidence_observed_at")

    def recompute_quality(self) -> tuple[str, tuple[str, ...]]:
        """The completeness verdict, recomputed from the raw vector.

        A builder may not simply *assert* ``COMPLETE``; this is the function that
        decides, and it is the same predicate the runtime applies.
        """
        notes = []
        quality = WEIGHT_COMPLETE
        low, high = WEIGHT_SUM_BAND
        if self.constituent_count != self.declared_constituent_count:
            quality = WEIGHT_INCOMPLETE
            notes.append(
                f"CONSTITUENT_COUNT_MISMATCH:counted={self.constituent_count}"
                f":declared={self.declared_constituent_count}"
            )
        if not (low <= self.weight_sum <= high):
            quality = WEIGHT_INCOMPLETE
            notes.append(f"WEIGHT_SUM_OUT_OF_BAND={self.weight_sum:.6f}")
        return quality, tuple(notes)

    def as_dict(self) -> dict:
        return {
            "benchmark_code": self.benchmark_code,
            "benchmark_name": self.benchmark_name,
            "provider": self.provider,
            "weight_source_type": self.weight_source_type,
            "constituent_effective_date": self.constituent_effective_date,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "declared_constituent_count": self.declared_constituent_count,
            "constituent_count": self.constituent_count,
            "weight_sum": self.weight_sum,
            "weight_quality": self.weight_quality,
            "notes": list(self.notes),
            "rows": [row.as_dict() for row in self.rows],
            "sources": [source.as_dict() for source in self.sources],
        }

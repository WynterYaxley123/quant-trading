"""PIT evidence classification contracts; public facade: schema.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.industry_level import default_taxonomy
from ._sources import PinnedSource
from ._validation import (
    CLASSIFICATION_CONFLICT,
    CLASSIFICATION_OFFICIAL,
    CLASSIFICATION_QUALITY_STATES,
    VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED,
    EvidenceError,
    bare_code,
    optional_day,
    optional_instant,
    parse_day,
    parse_instant,
    require_text,
)


@dataclass(frozen=True)
class ClassificationRow:
    security_code: str
    shenwan_l1_code: str
    shenwan_l1_name: str
    shenwan_l2_code: str
    shenwan_l2_name: str
    taxonomy_version: str
    classification_effective_from: str
    evidence_observed_at: str
    evidence_available_at: str
    classification_quality: str = CLASSIFICATION_OFFICIAL
    security_name: str | None = None
    classification_effective_to: str | None = None
    source_publication_at: str | None = None

    def __post_init__(self) -> None:
        if not bare_code(self.security_code):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "security_code"})
        taxonomy = default_taxonomy()
        taxonomy.assert_level(self.shenwan_l2_code)
        if self.classification_quality not in CLASSIFICATION_QUALITY_STATES:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "classification_quality"})
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        available = parse_instant(self.evidence_available_at, "evidence_available_at")
        published = optional_instant(self.source_publication_at, "source_publication_at")
        if published is not None and published > observed:
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER", {"reason": "PUBLICATION_AFTER_OBSERVATION"}
            )
        if available < observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        effective_from = parse_day(
            self.classification_effective_from, "classification_effective_from"
        )
        effective_to = optional_day(self.classification_effective_to, "classification_effective_to")
        if effective_to is not None and effective_to <= effective_from:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "EMPTY_VALIDITY"})

    @property
    def observed_at(self) -> datetime:
        return parse_instant(self.evidence_observed_at, "evidence_observed_at")

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.evidence_available_at, "evidence_available_at")

    def as_dict(self) -> dict:
        return {
            "security_code": bare_code(self.security_code),
            "security_name": self.security_name,
            "shenwan_l1_code": self.shenwan_l1_code,
            "shenwan_l1_name": self.shenwan_l1_name,
            "shenwan_l2_code": self.shenwan_l2_code,
            "shenwan_l2_name": self.shenwan_l2_name,
            "taxonomy_version": self.taxonomy_version,
            "classification_effective_from": self.classification_effective_from,
            "classification_effective_to": self.classification_effective_to,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "classification_quality": self.classification_quality,
        }


@dataclass(frozen=True)
class ClassificationSnapshot:
    """One immutable view of security -> Shenwan L2, with its own availability."""

    snapshot_id: str
    taxonomy_version: str
    validity_semantics: str
    evidence_observed_at: str
    evidence_available_at: str
    rows: tuple[ClassificationRow, ...]
    sources: tuple[PinnedSource, ...] = ()
    snapshot_as_observed_at: str | None = None
    superseded_by: str | None = None
    source_publication_at: str | None = None
    coverage_gap: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.snapshot_id, "snapshot_id")
        if self.validity_semantics != VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "validity_semantics"})
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        available = parse_instant(self.evidence_available_at, "evidence_available_at")
        if available < observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        if not isinstance(self.rows, tuple) or not self.rows:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"reason": "EMPTY_SNAPSHOT"})
        codes = [row.security_code for row in self.rows]
        if len(set(codes)) != len(codes):
            raise EvidenceError("EVIDENCE_CLASSIFICATION_DUPLICATE_BLOCKER")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"reason": "NO_PINNED_SOURCE"})

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.evidence_available_at, "evidence_available_at")

    @property
    def by_security(self) -> dict[str, ClassificationRow]:
        return {row.security_code: row for row in self.rows}

    @property
    def conflicts(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                row.security_code
                for row in self.rows
                if row.classification_quality == CLASSIFICATION_CONFLICT
            )
        )

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "taxonomy_version": self.taxonomy_version,
            "validity_semantics": self.validity_semantics,
            "snapshot_as_observed_at": self.snapshot_as_observed_at,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "superseded_by": self.superseded_by,
            "coverage_gap": list(self.coverage_gap),
            "security_count": len(self.rows),
            "conflict_count": len(self.conflicts),
            "rows": [row.as_dict() for row in self.rows],
            "sources": [source.as_dict() for source in self.sources],
        }

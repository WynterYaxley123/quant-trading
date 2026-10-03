"""PIT evidence sources contracts; public facade: schema.py."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from ._validation import (
    TRACKING_STATUSES,
    EvidenceError,
    optional_day,
    optional_instant,
    parse_day,
    parse_instant,
    require_official_url,
    require_safe_name,
    require_sha256,
    require_text,
)


@dataclass(frozen=True)
class PinnedSource:
    """One immutable official byte stream, pinned by SHA-256.

    ``relative_path`` is where the bytes live under the package source root. The
    runtime adapter reads it with ``contained(root, name)`` and joins it with ``/``
    without rejecting a separator, so paths are always POSIX-relative and confined.

    ``evidence_available_at`` is when this system could first have used these bytes.
    It is never earlier than the instant they were observed, and it is never the
    date the document merely describes.
    """

    relative_path: str
    source_url: str
    source_publication_at: str | None
    evidence_observed_at: str
    source_retrieved_at: str
    source_sha256: str
    evidence_available_at: str | None = None
    content_type: str | None = None
    byte_length: int | None = None

    def __post_init__(self) -> None:
        require_safe_name(self.relative_path, "relative_path")
        require_official_url(self.source_url, "source_url")
        require_sha256(self.source_sha256, "source_sha256")
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        retrieved = parse_instant(self.source_retrieved_at, "source_retrieved_at")
        published = optional_instant(self.source_publication_at, "source_publication_at")
        if published is not None and published > observed:
            # A file cannot have been observed before it was published.
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER",
                {"field": "source_publication_at", "reason": "PUBLICATION_AFTER_OBSERVATION"},
            )
        if retrieved > observed:
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER",
                {"field": "source_retrieved_at", "reason": "RETRIEVAL_AFTER_OBSERVATION"},
            )
        if self.evidence_available_at is not None:
            available = parse_instant(self.evidence_available_at, "evidence_available_at")
            if available < observed:
                # The forward-only rule, enforced at the source as well as the package.
                raise EvidenceError(
                    "EVIDENCE_TIME_BLOCKER",
                    {"field": "evidence_available_at", "reason": "AVAILABLE_BEFORE_OBSERVED"},
                )
        if self.byte_length is not None and (
            not isinstance(self.byte_length, int) or self.byte_length <= 0
        ):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "byte_length"})

    @property
    def available_at(self) -> datetime:
        """The first instant this source was usable; defaults to first observation."""
        return parse_instant(
            self.evidence_available_at or self.evidence_observed_at, "evidence_available_at"
        )

    @property
    def observed_at(self) -> datetime:
        return parse_instant(self.evidence_observed_at, "evidence_observed_at")

    def as_dict(self) -> dict:
        return {
            "relative_path": self.relative_path,
            "source_url": self.source_url,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "source_retrieved_at": self.source_retrieved_at,
            "source_sha256": self.source_sha256,
            "content_type": self.content_type,
            "byte_length": self.byte_length,
        }


@dataclass(frozen=True)
class TrackingRelation:
    exchange: str
    etf_code: str
    etf_name: str
    benchmark_code: str
    benchmark_name: str
    index_provider: str
    listing_status: str
    listing_date: str | None
    source_type: str
    official_source_url: str
    source_publication_at: str | None
    evidence_observed_at: str
    evidence_available_at: str
    raw_source_hash: str
    valid_from: str
    valid_to: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", self.etf_code or ""):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "etf_code"})
        if self.exchange not in ("SSE", "SZSE"):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "exchange"})
        for name in (
            "etf_name",
            "benchmark_code",
            "benchmark_name",
            "index_provider",
            "source_type",
        ):
            require_text(getattr(self, name), name)
        if self.listing_status not in TRACKING_STATUSES:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "listing_status"})
        require_official_url(self.official_source_url, "official_source_url")
        require_sha256(self.raw_source_hash, "raw_source_hash")
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        available = parse_instant(self.evidence_available_at, "evidence_available_at")
        published = optional_instant(self.source_publication_at, "source_publication_at")
        valid_from = parse_day(self.valid_from, "valid_from")
        valid_to = optional_day(self.valid_to, "valid_to")
        if published is not None and published > observed:
            raise EvidenceError(
                "EVIDENCE_TIME_BLOCKER", {"reason": "PUBLICATION_AFTER_OBSERVATION"}
            )
        if available < observed:
            # The whole point of the forward-only rule.
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        if valid_to is not None and valid_to <= valid_from:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "EMPTY_VALIDITY"})
        if self.listing_date is not None:
            parse_day(self.listing_date, "listing_date")

    @property
    def observed_at(self) -> datetime:
        return parse_instant(self.evidence_observed_at, "evidence_observed_at")

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.evidence_available_at, "evidence_available_at")

    def as_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "etf_code": self.etf_code,
            "etf_name": self.etf_name,
            "benchmark_code": self.benchmark_code,
            "benchmark_name": self.benchmark_name,
            "index_provider": self.index_provider,
            "listing_status": self.listing_status,
            "listing_date": self.listing_date,
            "source_type": self.source_type,
            "official_source_url": self.official_source_url,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "raw_source_hash": self.raw_source_hash,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "notes": list(self.notes),
        }

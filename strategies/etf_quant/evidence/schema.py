"""Production point-in-time evidence schemas for ETF-Quant V1.

Why this module exists
----------------------
``mapping/pit.py`` can already consume an audited external evidence book, but it
consumes *whatever it is handed*: it proves the raw official bytes hash to the
recorded values, it proves the pinned extraction equals the pinned bytes, and it
proves the timestamp chain is ordered. It does **not** know where those bytes came
from, whether they cover a whole benchmark, or whether a classification snapshot
was observed before the decision it is used for.

This module is the missing contract layer. It defines the immutable evidence
packages that a *builder* may produce, and it enforces the four properties the
runtime adapter cannot check on its own:

1. **Provenance.** Every package names the official HTTPS source of every pinned
   byte stream, and the source host must be one of the official index providers,
   exchanges or SWS Research.
2. **Completeness.** A benchmark weight vector is ``COMPLETE`` only when the
   counted constituents equal the count the provider itself declares *and* the
   weights sum inside the same band the runtime uses. Weights are never
   renormalised to reach that band.
3. **Attribution.** Every constituent must carry an explicit classification row.
   A constituent with no classification is a hard failure for the package, not a
   silent entry in ``unmapped_weight``.
4. **Forward-only availability.** ``effective_date`` (what the data describes),
   ``source_publication_at`` (what the issuer announced), ``evidence_observed_at``
   (when this system actually saw the bytes) and ``evidence_available_at`` (when
   this system could first have used them) are four different fields and are never
   collapsed into one. A package may never claim to have been available before the
   moment it was observed.

Nothing here re-derives a strategy decision. These are evidence containers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
import re

from ..domain.industry_level import default_taxonomy

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

EVIDENCE_SCHEMA_VERSION = "1.0.0"
TRACKING_IDENTITY = "ETF_TRACKING_RELATION_EVIDENCE_V1"
WEIGHT_IDENTITY = "BENCHMARK_CONSTITUENT_WEIGHT_EVIDENCE_V1"
CLASSIFICATION_IDENTITY = "SHENWAN_L2_CLASSIFICATION_EVIDENCE_V1"
EXPOSURE_IDENTITY = "BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1"
MAPPING_IDENTITY = "B40_MAPPING_EVIDENCE_V1"
REGISTRY_IDENTITY = "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1"

#: Hosts whose HTTPS responses may be pinned as production evidence. This is the
#: same tuple the runtime adapter enforces; duplicating it here means a builder
#: fails while building rather than while trading.
OFFICIAL_HOST_SUFFIXES = ("csindex.com.cn", "cnindex.com.cn", "sse.com.cn", "szse.cn",
                          "swsresearch.com")

_HTTPS = re.compile(r"https:[/]{2}([^/@:\s]+)/([^\s#]+)")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SAFE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")

#: Availability semantics a package may declare about itself.
AVAILABILITY_HISTORICAL_PIT = "HISTORICAL_PIT_PROVEN"
AVAILABILITY_FORWARD_ONLY = "FORWARD_ONLY"
AVAILABILITY_UNUSABLE = "NOT_PRODUCTION_USABLE"
AVAILABILITY_STATES = (AVAILABILITY_HISTORICAL_PIT, AVAILABILITY_FORWARD_ONLY,
                       AVAILABILITY_UNUSABLE)

#: Validity semantics for a snapshot that cannot be bounded in the past.
VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED = "FORWARD_ONLY_UNTIL_SUPERSEDED"

#: Weight-vector quality labels. Only ``COMPLETE`` may be admitted.
WEIGHT_COMPLETE = "COMPLETE"
WEIGHT_INCOMPLETE = "INCOMPLETE"
WEIGHT_QUALITY_STATES = (WEIGHT_COMPLETE, WEIGHT_INCOMPLETE)

#: Classification row quality labels.
CLASSIFICATION_OFFICIAL = "OFFICIAL_CLASSIFICATION"
CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"
CLASSIFICATION_UNCLASSIFIED = "UNCLASSIFIED_FOR_V1"
CLASSIFICATION_QUALITY_STATES = (CLASSIFICATION_OFFICIAL, CLASSIFICATION_CONFLICT,
                                 CLASSIFICATION_UNCLASSIFIED)

#: The weight-sum band. Transcribed from ``mapping/proxy.py:WEIGHT_SUM_BAND`` so a
#: package can never be built that the runtime would then silently mark incomplete.
WEIGHT_SUM_BAND = (99.0, 100.5)

TRACKING_STATUSES = ("LISTED", "NOT_LISTED", "DELISTED", "UNKNOWN")
REJECTION_NO_OFFICIAL_WEIGHT = "NO_OFFICIAL_COMPLETE_WEIGHT_VECTOR"
REJECTION_CLASSIFICATION_INCOMPLETE = "CLASSIFICATION_INCOMPLETE"
REJECTION_CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"
REJECTION_NOT_YET_AVAILABLE = "EVIDENCE_NOT_AVAILABLE_AT_DECISION"
REJECTION_BELOW_THRESHOLD = "TARGET_EXPOSURE_BELOW_THRESHOLD"
REJECTION_NOT_LARGEST = "TARGET_NOT_LARGEST_L2"
REJECTION_NO_TRACKING = "NO_OFFICIAL_TRACKING_RELATION"


class EvidenceError(ValueError):
    """An evidence package could not be established from official artifacts."""

    def __init__(self, code: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = {} if details is None else details


# ---------------------------------------------------------------------------
# Small typed helpers
# ---------------------------------------------------------------------------

def canonical_bytes(value) -> bytes:
    """Deterministic JSON encoding used for every hash in the evidence layer."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_json(value) -> str:
    return sha256_bytes(canonical_bytes(value))


def require_text(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": field_name})
    return value.strip()


def require_sha256(value, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": field_name})
    return value


def require_official_url(value, field_name: str) -> str:
    """Only an official HTTPS URL with a real path may be pinned."""
    if not isinstance(value, str) or not isinstance(value, str):
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"field": field_name})
    match = _HTTPS.fullmatch(value)
    if match is None:
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                            {"field": field_name, "reason": "NOT_OFFICIAL_HTTPS_URL"})
    host = match.group(1).lower()
    if not any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                            {"field": field_name, "host": host,
                             "reason": "HOST_NOT_AN_OFFICIAL_PUBLISHER"})
    return value


def require_safe_name(value, field_name: str) -> str:
    """Relative POSIX path of a pinned raw file, confined to the source root."""
    if not isinstance(value, str) or not value:
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER", {"field": field_name})
    if value.startswith("/") or "\\" in value or ".." in value.split("/"):
        raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                            {"field": field_name, "reason": "ESCAPES_SOURCE_ROOT"})
    for part in value.split("/"):
        if not _SAFE_NAME.fullmatch(part):
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"field": field_name, "reason": "UNSAFE_PATH_PART"})
    return value


def parse_instant(value, field_name: str) -> datetime:
    """An explicit, timezone-aware instant. A naive timestamp is never assumed local."""
    if not isinstance(value, str):
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name,
                                                      "reason": "NOT_A_STRING"})
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name,
                                                      "reason": "UNPARSEABLE"}) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name,
                                                      "reason": "TIMEZONE_REQUIRED"})
    return parsed


def parse_day(value, field_name: str) -> date:
    if not isinstance(value, str):
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name})
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"field": field_name,
                                                      "reason": "NOT_AN_ISO_DATE"}) from error


def optional_instant(value, field_name: str) -> datetime | None:
    return None if value is None else parse_instant(value, field_name)


def optional_day(value, field_name: str) -> date | None:
    return None if value is None else parse_day(value, field_name)


def parse_weight_pct(value):
    """Parse an official weight, or ``None`` when the provider published none.

    Deliberately identical in behaviour to ``mapping/proxy.py:parse_weight_pct``:
    a missing weight is missing evidence, never a zero.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    if isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if text in {"-", "--", "- -", "—", "N/A", "n/a"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def bare_code(value) -> str:
    """``600519.SH`` -> ``600519``. The identity used on both sides of a join."""
    if not isinstance(value, str):
        return ""
    return value.strip().split(".")[0].strip()


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

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
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"field": "source_publication_at",
                                 "reason": "PUBLICATION_AFTER_OBSERVATION"})
        if retrieved > observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"field": "source_retrieved_at",
                                 "reason": "RETRIEVAL_AFTER_OBSERVATION"})
        if self.evidence_available_at is not None:
            available = parse_instant(self.evidence_available_at, "evidence_available_at")
            if available < observed:
                # The forward-only rule, enforced at the source as well as the package.
                raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                    {"field": "evidence_available_at",
                                     "reason": "AVAILABLE_BEFORE_OBSERVED"})
        if self.byte_length is not None and (not isinstance(self.byte_length, int)
                                             or self.byte_length <= 0):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "byte_length"})

    @property
    def available_at(self) -> datetime:
        """The first instant this source was usable; defaults to first observation."""
        return parse_instant(self.evidence_available_at or self.evidence_observed_at,
                             "evidence_available_at")

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


# ---------------------------------------------------------------------------
# ETF -> benchmark tracking relation
# ---------------------------------------------------------------------------

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
        for name in ("etf_name", "benchmark_code", "benchmark_name", "index_provider",
                     "source_type"):
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
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "PUBLICATION_AFTER_OBSERVATION"})
        if available < observed:
            # The whole point of the forward-only rule.
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "AVAILABLE_BEFORE_OBSERVED"})
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
            "exchange": self.exchange, "etf_code": self.etf_code, "etf_name": self.etf_name,
            "benchmark_code": self.benchmark_code, "benchmark_name": self.benchmark_name,
            "index_provider": self.index_provider, "listing_status": self.listing_status,
            "listing_date": self.listing_date, "source_type": self.source_type,
            "official_source_url": self.official_source_url,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "raw_source_hash": self.raw_source_hash, "valid_from": self.valid_from,
            "valid_to": self.valid_to, "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Benchmark constituents + weights
# ---------------------------------------------------------------------------

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
            raise EvidenceError("EVIDENCE_WEIGHT_BLOCKER", {"field": "weight_pct",
                                                            "value": self.weight_pct})

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
            parse_instant(self.evidence_observed_at, "evidence_observed_at") \
                if name == "evidence_observed_at" else None
        observed = parse_instant(self.evidence_observed_at, "evidence_observed_at")
        available = parse_instant(self.evidence_available_at, "evidence_available_at")
        published = optional_instant(self.source_publication_at, "source_publication_at")
        effective = parse_day(self.constituent_effective_date, "constituent_effective_date")
        valid_from = parse_day(self.valid_from, "valid_from")
        valid_to = optional_day(self.valid_to, "valid_to")
        if published is not None and published > observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "PUBLICATION_AFTER_OBSERVATION"})
        if available < observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        if effective > available.date():
            # The data describes a date the system could not yet have seen.
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "EFFECTIVE_DATE_AFTER_AVAILABILITY"})
        if valid_to is not None and valid_to <= valid_from:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "EMPTY_VALIDITY"})
        if type(self.declared_constituent_count) is not int or self.declared_constituent_count <= 0:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER",
                                {"field": "declared_constituent_count"})
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
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "DUPLICATE_PINNED_SOURCE"})

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
            notes.append(f"CONSTITUENT_COUNT_MISMATCH:counted={self.constituent_count}"
                         f":declared={self.declared_constituent_count}")
        if not (low <= self.weight_sum <= high):
            quality = WEIGHT_INCOMPLETE
            notes.append(f"WEIGHT_SUM_OUT_OF_BAND={self.weight_sum:.6f}")
        return quality, tuple(notes)

    def as_dict(self) -> dict:
        return {
            "benchmark_code": self.benchmark_code, "benchmark_name": self.benchmark_name,
            "provider": self.provider, "weight_source_type": self.weight_source_type,
            "constituent_effective_date": self.constituent_effective_date,
            "source_publication_at": self.source_publication_at,
            "evidence_observed_at": self.evidence_observed_at,
            "evidence_available_at": self.evidence_available_at,
            "valid_from": self.valid_from, "valid_to": self.valid_to,
            "declared_constituent_count": self.declared_constituent_count,
            "constituent_count": self.constituent_count,
            "weight_sum": self.weight_sum,
            "weight_quality": self.weight_quality,
            "notes": list(self.notes),
            "rows": [row.as_dict() for row in self.rows],
            "sources": [source.as_dict() for source in self.sources],
        }


# ---------------------------------------------------------------------------
# Security -> Shenwan L2 classification
# ---------------------------------------------------------------------------

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
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "PUBLICATION_AFTER_OBSERVATION"})
        if available < observed:
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "AVAILABLE_BEFORE_OBSERVED"})
        effective_from = parse_day(self.classification_effective_from,
                                   "classification_effective_from")
        effective_to = optional_day(self.classification_effective_to,
                                    "classification_effective_to")
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
            "security_code": bare_code(self.security_code), "security_name": self.security_name,
            "shenwan_l1_code": self.shenwan_l1_code, "shenwan_l1_name": self.shenwan_l1_name,
            "shenwan_l2_code": self.shenwan_l2_code, "shenwan_l2_name": self.shenwan_l2_name,
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
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "AVAILABLE_BEFORE_OBSERVED"})
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
        return tuple(sorted(row.security_code for row in self.rows
                            if row.classification_quality == CLASSIFICATION_CONFLICT))

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id, "taxonomy_version": self.taxonomy_version,
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


# ---------------------------------------------------------------------------
# Derived benchmark -> L2 exposure
# ---------------------------------------------------------------------------

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
        parse_instant(self.classification_evidence_available_at,
                      "classification_evidence_available_at")
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
        if derived < parse_instant(self.benchmark_evidence_available_at,
                                   "benchmark_evidence_available_at"):
            raise EvidenceError("EVIDENCE_TIME_BLOCKER", {"reason": "DERIVED_BEFORE_INPUT"})
        if derived < parse_instant(self.classification_evidence_available_at,
                                   "classification_evidence_available_at"):
            raise EvidenceError("EVIDENCE_TIME_BLOCKER",
                                {"reason": "DERIVED_BEFORE_CLASSIFICATION"})

    @property
    def production_available_at(self) -> datetime:
        """The earliest instant this derivation could honestly have been used.

        It is the maximum over every input, never the minimum, and never the date
        the data merely describes.
        """
        return max(parse_instant(self.benchmark_evidence_available_at,
                                 "benchmark_evidence_available_at"),
                   parse_instant(self.classification_evidence_available_at,
                                 "classification_evidence_available_at"),
                   parse_instant(self.derived_at, "derived_at"))

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
            "dominance_margin": round((largest[1] - second[1]), 6) if largest and second else (
                largest[1] if largest else None),
            "unmapped_weight": self.unmapped_weight,
            "weight_sum": self.weight_sum,
            "input_package_hashes": list(self.input_package_hashes),
            "derivation_code_hash": self.derivation_code_hash,
            "note": list(self.note),
        }


def derive_l2_exposure(*, weights: WeightVector, snapshot: ClassificationSnapshot,
                       derived_at: str, derivation_code_hash: str,
                       availability_semantics: str = AVAILABILITY_FORWARD_ONLY
                       ) -> BenchmarkL2Exposure:
    """Attribute a verified official weight vector onto Shenwan L2 industries.

    Fails closed on the two things this layer exists to catch: a constituent with
    no classification row, and a constituent whose classification is a recorded
    conflict. Neither is redistributed and neither is guessed.
    """
    rows = snapshot.by_security
    missing = [row.security_code for row in weights.rows if row.security_code not in rows]
    if missing:
        raise EvidenceError(REJECTION_CLASSIFICATION_INCOMPLETE,
                            {"benchmark_code": weights.benchmark_code,
                             "missing_count": len(missing), "sample": sorted(missing)[:10]})
    conflicted = [row.security_code for row in weights.rows
                  if rows[row.security_code].classification_quality == CLASSIFICATION_CONFLICT]
    if conflicted:
        raise EvidenceError(REJECTION_CLASSIFICATION_CONFLICT,
                            {"benchmark_code": weights.benchmark_code,
                             "conflict_count": len(conflicted), "sample": sorted(conflicted)[:10]})
    unusable = [row.security_code for row in weights.rows
                if rows[row.security_code].classification_quality != CLASSIFICATION_OFFICIAL]
    if unusable:
        raise EvidenceError(REJECTION_CLASSIFICATION_INCOMPLETE,
                            {"benchmark_code": weights.benchmark_code,
                             "unusable_count": len(unusable), "sample": sorted(unusable)[:10]})
    if (weights.recompute_quality()[0] != WEIGHT_COMPLETE
            or weights.weight_quality != WEIGHT_COMPLETE):
        raise EvidenceError(REJECTION_NO_OFFICIAL_WEIGHT,
                            {"benchmark_code": weights.benchmark_code,
                             "weight_sum": weights.weight_sum,
                             "counted": weights.constituent_count,
                             "declared": weights.declared_constituent_count})
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
        input_package_hashes=tuple(sorted({sha256_json(weights.as_dict()),
                                           sha256_json(snapshot.as_dict())})),
        derivation_code_hash=derivation_code_hash,
        availability_semantics=availability_semantics,
        note=tuple(weights.notes),
    )


# ---------------------------------------------------------------------------
# B40 admission mapping
# ---------------------------------------------------------------------------

B40_MIN_TARGET_EXPOSURE = 40.0


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
                self.target_l2_exposure, (int, float)):
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"field": "target_l2_exposure"})
        parse_instant(self.production_available_at, "production_available_at")
        if not isinstance(self.input_package_hashes, tuple) or not self.input_package_hashes:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER", {"reason": "NO_INPUT_HASHES"})
        if self.admission_status == "ADMITTED" and self.rejection_reason is not None:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER",
                                {"reason": "ADMITTED_WITH_REJECTION_REASON"})
        if self.admission_status != "ADMITTED" and not self.rejection_reason:
            raise EvidenceError("EVIDENCE_SCHEMA_BLOCKER",
                                {"reason": "REJECTED_WITHOUT_REASON"})

    @property
    def available_at(self) -> datetime:
        return parse_instant(self.production_available_at, "production_available_at")

    @property
    def passes_b40(self) -> bool:
        """The frozen B40 predicate, restated over evidence rather than asserted."""
        return (self.admission_status == "ADMITTED"
                and float(self.target_l2_exposure) >= B40_MIN_TARGET_EXPOSURE
                and self.target_is_largest is True)

    def as_dict(self) -> dict:
        return {
            "target_l2_code": self.target_l2_code, "target_l2_name": self.target_l2_name,
            "etf_code": self.etf_code, "etf_name": self.etf_name,
            "benchmark_code": self.benchmark_code,
            "target_l2_exposure": round(float(self.target_l2_exposure), 6),
            "target_is_largest": self.target_is_largest,
            "dominance_margin": round(float(self.dominance_margin), 6),
            "mapping_type": self.mapping_type, "admission_status": self.admission_status,
            "rejection_reason": self.rejection_reason,
            "production_available_at": self.production_available_at,
            "input_package_hashes": list(self.input_package_hashes),
        }


def decide_b40_mapping(*, exposure: BenchmarkL2Exposure, target_l2_code: str, etf_code: str,
                       etf_name: str, available_from: datetime
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
        etf_code=etf_code, etf_name=etf_name, benchmark_code=exposure.benchmark_code,
        target_l2_exposure=target_exposure, target_is_largest=largest,
        dominance_margin=margin, mapping_type="PROXY_EXPOSURE",
        admission_status="ADMITTED" if not reasons else "REJECTED",
        rejection_reason=None if not reasons else "|".join(reasons),
        production_available_at=production_available_at,
        input_package_hashes=tuple(sorted({sha256_json(exposure.as_dict())})),
    )


__all__ = [
    "AVAILABILITY_FORWARD_ONLY",
    "AVAILABILITY_HISTORICAL_PIT",
    "AVAILABILITY_STATES",
    "AVAILABILITY_UNUSABLE",
    "B40MappingEvidence",
    "B40_MIN_TARGET_EXPOSURE",
    "BenchmarkL2Exposure",
    "CLASSIFICATION_CONFLICT",
    "CLASSIFICATION_IDENTITY",
    "CLASSIFICATION_OFFICIAL",
    "CLASSIFICATION_QUALITY_STATES",
    "CLASSIFICATION_UNCLASSIFIED",
    "ClassificationRow",
    "ClassificationSnapshot",
    "ConstituentRow",
    "EVIDENCE_SCHEMA_VERSION",
    "EXPOSURE_IDENTITY",
    "EvidenceError",
    "MAPPING_IDENTITY",
    "OFFICIAL_HOST_SUFFIXES",
    "PinnedSource",
    "REGISTRY_IDENTITY",
    "REJECTION_BELOW_THRESHOLD",
    "REJECTION_CLASSIFICATION_CONFLICT",
    "REJECTION_CLASSIFICATION_INCOMPLETE",
    "REJECTION_NOT_LARGEST",
    "REJECTION_NOT_YET_AVAILABLE",
    "REJECTION_NO_OFFICIAL_WEIGHT",
    "REJECTION_NO_TRACKING",
    "TRACKING_IDENTITY",
    "TRACKING_STATUSES",
    "TrackingRelation",
    "VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED",
    "WEIGHT_COMPLETE",
    "WEIGHT_IDENTITY",
    "WEIGHT_INCOMPLETE",
    "WEIGHT_QUALITY_STATES",
    "WEIGHT_SUM_BAND",
    "bare_code",
    "canonical_bytes",
    "decide_b40_mapping",
    "derive_l2_exposure",
    "optional_day",
    "optional_instant",
    "parse_day",
    "parse_instant",
    "parse_weight_pct",
    "require_official_url",
    "require_safe_name",
    "require_sha256",
    "require_text",
    "sha256_bytes",
    "sha256_json",
]

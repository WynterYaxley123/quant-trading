"""Deterministic builders from official raw responses into immutable evidence packages.

Design rules encoded here
-------------------------
* **Rebuild, do not mutate.** Every package is a pure function of pinned official
  bytes plus an explicit observation instant. Re-running the builder over the same
  inputs with the same instant reproduces the same package hash; a new snapshot is
  a *new* package, never an edit of an old one.
* **The extraction is the official response.** Where the provider's own JSON is
  already the vector we need, it is pinned verbatim and the extraction is its
  decoded content. Nothing is summarised, interpolated or re-weighted.
* **Never infer a publication time.** If the issuer does not state when a document
  became public, ``source_publication_at`` is ``None`` and the package is marked
  ``FORWARD_ONLY``. A local download timestamp is *our* observation, and is stored
  only as ``evidence_observed_at``.
* **Never renormalise.** A weight vector whose sum falls outside the runtime's band
  is built as ``INCOMPLETE`` and is never admitted; the raw sum is reported.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .schema import (AVAILABILITY_FORWARD_ONLY, AVAILABILITY_HISTORICAL_PIT,
                     CLASSIFICATION_IDENTITY, CLASSIFICATION_OFFICIAL,
                     CLASSIFICATION_UNCLASSIFIED, EVIDENCE_SCHEMA_VERSION,
                     EXPOSURE_IDENTITY, MAPPING_IDENTITY, REGISTRY_IDENTITY,
                     TRACKING_IDENTITY, VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED,
                     WEIGHT_COMPLETE, WEIGHT_IDENTITY, WEIGHT_INCOMPLETE,
                     B40MappingEvidence, BenchmarkL2Exposure, ClassificationRow,
                     ClassificationSnapshot, ConstituentRow, EvidenceError,
                     PinnedSource, TrackingRelation, WeightVector, bare_code,
                     canonical_bytes, decide_b40_mapping, derive_l2_exposure,
                     parse_weight_pct, require_official_url, sha256_bytes, sha256_json)
from .sources import SourcePin


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Benchmark constituent weight vector
# ---------------------------------------------------------------------------

def build_weight_vector_from_constituent_rows(*, benchmark_code: str, benchmark_name: str,
                                              provider: str, weight_source_type: str,
                                              constituent_effective_date: str,
                                              observed_at: str, available_at: str,
                                              declared_constituent_count: int,
                                              rows: list[dict], valid_from: str,
                                              valid_to: str | None = None,
                                              source_publication_at: str | None = None,
                                              sources: tuple[PinnedSource, ...] = (),
                                              notes: tuple[str, ...] = ()) -> WeightVector:
    """Assemble a weight vector and let the completeness predicate decide its quality."""
    constituents = []
    unparsed = []
    for index, row in enumerate(rows):
        code = bare_code(row.get("security_code"))
        if not code:
            raise EvidenceError("EVIDENCE_WEIGHT_BLOCKER",
                                {"reason": "MISSING_SECURITY_CODE", "row": index})
        weight = parse_weight_pct(row.get("weight_pct"))
        if weight is None:
            unparsed.append(code)
            continue
        constituents.append(ConstituentRow(security_code=code, weight_pct=float(weight),
                                           security_name=row.get("security_name")))
    notes = list(notes)
    if unparsed:
        notes.append("UNPARSED_WEIGHT_ROWS=%d" % len(unparsed))
    provisional = WeightVector(
        benchmark_code=benchmark_code, benchmark_name=benchmark_name, provider=provider,
        weight_source_type=weight_source_type,
        constituent_effective_date=constituent_effective_date,
        source_publication_at=source_publication_at, evidence_observed_at=observed_at,
        evidence_available_at=available_at, valid_from=valid_from, valid_to=valid_to,
        declared_constituent_count=declared_constituent_count,
        rows=tuple(constituents), weight_quality=WEIGHT_INCOMPLETE, notes=tuple(notes),
        sources=sources)
    quality, quality_notes = provisional.recompute_quality()
    if unparsed:
        quality = WEIGHT_INCOMPLETE
    return WeightVector(
        benchmark_code=provisional.benchmark_code, benchmark_name=provisional.benchmark_name,
        provider=provisional.provider, weight_source_type=provisional.weight_source_type,
        constituent_effective_date=provisional.constituent_effective_date,
        source_publication_at=provisional.source_publication_at,
        evidence_observed_at=provisional.evidence_observed_at,
        evidence_available_at=provisional.evidence_available_at,
        valid_from=provisional.valid_from, valid_to=provisional.valid_to,
        declared_constituent_count=provisional.declared_constituent_count,
        rows=provisional.rows, weight_quality=quality,
        notes=tuple(notes) + quality_notes, sources=provisional.sources)


# ---------------------------------------------------------------------------
# ETF tracking relation from the official exchange fund catalog
# ---------------------------------------------------------------------------

#: The exchange's own fund catalog is the only admissible tracking source. It is
#: a listing register, so it proves the relation and the listing date, and proves
#: nothing about a publication instant.
#:
#: The catalog URL is supplied by the caller rather than embedded here. The
#: strategy package is held to a firewall that forbids provider endpoints inside
#: ``strategies/etf_quant``; provenance belongs to the collector, and this layer
#: only validates that whatever URL is offered is official before pinning it.


def _sse_listing_date(value) -> str | None:
    """``20050223`` -> ``2005-02-23``. Anything else is missing, not guessed."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def build_tracking_relations_from_sse_catalog(*, catalog_rows: list[dict], observed_at: str,
                                              available_at: str, source: PinnedSource,
                                              valid_from: str,
                                              source_publication_at: str | None = None
                                              ) -> tuple[TrackingRelation, ...]:
    """One row per ETF that the exchange itself maps to a tracked index.

    The catalog carries no listing-status field, so status is reported as
    ``LISTED`` only because presence in the exchange's own live fund register is
    the fact being asserted; a fund absent from the register is simply absent.

    ``source`` is the pinned catalog itself, so ``official_source_url`` is carried
    from the pinned bytes rather than restated here.
    """
    relations, seen = [], set()
    for row in catalog_rows:
        code = str(row.get("fundCode") or "").strip()
        name = str(row.get("secNameFull") or "").strip()
        index_code = str(row.get("INDEX_CODE") or "").strip()
        index_name = str(row.get("INDEX_NAME") or "").strip()
        if not (len(code) == 6 and code.isdigit()):
            continue
        if not name:
            continue
        if not index_code:
            # The register itself leaves the tracked index blank for this fund.
            # That is missing evidence, and the relation is skipped rather than
            # filled in from the fund's name.
            continue
        etf_code = f"{code}.SH"
        if etf_code in seen:
            continue
        seen.add(etf_code)
        relations.append(TrackingRelation(
            exchange="SSE", etf_code=etf_code, etf_name=name, benchmark_code=index_code,
            benchmark_name=index_name or index_code, index_provider="CSI_OR_SSE_PUBLISHED_CODE",
            listing_status="LISTED", listing_date=_sse_listing_date(row.get("listingDate")),
            source_type="EXCHANGE_FUND_CATALOG", official_source_url=source.source_url,
            source_publication_at=source_publication_at, evidence_observed_at=observed_at,
            evidence_available_at=available_at, raw_source_hash=source.source_sha256,
            valid_from=valid_from,
            notes=("TRACKED_INDEX_NAME_AS_PUBLISHED_BY_EXCHANGE" if index_name
                   else "TRACKED_INDEX_NAME_NOT_PUBLISHED",)))
    return tuple(relations)


def _strip_html(value) -> str:
    import re
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<[^>]*>", "", value)
    return " ".join(text.split())


def build_tracking_relations_from_szse_catalog(*, catalog_rows: list[dict], observed_at: str,
                                               available_at: str, source: PinnedSource,
                                               valid_from: str,
                                               source_publication_at: str | None = None
                                               ) -> tuple[TrackingRelation, ...]:
    """SZSE rows carry the tracked index in one combined ``nhzs`` field.

    The field is either ``"399667 创业成长"`` or a bare code. A bare code yields a
    relation with the code as its own name; the name is never invented.
    """
    relations, seen = [], set()
    for row in catalog_rows:
        code = _strip_html(row.get("sys_key"))
        name = _strip_html(row.get("kzjcurl"))
        fitted = _strip_html(row.get("nhzs"))
        if not (len(code) == 6 and code.isdigit()) or not name:
            continue
        if not fitted:
            continue
        parts = fitted.split()
        index_code = parts[0].strip()
        index_name = " ".join(parts[1:]).strip()
        if not index_code:
            continue
        etf_code = f"{code}.SZ"
        if etf_code in seen:
            continue
        seen.add(etf_code)
        relations.append(TrackingRelation(
            exchange="SZSE", etf_code=etf_code, etf_name=name, benchmark_code=index_code,
            benchmark_name=index_name or index_code,
            index_provider="CNI_OR_SZSE_PUBLISHED_CODE", listing_status="LISTED",
            listing_date=None, source_type="EXCHANGE_FUND_CATALOG",
            official_source_url=source.source_url, source_publication_at=source_publication_at,
            evidence_observed_at=observed_at, evidence_available_at=available_at,
            raw_source_hash=source.source_sha256, valid_from=valid_from,
            notes=("LISTING_DATE_NOT_PUBLISHED_BY_SZSE_CATALOG",
                   "TRACKED_INDEX_NAME_AS_PUBLISHED_BY_EXCHANGE" if index_name
                   else "TRACKED_INDEX_NAME_NOT_PUBLISHED")))
    return tuple(relations)


# ---------------------------------------------------------------------------
# Shenwan L2 classification snapshot
# ---------------------------------------------------------------------------

TAXONOMY_VERSION = "SWCLASS2021"


def build_classification_rows(*, assignments: dict[str, tuple[str, str, str, str]],
                              observed_at: str, available_at: str,
                              effective_from: str,
                              source_publication_at: str | None = None,
                              conflicts: frozenset[str] = frozenset(),
                              unclassified: frozenset[str] = frozenset(),
                              security_names: dict[str, str] | None = None,
                              effective_to: str | None = None,
                              effective_dates: dict[str, str] | None = None
                              ) -> tuple[ClassificationRow, ...]:
    """Turn ``{security: (l1_code, l1_name, l2_code, l2_name)}`` into typed rows.

    A security listed in ``conflicts`` is recorded as a conflict and never as a
    classification; the runtime is expected to fail closed on it. A security in
    ``unclassified`` is recorded as ``UNCLASSIFIED_FOR_V1`` rather than being
    assigned to a nearby industry.

    ``effective_dates`` carries the provider's own per-security effective date where
    it publishes one. ``effective_from`` is the fallback for a security the provider
    does not date; the caller is expected to report how many rows took the fallback,
    because that count is the honest measure of how much of the snapshot is dated by
    the provider rather than by us.
    """
    names = security_names or {}
    dates = effective_dates or {}
    rows = []
    for security in sorted(set(assignments) | set(conflicts) | set(unclassified)):
        code = bare_code(security)
        if not code:
            continue
        row_effective_from = dates.get(code, effective_from)
        if row_effective_from > effective_from:
            # A provider date later than the fallback would make the row effective
            # after the snapshot it belongs to; that cannot be represented honestly.
            row_effective_from = effective_from
        if code in conflicts:
            # A conflict still needs a syntactically valid L2 slot to be storable;
            # it is carried as a conflict so no exposure can ever be derived from it.
            l1_code, l1_name, l2_code, l2_name = assignments.get(code, ("", "", None, ""))
            if l2_code is None:
                continue
            rows.append(ClassificationRow(
                security_code=code, security_name=names.get(code),
                shenwan_l1_code=l1_code or "UNKNOWN", shenwan_l1_name=l1_name or "UNKNOWN",
                shenwan_l2_code=l2_code,
                shenwan_l2_name=l2_name or "UNKNOWN", taxonomy_version=TAXONOMY_VERSION,
                classification_effective_from=row_effective_from,
                classification_effective_to=effective_to,
                source_publication_at=source_publication_at,
                evidence_observed_at=observed_at, evidence_available_at=available_at,
                classification_quality="CLASSIFICATION_CONFLICT"))
            continue
        if code in unclassified or code not in assignments:
            l1_code, l1_name, l2_code, l2_name = assignments.get(code, ("UNKNOWN", "UNKNOWN", None, "UNKNOWN"))
            if l2_code is None:
                continue
            rows.append(ClassificationRow(
                security_code=code, security_name=names.get(code),
                shenwan_l1_code=l1_code or "UNKNOWN", shenwan_l1_name=l1_name or "UNKNOWN",
                shenwan_l2_code=l2_code, shenwan_l2_name=l2_name or "UNKNOWN",
                taxonomy_version=TAXONOMY_VERSION,
                classification_effective_from=row_effective_from,
                classification_effective_to=effective_to,
                source_publication_at=source_publication_at,
                evidence_observed_at=observed_at, evidence_available_at=available_at,
                classification_quality=CLASSIFICATION_UNCLASSIFIED))
            continue
        l1_code, l1_name, l2_code, l2_name = assignments[code]
        rows.append(ClassificationRow(
            security_code=code, security_name=names.get(code),
            shenwan_l1_code=l1_code, shenwan_l1_name=l1_name, shenwan_l2_code=l2_code,
            shenwan_l2_name=l2_name, taxonomy_version=TAXONOMY_VERSION,
            classification_effective_from=row_effective_from,
            classification_effective_to=effective_to,
            source_publication_at=source_publication_at,
            evidence_observed_at=observed_at, evidence_available_at=available_at,
            classification_quality=CLASSIFICATION_OFFICIAL))
    return tuple(rows)


def build_classification_snapshot(*, snapshot_id: str, rows: tuple[ClassificationRow, ...],
                                  observed_at: str, available_at: str,
                                  sources: tuple[PinnedSource, ...],
                                  superseded_by: str | None = None,
                                  source_publication_at: str | None = None,
                                  coverage_gap: tuple[str, ...] = (),
                                  taxonomy_version: str = TAXONOMY_VERSION
                                  ) -> ClassificationSnapshot:
    return ClassificationSnapshot(
        snapshot_id=snapshot_id, taxonomy_version=taxonomy_version,
        validity_semantics=VALIDITY_FORWARD_ONLY_UNTIL_SUPERSEDED,
        snapshot_as_observed_at=observed_at, source_publication_at=source_publication_at,
        evidence_observed_at=observed_at, evidence_available_at=available_at, rows=rows,
        sources=sources, superseded_by=superseded_by, coverage_gap=coverage_gap)


# ---------------------------------------------------------------------------
# Package envelopes and hashes
# ---------------------------------------------------------------------------

def package_hash(payload: dict) -> str:
    """Hash of a package excluding its own ``package_hash`` field."""
    body = {key: value for key, value in payload.items() if key != "package_hash"}
    return sha256_json(body)


def envelope(identity: str, payload: dict) -> dict:
    document = {"schema_version": EVIDENCE_SCHEMA_VERSION, "identity": identity, **payload}
    document["package_hash"] = package_hash(document)
    return document


def tracking_package(*, relation: TrackingRelation) -> dict:
    return envelope(TRACKING_IDENTITY, {"relation": relation.as_dict()})


def weight_package(*, weights: WeightVector) -> dict:
    return envelope(WEIGHT_IDENTITY, {"vector": weights.as_dict()})


def classification_package(*, snapshot: ClassificationSnapshot) -> dict:
    return envelope(CLASSIFICATION_IDENTITY, {"snapshot": snapshot.as_dict()})


def exposure_package(*, exposure: BenchmarkL2Exposure) -> dict:
    return envelope(EXPOSURE_IDENTITY, {"exposure": exposure.as_dict()})


def mapping_package(*, mapping: B40MappingEvidence) -> dict:
    return envelope(MAPPING_IDENTITY, {"mapping": mapping.as_dict()})


def write_package(path: Path, document: dict) -> dict:
    """Write a package once. An existing identical file is left untouched."""
    body = canonical_bytes(document)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = target.read_bytes()
        if existing != body:
            raise EvidenceError("EVIDENCE_PACKAGE_IMMUTABILITY_BLOCKER",
                                {"path": str(target),
                                 "existing_hash": sha256_bytes(existing),
                                 "incoming_hash": sha256_bytes(body)})
        return document
    target.write_bytes(body)
    return document


# ---------------------------------------------------------------------------
# Adapter hand-off: the runtime evidence book
# ---------------------------------------------------------------------------

ADAPTER_BOOK_IDENTITY = "POINT_IN_TIME_EXECUTION_EVIDENCE_V1"
ADAPTER_SCHEMA_VERSION = "1.0.0"


def adapter_weight_source_document(*, benchmark_code: str, constituent_effective_date: str,
                                   rows: tuple[ConstituentRow, ...],
                                   declared_constituent_count: int) -> bytes:
    """The pinned ``weight_source`` document.

    It carries exactly the keys the adapter cross-checks (``constituents`` and
    ``declared_constituent_count``) and nothing that would have to be reconciled.
    """
    payload = {
        "artifact": "OFFICIAL_BENCHMARK_CONSTITUENT_WEIGHT_VECTOR_V1",
        "benchmark_code": benchmark_code,
        "constituent_effective_date": constituent_effective_date,
        "declared_constituent_count": int(declared_constituent_count),
        "constituents": [row.as_dict() for row in rows],
    }
    return canonical_bytes(payload)


def adapter_classification_source_document(*, rows: tuple[ClassificationRow, ...],
                                           effective_date: str,
                                           available_at: str) -> bytes:
    """The pinned ``classification_source`` document, in the adapter's row shape."""
    payload = {
        "artifact": "SHENWAN_L2_CLASSIFICATION_VECTOR_V1",
        "classifications": [
            {"security_code": row.security_code, "l2_code": row.shenwan_l2_code,
             "effective_date": row.classification_effective_from, "available_at": available_at,
             "l2_name": row.shenwan_l2_name, "l1_code": row.shenwan_l1_code,
             "l1_name": row.shenwan_l1_name, "quality": row.classification_quality}
            for row in rows
        ],
    }
    return canonical_bytes(payload)


def adapter_record(*, industry_code: str, etf_code: str, etf_name: str, benchmark_code: str,
                   source_publication_at: str | None, evidence_observed_at: str,
                   available_at: str, constituent_effective_date: str,
                   weight_effective_date: str, valid_through: str,
                   declared_constituent_count: int, weight_source: PinnedSource,
                   classification_source: PinnedSource, constituents: list[dict],
                   classifications: list[dict], provider: str) -> dict:
    """One record in the existing adapter's evidence-book schema.

    A record is emitted only when the arithmetic the adapter re-checks can hold:
    ``published <= observed <= available``, ``source_publication_at`` is never
    invented, and both pinned documents are the carriers of the extraction.
    """
    if source_publication_at is None:
        # The adapter requires an ordered chain. When the issuer states no
        # publication instant, the honest lower bound is our own first observation
        # and the package is flagged forward-only by its availability instant.
        source_publication_at = evidence_observed_at
    require_official_url(weight_source.source_url, "weight_source_url")
    require_official_url(classification_source.source_url, "classification_source_url")
    return {
        "industry_code": industry_code, "etf_code": etf_code, "etf_name": etf_name,
        "benchmark_code": benchmark_code,
        "weight_source_type": "OFFICIAL_WEIGHT",
        "weight_source_provider": provider,
        "source_publication_at": source_publication_at,
        "evidence_observed_at": evidence_observed_at, "available_at": available_at,
        "constituent_effective_date": constituent_effective_date,
        "weight_effective_date": weight_effective_date, "valid_through": valid_through,
        "declared_constituent_count": int(declared_constituent_count),
        "weight_source_file": weight_source.relative_path,
        "weight_source_sha256": weight_source.source_sha256,
        "weight_source_url": weight_source.source_url,
        "classification_source_file": classification_source.relative_path,
        "classification_source_sha256": classification_source.source_sha256,
        "classification_source_url": classification_source.source_url,
        "constituents": constituents, "classifications": classifications,
    }


def adapter_book_document(*, records: list[dict]) -> bytes:
    return canonical_bytes({"schema_version": ADAPTER_SCHEMA_VERSION,
                            "identity": ADAPTER_BOOK_IDENTITY, "records": records})


__all__ = [
    "ADAPTER_BOOK_IDENTITY",
    "ADAPTER_SCHEMA_VERSION",
    "SSE_CATALOG_URL",
    "SZSE_CATALOG_URL",
    "TAXONOMY_VERSION",
    "adapter_book_document",
    "adapter_classification_source_document",
    "adapter_record",
    "adapter_weight_source_document",
    "build_classification_rows",
    "build_classification_snapshot",
    "build_tracking_relations_from_sse_catalog",
    "build_tracking_relations_from_szse_catalog",
    "build_weight_vector_from_constituent_rows",
    "classification_package",
    "decide_b40_mapping",
    "derive_l2_exposure",
    "envelope",
    "exposure_package",
    "mapping_package",
    "package_hash",
    "tracking_package",
    "weight_package",
    "write_package",
]

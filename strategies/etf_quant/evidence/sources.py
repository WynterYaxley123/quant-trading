"""Pinning of official raw bytes, outside the repository.

The runtime adapter proves that two pinned byte streams hash to the values a
record names. It cannot prove where those bytes came from. This module is what
makes that link: it copies each official response into a package-local
``raw/`` tree, hashes the bytes as received, and records the URL, the HTTP
metadata and the wall-clock instant of retrieval.

Nothing here is committed to Git. The repository receives only schemas, builders,
tests and small metadata manifests; the raw official artifacts stay under
``D:\\QuantForge\\runtime\\...`` and are referenced by hash.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from .schema import (EvidenceError, PinnedSource, require_official_url, require_safe_name,
                     sha256_bytes)

#: Default runtime root for this task. Never inside a Git work tree.
DEFAULT_RUNTIME_ROOT = Path(r"D:\QuantForge\runtime\etf-quant-v1\production-pit-evidence-v1")

MANIFEST_NAME = "raw_source_manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


#: What a pinned byte stream actually is.
KIND_VERBATIM_PROVIDER_BYTES = "VERBATIM_PROVIDER_BYTES"
KIND_DOCUMENTED_EXTRACTION = "DOCUMENTED_EXTRACTION"
SOURCE_KINDS = (KIND_VERBATIM_PROVIDER_BYTES, KIND_DOCUMENTED_EXTRACTION)


@dataclass(frozen=True)
class RawSourceRecord:
    """Audit row for one pinned byte stream.

    ``kind`` is not decoration. ``VERBATIM_PROVIDER_BYTES`` means re-fetching
    ``source_url`` reproduces these exact bytes, so the hash is independently
    checkable by a reviewer. ``DOCUMENTED_EXTRACTION`` means the file is a document
    this system assembled, and ``derived_from`` names the verbatim captures it came
    from together with their URLs and hashes. Presenting the second kind as if it
    were the first is precisely what an independent audit caught in the previous
    revision of this build, so the distinction is now recorded per source.
    """

    relative_path: str
    stored_name: str
    source_url: str
    source_sha256: str
    byte_length: int
    content_type: str | None
    source_retrieved_at: str
    evidence_observed_at: str
    source_publication_at: str | None
    note: str = ""
    kind: str = KIND_VERBATIM_PROVIDER_BYTES
    derived_from: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in SOURCE_KINDS:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "UNKNOWN_SOURCE_KIND", "kind": self.kind})
        if self.kind == KIND_DOCUMENTED_EXTRACTION and not self.derived_from:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "EXTRACTION_WITHOUT_UPSTREAM",
                                 "relative_path": self.relative_path})

    def as_dict(self) -> dict:
        return {
            "relative_path": self.relative_path, "stored_name": self.stored_name,
            "source_url": self.source_url, "kind": self.kind,
            "source_sha256": self.source_sha256, "byte_length": self.byte_length,
            "content_type": self.content_type,
            "source_retrieved_at": self.source_retrieved_at,
            "evidence_observed_at": self.evidence_observed_at,
            "source_publication_at": self.source_publication_at,
            "derived_from": [dict(item) for item in self.derived_from],
            "note": self.note,
        }


class SourcePin:
    """Copy-once store of official raw bytes under a package source root.

    A path may be pinned exactly once. Re-pinning the same relative path with
    different bytes is refused outright: evidence packages are append-only, and a
    silent overwrite would invalidate every hash that already referenced it.

    ``relative_path`` is the audit identity of the byte stream and may contain
    ``/``. ``stored_name`` is the flat name the bytes are written under, because
    the runtime adapter refuses any pinned filename containing a path separator.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, RawSourceRecord] = {}

    # -- population ---------------------------------------------------------

    def pin_bytes(self, *, relative_path: str, body: bytes, source_url: str,
                  content_type: str | None = None,
                  source_publication_at: str | None = None,
                  evidence_observed_at: str | None = None,
                  source_retrieved_at: str | None = None,
                  note: str = "", stored_name: str | None = None,
                  kind: str = KIND_VERBATIM_PROVIDER_BYTES,
                  derived_from: tuple[dict, ...] = ()) -> PinnedSource:
        require_safe_name(relative_path, "relative_path")
        require_official_url(source_url, "source_url")
        if not isinstance(body, bytes) or not body:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "EMPTY_SOURCE_BODY", "relative_path": relative_path})
        if stored_name is None:
            stored_name = relative_path.replace("/", "__")
        # The adapter's filename rule, applied at build time rather than at trade time.
        if "/" in stored_name or "\\" in stored_name:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "STORED_NAME_MUST_BE_FLAT", "stored_name": stored_name})
        observed = evidence_observed_at or _now()
        retrieved = source_retrieved_at or observed
        digest = sha256_bytes(body)
        existing = self._records.get(relative_path)
        if existing is not None:
            if existing.source_sha256 != digest or existing.source_url != source_url:
                # Immutability: a path is bound to one URL and one byte stream.
                raise EvidenceError("EVIDENCE_SOURCE_IMMUTABILITY_BLOCKER",
                                    {"relative_path": relative_path,
                                     "existing_sha256": existing.source_sha256,
                                     "incoming_sha256": digest})
            return self._as_pinned(existing)
        target = self.root / stored_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            on_disk = target.read_bytes()
            if sha256_bytes(on_disk) != digest:
                raise EvidenceError("EVIDENCE_SOURCE_IMMUTABILITY_BLOCKER",
                                    {"relative_path": relative_path,
                                     "reason": "ON_DISK_BYTES_DIFFER"})
        else:
            temp = target.with_name("." + target.name + ".tmp")
            with temp.open("wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        record = RawSourceRecord(
            relative_path=relative_path, stored_name=stored_name, source_url=source_url,
            source_sha256=digest, byte_length=len(body), content_type=content_type,
            source_retrieved_at=retrieved, evidence_observed_at=observed,
            source_publication_at=source_publication_at, note=note, kind=kind,
            derived_from=tuple(derived_from))
        self._records[relative_path] = record
        return self._as_pinned(record)

    def pin_file(self, source: Path, *, relative_path: str, source_url: str, **kwargs
                 ) -> PinnedSource:
        """Pin an already-downloaded official file byte-for-byte."""
        source = Path(source)
        if not source.is_file():
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "SOURCE_FILE_MISSING", "path": str(source)})
        return self.pin_bytes(relative_path=relative_path, body=source.read_bytes(),
                              source_url=source_url, **kwargs)

    def require_pinned(self, relative_path: str) -> PinnedSource:
        try:
            return self._as_pinned(self._records[relative_path])
        except KeyError as error:
            raise EvidenceError("EVIDENCE_OFFICIAL_SOURCE_BLOCKER",
                                {"reason": "SOURCE_NOT_PINNED",
                                 "relative_path": relative_path}) from error

    # -- views --------------------------------------------------------------

    def _as_pinned(self, record: RawSourceRecord) -> PinnedSource:
        return PinnedSource(
            relative_path=record.stored_name, source_url=record.source_url,
            source_publication_at=record.source_publication_at,
            evidence_observed_at=record.evidence_observed_at,
            source_retrieved_at=record.source_retrieved_at,
            source_sha256=record.source_sha256,
            evidence_available_at=record.evidence_observed_at,
            content_type=record.content_type, byte_length=record.byte_length)

    @property
    def records(self) -> tuple[RawSourceRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def verify(self) -> dict:
        """Re-read every pinned file from disk and re-check its hash."""
        checked, failures = 0, []
        for record in self.records:
            target = self.root / record.stored_name
            try:
                body = target.read_bytes()
            except OSError as error:
                failures.append({"relative_path": record.relative_path,
                                 "reason": f"UNREADABLE:{type(error).__name__}"})
                continue
            if sha256_bytes(body) != record.source_sha256:
                failures.append({"relative_path": record.relative_path,
                                 "reason": "HASH_MISMATCH"})
                continue
            if len(body) != record.byte_length:
                failures.append({"relative_path": record.relative_path,
                                 "reason": "LENGTH_MISMATCH"})
                continue
            checked += 1
        return {"checked": checked, "failures": failures, "ok": not failures}

    def write_manifest(self, path: Path | None = None) -> Path:
        target = Path(path) if path is not None else self.root / MANIFEST_NAME
        records = self.records
        payload = {
            "schema_version": "1.0.0",
            "artifact": "RAW_OFFICIAL_SOURCE_MANIFEST_V1",
            "source_root": str(self.root),
            "source_count": len(records),
            "total_bytes": sum(r.byte_length for r in records),
            "verbatim_provider_bytes": sum(
                1 for r in records if r.kind == KIND_VERBATIM_PROVIDER_BYTES),
            "documented_extractions": sum(
                1 for r in records if r.kind == KIND_DOCUMENTED_EXTRACTION),
            "reproducibility_note": (
                "A source whose kind is VERBATIM_PROVIDER_BYTES can be re-fetched from "
                "its source_url and will hash to source_sha256. A source whose kind is "
                "DOCUMENTED_EXTRACTION is a document this system assembled from the "
                "captures named in derived_from; its own bytes are not served by any "
                "provider and the URL records where its inputs came from."),
            "sources": [record.as_dict() for record in records],
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False)
                           .encode("utf-8"))
        return target


def copy_tree(source_dir: Path, destination: Path, *, only_suffixes=(".json",)) -> int:
    """Copy a verified raw cache verbatim, refusing to overwrite differing bytes."""
    source_dir, destination = Path(source_dir), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in sorted(source_dir.iterdir()):
        if not item.is_file() or (only_suffixes and item.suffix not in only_suffixes):
            continue
        target = destination / item.name
        body = item.read_bytes()
        if target.exists():
            if target.read_bytes() != body:
                raise EvidenceError("EVIDENCE_SOURCE_IMMUTABILITY_BLOCKER",
                                    {"path": str(target)})
            continue
        shutil.copyfile(item, target)
        copied += 1
    return copied


__all__ = [
    "DEFAULT_RUNTIME_ROOT",
    "MANIFEST_NAME",
    "RawSourceRecord",
    "SourcePin",
    "copy_tree",
]

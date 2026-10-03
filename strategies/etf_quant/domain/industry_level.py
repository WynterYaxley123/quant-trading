"""Frozen production industry level and the evidence-backed Shenwan taxonomy.

Frozen contract
---------------
``ETF_QUANT_INDUSTRY_LEVEL_V1 = "SHENWAN_L2"``

The V1 production chain (Source C -> 19 frozen factors -> frozen Ridge
H10/H40/H120 -> 0.25/0.50/0.25 fusion ranking -> industry->ETF mapping ->
5-ETF capped-softmax portfolio) is defined at Shenwan 2021 **Level 2**. The
width-4 resolution is not a display convention and not a rounding of a finer
truth: it is the granularity at which the frozen engineering model was fitted
and at which the verified industry->ETF mapping registry is keyed. The frozen
model is never re-cut to Level 3 to accommodate a mapping layer.

Why a taxonomy artifact instead of ``code[:4]``
-----------------------------------------------
The stored membership layer publishes 6-digit Shenwan codes. Deriving the
Level-2 code by truncating that string is a *guess about the taxonomy*, and a
guess that keeps producing plausible-looking codes even if the upstream code
scheme changes. This module therefore never truncates a runtime code. Every
6-digit code is resolved through an explicit, sealed ``level3 -> level2``
relation loaded from ``config/shenwan_industry_taxonomy_v1.json``, which is
generated from the official Shenwan classification publication and carries
that publication's URL, retrieval time and SHA-256. A stored code that is
absent from the table raises ``INDUSTRY_TAXONOMY_BLOCKER``; it is never
silently coerced.

Name-only or fuzzy matching is not implemented anywhere in this module.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

#: The single frozen production industry level for ETF-Quant V1.
ETF_QUANT_INDUSTRY_LEVEL_V1 = "SHENWAN_L2"
#: Digit width of an ``ETF_QUANT_INDUSTRY_LEVEL_V1`` code.
INDUSTRY_LEVEL_WIDTH = 4
#: Digit width of a stored Shenwan Level-3 code.
LEVEL3_WIDTH = 6
TAXONOMY_IDENTITY = "SHENWAN_INDUSTRY_TAXONOMY_2021_V1"
CLASSIFICATION_VERSION = "SWCLASS2021"
TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "config" / "shenwan_industry_taxonomy_v1.json"

_LEVEL3 = re.compile(r"[0-9]{%d}" % LEVEL3_WIDTH)
_LEVEL2 = re.compile(r"[0-9]{%d}" % INDUSTRY_LEVEL_WIDTH)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_HTTPS = re.compile(r"https:[/]{2}[^/@\s]+[/][^\s]*")
_OPTIONAL_HTTPS = re.compile(r"(https:[/]{2}[^/@\s]+[/][^\s]*)?")


class TaxonomyError(ValueError):
    """A taxonomy fact could not be established from sealed evidence."""

    def __init__(self, code: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = {} if details is None else details


def _retrieved(value, field: str) -> datetime:
    if not isinstance(value, str):
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"field": field})
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"field": field}) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TaxonomyError("TAXONOMY_TIME_SEMANTICS_BLOCKER", {"field": field})
    return parsed


@dataclass(frozen=True)
class IndustryTaxonomy:
    """Sealed Shenwan taxonomy: explicit Level-3 -> Level-2 relation plus names.

    ``level3_children`` / ``level3_to_level2`` are complete for the codes the
    official classification actually publishes. ``industry_names`` is a subset:
    a name is present only where the artifact records evidence for it, and
    nothing downstream may invent a name for a code that lacks one.
    """

    industry_level: str
    level_width: int
    classification_version: str
    industry_names: Mapping[str, str]
    level3_to_level2: Mapping[str, str]
    level3_children: Mapping[str, tuple[str, ...]]
    publisher: str
    source_url: str
    source_sha256: str
    source_retrieved_at: datetime
    hierarchy_evidence: tuple[dict, ...]
    name_evidence: tuple[dict, ...]
    sha256: str
    identity: str = TAXONOMY_IDENTITY
    schema_version: str = "1.0.0"

    @property
    def industry_codes(self) -> tuple[str, ...]:
        """Every Level-2 code the sealed classification defines."""
        return tuple(sorted(self.level3_children))

    @property
    def named_industry_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self.industry_names))

    def level2_of(self, level3_code: str) -> str:
        """Explicit relation lookup. Never a prefix truncation."""
        if not isinstance(level3_code, str) or not _LEVEL3.fullmatch(level3_code):
            raise TaxonomyError("INDUSTRY_TAXONOMY_BLOCKER", {"reason": "MALFORMED_LEVEL3_CODE"})
        try:
            return self.level3_to_level2[level3_code]
        except KeyError as error:
            raise TaxonomyError(
                "INDUSTRY_TAXONOMY_BLOCKER",
                {"reason": "LEVEL3_CODE_ABSENT_FROM_OFFICIAL_TAXONOMY", "level3_code": level3_code},
            ) from error

    def name_of(self, industry_code: str) -> str:
        try:
            return self.industry_names[industry_code]
        except KeyError as error:
            raise TaxonomyError(
                "INDUSTRY_TAXONOMY_BLOCKER",
                {
                    "reason": "NO_EVIDENCE_BACKED_NAME_FOR_INDUSTRY_CODE",
                    "industry_code": industry_code,
                },
            ) from error

    def assert_level(self, industry_code: str) -> str:
        """A production mapping key must be a Level-2 code of this taxonomy."""
        if not isinstance(industry_code, str) or not _LEVEL2.fullmatch(industry_code):
            raise TaxonomyError(
                "INDUSTRY_LEVEL_CONTRACT_BLOCKER",
                {"reason": "INDUSTRY_CODE_NOT_LEVEL2", "industry_code": industry_code},
            )
        if industry_code not in self.level3_children:
            raise TaxonomyError(
                "INDUSTRY_LEVEL_CONTRACT_BLOCKER",
                {
                    "reason": "INDUSTRY_CODE_ABSENT_FROM_OFFICIAL_TAXONOMY",
                    "industry_code": industry_code,
                },
            )
        return industry_code


def parse_taxonomy(body: bytes) -> IndustryTaxonomy:
    try:
        doc = json.loads(body)
    except (ValueError, TypeError) as error:
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"reason": "NOT_JSON"}) from error
    if not isinstance(doc, dict):
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"reason": "NOT_AN_OBJECT"})
    if (
        doc.get("schema_version") != "1.0.0"
        or doc.get("taxonomy_identity") != TAXONOMY_IDENTITY
        or doc.get("industry_level") != ETF_QUANT_INDUSTRY_LEVEL_V1
        or doc.get("level_width") != INDUSTRY_LEVEL_WIDTH
        or doc.get("classification_version") != CLASSIFICATION_VERSION
    ):
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"reason": "IDENTITY_OR_LEVEL_MISMATCH"})
    source = doc.get("source")
    if not isinstance(source, dict):
        raise TaxonomyError("TAXONOMY_EVIDENCE_BLOCKER", {"reason": "MISSING_SOURCE"})
    publisher, source_url = source.get("publisher"), source.get("source_url")
    if (
        not isinstance(publisher, str)
        or not publisher.strip()
        or not isinstance(source_url, str)
        or not _HTTPS.fullmatch(source_url)
        or not isinstance(source.get("source_sha256"), str)
        or not _SHA256.fullmatch(source["source_sha256"])
    ):
        raise TaxonomyError("TAXONOMY_EVIDENCE_BLOCKER", {"reason": "UNUSABLE_SOURCE"})
    retrieved = _retrieved(source.get("source_retrieved_at"), "source.source_retrieved_at")
    evidence = doc.get("hierarchy_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise TaxonomyError("TAXONOMY_EVIDENCE_BLOCKER", {"reason": "MISSING_HIERARCHY_EVIDENCE"})
    checked = []
    for item in evidence:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("source_url"), str)
            or not _OPTIONAL_HTTPS.fullmatch(item["source_url"])
            or not isinstance(item.get("statement"), str)
            or not item["statement"].strip()
            or not isinstance(item.get("publisher"), str)
            or not item["publisher"].strip()
        ):
            raise TaxonomyError(
                "TAXONOMY_EVIDENCE_BLOCKER", {"reason": "MALFORMED_HIERARCHY_EVIDENCE"}
            )
        checked.append(
            {
                "publisher": item["publisher"],
                "source_url": item["source_url"],
                "statement": item["statement"],
                "evidence_type": item.get("evidence_type", "OFFICIAL_PUBLICATION"),
                "observed_at": item.get("observed_at"),
            }
        )
    name_evidence = doc.get("name_evidence")
    if not isinstance(name_evidence, list) or not name_evidence:
        raise TaxonomyError("TAXONOMY_EVIDENCE_BLOCKER", {"reason": "MISSING_NAME_EVIDENCE"})
    checked_names = []
    for item in name_evidence:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("publisher"), str)
            or not item["publisher"].strip()
            or not isinstance(item.get("statement"), str)
            or not item["statement"].strip()
            or not isinstance(item.get("source_url"), str)
            or not _OPTIONAL_HTTPS.fullmatch(item["source_url"])
        ):
            raise TaxonomyError("TAXONOMY_EVIDENCE_BLOCKER", {"reason": "MALFORMED_NAME_EVIDENCE"})
        checked_names.append(
            {
                "publisher": item["publisher"],
                "source_url": item["source_url"],
                "statement": item["statement"],
                "evidence_type": item.get("evidence_type", "OFFICIAL_PUBLICATION"),
                "observed_at": item.get("observed_at"),
            }
        )
    rows = doc.get("industries")
    if not isinstance(rows, list) or not rows:
        raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"reason": "NO_INDUSTRIES"})
    names = {}
    children = {}
    relation: dict[str, str] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise TaxonomyError("TAXONOMY_SCHEMA_BLOCKER", {"reason": "INDUSTRY_ROW_NOT_OBJECT"})
        code, name = raw.get("industry_code"), raw.get("industry_name")
        kids = raw.get("level3_children")
        # A name is optional; when present it must be a usable label. Names are
        # never invented for a code the evidence does not cover.
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise TaxonomyError(
                "TAXONOMY_SCHEMA_BLOCKER", {"reason": "EMPTY_INDUSTRY_NAME", "industry_code": code}
            )
        if (
            raw.get("industry_level") != ETF_QUANT_INDUSTRY_LEVEL_V1
            or not isinstance(code, str)
            or not _LEVEL2.fullmatch(code)
            or not isinstance(kids, list)
            or not kids
            or any(not isinstance(k, str) or not _LEVEL3.fullmatch(k) for k in kids)
            or len(set(kids)) != len(kids)
        ):
            raise TaxonomyError(
                "TAXONOMY_SCHEMA_BLOCKER",
                {"reason": "MALFORMED_INDUSTRY_ROW", "industry_code": code},
            )
        if code in children:
            raise TaxonomyError("TAXONOMY_DUPLICATE_BLOCKER", {"industry_code": code})
        ordered = tuple(sorted(kids))
        if name is not None:
            names[code] = name.strip()
        children[code] = ordered
        for kid in ordered:
            if kid in relation:
                raise TaxonomyError(
                    "TAXONOMY_DUPLICATE_BLOCKER",
                    {"level3_code": kid, "level2_codes": [relation[kid], code]},
                )
            relation[kid] = code
    return IndustryTaxonomy(
        industry_level=ETF_QUANT_INDUSTRY_LEVEL_V1,
        level_width=INDUSTRY_LEVEL_WIDTH,
        classification_version=CLASSIFICATION_VERSION,
        industry_names=MappingProxyType(names),
        level3_to_level2=MappingProxyType(relation),
        level3_children=MappingProxyType(children),
        publisher=publisher.strip(),
        source_url=source_url,
        source_sha256=source["source_sha256"],
        source_retrieved_at=retrieved,
        hierarchy_evidence=tuple(checked),
        name_evidence=tuple(checked_names),
        sha256=_digest(body),
    )


def _digest(body: bytes) -> str:
    import hashlib

    return hashlib.sha256(body).hexdigest()


def load_taxonomy(path: Path | None = None) -> IndustryTaxonomy:
    target = TAXONOMY_PATH if path is None else Path(path)
    try:
        return parse_taxonomy(target.read_bytes())
    except TaxonomyError:
        raise
    except OSError as error:
        raise TaxonomyError(
            "TAXONOMY_EVIDENCE_BLOCKER", {"reason": "TAXONOMY_ARTIFACT_UNREADABLE"}
        ) from error


@functools.lru_cache(maxsize=4)
def _default_taxonomy(identity: str) -> IndustryTaxonomy:
    return load_taxonomy()


def default_taxonomy() -> IndustryTaxonomy:
    """The single sealed V1 taxonomy shipped with the strategy package."""
    return _default_taxonomy(TAXONOMY_IDENTITY)


def level2_codes(codes, taxonomy: IndustryTaxonomy | None = None) -> tuple[str, ...]:
    """Resolve stored Level-3 codes to Level-2 in taxonomy order, failing closed."""
    taxonomy = default_taxonomy() if taxonomy is None else taxonomy
    return tuple(sorted({taxonomy.level2_of(code) for code in codes}))


__all__ = [
    "CLASSIFICATION_VERSION",
    "ETF_QUANT_INDUSTRY_LEVEL_V1",
    "INDUSTRY_LEVEL_WIDTH",
    "LEVEL3_WIDTH",
    "TAXONOMY_IDENTITY",
    "TAXONOMY_PATH",
    "IndustryTaxonomy",
    "TaxonomyError",
    "default_taxonomy",
    "level2_codes",
    "load_taxonomy",
    "parse_taxonomy",
]

"""Offline ETF mapping/tradability audit.  Never imports or downloads quotes."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.data.verify_etf_evidence import verify_etf_evidence  # noqa: E402
from src.data.loaders.shenwan_sector_loader import (  # noqa: E402
    load_sector_catalog,
    load_sector_panel,
)
from src.data.providers.etf_local import read_local_etf_snapshot  # noqa: E402
from src.data.providers.shenwan_official import sha256_file  # noqa: E402
from src.data.providers.shenwan_sector import candidate_research_range  # noqa: E402
from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import (  # noqa: E402
    MappingEvidence,
    daily_mapping_availability,
    mapping_admission,
    resolve_primary_mapping,
    validate_mapping_evidence,
)


class EvidenceIntegrityFailure(RuntimeError):
    """The official-evidence chain is inconsistent; admission must stop."""


@dataclass(frozen=True)
class ProxyAdmissionEvidence:
    """Derived proxy evidence; deliberately not a direct MappingEvidence row."""

    etf_code: str
    sector_code: str
    mapping_kind: str = "PROXY_MAPPING"
    official_direct_equivalence: bool = False
    methodology_official: bool = (
        False  # official index basic info is not an archived methodology version
    )
    methodology_historical_version_confirmed: bool = False
    methodology_available_at: str | None = None
    methodology_available_before_signal: bool = False
    methodology_valid_from: str | None = None
    methodology_valid_to: str | None = None
    composition_source_type: str = "NO_CONSTITUENT_EVIDENCE"
    composition_coverage_type: str = "NONE"
    composition_source_official: bool = False
    composition_as_of_date: str | None = None
    composition_available_at: str | None = None
    composition_valid_from: str | None = None
    composition_valid_to: str | None = None
    available_before_signal: bool = False
    constituent_count: int = 0
    classified_count: int = 0
    count_share: float | None = None  # percent of observed constituents
    weight_share: float | None = None  # percent of observed weight, never inferred
    other_l2_count: int = 0
    other_l2_summary: str | None = None
    unclassified_count: int = 0
    relationship_documented_from: str | None = None
    official_listing_date: str | None = None
    tradable_start_candidate: str | None = None
    relationship_effective_from: str | None = None  # confirmed, not a candidate date
    relationship_effective_to: str | None = None
    relationship_evidence_available_at: str | None = None
    relationship_available_before_signal: bool = False
    relationship_continuity_status: str = "UNPROVEN"
    relationship_continuity_proven_at: str | None = None
    relationship_continuity_valid_through: str | None = None
    index_change_event_found: bool | None = None
    index_change_search_note: str | None = None
    sw_classification_status: str = "FIXED_CLASSIFICATION_RESEARCH"
    sw_classification_valid_from: str | None = None
    sw_classification_valid_to: str | None = None
    sw_classification_available_at: str | None = None
    sw_classification_available_before_signal: bool = False


def _on_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def current_proxy_status(e: ProxyAdmissionEvidence) -> str:
    """Descriptive concentration of *observed* material, not admission."""
    if not e.methodology_official or not e.composition_source_official or not e.constituent_count:
        return "PROXY_CURRENT_INSUFFICIENT"
    if e.composition_source_type == "ETF_REPLICATION_BASKET_PROXY":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 90
            and e.unclassified_count == 0
            and e.other_l2_count / e.constituent_count <= 0.10
        )
    elif e.composition_source_type == "TOP10_ONLY_PROXY":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 80
            and e.weight_share is not None
            and e.weight_share >= 85
            and e.unclassified_count <= 1
        )
    elif e.composition_source_type == "FULL_INDEX_CONSTITUENTS_WITH_WEIGHTS":
        strong_observed = (
            e.count_share is not None
            and e.count_share >= 90
            and e.weight_share is not None
            and e.weight_share >= 90
            and e.unclassified_count == 0
            and e.other_l2_count / e.constituent_count <= 0.10
        )
    else:
        return "PROXY_CURRENT_INSUFFICIENT"
    return "PROXY_CURRENT_STRONG" if strong_observed else "PROXY_CURRENT_MIXED"


def historical_proxy_admissible(
    e: ProxyAdmissionEvidence,
    research_date: str,
    *,
    require_historical_sw: bool = True,
) -> bool:
    """Point-in-time gate. A later snapshot or an unproven interval never backfills t."""
    t = date.fromisoformat(research_date)
    if e.mapping_kind != "PROXY_MAPPING" or e.official_direct_equivalence:
        return False
    if (
        not e.methodology_official
        or not e.methodology_historical_version_confirmed
        or not e.composition_source_official
    ):
        return False
    m_available = _on_date(e.methodology_available_at)
    m_start, m_end = _on_date(e.methodology_valid_from), _on_date(e.methodology_valid_to)
    if (
        m_available is None
        or m_start is None
        or m_end is None
        or m_available > t
        or not m_start <= t <= m_end
        or (m_available == t and not e.methodology_available_before_signal)
    ):
        return False
    # PCF is an ETF creation basket, and Top10 is a subset. Neither proves the full index.
    if e.composition_source_type != "FULL_INDEX_CONSTITUENTS_WITH_WEIGHTS":
        return False
    if (
        e.count_share is None
        or e.count_share < 90
        or e.weight_share is None
        or e.weight_share < 90
        or e.constituent_count <= 0
        or e.unclassified_count != 0
        or e.count_share > 100
        or e.weight_share > 100
        or not 0 <= e.other_l2_count <= e.constituent_count
        or e.other_l2_count / e.constituent_count > 0.10
    ):
        return False
    observed, available = _on_date(e.composition_as_of_date), _on_date(e.composition_available_at)
    if observed is None or available is None or observed > t or available > t:
        return False
    c_start, c_end = _on_date(e.composition_valid_from), _on_date(e.composition_valid_to)
    if (c_start is None) != (c_end is None):
        return False
    if c_start is not None and c_end is not None:
        if not c_start <= t <= c_end:
            return False
    elif observed != t:
        return False  # one snapshot is not an indefinite effective interval
    if available == t and not e.available_before_signal:
        return False  # date-only same-day publication timing is insufficient
    r_start, r_end = _on_date(e.relationship_effective_from), _on_date(e.relationship_effective_to)
    r_available = _on_date(e.relationship_evidence_available_at)
    continuity_proven = _on_date(e.relationship_continuity_proven_at)
    continuity_through = _on_date(e.relationship_continuity_valid_through)
    if (
        r_start is None
        or r_start > t
        or (r_end is not None and t > r_end)
        or e.relationship_continuity_status != "PROVEN_CONTINUOUS"
        or r_available is None
        or r_available > t
        or (r_available == t and not e.relationship_available_before_signal)
        or continuity_proven is None
        or continuity_proven > t
        or continuity_through is None
        or continuity_through < t
        or (continuity_proven == t and not e.relationship_available_before_signal)
    ):
        return False
    # A search finding no index-change notice is not affirmative continuity proof.
    if require_historical_sw:
        s_start, s_end = (
            _on_date(e.sw_classification_valid_from),
            _on_date(e.sw_classification_valid_to),
        )
        s_available = _on_date(e.sw_classification_available_at)
        if (
            e.sw_classification_status != "HISTORICAL_PIT"
            or s_start is None
            or s_end is None
            or s_available is None
            or not s_start <= t <= s_end
            or s_available > t
            or (s_available == t and not e.sw_classification_available_before_signal)
        ):
            return False
    return True


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise EvidenceIntegrityFailure(f"missing evidence file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_official_evidence(
    repo_root: Path,
    evidence_dir: Path,
    catalog: dict[str, str],
) -> dict:
    """Audit local catalog, field provenance, raw histories and legacy reviews."""
    integrity = verify_etf_evidence(repo_root)
    if not integrity.get("integrity_pass") or integrity.get("orphan_pdf_count") != 0:
        raise EvidenceIntegrityFailure(
            f"DATA_EVIDENCE_INTEGRITY_FAILURE: {integrity.get('problems')} / "
            f"orphans={integrity.get('orphan_pdfs')}"
        )
    rows = _read_rows(evidence_dir / "evidence_catalog.csv")
    sources = _read_rows(evidence_dir / "evidence_sources.csv")
    legacy = _read_rows(evidence_dir / "legacy_mapping_review.csv")
    reference = _read_rows(evidence_dir / "legacy_reference_doc_review.csv")
    problems: list[str] = []
    codes = [r["etf_code"] for r in rows]
    if not rows or len(set(codes)) != len(rows):
        problems.append("evidence catalog must have unique ETF codes")
    if not legacy or any(not r["final_evidence_status"] for r in legacy):
        problems.append("legacy review has unconcluded rows")
    if not reference:
        problems.append("reference review is empty")
    manifest = json.loads(
        (repo_root / "data/raw/etf_evidence/documents_manifest.json").read_text(encoding="utf-8")
    )
    registered = {
        (code, d["document"]): d
        for code, entry in manifest.items()
        for d in [entry, *entry.get("extra_docs", [])]
        if d.get("document")
    }
    if set(codes) != set(manifest):
        problems.append("evidence catalog/manifest ETF code sets differ")
    by_code: dict[str, list[dict]] = {}
    for item in sources:
        code, document = item["etf_code"], item["document"]
        record = registered.get((code, document))
        if record is None or not item["on_disk"].lower() == "true":
            problems.append(f"{code}: supporting document is not registered/on disk: {document}")
            continue
        if (
            item["sha256"] != record.get("sha256")
            or item["source_url"] != record.get("source_url")
            or item["size_bytes"] != str(record.get("bytes"))
        ):
            problems.append(f"{code}: supporting document provenance mismatch: {document}")
        by_code.setdefault(code, []).append(item)
    if len(sources) != len(registered) or len(
        {(x["etf_code"], x["document"]) for x in sources}
    ) != len(sources):
        problems.append("evidence_sources must list each registered document exactly once")
    required_fields = {
        "etf_name": "fund_identity",
        "fund_manager": "fund_identity",
        "official_listing_date": "official_listing_date",
        "fund_establishment_date": "fund_establishment_date",
        "tracking_index_name": "tracking_index_name",
    }
    statuses = {"VALIDATED", "PARTIAL_EVIDENCE", "NOT_DIRECT_MAPPING", "CONFLICT", "UNVERIFIED"}
    for row in rows:
        code = row["etf_code"]
        if row["evidence_status"] not in statuses:
            problems.append(f"{code}: unknown evidence_status")
        if row["market"] not in {"sh", "sz"} or not code.isdigit() or len(code) != 6:
            problems.append(f"{code}: invalid ETF code/market")
        primary = [x for x in by_code.get(code, []) if x["is_primary"].lower() == "true"]
        if len(primary) != 1 or primary[0]["document"] != row["source_document"]:
            problems.append(f"{code}: primary source selection mismatch")
        tags = {tag for x in by_code.get(code, []) for tag in x["substantiates"].split(";") if tag}
        for field, tag in required_fields.items():
            if row[field] and tag not in tags:
                problems.append(f"{code}: {field} lacks field-level official provenance")
        for field in (
            "official_listing_date",
            "fund_establishment_date",
            "mapping_effective_from",
            "mapping_effective_to",
        ):
            if row[field]:
                try:
                    date.fromisoformat(row[field])
                except ValueError:
                    problems.append(f"{code}: invalid {field} date")
        if (
            row["tracking_relationship"] == "CURRENT_RELATIONSHIP_ONLY"
            and row["mapping_effective_from"]
        ):
            problems.append(f"{code}: current relationship was backfilled")
        if row["evidence_status"] == "PARTIAL_EVIDENCE":  # noqa: SIM102 -- Preserve independently documented frozen validation branches.
            if catalog.get(row["sector_code"]) != row["sector_name"]:
                problems.append(f"{code}: partial candidate not in canonical Level-2 catalog")
        if row["evidence_status"] == "VALIDATED":  # noqa: SIM102 -- Preserve independently documented frozen validation branches.
            if not row["mapping_effective_from"] or "shenwan_l2_direct_equivalence" not in tags:
                problems.append(f"{code}: VALIDATED lacks historical Layer-2 evidence")

    raw_manifest_path = repo_root / "data/raw/etf/manifest_etf_daily_raw.json"
    if not raw_manifest_path.is_file():
        raise EvidenceIntegrityFailure(
            f"DATA_EVIDENCE_INTEGRITY_FAILURE: missing {raw_manifest_path}"
        )
    history_manifest = json.loads(raw_manifest_path.read_text(encoding="utf-8"))
    history_root = repo_root / "data/raw/etf"
    if not set(history_manifest).issubset(codes):
        problems.append("raw ETF history includes codes absent from official catalog")
    history_total = 0
    for code, meta in history_manifest.items():
        filename = meta["file"]
        if Path(filename).name != filename:
            problems.append(f"{code}: unsafe raw filename")
            continue
        path = history_root / filename
        if (
            not path.is_file()
            or sha256_file(path) != meta["sha256"]
            or path.stat().st_size != meta["bytes"]
        ):
            problems.append(f"{code}: raw file SHA256/size mismatch")
            continue
        history = _read_rows(path)
        dates = [r["date"] for r in history]
        if (
            not dates
            or len(history) != meta["row_count"]
            or min(dates) != meta["start_date"]
            or max(dates) != meta["end_date"]
            or list(history[0]) != meta["columns"]
        ):
            problems.append(f"{code}: raw row count/date range/columns mismatch")
        history_total += len(history)
    for row in rows:
        code = row["etf_code"]
        raw = history_manifest.get(code)
        if raw is None:
            if code != "159915" or row["history_filename"] or row["history_sha256"]:
                problems.append(f"{code}: unexpected missing raw history")
            if code == "159915" and "local Hikyuu only" not in row["history_source"]:
                problems.append(f"{code}: independent raw absence is not disclosed")
        elif (
            row["history_filename"] != raw["file"]
            or row["history_sha256"] != raw["sha256"]
            or row["history_start_date"] != raw["start_date"]
            or row["history_end_date"] != raw["end_date"]
            or row["history_row_count"] != str(raw["row_count"])
        ):
            problems.append(f"{code}: catalog/raw manifest link mismatch")
    if problems:
        raise EvidenceIntegrityFailure("DATA_EVIDENCE_INTEGRITY_FAILURE: " + "; ".join(problems))
    return {
        "catalog": rows,
        "sources": sources,
        "legacy": legacy,
        "reference": reference,
        "integrity": integrity,
        "raw_file_count": len(history_manifest),
        "raw_total_rows": history_total,
    }


def _evidence_diagnostics(evidence: dict, sector_codes: dict[str, str]) -> dict:
    """Report Layer-1 facts and non-executable Layer-2 candidates separately."""
    rows = evidence["catalog"]
    statuses = Counter(row["evidence_status"] for row in rows)
    partial = []
    for row in rows:
        if row["evidence_status"] != "PARTIAL_EVIDENCE":
            continue
        partial.append(
            {
                "etf_code": row["etf_code"],
                "etf_name": row["etf_name"],
                "tracking_index_code": row["tracking_index_code"] or None,
                "tracking_index_name": row["tracking_index_name"],
                "candidate_sector_code": row["sector_code"],
                "candidate_sector_name": row["sector_name"],
                "layer1_evidence": row["tracking_relationship"],
                "layer2_evidence": "NOT_PROVEN",
                "official_listing_date": row["official_listing_date"],
                "mapping_effective_from": row["mapping_effective_from"] or None,
                "final_evidence_status": row["evidence_status"],
                "missing_evidence": [
                    "official tracking-index-to-Shenwan-Level-2 equivalence",
                    "historical mapping_effective_from",
                ],
            }
        )
    candidate_sectors = {item["candidate_sector_code"] for item in partial}
    legacy = Counter(row["final_evidence_status"] for row in evidence["legacy"])
    reference = Counter(row["official_evidence_status"] for row in evidence["reference"])
    return {
        "evidence_integrity": "PASS",
        "official_document_count": evidence["integrity"]["disk_pdf_count"],
        "manifest_document_count": evidence["integrity"]["manifest_file_count"],
        "catalog_etf_count": len(rows),
        "catalog_provenance_match_count": len(rows),
        "supporting_document_count": len(evidence["sources"]),
        "raw_etf_integrity_count": evidence["raw_file_count"],
        "raw_etf_total_rows": evidence["raw_total_rows"],
        "official_identity_complete_count": sum(
            bool(r["etf_name"] and r["fund_manager"]) for r in rows
        ),
        "official_listing_complete_count": sum(bool(r["official_listing_date"]) for r in rows),
        "fund_establishment_complete_count": sum(bool(r["fund_establishment_date"]) for r in rows),
        "tracking_index_name_complete_count": sum(bool(r["tracking_index_name"]) for r in rows),
        "tracking_index_code_complete_count": sum(bool(r["tracking_index_code"]) for r in rows),
        "mapping_effective_from_complete_count_official": sum(
            bool(r["mapping_effective_from"]) for r in rows
        ),
        "mapping_effective_to_complete_count_official": sum(
            bool(r["mapping_effective_to"]) for r in rows
        ),
        "official_evidence_status_counts": {
            status: statuses[status]
            for status in (
                "VALIDATED",
                "PARTIAL_EVIDENCE",
                "NOT_DIRECT_MAPPING",
                "CONFLICT",
                "UNVERIFIED",
            )
        },
        "partial_candidate_sector_count": len(candidate_sectors),
        "partial_candidate_coverage_ratio": len(candidate_sectors) / len(sector_codes),
        "partial_candidate_notice": "CANDIDATE ONLY; NOT ADMITTED FOR BACKTEST",
        "partial_candidates": sorted(partial, key=lambda r: r["etf_code"]),
        "legacy_review_count": len(evidence["legacy"]),
        "legacy_review_status_counts": dict(sorted(legacy.items())),
        "reference_review_count": len(evidence["reference"]),
        "reference_review_status_counts": dict(sorted(reference.items())),
        "reference_review_treatment": "REFERENCE ONLY; EXCLUDED FROM FORMAL COVERAGE",
    }


def _load_proxy_evidence(
    repo_root: Path,
    evidence_dir: Path,
    official: dict,
    sector_codes: dict[str, str],
    sector_admission: str,
) -> list[ProxyAdmissionEvidence]:
    """Read the six reconciled Layer-2 rows without changing the direct mapping."""
    rows = _read_rows(evidence_dir / "six_candidate_second_layer_evidence.csv")
    sources = _read_rows(evidence_dir / "six_candidate_second_layer_sources.csv")
    directories = {
        "ann": "etf_announcements",
        "cons": "index_constituents",
        "meth": "index_methodology",
        "sw": "sw_l2_constituents",
        "sw_l2_constituents": "sw_l2_constituents",
    }
    raw_root = repo_root / "data/raw/etf_evidence"
    source_by_sha: dict[str, list[dict]] = {}
    for source in sources:
        filename, directory = source["file"], directories.get(source["dir"])
        if not directory or Path(filename).name != filename:
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: unsafe Layer-2 source {filename}"
            )
        path = raw_root / directory / filename
        if (
            not path.is_file()
            or sha256_file(path) != source["sha256"]
            or path.stat().st_size != int(source["bytes"])
        ):
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: Layer-2 SHA/size {path}"
            )
        source_by_sha.setdefault(source["sha256"], []).append(source)
    catalog_by_code = {r["etf_code"]: r for r in official["catalog"]}
    sw_snapshot = next((s for s in sources if s["key"] == "sws_l2_all"), None)
    if sw_snapshot is None:
        raise EvidenceIntegrityFailure(
            "DATA_EVIDENCE_INTEGRITY_FAILURE: missing fixed SW snapshot source"
        )
    sw_observed_at = datetime.fromisoformat(sw_snapshot["retrieved_at"]).date().isoformat()
    expected = {
        r["etf_code"] for r in official["catalog"] if r["evidence_status"] == "PARTIAL_EVIDENCE"
    }
    if len(rows) != len({r["etf_code"] for r in rows}) or {r["etf_code"] for r in rows} != expected:
        raise EvidenceIntegrityFailure(
            "DATA_EVIDENCE_INTEGRITY_FAILURE: Layer-2 candidate code set differs"
        )
    out = []
    for row in rows:
        code = row["etf_code"]
        layer1 = catalog_by_code[code]
        if row["candidate_sw_l2_code"] != layer1["sector_code"] or row[
            "candidate_sw_l2_name"
        ] != sector_codes.get(row["candidate_sw_l2_code"]):
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} sector mismatch"
            )
        if row["official_listing_date"] != layer1["official_listing_date"]:
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} listing source mismatch"
            )
        method = next(
            (s for s in source_by_sha.get(row["methodology_sha256"], []) if s["dir"] == "meth"),
            None,
        )
        composition = next(
            (s for s in source_by_sha.get(row["constituents_sha256"], []) if s["dir"] == "cons"),
            None,
        )
        if row["methodology_sha256"] and (method is None or method["dir"] != "meth"):
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} methodology source"
            )
        if row["constituents_sha256"] and (composition is None or composition["dir"] != "cons"):
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} composition source"
            )
        if composition is None:
            source_type = "NO_CONSTITUENT_EVIDENCE"
            coverage_type = "NONE"
        elif "申购赎回清单" in composition["role"]:
            source_type = "ETF_REPLICATION_BASKET_PROXY"
            coverage_type = "PCF_BASKET_NOT_FULL_INDEX"
        elif "前十大" in composition["role"]:
            source_type = "TOP10_ONLY_PROXY"
            coverage_type = "TOP10_NOT_FULL_INDEX"
        else:
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} unknown composition type"
            )
        as_of = row["constituents_as_of_date"] or None
        if as_of:
            date.fromisoformat(as_of)
        retrieved = (
            datetime.fromisoformat(composition["retrieved_at"]).date().isoformat()
            if composition
            else None
        )
        if as_of and retrieved and as_of > retrieved:
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} future-dated source"
            )
        documented = row["earliest_tracking_document_date"] or None
        if documented:
            date.fromisoformat(documented)
        total = int(row["constituent_count"])
        classified = int(row["classified_count"])
        candidate = int(row["candidate_l2_count"])
        other = int(row["other_l2_count"])
        unclassified = int(row["unclassified_count"])
        if classified + unclassified != total or candidate + other != classified:
            raise EvidenceIntegrityFailure(
                f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} constituent counts"
            )
        if (
            row["candidate_l2_count_share"]
            and abs(float(row["candidate_l2_count_share"]) - 100 * candidate / total) > 0.02
        ):
            raise EvidenceIntegrityFailure(f"DATA_EVIDENCE_INTEGRITY_FAILURE: {code} count share")
        out.append(
            ProxyAdmissionEvidence(
                etf_code=code,
                sector_code=row["candidate_sw_l2_code"],
                official_direct_equivalence=row["official_direct_sw_equivalence"].lower() == "true",
                methodology_official=bool(method and method["provider"] == "csindex.com.cn"),
                composition_source_type=source_type,
                composition_coverage_type=coverage_type,
                composition_source_official=bool(
                    composition and composition["provider"] in {"sse.com.cn", "csindex.com.cn"}
                ),
                composition_as_of_date=as_of,
                composition_available_at=retrieved,
                constituent_count=total,
                classified_count=classified,
                count_share=float(row["candidate_l2_count_share"])
                if row["candidate_l2_count_share"]
                else None,
                weight_share=float(row["candidate_l2_weight_share"])
                if row["candidate_l2_weight_share"]
                else None,
                other_l2_count=other,
                other_l2_summary=row["other_l2_summary"] or None,
                unclassified_count=unclassified,
                relationship_documented_from=documented,
                official_listing_date=row["official_listing_date"] or None,
                tradable_start_candidate=row["tradable_mapping_start_candidate"] or None,
                relationship_continuity_status=row["historical_relationship_status"],
                index_change_event_found=row["index_change_event_found"].lower() == "true",
                index_change_search_note=row["index_change_search_note"] or None,
                sw_classification_status=sector_admission,
                sw_classification_available_at=sw_observed_at,
            )
        )
    return out


def _proxy_diagnostics(
    evidence: list[ProxyAdmissionEvidence],
    candidate_dates: list[str],
) -> dict:
    details = []
    for item in evidence:
        status = current_proxy_status(item)
        observed = item.composition_as_of_date
        if item.composition_valid_from and item.composition_valid_to:
            historical_dates = [
                day
                for day in candidate_dates
                if item.composition_valid_from <= day <= item.composition_valid_to
            ]
        else:
            historical_dates = [day for day in candidate_dates if day == observed]
        available_dates = [
            day
            for day in historical_dates
            if item.composition_available_at
            and item.composition_available_at <= day
            and (item.composition_available_at < day or item.available_before_signal)
        ]
        historical_admissible = any(
            historical_proxy_admissible(item, day) for day in available_dates
        )
        reasons = []
        if item.composition_source_type == "NO_CONSTITUENT_EVIDENCE":
            reasons.append("no official constituent snapshot")
        elif item.composition_source_type == "ETF_REPLICATION_BASKET_PROXY":
            reasons.append("PCF basket is not full index constituents or index weights")
        elif item.composition_source_type == "TOP10_ONLY_PROXY":
            reasons.append("Top10 does not establish full index composition")
        if item.weight_share is None:
            reasons.append("candidate full-index weight share unavailable")
        if item.unclassified_count:
            reasons.append("observed constituents include unclassified names")
        if observed is None or observed > max(candidate_dates):
            reasons.append("composition snapshot is later than the research interval")
        if item.relationship_continuity_status != "PROVEN_CONTINUOUS":
            reasons.append("relationship documented, continuity not proven")
        if not item.methodology_historical_version_confirmed:
            reasons.append("historical methodology version/effective interval not proven")
        if item.relationship_effective_from is None:
            reasons.append("historical relationship effective-from unproven")
        if item.sw_classification_status != "HISTORICAL_PIT":
            reasons.append("Shenwan classification is fixed/current, not historical PIT")
        if status == "PROXY_CURRENT_MIXED":
            reasons.append("observed basket spans material other Level-2 sectors")
        if status == "PROXY_CURRENT_STRONG":
            priority = "HISTORICAL_EVIDENCE_ACQUISITION"
            needed = [
                "official full historical index constituents with weights and publication/effective interval",
                "affirmative ETF-index relationship continuity and effective start",
                "historically available Shenwan Level-2 constituent classification",
            ]
        elif status == "PROXY_CURRENT_MIXED":
            priority = "EXCLUDE_SINGLE_SECTOR_PROXY"
            needed = [
                "new full-index evidence would have to reverse the observed multi-sector breadth"
            ]
        else:
            priority = "DEFER_CURRENT_AND_HISTORICAL_RESEARCH"
            needed = [
                "official methodology and full current constituents with weights first",
                "historical temporal and classification evidence only if current proxy is viable",
            ]
        details.append(
            {
                **asdict(item),
                "current_status": status,
                "temporal_status": "PROXY_HISTORICALLY_SUPPORTED"
                if historical_admissible
                else "PROXY_HISTORICALLY_INSUFFICIENT",
                "historical_composition_evidence_available": bool(available_dates),
                "earliest_historical_proxy_evidence_date": min(available_dates)
                if available_dates
                else None,
                "latest_historical_proxy_evidence_date": max(available_dates)
                if available_dates
                else None,
                "proxy_currently_admissible": bool(
                    observed
                    and historical_proxy_admissible(item, observed, require_historical_sw=False)
                ),
                "proxy_historical_backtest_admissible": historical_admissible,
                "evidence_acquisition_priority": priority,
                "reason": reasons,
                "remaining_evidence_needed": needed,
            }
        )
    counts = Counter(d["current_status"] for d in details)
    historical_count = sum(d["proxy_historical_backtest_admissible"] for d in details)
    return {
        "proxy_mapping_admission": (
            "PROXY_MAPPING_HISTORICALLY_SUPPORTED"
            if historical_count
            else "PROXY_MAPPING_CURRENT_ONLY"
            if counts["PROXY_CURRENT_STRONG"]
            else "PROXY_MAPPING_NOT_ADMISSIBLE"
        ),
        "proxy_current_strong_count": counts["PROXY_CURRENT_STRONG"],
        "proxy_current_mixed_count": counts["PROXY_CURRENT_MIXED"],
        "proxy_current_insufficient_count": counts["PROXY_CURRENT_INSUFFICIENT"],
        "proxy_currently_admissible_count": sum(d["proxy_currently_admissible"] for d in details),
        "proxy_historical_admissible_count": historical_count,
        "proxy_current_only_count": sum(
            d["current_status"] == "PROXY_CURRENT_STRONG"
            and not d["proxy_historical_backtest_admissible"]
            for d in details
        ),
        "proxy_candidate_diagnostic_count": len(details),
        "proxy_formal_executable_count": 0,  # proxy execution resolver is intentionally not enabled
        "proxy_formal_execution_notice": "TEMPORAL ADMISSION IS NOT EXECUTION INTEGRATION",
        "proxy_candidate_notice": "CURRENT EVIDENCE ONLY; NOT ADMITTED FOR HISTORICAL BACKTEST",
        "proxy_evaluations": sorted(details, key=lambda d: d["etf_code"]),
    }


def _mapping_rows(path: Path | None, catalog: pd.DataFrame) -> list[MappingEvidence]:
    if path is None:
        # Explicitly unknown; the legacy example is not tracking evidence.
        return [
            MappingEvidence(
                str(r.sector_code),
                str(r.sector_name),
                notes="No locally verified ETF tracking/effective-date evidence",
            )
            for r in catalog.itertuples()
        ]
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {f.name for f in fields(MappingEvidence)}
    if not required.issubset(frame.columns):
        raise ValueError(f"mapping evidence schema missing: {sorted(required - set(frame))}")
    out = []
    for item in frame.to_dict("records"):
        values = {key: (item[key] or None) for key in required}
        values["is_primary"] = item["is_primary"].strip().lower() == "true"
        if item["is_primary"].strip().lower() not in {"true", "false"}:
            raise ValueError("is_primary must be true or false")
        row = MappingEvidence(**values)
        if row.source_file:
            source = Path(row.source_file)
            if not source.is_file() or sha256_file(source) != row.source_sha256:
                raise ValueError(f"mapping source_file SHA256 mismatch: {source}")
        out.append(row)
    return out


def build(
    *,
    sector_dir: Path,
    hikyuu_dir: Path,
    output_dir: Path,
    mapping_file: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict:
    sector_meta = json.loads((sector_dir / "sector_admission.json").read_text(encoding="utf-8"))
    if (
        sector_meta.get("admission_level") != "FIXED_CLASSIFICATION_RESEARCH"
        or sector_meta.get("strict_pit") is not False
    ):
        raise ValueError("sector admission changed; do not silently upgrade PIT semantics")
    catalog = load_sector_catalog(sector_dir)
    codes = {str(r.sector_code): str(r.sector_name) for r in catalog.itertuples()}
    evidence = _load_official_evidence(
        _ROOT,
        evidence_dir or _ROOT / "data/processed/shenwan_etf_mapping",
        codes,
    )
    diagnostics = _evidence_diagnostics(evidence, codes)
    rows = _mapping_rows(mapping_file, catalog)
    validate_mapping_evidence(rows, codes)
    etfs, bars = read_local_etf_snapshot(hikyuu_dir)
    etf_meta = {r.etf_code: r for r in etfs.itertuples()}
    bar_lookup = {
        (r.etf_code, r.date): {
            "etf_code": r.etf_code,
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
        }
        for r in bars.itertuples()
    }

    common_start, common_end = sector_meta["common_start_date"], sector_meta["common_end_date"]
    panel = load_sector_panel(list(codes), common_start, common_end, processed_dir=sector_dir)
    sector_start, sector_end = candidate_research_range(panel, sector_meta)
    if (sector_start, sector_end) != (
        sector_meta["research_eligible_start"],
        sector_meta["research_eligible_end"],
    ):
        raise ValueError("sector candidate range differs from verified canonical metadata")
    all_dates = sorted(panel["date"].dt.strftime("%Y-%m-%d").unique().tolist())
    next_session = {day: all_dates[i + 1] for i, day in enumerate(all_dates[:-1])}
    candidate_dates = [day for day in all_dates if sector_start <= day <= sector_end]
    proxy_evidence = _load_proxy_evidence(
        _ROOT,
        evidence_dir or _ROOT / "data/processed/shenwan_etf_mapping",
        evidence,
        codes,
        sector_meta["admission_level"],
    )
    proxy_report = _proxy_diagnostics(proxy_evidence, candidate_dates)
    audit_dates = sorted(set(candidate_dates) | {common_end})
    sector_valid = {
        (str(r.sector_code), r.date.strftime("%Y-%m-%d")): bool(r.is_valid_ohlc)
        for r in panel.itertuples()
    }
    daily = []
    for day in audit_dates:
        execution_date = next_session.get(day)
        for code in codes:
            mapping = resolve_primary_mapping(rows, code, day)
            etf_code = mapping.etf_code if mapping else None
            bar = (
                bar_lookup.get((etf_code, execution_date)) if etf_code and execution_date else None
            )
            availability = daily_mapping_availability(
                rows,
                code,
                day,
                execution_date=execution_date,
                bar=bar,
                sector_bar_valid=sector_valid.get((code, day), False),
            )
            availability["etf_code"] = etf_code
            availability["local_etf_metadata_present"] = bool(etf_code in etf_meta)
            daily.append(availability)
    daily_frame = pd.DataFrame(daily)
    candidate = daily_frame.loc[daily_frame["date"].isin(candidate_dates)]
    coverage = (
        candidate.groupby("date")
        .agg(
            mapped_sector_count=("is_mapping_active", "sum"),
            available_sector_count=("is_etf_executable", "sum"),
            executable_sector_count=("is_executable", "sum"),
            sector_factor_count=("sector_bar_valid", "sum"),
        )
        .reset_index()
    )
    for col in ("mapped", "available", "executable"):
        coverage[f"{col}_ratio"] = coverage[f"{col}_sector_count"] / len(codes)
    counts = coverage["executable_sector_count"].astype(int).tolist()
    level = mapping_admission(rows, codes, counts)
    mapped_codes = sorted(
        {r.sector_code for r in rows if r.mapping_status == "VALIDATED" and r.is_primary}
    )
    etf_codes = [r.etf_code for r in rows if r.sector_code in mapped_codes and r.is_primary]
    duplicates = sorted({code for code in etf_codes if etf_codes.count(code) > 1})
    complete_dates = [day for day, count in zip(coverage["date"], counts) if count >= 5]
    report = {
        "status": level,
        "mapping_admission": level,
        **diagnostics,
        **proxy_report,
        "sector_data_admission": sector_meta["admission_level"],
        "strict_pit": False,
        "pit_notice": "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
        "sector_data_snapshot_id": sector_meta["data_snapshot_id"],
        "level2_sector_count": len(codes),
        "mapped_sector_count": len(mapped_codes),
        "unmapped_sector_count": len(codes) - len(mapped_codes),
        "unmapped_sectors": [
            {"sector_code": code, "sector_name": name}
            for code, name in codes.items()
            if code not in mapped_codes
        ],
        "mapping_coverage_ratio": len(mapped_codes) / len(codes),
        "strict_validated_coverage_ratio": len(mapped_codes) / len(codes),
        "validated_primary_etf_count": len(etf_codes),
        "formal_executable_universe_count": int(
            daily_frame.loc[daily_frame["date"].eq(common_end), "is_executable"].sum()
        )
        + proxy_report["proxy_formal_executable_count"],
        "unique_etf_count": len(set(etf_codes)),
        "duplicate_etfs_across_sectors": duplicates,
        "multiple_candidate_sectors": sorted(
            {r.sector_code for r in rows if r.mapping_status == "MULTIPLE_CANDIDATES"}
        ),
        "listing_date_complete_count": sum(bool(r.etf_listing_date) for r in rows if r.is_primary),
        "mapping_effective_from_complete_count": sum(
            bool(r.mapping_effective_from) for r in rows if r.is_primary
        ),
        "mapping_provenance_complete_count": sum(
            bool(r.source_provider and r.source_retrieved_at and (r.source_url or r.source_file))
            for r in rows
            if r.is_primary
        ),
        "local_etf_count": len(etfs),
        "local_listing_date_known_count": int(etfs["listing_date"].notna().sum()),
        "etf_159915": {
            "official_listing_date": next(
                r["official_listing_date"] for r in evidence["catalog"] if r["etf_code"] == "159915"
            ),
            "local_market_data_available": bool(etf_meta.get("sz159915")),
            "local_hikyuu_bar_count": int(etf_meta["sz159915"].bar_count),
            "independent_raw_refresh": False,
            "listing_source": "official evidence; not Hikyuu first bar",
        },
        "latest_common_date": common_end,
        "latest_executable_sector_count": int(
            daily_frame.loc[daily_frame["date"].eq(common_end), "is_executable"].sum()
        ),
        "candidate_session_count": len(counts),
        "historical_executable_min": min(counts) if counts else None,
        "historical_executable_median": statistics.median(counts) if counts else None,
        "historical_executable_mean": statistics.mean(counts) if counts else None,
        "historical_executable_max": max(counts) if counts else None,
        "historical_executable_coverage_ratio_min": min(counts) / len(codes) if counts else None,
        "historical_executable_coverage_ratio_median": statistics.median(counts) / len(codes)
        if counts
        else None,
        "historical_executable_coverage_ratio_mean": statistics.mean(counts) / len(codes)
        if counts
        else None,
        "historical_executable_coverage_ratio_max": max(counts) / len(codes) if counts else None,
        "days_with_executable_ge_5": sum(c >= 5 for c in counts),
        "days_with_executable_lt_5": sum(c < 5 for c in counts),
        "sector_only_eligible_start": sector_start,
        "sector_only_eligible_end": sector_end,
        "sector_plus_etf_candidate_start": min(complete_dates) if complete_dates else None,
        "sector_plus_etf_candidate_end": max(complete_dates) if complete_dates else None,
        "sector_801193_missing_candidate_sessions": len(candidate_dates)
        - sum(sector_valid.get(("801193", day), False) for day in candidate_dates),
        "sector_801193_missing_common_sessions": len(all_dates)
        - sum(sector_valid.get(("801193", day), False) for day in all_dates),
        "candidate_range_note": (
            "Existing sector-only rule reserves 120 prior sessions for features, "
            "six calendar months for training with a 120-session label/purge boundary, "
            "and 120 future sessions for labels. Next-session execution has not been "
            "separately proven or added to this date calculation."
        ),
        "limitations": [
            "Legacy example is unverified and excluded from canonical mapping.",
            "Hikyuu stock.startDate / first local bar do not prove official ETF listing.",
            "Official Layer-1 ETF-to-tracking-index evidence exists, but no official Layer-2 direct equivalence is proven.",
            "Current tracking relationships do not establish historical mapping_effective_from.",
            "Daily bar presence and OHLC do not prove absence of suspension/limit restrictions.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(r) for r in rows]).to_csv(
        output_dir / "etf_mapping_evidence.csv", index=False
    )
    etfs.to_csv(output_dir / "etf_local_metadata.csv", index=False)
    daily_frame.to_csv(output_dir / "etf_daily_availability.csv", index=False)
    coverage.to_csv(output_dir / "etf_daily_coverage.csv", index=False)
    (output_dir / "etf_mapping_admission.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--hikyuu-dir", type=Path, default=Path("data/hikyuu"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/shenwan_etf_mapping")
    )
    parser.add_argument("--mapping-file", type=Path, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                sector_dir=args.sector_dir,
                hikyuu_dir=args.hikyuu_dir,
                output_dir=args.output_dir,
                mapping_file=args.mapping_file,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

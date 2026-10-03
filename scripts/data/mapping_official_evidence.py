"""Offline ETF mapping/tradability audit.  Never imports or downloads quotes."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- CLI checkout bootstrap.
    EvidenceIntegrityFailure as EvidenceIntegrityFailure,
)
from scripts.data.verify_etf_evidence import verify_etf_evidence  # noqa: E402
from src.data.providers.shenwan_official import sha256_file  # noqa: E402


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

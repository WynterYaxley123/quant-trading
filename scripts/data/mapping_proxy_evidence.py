"""Offline ETF mapping/tradability audit.  Never imports or downloads quotes."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from scripts.data.mapping_official_evidence import (  # noqa: E402 -- CLI checkout bootstrap.
    _read_rows as _read_rows,
)
from scripts.data.mapping_proxy_contract import (  # noqa: E402 -- CLI checkout bootstrap.
    EvidenceIntegrityFailure as EvidenceIntegrityFailure,
)
from scripts.data.mapping_proxy_contract import (
    ProxyAdmissionEvidence as ProxyAdmissionEvidence,
)
from scripts.data.mapping_proxy_contract import (
    current_proxy_status as current_proxy_status,
)
from scripts.data.mapping_proxy_contract import (
    historical_proxy_admissible as historical_proxy_admissible,
)
from src.data.providers.shenwan_official import sha256_file  # noqa: E402


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

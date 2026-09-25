"""Offline, point-in-time audit of four historical ETF proxy candidates.

The periodic reports are ETF index-investment sleeves observed on three dates,
not archived full-index constituent intervals. No quote loading or network I/O.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.data.admit_shenwan_etf_mapping import (
    EvidenceIntegrityFailure, ProxyAdmissionEvidence, historical_proxy_admissible,
)

EVIDENCE_DIR = Path("data/processed/shenwan_etf_mapping")
RAW_DIR = Path("data/raw/etf_evidence")
PUBLICATIONS = Path("docs/data/shenwan_historical_proxy_publications.csv")
RESEARCH_START = "2025-04-02"
RESEARCH_END = "2026-03-27"
ETF_CODES = ("512480", "512880", "159852", "159883")
DIR_ALIASES = {
    "ann": "etf_announcements", "cons": "index_constituents",
    "meth": "index_methodology", "sw": "sw_l2_constituents",
}


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise EvidenceIntegrityFailure(f"DATA_EVIDENCE_INTEGRITY_FAILURE: missing {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fail(message: str) -> None:
    raise EvidenceIntegrityFailure("DATA_EVIDENCE_INTEGRITY_FAILURE: " + message)


def _iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(f"invalid date: {value}")
        raise AssertionError("unreachable")


def _wall_time(value: str) -> datetime:
    """Compare recorded local wall clocks without inventing a timezone."""
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs(root: Path) -> tuple[list[dict], list[dict], list[dict], list[str], list[dict], list[dict], int]:
    """Verify bytes/provenance before any temporal or admission calculation."""
    raw = root / RAW_DIR
    manifest = json.loads((raw / "index_evidence_manifest.json").read_text(encoding="utf-8"))
    by_file: dict[str, dict] = {}
    for key, item in manifest.items():
        directory = DIR_ALIASES.get(item["dir"], item["dir"])
        filename = item["file"]
        if Path(directory).name != directory or Path(filename).name != filename:
            _fail(f"unsafe manifest path: {key}")
        path = raw / directory / filename
        if not path.is_file() or path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
            _fail(f"missing/size/SHA mismatch: {key} / {path}")
        if not item.get("source_url") or not item.get("retrieved_at"):
            _fail(f"missing provenance: {key}")
        if filename in by_file:
            _fail(f"duplicate manifest filename: {filename}")
        by_file[filename] = item

    evidence = _rows(root / EVIDENCE_DIR / "four_proxy_historical_evidence.csv")
    coverage = _rows(root / EVIDENCE_DIR / "four_proxy_temporal_coverage.csv")
    sources = _rows(root / EVIDENCE_DIR / "four_proxy_historical_sources.csv")
    publications = _rows(root / PUBLICATIONS)
    calendar = _rows(root / EVIDENCE_DIR / "historical_evidence_calendar.csv")
    sessions = [row["date"] for row in _rows(root / EVIDENCE_DIR / "etf_daily_coverage.csv")]
    if len(evidence) != 12 or len(publications) != 12 or len(coverage) != 12:
        _fail("expected exactly twelve evidence, publication and interval rows")
    if len({(r["etf_code"], r["composition_source_date"]) for r in evidence}) != 12:
        _fail("duplicate historical snapshot")
    if len({r["source_document"] for r in publications}) != 12:
        _fail("duplicate publication record")
    if sorted(sessions) != sessions or len(set(sessions)) != len(sessions):
        _fail("trading calendar dates are unsorted or duplicated")
    if not sessions or sessions[0] != RESEARCH_START or sessions[-1] != RESEARCH_END:
        _fail("project trading calendar does not match candidate range")

    for item in sources:
        source = by_file.get(item["file"])
        if (source is None or source["sha256"] != item["sha256"]
                or source["bytes"] != int(item["bytes"])
                or source["source_url"] != item["source_url"]
                or _wall_time(source["retrieved_at"]) != _wall_time(item["retrieved_at"])):
            _fail(f"source/manifest provenance mismatch: {item['file']}")
    source_by_file = {item["file"]: item for item in sources}
    publication_by_file = {item["source_document"]: item for item in publications}
    if set(publication_by_file) != {r["source_document"] for r in evidence}:
        _fail("publication table does not match the twelve source reports")
    for item in evidence:
        code, filename = item["etf_code"], item["source_document"]
        source = source_by_file.get(filename)
        pub = publication_by_file[filename]
        if (source is None or source["etf_code"] != code
                or source["source_url"] != item["source_url"]
                or source["sha256"] != item["source_sha256"]
                or pub["etf_code"] != code
                or pub["snapshot_as_of_date"] != item["composition_source_date"]
                or pub["report_period_end"] != pub["snapshot_as_of_date"]
                or pub["publication_basis"] != "PDF_COVER_SENT_DATE_AND_OFFICIAL_URL_DATE"):
            _fail(f"historical source/publication mismatch: {filename}")
        asof, released = _iso(pub["snapshot_as_of_date"]), _iso(pub["official_publication_date"])
        url_date = re.search(r"/(20\d\d-\d\d-\d\d)/", source["source_url"])
        if (released <= asof or url_date is None or url_date.group(1) != released.isoformat()
                or released > _wall_time(source["retrieved_at"]).date()):
            _fail(f"unreconciled publication date: {filename}")
        if (item["classification_basis"] != "FIXED_CLASSIFICATION_COMPARISON"
                or item["strict_pit"].lower() != "false"):
            _fail(f"classification semantics changed: {filename}")
        if int(item["classified_count"]) + int(item["unclassified_count"]) != int(item["constituent_count"]):
            _fail(f"constituent counts do not reconcile: {filename}")
        if int(item["candidate_l2_count"]) + int(item["other_l2_count"]) != int(item["classified_count"]):
            _fail(f"sector counts do not reconcile: {filename}")
    if len(calendar) != 24 or len(sources) != 19:
        _fail("calendar/source inventory changed")
    coverage_by_key = {(r["etf_code"], r["snapshot_as_of"]): r for r in coverage}
    if len(coverage_by_key) != 12:
        _fail("duplicate temporal-coverage key")
    for item in evidence:
        key = (item["etf_code"], item["composition_source_date"])
        interval = coverage_by_key.get(key)
        start = max(_iso(item["composition_effective_from"]), _iso(RESEARCH_START))
        end = min(_iso(item["composition_effective_to"]), _iso(RESEARCH_END))
        if (interval is None or interval["evidence_interval_start"] != start.isoformat()
                or interval["evidence_interval_end"] != end.isoformat()
                or int(interval["coverage_days"]) != (end - start).days
                or interval["snapshot_source"] != item["source_document"].removesuffix(".pdf")
                or interval["coverage_complete"].lower() != "true"):
            _fail(f"Hermes temporal-coverage row inconsistent: {key}")
    return evidence, coverage, publications, sessions, calendar, sources, len(manifest)


def numeric_purity(row: dict[str, str]) -> bool:
    """Pre-backtest 90/90 screen; still not a formal full-index/PIT admission."""
    total = int(row["constituent_count"])
    return (total > 0 and 100 * int(row["candidate_l2_count"]) / total >= 90
            and float(row["candidate_l2_weight_share"]) >= 90
            and int(row["unclassified_count"]) == 0
            and 100 * int(row["other_l2_count"]) / total <= 10)


def point_status(t: str, snapshot: str, publication: str) -> str:
    """A dated periodic-report sleeve proves at most its observation date."""
    if snapshot > t:
        return "FUTURE_EVIDENCE"
    if snapshot == t:
        return ("EX_ANTE_AVAILABLE_EVIDENCE_POINT_ONLY" if publication < t
                else "EX_POST_INTERVAL_VALIDATION_POINT_ONLY")
    return ("PAST_SNAPSHOT_AVAILABLE_NO_INTERVAL_PROOF" if publication < t
            else "PAST_SNAPSHOT_NOT_YET_AVAILABLE")


def _regular_announcements(calendar: list[dict], root: Path) -> list[dict]:
    pairs = {(r["announcement_date"], r["effective_date"]) for r in calendar
             if r["review_event_type"] == "定期调整"}
    expected = {
        ("2024-11-29", "2024-12-13"), ("2025-05-30", "2025-06-13"),
        ("2025-11-28", "2025-12-12"), ("2026-05-29", "2026-06-12"),
    }
    if pairs != expected:
        _fail("regular announcement/effective-date pairs changed")
    details_path = root / RAW_DIR / "index_rebalance_announcements" / "csindex_rebalance_announcement_details.json"
    details = json.loads(details_path.read_text(encoding="utf-8"))
    official_pairs = {(v["publishDate"], effective)
                      for v in details.values() for effective in v.get("effective_dates_found", [])}
    if not pairs.issubset(official_pairs):
        _fail("calendar dates are not corroborated by official announcement metadata")
    return [{"announcement_date": announced, "effective_at_close": effective,
             "first_affected_session": next((r["period_start"] for r in calendar
                                             if r["announcement_date"] == announced
                                             and r["period_start"]), None),
             "index_specific_full_constituents_proven": False}
            for announced, effective in sorted(pairs)]


def audit(root: Path = ROOT) -> tuple[dict, list[dict], list[dict]]:
    evidence, coverage, publications, sessions, calendar, sources, manifest_count = verify_inputs(root)
    publications_by_file = {r["source_document"]: r for r in publications}
    sources_by_file = {r["file"]: r for r in sources}
    report_rows = []
    for item in evidence:
        pub = publications_by_file[item["source_document"]]
        report_rows.append({**item, **pub,
                            "numeric_purity_pass": numeric_purity(item),
                            "evidence_available_at": pub["official_publication_date"],
                            "source_retrieved_at": sources_by_file[item["source_document"]]["retrieved_at"],
                            "source_sidecar_as_of_date": sources_by_file[item["source_document"]]["as_of_date"]})
    by_code = defaultdict(list)
    for item in report_rows:
        by_code[item["etf_code"]].append(item)
    for rows in by_code.values():
        rows.sort(key=lambda r: r["snapshot_as_of_date"])
    if set(by_code) != set(ETF_CODES) or any(len(rows) != 3 for rows in by_code.values()):
        _fail("expected three snapshots for each of four ETFs")

    session_rows = []
    for code in ETF_CODES:
        rows = by_code[code]
        for t in sessions:
            past = [r for r in rows if r["snapshot_as_of_date"] <= t]
            latest = past[-1] if past else rows[0]
            nominal = next((r for r in rows
                            if r["composition_effective_from"] <= t
                            < r["composition_effective_to"]), None)
            if nominal is None:
                _fail(f"no Hermes interval row for {code} on {t}")
            exact = latest["snapshot_as_of_date"] == t
            published_before_signal = latest["evidence_available_at"] < t
            relationship_document_known = any(
                r["snapshot_as_of_date"] <= t and r["evidence_available_at"] < t
                for r in rows
            )
            # The recorded continuity is retrospective, not proven by a
            # versioned relationship document valid and available through t.
            proven_at = latest.get("relationship_continuity_proven_at") or ""
            proven_through = latest.get("relationship_continuity_valid_through") or ""
            continuity_known = (
                latest["relationship_continuity_status"] == "PROVEN_CONTINUOUS"
                and bool(proven_at and proven_through)
                and proven_at < t <= proven_through
            )
            candidate = ProxyAdmissionEvidence(
                etf_code=code, sector_code=latest["candidate_sw_l2_code"],
                composition_source_type=latest["composition_source_type"],
                composition_source_official=True,
                composition_as_of_date=latest["snapshot_as_of_date"],
                composition_available_at=latest["evidence_available_at"],
                constituent_count=int(latest["constituent_count"]),
                count_share=100 * int(latest["candidate_l2_count"]) / int(latest["constituent_count"]),
                weight_share=float(latest["candidate_l2_weight_share"]),
                other_l2_count=int(latest["other_l2_count"]),
                unclassified_count=int(latest["unclassified_count"]),
                relationship_continuity_status=latest["relationship_continuity_status"],
                sw_classification_status="FIXED_CLASSIFICATION_RESEARCH",
            )
            admitted = historical_proxy_admissible(candidate, t)
            session_rows.append({
                "etf_code": code, "date": t,
                "tracking_index_code": latest["tracking_index_code"],
                "nominal_interval_snapshot_as_of_date": nominal["snapshot_as_of_date"],
                "nominal_interval_source": nominal["source_document"],
                "snapshot_as_of_date": nominal["snapshot_as_of_date"],
                "official_publication_date": nominal["official_publication_date"],
                "evidence_available_at": nominal["evidence_available_at"],
                "evidence_status_at_t": point_status(
                    t, nominal["snapshot_as_of_date"], nominal["evidence_available_at"]),
                "has_past_snapshot_as_of_t": bool(past),
                "prior_snapshot_available_at_t": any(
                    r["snapshot_as_of_date"] <= t and r["evidence_available_at"] < t
                    for r in rows),
                "ex_ante_point_coverage": exact and published_before_signal,
                "ex_post_point_diagnostic": exact and not published_before_signal,
                "relationship_document_known_at_t": relationship_document_known,
                "relationship_continuity_known_at_t": continuity_known,
                "classification_basis": latest["classification_basis"],
                "numeric_purity_pass_at_latest_snapshot": numeric_purity(latest),
                "proxy_admissible_at_t": admitted,
            })

    claimed = sum(int(r["coverage_days"]) for r in coverage)
    calendar_days = (_iso(RESEARCH_END) - _iso(RESEARCH_START)).days + 1
    if claimed != 1436 or len(sessions) != 239:
        _fail("published 1436-day claim or project session denominator changed")
    per_etf = {}
    for code in ETF_CODES:
        sr = [r for r in session_rows if r["etf_code"] == code]
        er = by_code[code]
        per_etf[code] = {
            "ex_ante_point_sessions": sum(r["ex_ante_point_coverage"] for r in sr),
            "ex_post_diagnostic_point_sessions": sum(r["ex_post_point_diagnostic"] for r in sr),
            "prior_snapshot_available_sessions_not_interval_proof": sum(
                r["prior_snapshot_available_at_t"] for r in sr),
            "strict_proxy_admissible_sessions": sum(r["proxy_admissible_at_t"] for r in sr),
            "earliest_ex_ante_proxy_admissible_date": next(
                (r["date"] for r in sr if r["proxy_admissible_at_t"]), None),
            "relationship_document_known_sessions": sum(r["relationship_document_known_at_t"] for r in sr),
            "relationship_continuity_known_sessions": sum(r["relationship_continuity_known_at_t"] for r in sr),
            "numeric_purity_pass_snapshots": sum(numeric_purity(r) for r in er),
            "fixed_proxy_diagnostic_points_with_numeric_purity": [
                r["date"] for r in sr if r["ex_post_point_diagnostic"]
                and r["numeric_purity_pass_at_latest_snapshot"]],
            "can_use_on_2025_04_02": next(
                r["proxy_admissible_at_t"] for r in sr if r["date"] == RESEARCH_START),
            "classification_basis": "FIXED_CLASSIFICATION_COMPARISON",
        }
    direct = json.loads((root / EVIDENCE_DIR / "etf_mapping_admission.json").read_text(encoding="utf-8"))
    summary = {
        "status": "PROXY MAPPING NOT ADMISSIBLE",
        "direct_mapping_result": direct["mapping_admission"],
        "strict_pit": False,
        "pit_notice": "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
        "ex_ante_proxy_mapping_result": "NOT_ADMISSIBLE",
        "fixed_proxy_research_result": "NOT_ADMITTED_FOR_INTERVAL; SNAPSHOT_DIAGNOSTICS_ONLY",
        "formal_executable_universe_count": direct["formal_executable_universe_count"],
        "research_start": RESEARCH_START, "research_end": RESEARCH_END,
        "calendar_days_inclusive": calendar_days,
        "entity_calendar_days_inclusive": calendar_days * len(ETF_CODES),
        "hermes_reported_coverage_days": claimed,
        "hermes_denominator_semantics": "4 ETF x 359 half-open calendar days; not trading sessions or point-in-time coverage; final research date omitted",
        "trading_session_count": len(sessions),
        "etf_session_denominator": len(sessions) * len(ETF_CODES),
        "ex_ante_point_coverage_entity_sessions": sum(r["ex_ante_point_coverage"] for r in session_rows),
        "ex_post_diagnostic_point_entity_sessions": sum(r["ex_post_point_diagnostic"] for r in session_rows),
        "ex_ante_strict_admissible_entity_sessions": sum(r["proxy_admissible_at_t"] for r in session_rows),
        "proxy_ex_ante_candidate_start": None, "proxy_ex_ante_candidate_end": None,
        "fixed_proxy_research_start": None, "fixed_proxy_research_end": None,
        "announcement_events": _regular_announcements(calendar, root),
        "publication_date_complete_count": len(publications),
        "manifest_verified_file_count": manifest_count,
        "source_sidecar_as_of_missing_count": sum(not r["source_sidecar_as_of_date"] for r in report_rows),
        "source_sidecar_as_of_mislabeled_count": sum(
            bool(r["source_sidecar_as_of_date"])
            and r["source_sidecar_as_of_date"] != r["snapshot_as_of_date"]
            for r in report_rows),
        "snapshot_as_of_dates": sorted({r["snapshot_as_of_date"] for r in report_rows}),
        "per_etf": per_etf,
        "limitations": [
            "Periodic-report index-investment sleeves are point observations, not archived full-index constituents with weights or verified interval holdings.",
            "PDF cover sent dates and matching official URL dates establish day-level publication, not intraday availability before a same-day signal.",
            "Retrospective interval documents do not establish ETF-index relationship continuity known at each historical decision.",
            "The comparison uses fixed current Shenwan classification; historical PIT is unavailable.",
            "Generic CSI adjustment notices/partial attachments disclose future adjustment dates, not full constituents for these four indices.",
            "ETF daily bars/tradability are not promoted to formal execution when the proxy evidence gate fails.",
        ],
    }
    publication_rows = [{
        "etf_code": r["etf_code"], "source_document": r["source_document"],
        "report_period_end": r["report_period_end"],
        "snapshot_as_of_date": r["snapshot_as_of_date"],
        "official_publication_date": r["official_publication_date"],
        "evidence_available_at": r["evidence_available_at"],
        "source_retrieved_at": r["source_retrieved_at"],
        "source_sidecar_as_of_date": r["source_sidecar_as_of_date"] or None,
        "source_url": r["source_url"], "source_sha256": r["source_sha256"],
        "numeric_purity_pass": r["numeric_purity_pass"],
        "candidate_count_share_of_total": round(100 * int(r["candidate_l2_count"]) / int(r["constituent_count"]), 4),
        "candidate_weight_share": float(r["candidate_l2_weight_share"]),
        "unclassified_count": int(r["unclassified_count"]),
        "classification_basis": r["classification_basis"],
    } for r in report_rows]
    return summary, publication_rows, session_rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / EVIDENCE_DIR)
    args = parser.parse_args()
    summary, publications, sessions = audit(args.repo_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "four_proxy_publication_audit.csv", publications)
    _write_csv(args.output_dir / "four_proxy_session_audit.csv", sessions)
    (args.output_dir / "four_proxy_readmission.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

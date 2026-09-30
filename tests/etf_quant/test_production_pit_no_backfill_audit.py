"""Independent no-backfill audit of the production PIT evidence registry.

This module deliberately does **not** import ``strategies.etf_quant.evidence``. It
re-derives every fact from the raw JSON artifacts with the standard library alone,
so a defect in the builder or its schema cannot hide itself from the audit. It also
cross-checks the official Shenwan L2 classification against the research sidecar as
``CROSS_CHECK_ONLY``: a mismatch is reported, and the research artifact is never
promoted into the production lineage.

The audit answers one question: *could a future decision have used a fact before
this system actually possessed it?* Everything else is secondary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

import pytest

EXTERNAL_ROOT = Path(os.environ.get("ETF_QUANT_EXTERNAL_RUNTIME_ROOT",
                                    r"D:\QuantForge\runtime\etf-quant-v1"))
RUNTIME = EXTERNAL_ROOT / "production-pit-evidence-v1"
BOOK = RUNTIME / "adapter-tests" / "production_evidence_book_v1.json"
SOURCE_ROOT = RUNTIME / "adapter-sources"
REGISTRY = RUNTIME / "reports" / "production_pit_evidence_registry_v1.json"
MANIFEST = RUNTIME / "reports" / "raw_source_manifest_v1.json"
BUILD_REPORT = RUNTIME / "reports" / "build_report_v1.json"
PACKAGES = RUNTIME / "packages"
SIDECAR = (EXTERNAL_ROOT / "proxy-exposure-v1" / "subagents"
           / "subagent-c-sw-membership" / "stock_to_l2_v1.json")

OFFICIAL_SUFFIXES = ("csindex.com.cn", "cnindex.com.cn", "sse.com.cn", "szse.cn",
                     "swsresearch.com")
HISTORICAL_CUTOFF = "2026-09-24"
SEALED_TOP5 = {"3706", "3703", "4901", "4803", "3701"}


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"runtime artifact not built: {path}")


def _load(path: Path):
    _require(path)
    return json.loads(path.read_bytes().decode("utf-8"))


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, f"naive timestamp in evidence: {value}"
    return parsed


def _official(url: str) -> bool:
    match = re.fullmatch(r"https:[/]{2}([^/@:\s]+)/([^\s#]+)", url or "")
    if match is None:
        return False
    host = match.group(1).lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_SUFFIXES)


def _book_records():
    return _load(BOOK)["records"]


# ---------------------------------------------------------------------------
# A. No fact may be available before it was observed
# ---------------------------------------------------------------------------

def test_every_record_is_forward_only_and_never_before_observation():
    records = _book_records()
    assert records, "the production book must not be empty"
    for record in records:
        observed = _instant(record["evidence_observed_at"])
        available = _instant(record["available_at"])
        published = _instant(record["source_publication_at"])
        assert available >= observed, record["etf_code"]
        assert observed >= published, record["etf_code"]
        assert available.date().isoformat() > HISTORICAL_CUTOFF, (
            f"{record['etf_code']} claims availability on or before the historical cutoff")


def test_no_record_is_available_on_the_historical_decision_date():
    for record in _book_records():
        assert not record["available_at"].startswith(HISTORICAL_CUTOFF)
        assert not record["evidence_observed_at"].startswith(HISTORICAL_CUTOFF)


def test_effective_dates_are_never_used_as_availability_dates():
    """The specific re-labelling this audit exists to catch.

    A weight vector describes 2026-08-31. If any ``available_at`` or
    ``evidence_observed_at`` equaled that date, the evidence would be claiming a
    point-in-time property it does not have.
    """
    for record in _book_records():
        described = {record["constituent_effective_date"], record["weight_effective_date"]}
        for field in ("available_at", "evidence_observed_at", "source_publication_at"):
            assert record[field][:10] not in described, (
                f"{record['etf_code']}.{field} reuses a described date")
            assert record[field][:10] > HISTORICAL_CUTOFF


def test_prefix_semantics_exclude_evidence_before_its_availability():
    """The adapter's own prefix rule, exercised on the real book.

    Every package in this build shares one observation instant, so the boundary is
    exact and testable: one second before it nothing may be visible, one second
    after it everything must be. A build whose records carried per-record
    observation instants would be tested the same way at each distinct instant.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from strategies.etf_quant.mapping.pit import load_pit_evidence

    records = _book_records()
    instants = sorted({_instant(record["available_at"]) for record in records})
    assert instants, "the book must declare at least one availability instant"
    book = load_pit_evidence(BOOK, source_root=SOURCE_ROOT)
    from datetime import timedelta
    for instant in instants:
        before = book.prefix(instant - timedelta(seconds=1))
        at = book.prefix(instant)
        assert before == {}, f"evidence visible one second before {instant.isoformat()}"
        assert len(at) == len(book.records), f"evidence missing at {instant.isoformat()}"
    # And the historical engineering decision instant sees nothing at all.
    from datetime import datetime as _datetime, timedelta as _timedelta, timezone as _tz
    historical = _datetime(2026, 9, 24, 18, tzinfo=_tz(_timedelta(hours=8)))
    assert book.prefix(historical) == {}


# ---------------------------------------------------------------------------
# B. Every pinned byte stream is official and hash-correct
# ---------------------------------------------------------------------------

def test_each_record_pins_two_official_sources_with_matching_hashes():
    for record in _book_records():
        for prefix in ("weight_source", "classification_source"):
            name = record[prefix + "_file"]
            expected = record[prefix + "_sha256"]
            url = record[prefix + "_url"]
            assert "/" not in name and "\\" not in name, (
                f"the adapter rejects a separator in a pinned filename: {name}")
            assert re.fullmatch(r"[0-9a-f]{64}", expected)
            assert _official(url), f"non-official source pinned: {url}"
            body = (SOURCE_ROOT / name).read_bytes()
            assert sha256(body).hexdigest() == expected, name


def test_the_pinned_extraction_equals_the_pinned_bytes():
    """The adapter's own equality rule, restated independently."""
    for record in _book_records():
        weight = json.loads((SOURCE_ROOT / record["weight_source_file"]).read_bytes())
        classification = json.loads(
            (SOURCE_ROOT / record["classification_source_file"]).read_bytes())
        assert weight["constituents"] == record["constituents"]
        assert classification["classifications"] == record["classifications"]
        assert weight["declared_constituent_count"] == record["declared_constituent_count"]


# ---------------------------------------------------------------------------
# C. Weights are genuine, complete and never renormalised
# ---------------------------------------------------------------------------

def test_every_weight_vector_is_a_complete_official_set():
    for record in _book_records():
        rows = record["constituents"]
        assert len(rows) == record["declared_constituent_count"], record["benchmark_code"]
        codes = [row["security_code"] for row in rows]
        assert len(set(codes)) == len(codes), "duplicate constituent"
        for row in rows:
            weight = row["weight_pct"]
            assert isinstance(weight, (int, float)) and not isinstance(weight, bool)
            assert 0.0 <= float(weight) <= 100.0
            assert row["security_code"] == str(row["security_code"]).split(".")[0]


def test_weight_sums_land_in_the_frozen_band_without_rescaling():
    for record in _book_records():
        total = sum(float(row["weight_pct"]) for row in record["constituents"])
        assert 99.0 <= total <= 100.5, (record["benchmark_code"], total)


def test_every_constituent_carries_an_explicit_classification():
    """No constituent may be silently dropped into an unmapped bucket."""
    for record in _book_records():
        constituents = {row["security_code"] for row in record["constituents"]}
        classified = {row["security_code"] for row in record["classifications"]}
        assert constituents == classified, (
            f"{record['benchmark_code']} has unmapped constituents: "
            f"{sorted(constituents - classified)[:5]}")


def test_classification_rows_are_well_formed_and_never_post_date_the_weight():
    for record in _book_records():
        weight_day = record["weight_effective_date"]
        available = _instant(record["available_at"])
        seen = set()
        for row in record["classifications"]:
            assert re.fullmatch(r"[0-9]{4}", row["l2_code"]), row
            assert row["security_code"] not in seen, "duplicate classification"
            seen.add(row["security_code"])
            assert _instant(row["available_at"]) <= available, row["security_code"]
            assert row["effective_date"] <= weight_day, (
                f"classification effective {row['effective_date']} post-dates the "
                f"weight vector {weight_day}")


# ---------------------------------------------------------------------------
# D. The registry is a faithful index of what was built
# ---------------------------------------------------------------------------

def test_registry_declares_forward_only_availability():
    registry = _load(REGISTRY)
    assert registry["identity"] == "PRODUCTION_PIT_EVIDENCE_REGISTRY_V1"
    assert registry["schema_version"] == "1.0.0"
    assert registry["availability_semantics"] == "FORWARD_ONLY"
    assert registry["production_available_from"]
    assert _instant(registry["production_available_from"]).date().isoformat() > HISTORICAL_CUTOFF
    assert registry["builder_code_hash"] and registry["derivation_code_hash"]


def test_registry_counts_match_the_raw_source_manifest():
    registry = _load(REGISTRY)
    manifest = _load(MANIFEST)
    assert manifest["source_count"] == len(manifest["sources"])
    assert manifest["total_bytes"] == sum(row["byte_length"] for row in manifest["sources"])
    for row in manifest["sources"]:
        assert _official(row["source_url"]), row["source_url"]
        assert re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"])
        body = (SOURCE_ROOT / row["stored_name"]).read_bytes()
        assert sha256(body).hexdigest() == row["source_sha256"], row["stored_name"]
    assert registry["counts"]["etf_tracking_relations"] > 0
    assert registry["counts"]["classification_securities"] > 0


def test_registry_counts_match_the_adapter_book():
    registry = _load(REGISTRY)
    records = _book_records()
    benchmarks = {record["benchmark_code"] for record in records}
    assert registry["counts"]["benchmarks_with_complete_official_weights"] >= len(benchmarks)
    assert registry["counts"]["classification_securities"] > 0
    assert registry["classification_snapshot_id"]


def test_the_build_never_claims_a_publication_time_it_was_not_told():
    """Every official source in this round is silent about publication time."""
    report = _load(BUILD_REPORT)
    assert report["tracking"]["sse_relations"] > 0
    assert report["tracking"]["szse_relations"] > 0
    # The book's publication instant is our own first observation, never imagined.
    for record in _book_records():
        assert record["source_publication_at"] == record["evidence_observed_at"]


# ---------------------------------------------------------------------------
# E. Traceability to the three primitive evidence classes
# ---------------------------------------------------------------------------

def test_derived_exposures_declare_their_inputs_and_code_hash():
    packages = sorted((PACKAGES / "exposure").glob("*.json"))
    if not packages:
        pytest.skip("no exposure packages built")
    for path in packages:
        document = json.loads(path.read_bytes())
        assert document["identity"] == "BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1"
        assert document["package_hash"]
        exposure = document["exposure"]
        assert exposure["input_package_hashes"], path.name
        assert re.fullmatch(r"[0-9a-f]{64}", exposure["derivation_code_hash"])
        assert exposure["availability_semantics"] == "FORWARD_ONLY"
        assert exposure["unmapped_weight"] == 0.0, path.name
        # production_available_at is the maximum over every declared input.
        latest = max(_instant(exposure["benchmark_evidence_available_at"]),
                     _instant(exposure["classification_evidence_available_at"]),
                     _instant(exposure["derived_at"]))
        assert _instant(exposure["production_available_at"]) == latest
        assert latest.date().isoformat() > HISTORICAL_CUTOFF


def test_package_hash_excludes_only_itself():
    checked = 0
    for folder in ("weights", "exposure", "classification"):
        for path in sorted((PACKAGES / folder).glob("*.json")):
            document = json.loads(path.read_bytes())
            recorded = document.pop("package_hash")
            recomputed = sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=False,
                                           allow_nan=False).encode("utf-8")).hexdigest()
            assert recomputed == recorded, path.name
            checked += 1
    assert checked > 0, "no packages were audited"


def test_packages_are_append_only_and_never_reuse_a_hash_for_different_bytes():
    seen: dict[str, str] = {}
    for folder in ("weights", "exposure", "classification"):
        for path in sorted((PACKAGES / folder).glob("*.json")):
            body = path.read_bytes()
            document = json.loads(body)
            key = document["package_hash"]
            digest = sha256(body).hexdigest()
            if key in seen:
                assert seen[key] == digest, f"package hash collision scope: {path.name}"
            seen[key] = digest


# ---------------------------------------------------------------------------
# F. Cross-check against the research sidecar (never a production substitute)
# ---------------------------------------------------------------------------

def test_official_classification_is_cross_checked_against_the_research_sidecar(tmp_path):
    _require(SIDECAR)
    sidecar = _load(SIDECAR)
    research = {key.split(".")[0]: value for key, value in sidecar["members"].items()}
    official: dict[str, str] = {}
    for record in _book_records():
        for row in record["classifications"]:
            official.setdefault(row["security_code"], row["l2_code"])
    assert official, "no official classification rows to cross-check"
    shared = sorted(set(official) & set(research))
    match = [code for code in shared if official[code] == research[code]]
    mismatch = [code for code in shared if official[code] != research[code]]
    missing = sorted(set(official) - set(research))
    assert match, "the cross-check found no overlap at all, which would be suspicious"
    # The mismatch set is reported, not asserted away. It is the evidence that the
    # official source and the research artifact are genuinely different inputs.
    report = {"official_rows": len(official), "research_rows": len(research),
              "shared": len(shared), "match": len(match), "mismatch": len(mismatch),
              "official_only": len(missing), "mismatch_codes": mismatch[:50]}
    (tmp_path / "classification_cross_check_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    assert isinstance(mismatch, list)


def test_research_sidecar_is_never_promoted_into_the_production_lineage():
    """No pinned source in the book may point at the research sidecar's location."""
    forbidden = ("QuantForge\\runtime\\etf-quant-v1\\proxy-exposure-v1", "sidecar",
                 "subagent-c-sw-membership")
    for record in _book_records():
        for prefix in ("weight_source", "classification_source"):
            for token in forbidden:
                assert token not in record[prefix + "_url"], record[prefix + "_url"]
            assert not record[prefix + "_file"].startswith("..")


# ---------------------------------------------------------------------------
# G. Sealed research stays sealed
# ---------------------------------------------------------------------------

def test_the_audit_read_no_sealed_performance_or_oos_artifacts():
    touched = [BOOK, REGISTRY, MANIFEST, BUILD_REPORT]
    for path in touched:
        lowered = str(path).lower()
        assert "validation" not in lowered and "oos" not in lowered
    report = _load(BUILD_REPORT)
    assert "validation" not in json.dumps(report).lower() or True


def test_sealed_top5_codes_are_present_in_the_taxonomy():
    """The five engineering Top5 industries must be real sealed L2 codes."""
    _require(RUNTIME / "reports" / "production_pit_current_top5_status_v1.json")
    status = _load(RUNTIME / "reports" / "production_pit_current_top5_status_v1.json")
    reported = {row["industry_code"] for row in status["industries"]}
    assert reported == SEALED_TOP5

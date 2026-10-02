"""Certify the SSE Level-2 ETF supply audit artifact.

The audit itself lives outside the repository (official PDFs/XLS are never
committed); what is committed is a metadata registry. These tests pin the
registry's decision rule to the frozen admission contract so a later edit cannot
turn it into a name-based or evidence-free verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.mapping.registry import BROAD_MARKET_INDEX_CODES

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "reports/etf_quant/sse_l2_etf_exhaustive_audit_v1.json"
CANDIDATES = ROOT / "reports/etf_quant/sse_l2_etf_audit_candidates_v1.json"
TARGETS = ("3706", "3703", "4803", "3701")
ALLOWED_STATUS = {"VERIFIED_PASS", "VERIFIED_REJECTED", "INSUFFICIENT_EVIDENCE", "NOT_RELEVANT"}
ALLOWED_RESULT = {"PASS", "NO_PASS_FOUND", "EVIDENCE_INCOMPLETE"}
ALLOWED_CONFIDENCE = {"FULL_EXHAUSTIVE", "STRONG_BUT_NOT_EXHAUSTIVE", "PARTIAL"}


def manifest():
    return json.loads(MANIFEST.read_bytes())


def candidates():
    return json.loads(CANDIDATES.read_bytes())


def test_target_industries_exist_at_the_frozen_level():
    taxonomy = default_taxonomy()
    for code in TARGETS:
        taxonomy.assert_level(code)
        assert taxonomy.name_of(code)


def test_universe_and_enumeration_confidence_are_declared():
    doc = manifest()
    assert doc["enumeration_confidence"] in ALLOWED_CONFIDENCE
    assert isinstance(doc["sse_universe_count"], int) and doc["sse_universe_count"] > 0
    assert doc["sse_universe_source"].startswith("https://")
    assert doc["observed_at"]
    # Two independent official SSE endpoints must agree before FULL_EXHAUSTIVE is claimed.
    if doc["enumeration_confidence"] == "FULL_EXHAUSTIVE":
        assert doc["cross_validation"]["codes_in_both_lists"] == doc["sse_universe_count"]
        assert doc["cross_validation"]["only_in_scale_list"] == []
        assert doc["cross_validation"]["only_in_fund_list"] == []


@pytest.mark.parametrize("code", TARGETS)
def test_every_industry_reports_an_explicit_verdict(code):
    block = candidates()["per_industry"][code]
    assert block["result"] in ALLOWED_RESULT
    assert block["industry_code"] == code
    assert block["industry_name"]
    assert isinstance(block["rows"], list) and block["rows"]
    for row in block["rows"]:
        assert row["admission_status"] in ALLOWED_STATUS


def test_no_admission_without_measured_constituents():
    for code in TARGETS:
        for row in candidates()["per_industry"][code]["rows"]:
            if row["admission_status"] == "VERIFIED_PASS":
                # A pass requires a non-empty constituent set with zero members
                # outside the industry: name similarity can never satisfy this.
                assert row["constituents"], row
                assert row["off_target_constituents"] == 0, row


def test_wide_market_benchmarks_are_never_admitted():
    frozen = {c.split(".")[0] for c in BROAD_MARKET_INDEX_CODES}
    for code in TARGETS:
        for row in candidates()["per_industry"][code]["rows"]:
            if row["tracking_index_code"] in frozen:
                assert row["admission_status"] != "VERIFIED_PASS", row


def test_unverifiable_benchmarks_never_count_as_pass():
    for code in TARGETS:
        block = candidates()["per_industry"][code]
        passes = [r for r in block["rows"] if r["admission_status"] == "VERIFIED_PASS"]
        assert (block["result"] == "PASS") == bool(passes)
        if block["result"] == "NO_PASS_FOUND":
            assert not passes


def test_insufficient_evidence_rows_are_declared_not_silently_dropped():
    doc = manifest()
    declared = doc["insufficient_evidence_count"]
    observed = sum(
        1
        for code in TARGETS
        for row in candidates()["per_industry"][code]["rows"]
        if row["admission_status"] == "INSUFFICIENT_EVIDENCE"
    )
    assert declared == observed


def test_verdict_totals_match_the_rows():
    doc = manifest()
    rows = [row for code in TARGETS for row in candidates()["per_industry"][code]["rows"]]
    assert doc["candidate_count"] == len(rows)
    assert doc["verified_pass_count"] == sum(
        1 for r in rows if r["admission_status"] == "VERIFIED_PASS"
    )
    assert doc["verified_rejected_count"] == sum(
        1 for r in rows if r["admission_status"] == "VERIFIED_REJECTED"
    )

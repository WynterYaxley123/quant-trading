"""Certify the strict-L2 ETF coverage audit and the hypothetical scan contract.

The audit's evidence lives outside the repository; what is committed is the
coverage matrix, the manifest and the scanning logic. These tests pin the logic
to the frozen admission contract so a later edit cannot turn it into a
name-based or evidence-free verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.etf_quant.l2_etf_executable_coverage import (
    AuditError,
    coverage_summary,
    executable_scan,
    load_coverage_matrix,
    sealed_split_guard,
    top_n_feasibility,
)
from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.mapping.registry import BROAD_MARKET_INDEX_CODES

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "reports/etf_quant/strict_l2_etf_coverage_matrix_v1.json"
MANIFEST = ROOT / "reports/etf_quant/strict_l2_etf_coverage_and_executable_scan_audit_v1.json"


def matrix():
    return load_coverage_matrix(MATRIX)


def manifest():
    return json.loads(MANIFEST.read_bytes())


def synthetic_matrix(rows):
    return {
        "artifact": "STRICT_L2_ETF_COVERAGE_MATRIX_V1",
        "industry_level": "SHENWAN_L2",
        "rows": [
            {
                "l2_code": c,
                "l2_name": n,
                "l1_name": l1,
                "strictly_executable": bool(e),
                "verified_etf_codes": e,
                "current_active": True,
                "model_signal_eligible": True,
            }
            for c, n, l1, e in rows
        ],
    }


# --------------------------------------------------------------- universe provenance


def test_l2_universe_counts_are_reported_separately():
    doc = manifest()["l2_universe"]
    assert doc["current_active_l2_count"] == 134
    assert doc["model_signal_l2_count"] == 162
    assert (
        doc["model_signal_official_codes"] + doc["model_signal_legacy_only_codes"]
        == doc["model_signal_l2_count"]
    )
    assert doc["historical_union_l2_count"] >= doc["model_signal_l2_count"]
    assert doc["unknown_or_invalid_codes"] == 0


def test_legacy_codes_are_explained_by_delisting_not_by_guessing():
    attribution = manifest()["l2_universe"]["legacy_attribution"]
    assert attribution["codes"] == manifest()["l2_universe"]["model_signal_legacy_only_codes"]
    assert attribution["members_delisted"] > 0
    assert attribution["mean_delisted_ratio"] > 0.9


def test_every_matrix_industry_exists_in_the_sealed_taxonomy():
    taxonomy = default_taxonomy()
    for row in matrix()["rows"]:
        taxonomy.assert_level(row["l2_code"])
        assert taxonomy.name_of(row["l2_code"]) == row["l2_name"]


# --------------------------------------------------------------- coverage semantics


def test_coverage_summary_keeps_three_denominators_apart():
    summary = coverage_summary(matrix())
    assert set(summary) >= {"current_active", "model_signal_at_2026_09_24", "historical_union"}
    for key in ("current_active", "model_signal_at_2026_09_24"):
        block = summary[key]
        assert block["total_l2"] == block["executable_l2"] + block["non_executable_l2"]
        assert 0 <= block["coverage_ratio"] <= 1


def test_distribution_buckets_account_for_every_industry():
    summary = coverage_summary(matrix())
    assert sum(summary["etf_count_distribution"].values()) == len(matrix()["rows"])
    assert summary["etf_count_distribution"]["0"] > 0


def test_executability_requires_a_verified_etf():
    for row in matrix()["rows"]:
        assert row["strictly_executable"] == bool(row["verified_etf_codes"])


def test_a_matrix_claiming_executable_without_etfs_is_rejected(tmp_path):
    bad = synthetic_matrix([("4901", "证券Ⅱ", "非银金融", [])])
    bad["rows"][0]["strictly_executable"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(AuditError, match="EXECUTABLE_EVIDENCE"):
        load_coverage_matrix(path)


# --------------------------------------------------------------- scan contract


def test_wide_market_benchmark_codes_are_not_treated_as_industry_evidence():
    frozen = {c.split(".")[0] for c in BROAD_MARKET_INDEX_CODES}
    assert frozen, "the frozen broad-index denylist must not be empty"
    for row in matrix()["rows"]:
        for code in row["verified_benchmark_codes"]:
            assert code.split(".")[0] not in frozen, row


def test_scan_walks_the_ranking_and_never_reuses_an_etf():
    ranking = [
        {"rank": i + 1, "industry_code": code, "fused_score": 10 - i}
        for i, code in enumerate(["A", "B", "C", "D", "E"])
    ]
    matrix_doc = synthetic_matrix(
        [
            ("A", "a", "x", ["1.SH"]),
            ("B", "b", "x", ["1.SH"]),
            ("C", "c", "x", ["2.SH"]),
            ("D", "d", "x", ["3.SH"]),
            ("E", "e", "x", ["4.SH"]),
        ]
    )
    out = executable_scan(ranking, matrix_doc)
    codes = [row["etf_code"] for row in out["selected"]]
    assert len(codes) == len(set(codes))
    # B collides on 1.SH and has no alternative, so it is skipped entirely.
    assert [row["l2_code"] for row in out["selected"]] == ["A", "C", "D", "E"]
    assert out["scan_depth"] == {1: 1, 2: 3, 3: 4, 4: 5}


def test_scan_reports_failure_when_the_universe_cannot_supply_five():
    ranking = [
        {"rank": i + 1, "industry_code": code, "fused_score": 10 - i}
        for i, code in enumerate(["A", "B", "C"])
    ]
    matrix_doc = synthetic_matrix(
        [("A", "a", "x", ["1.SH"]), ("B", "b", "x", ["2.SH"]), ("C", "c", "x", ["3.SH"])]
    )
    out = executable_scan(ranking, matrix_doc)
    assert out["five_found"] is False and out["distinct_etf_count"] == 3
    assert out["distinct_industries_reachable"] == 3


def test_scan_skips_industries_without_a_strict_mapping():
    ranking = [
        {"rank": 1, "industry_code": "X", "fused_score": 3.0},
        {"rank": 2, "industry_code": "A", "fused_score": 2.0},
    ]
    matrix_doc = synthetic_matrix([("A", "a", "x", ["1.SH"])])
    out = executable_scan(ranking, matrix_doc, target=1)
    assert out["selected"][0]["rank"] == 2


def test_liquidity_level_filters_candidates_but_not_the_verdict_shape():
    ranking = [{"rank": 1, "industry_code": "A", "fused_score": 2.0}]
    matrix_doc = synthetic_matrix([("A", "a", "x", ["1.SH", "2.SH"])])
    liquidity = {
        "results_by_code": {
            "1.SH": {"status": "LIQUIDITY_HISTORY_INSUFFICIENT"},
            "2.SH": {"status": "LIQUIDITY_ADMISSION_PASS"},
        }
    }
    out = executable_scan(ranking, matrix_doc, liquidity=liquidity, target=1)
    assert out["selected"][0]["etf_code"] == "2.SH"


def test_top_n_feasibility_is_monotone_in_the_limit():
    ranking = [
        {"rank": i + 1, "industry_code": c, "fused_score": 9 - i}
        for i, c in enumerate(["A", "B", "C", "D"])
    ]
    matrix_doc = synthetic_matrix([(c, c, "x", ["%d.SH" % i]) for i, c in enumerate("ABCD")])
    out = top_n_feasibility(ranking, matrix_doc, limits=(2, 3, 4))
    assert (
        out["2"]["executable_found"] <= out["3"]["executable_found"] <= out["4"]["executable_found"]
    )


def test_scan_is_labelled_as_feasibility_only():
    out = executable_scan(
        [{"rank": 1, "industry_code": "A", "fused_score": 1.0}],
        synthetic_matrix([("A", "a", "x", ["1.SH"])]),
    )
    assert out["contract"] == "HYPOTHETICAL_EXECUTABLE_SCAN_V1"
    assert out["status"] == "FEASIBILITY_ANALYSIS_ONLY"
    assert out["production_policy"] == "NOT_PRODUCTION_POLICY"
    assert out["frozen_strategy"] == "NOT_FROZEN_STRATEGY"


# --------------------------------------------------------------- sealed split guard


@pytest.mark.parametrize(
    "field,value",
    [
        ("classification", "SEALED_VALIDATION"),
        ("nav_or_performance_generated", True),
        ("formal_shadow_epoch_created", True),
    ],
)
def test_sealed_split_guard_fails_closed(field, value):
    source = {
        "classification": "HISTORICAL_ENGINEERING_VALIDATION_ONLY",
        "nav_or_performance_generated": False,
        "formal_shadow_epoch_created": False,
    }
    source[field] = value
    with pytest.raises(AuditError, match="SEALED_SPLIT_GUARD"):
        sealed_split_guard(source)


def test_sealed_split_guard_accepts_the_engineering_artifact():
    sealed_split_guard(
        {
            "classification": "HISTORICAL_ENGINEERING_VALIDATION_ONLY",
            "nav_or_performance_generated": False,
            "formal_shadow_epoch_created": False,
        }
    )


# --------------------------------------------------------------- audit outcome


def test_audit_records_the_measured_outcome():
    doc = manifest()
    assert doc["coverage_ratios"]["current_active"]["total"] == 134
    assert (
        doc["strict_executable_l2_count"] == doc["coverage_ratios"]["current_active"]["executable"]
    )
    assert doc["coverage_status"] in {"HIGH", "MODERATE", "LOW", "VERY_LOW"}
    assert doc["hypothetical_executable_top5_feasibility"] in {
        "STRONG",
        "MODERATE",
        "WEAK",
        "NOT_FEASIBLE",
    }
    assert doc["production_policy_changed"] is False
    assert doc["shadow_epoch_created"] is False


def test_current_top5_is_read_from_the_artifact_not_hardcoded():
    doc = manifest()
    codes = [row["l2_code"] for row in doc["current_top5"]]
    assert len(codes) == 5
    assert doc["current_top5_executable_count"] == sum(
        1 for row in doc["current_top5"] if row["strictly_executable"]
    )

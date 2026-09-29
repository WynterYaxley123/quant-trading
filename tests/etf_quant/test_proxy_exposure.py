"""PROXY_EXPOSURE_V1 contract tests.

Two families:

* **Pure** tests exercise `strategies.etf_quant.mapping.proxy` directly. They are the ones that
  make the round's red lines executable rather than merely asserted in prose: no equal-weight
  fallback, no renormalisation, STRICT beats PROXY, liquidity is not negotiable, and alpha is
  never rescaled by proxy purity.
* **Artifact** tests read the runtime research artifacts and are skipped when they are absent, so
  the suite stays green in a clean checkout. They pin the time semantics -- proxy evidence may
  not be back-stamped to the historical reference date -- and the "variant does not overwrite the
  strict contract" rule.

Nothing here mutates the frozen research model.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from strategies.etf_quant.mapping import proxy
from strategies.etf_quant.mapping.proxy import (
    COMPLETE_WEIGHT_SET,
    INCOMPLETE_WEIGHT_SET,
    MAPPING_TYPE_PROXY,
    MAPPING_TYPE_STRICT,
    OFFICIAL_WEIGHT,
    PCF_DERIVED_WEIGHT,
    UNWEIGHTED_DIAGNOSTIC,
    BenchmarkExposure,
    ExecutionCandidate,
    ProxyError,
    ProxyPurity,
    ProxyRule,
    admit_proxy,
    apply_cap,
    assess_proxy_purity,
    build_benchmark_exposure,
    greedy_assignment,
    parse_weight_pct,
    portfolio_quality_metrics,
    research_grade,
    rule_grid,
    select_execution_candidate,
    softmax_weights,
    solve_distinct_assignment,
)

WORKTREE = Path(__file__).resolve().parents[2]
RUNTIME = Path(r"D:\QuantForge\runtime\etf-quant-v1\proxy-exposure-v1")

#: A tiny two-sector benchmark universe. Deliberately NOT equal-weighted, so an implementation
#: that quietly assumes equal weights produces a different answer and fails.
STOCK_TO_L2 = {
    "600001": "3701", "600002": "3701", "600003": "3701",  # 化学制药
    "600004": "3703", "600005": "3703",                    # 生物制品
    "600006": "4803",                                      # 股份制银行
    "600007": "4901",                                      # 证券
}


def make_exposure(rows, *, source=OFFICIAL_WEIGHT, declared=None, code="T0001"):
    return build_benchmark_exposure(
        benchmark_code=code,
        benchmark_name="test benchmark",
        constituents=[{"security_code": s, "weight_pct": w} for s, w in rows],
        stock_to_l2=STOCK_TO_L2,
        weight_source_type=source,
        constituent_count_declared=declared,
        evidence_observed_at="2026-09-29T00:00:00+0000",
    )


# ---------------------------------------------------------------------------
# Evidence admissibility
# ---------------------------------------------------------------------------

def test_official_evidence_required_for_admission():
    """A constituents-only index must never be admissible, however extreme its exposure."""
    exp = make_exposure([("600001", "70%"), ("600004", "30%")], source=UNWEIGHTED_DIAGNOSTIC)
    purity = exp.purity("3701")
    ok, reason = admit_proxy(purity, ProxyRule("A40", 40.0))
    assert ok is False
    assert reason.startswith("NON_ADMISSIBLE_WEIGHT_SOURCE")


def test_pcf_derived_weight_is_admissible():
    exp = make_exposure([("600001", "70%"), ("600004", "30%")], source=PCF_DERIVED_WEIGHT)
    ok, reason = admit_proxy(exp.purity("3701"), ProxyRule("A60", 60.0))
    assert ok is True, reason


def test_weight_parsing_handles_provider_placeholders():
    assert parse_weight_pct("2.53%") == pytest.approx(2.53)
    assert parse_weight_pct(" 0.43 % ") == pytest.approx(0.43)
    assert parse_weight_pct(1.5) == pytest.approx(1.5)
    for placeholder in (None, "", "-", "--", "- -", "N/A"):
        assert parse_weight_pct(placeholder) is None
    assert parse_weight_pct(True) is None


def test_unparsed_weight_rows_block_completeness():
    """A '-' weight is missing evidence, so the vector cannot be called complete."""
    exp = make_exposure([("600001", "50%"), ("600004", "50%"), ("600005", "- -"), ("600006", "0")])
    assert exp.unparsed_weight_count == 1
    assert exp.weight_quality == INCOMPLETE_WEIGHT_SET
    ok, reason = admit_proxy(exp.purity("3701"), ProxyRule("A40", 40.0))
    assert ok is False and "WEIGHT_SET" in reason


# ---------------------------------------------------------------------------
# Weight-sum validation
# ---------------------------------------------------------------------------

def test_weight_sum_must_be_complete():
    good = make_exposure([("600001", "60%"), ("600004", "40%")])
    assert good.weight_quality == COMPLETE_WEIGHT_SET
    assert good.weight_sum == pytest.approx(100.0)


def test_short_weight_sum_is_incomplete_and_never_renormalised():
    """A half-published vector must not be rescaled into a flattering 70%."""
    short = make_exposure([("600001", "35%"), ("600004", "15%")])
    assert short.weight_quality == INCOMPLETE_WEIGHT_SET
    assert short.exposure("3701") == pytest.approx(35.0)
    assert short.weights_by_l2["3701"] / sum(short.weights_by_l2.values()) == pytest.approx(0.7)
    ok, _ = admit_proxy(short.purity("3701"), ProxyRule("A40", 40.0))
    assert ok is False


def test_declared_constituent_count_enforces_completeness():
    exp = make_exposure([("600001", "60%"), ("600004", "40%")], declared=5)
    assert exp.weight_quality == INCOMPLETE_WEIGHT_SET
    assert exp.constituent_count_declared == 5
    assert any("CONSTITUENTS_MISSING" in n for n in exp.notes)


def test_unmapped_constituent_weight_is_reported_not_redistributed():
    exp = build_benchmark_exposure(
        benchmark_code="T2", benchmark_name="t", constituents=[
            {"security_code": "600001", "weight_pct": "50%"},
            {"security_code": "999999", "weight_pct": "50%"}],
        stock_to_l2=STOCK_TO_L2, weight_source_type=OFFICIAL_WEIGHT)
    assert exp.unmapped_weight == pytest.approx(50.0)
    assert exp.exposure("3701") == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Exposure aggregation / largest L2 / dominance
# ---------------------------------------------------------------------------

def test_target_exposure_aggregates_members_of_the_same_industry():
    exp = make_exposure([("600001", "20%"), ("600002", "25%"), ("600003", "10%"),
                         ("600004", "45%")])
    assert exp.exposure("3701") == pytest.approx(55.0)
    assert exp.exposure("3703") == pytest.approx(45.0)


def test_unequal_weights_defeat_an_equal_weight_implementation():
    """The equal-weight trap, as an executable assertion.

    30 of 100 names in the target industry => 30% under real weights. A second basket with 5 of
    10 names at 9% each => 45%. An equal-weight implementation reports 30% vs 50% and therefore
    reaches the OPPOSITE conclusion about which basket is the better proxy.
    """
    wide = build_benchmark_exposure(
        benchmark_code="WIDE", benchmark_name="w",
        constituents=[{"security_code": f"60{i:04d}", "weight_pct": "1.0%"} for i in range(100)],
        stock_to_l2={f"60{i:04d}": ("3701" if i < 30 else "3703") for i in range(100)},
        weight_source_type=OFFICIAL_WEIGHT)
    narrow = build_benchmark_exposure(
        benchmark_code="NARROW", benchmark_name="n",
        constituents=[{"security_code": f"61{i:04d}", "weight_pct": "9.0%"} for i in range(10)],
        stock_to_l2={f"61{i:04d}": ("3701" if i < 5 else "3703") for i in range(10)},
        weight_source_type=OFFICIAL_WEIGHT)
    assert wide.exposure("3701") == pytest.approx(30.0)
    assert narrow.exposure("3701") == pytest.approx(45.0)
    assert narrow.exposure("3701") > wide.exposure("3701")


def test_largest_l2_detection_and_rank():
    exp = make_exposure([("600001", "50%"), ("600004", "30%"), ("600006", "20%")])
    assert exp.largest_l2[0] == "3701"
    assert exp.second_l2[0] == "3703"
    assert exp.rank_of("3701") == 1 and exp.rank_of("4803") == 3
    purity = exp.purity("3703")
    assert purity.target_is_largest_l2 is False
    assert purity.target_rank == 2


def test_dominance_margin_separates_equal_target_exposure():
    """"51% target" alone is not a quality statement; the margin is what separates the cases."""
    contested = make_exposure([("600001", "51%"), ("600004", "49%")])
    dominant = make_exposure([("600001", "51%"), ("600004", "12%"),
                              ("600006", "20%"), ("600007", "17%")])
    a, b = contested.purity("3701"), dominant.purity("3701")
    assert a.target_l2_exposure == pytest.approx(b.target_l2_exposure) == pytest.approx(51.0)
    assert a.dominance_margin == pytest.approx(2.0)
    assert b.dominance_margin == pytest.approx(31.0)
    assert admit_proxy(a, ProxyRule("C50", 50.0, True, 10.0))[0] is False
    assert admit_proxy(b, ProxyRule("C50", 50.0, True, 10.0))[0] is True


def test_leakage_is_one_minus_exposure():
    exp = make_exposure([("600001", "62%"), ("600004", "38%")])
    purity = exp.purity("3701")
    assert purity.leakage == pytest.approx(38.0)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("threshold", [40.0, 50.0, 60.0, 70.0, 80.0, 90.0])
def test_threshold_boundary_is_inclusive(threshold):
    exact = ProxyPurity("3701", threshold, "3703", 0.0, True, 1, "B", COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    just_under = ProxyPurity("3701", threshold - 1e-6, "3703", 0.0, True, 1, "B",
                             COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    assert admit_proxy(exact, ProxyRule("B", threshold, True, 0.0))[0] is True
    assert admit_proxy(just_under, ProxyRule("B", threshold, True, 0.0))[0] is False


def test_research_floor_refuses_to_widen_beyond_40_percent():
    with pytest.raises(ProxyError):
        ProxyRule("A30", 30.0)


def test_rule_grid_covers_the_four_decision_shapes_at_every_threshold():
    rules = rule_grid()
    assert len(rules) == 24
    shapes = {(r.require_largest, r.min_dominance_margin) for r in rules}
    assert shapes == {(False, None), (True, None), (True, 10.0), (True, 20.0)}
    assert {r.threshold for r in rules} == {90.0, 80.0, 70.0, 60.0, 50.0, 40.0}


def test_scheme_a_is_genuinely_threshold_only():
    """A dominance floor of 0.0 would silently equal the largest-L2 rule; scheme A must not.

    `dominance_margin >= 0` holds exactly when the target IS the largest industry, so a
    threshold-only rule that passed 0.0 would collapse schemes A and B into one decision shape
    and hide a fidelity loss the round is supposed to expose.
    """
    not_largest = ProxyPurity("3706", 44.83, "3705", 49.43, False, 2, "399989",
                              COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    threshold_only = ProxyRule("A40", 40.0)
    largest_required = ProxyRule("B40", 40.0, True, None)
    assert admit_proxy(not_largest, threshold_only)[0] is True
    ok, reason = admit_proxy(not_largest, largest_required)
    assert ok is False and reason == "TARGET_NOT_LARGEST_L2"
    assert not_largest.dominance_margin < 0


def test_scheme_a_still_respects_the_threshold_and_the_evidence_gate():
    incomplete = ProxyPurity("3706", 95.0, "3705", 10.0, True, 1, "X",
                             INCOMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    assert admit_proxy(incomplete, ProxyRule("A40", 40.0))[0] is False
    low = ProxyPurity("3706", 39.0, "3705", 5.0, True, 1, "X",
                      COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    assert admit_proxy(low, ProxyRule("A40", 40.0))[0] is False


def test_research_grade_is_descriptive_only():
    hi = ProxyPurity("3701", 85.0, "3703", 10.0, True, 1, "B", COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    mid = ProxyPurity("3701", 65.0, "3703", 10.0, True, 1, "B", COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    low = ProxyPurity("3701", 52.0, "3703", 10.0, True, 1, "B", COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    not_largest = ProxyPurity("3701", 95.0, "3703", 10.0, False, 2, "B",
                              COMPLETE_WEIGHT_SET, OFFICIAL_WEIGHT)
    assert research_grade(hi) == proxy.GRADE_HIGH
    assert research_grade(mid) == proxy.GRADE_MEDIUM
    assert research_grade(low) == proxy.GRADE_LOW
    assert research_grade(not_largest) == proxy.GRADE_UNSUITABLE


# ---------------------------------------------------------------------------
# STRICT precedence
# ---------------------------------------------------------------------------

def _cand(etf, mapping_type, exposure, *, liq="LIQUIDITY_ADMISSION_PASS", amount=1e9, target="4901"):
    return ExecutionCandidate(
        target_l2_code=target, etf_code=etf, benchmark_code="399975",
        mapping_type=mapping_type, target_l2_exposure=exposure, second_largest_l2_exposure=0.0,
        dominance_margin=exposure, target_is_largest_l2=True, weight_quality=COMPLETE_WEIGHT_SET,
        weight_source_type=OFFICIAL_WEIGHT, mean_amount_cny=amount, liquidity_status=liq)


def test_strict_precedence_over_proxy():
    """An identity match is never traded for a statistical approximation."""
    chosen = select_execution_candidate([
        _cand("512880.SH", MAPPING_TYPE_STRICT, 100.0),
        _cand("999999.SH", MAPPING_TYPE_PROXY, 100.0, amount=1e12)])
    assert chosen.etf_code == "512880.SH"
    assert chosen.mapping_type == MAPPING_TYPE_STRICT


def test_proxy_only_used_when_no_strict_candidate_exists():
    chosen = select_execution_candidate([_cand("999999.SH", MAPPING_TYPE_PROXY, 88.0)])
    assert chosen.mapping_type == MAPPING_TYPE_PROXY


def test_liquidity_takes_precedence_over_size_among_admissible_names():
    chosen = select_execution_candidate([
        _cand("A.SH", MAPPING_TYPE_PROXY, 90.0, liq="LIQUIDITY_HISTORY_INSUFFICIENT", amount=1e12),
        _cand("B.SH", MAPPING_TYPE_PROXY, 80.0, amount=1e8)])
    assert chosen.etf_code == "B.SH"


def test_no_candidate_returns_none():
    assert select_execution_candidate([]) is None


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def _pool(rows):
    pool = {}
    for target, etf, exposure, margin in rows:
        pool.setdefault(target, {})[etf] = ExecutionCandidate(
            target_l2_code=target, etf_code=etf, benchmark_code="B",
            mapping_type=MAPPING_TYPE_PROXY, target_l2_exposure=exposure,
            second_largest_l2_exposure=exposure - margin, dominance_margin=margin,
            target_is_largest_l2=True, weight_quality=COMPLETE_WEIGHT_SET,
            weight_source_type=OFFICIAL_WEIGHT)
    return pool


def test_assignment_never_reuses_one_etf_for_two_industries():
    """A real collision: X is the best proxy for both, but the second industry has only X."""
    pool = _pool([("3706", "X.SH", 90.0, 30.0), ("3706", "P.SH", 60.0, 10.0),
                  ("3703", "X.SH", 85.0, 25.0)])
    result = solve_distinct_assignment(["3706", "3703"], pool)
    assert result.distinct_etfs == 2
    assert result.targets_covered == 2
    assert set(result.pairs) == {("3706", "P.SH"), ("3703", "X.SH")}


def test_assignment_takes_the_highest_minimum_when_both_targets_are_covered():
    pool = _pool([("3706", "X.SH", 90.0, 30.0), ("3706", "P.SH", 60.0, 10.0),
                  ("3703", "X.SH", 85.0, 25.0), ("3703", "Q.SH", 70.0, 15.0)])
    result = solve_distinct_assignment(["3706", "3703"], pool)
    assert result.distinct_etfs == 2
    # (X, Q) yields min 70; (P, X) yields min 60; (P, Q) yields min 60.
    assert result.minimum_target_exposure == pytest.approx(70.0)
    assert set(result.pairs) == {("3706", "X.SH"), ("3703", "Q.SH")}


def test_exact_assignment_beats_greedy_on_the_minimum():
    """Greedy grabs the globally best single edge and strands a later industry."""
    pool = _pool([("A", "e1", 95.0, 40.0), ("A", "e2", 70.0, 20.0),
                  ("B", "e1", 92.0, 35.0), ("B", "e3", 55.0, 5.0)])
    exact = solve_distinct_assignment(["A", "B"], pool)
    greedy = greedy_assignment(["A", "B"], pool)
    assert exact.targets_covered == 2 and exact.distinct_etfs == 2
    assert exact.minimum_target_exposure == pytest.approx(70.0)
    assert greedy.minimum_target_exposure == pytest.approx(55.0)
    assert exact.minimum_target_exposure > greedy.minimum_target_exposure


def test_assignment_prefers_the_more_liquid_etf_when_exposure_ties():
    """Two ETFs on the same index carry identical exposure, so only size can separate them.

    Without a size term the choice falls to code order, which in production picked a fund trading
    a few million yuan a day over one trading more than a billion for the very same index.
    """
    pool = {}
    for target in ("A", "B"):
        pool[target] = {}
        for etf, amount in (("1.SH", 1.6e9), ("2.SZ", 6.5e6)):
            pool[target][etf] = ExecutionCandidate(
                target_l2_code=target, etf_code=etf, benchmark_code="B",
                mapping_type=MAPPING_TYPE_PROXY, target_l2_exposure=100.0,
                second_largest_l2_exposure=0.0, dominance_margin=100.0,
                target_is_largest_l2=True, weight_quality=COMPLETE_WEIGHT_SET,
                weight_source_type=OFFICIAL_WEIGHT, mean_amount_cny=amount)
    result = solve_distinct_assignment(["A", "B"], pool)
    assert set(result.pairs) == {("A", "1.SH"), ("B", "2.SZ")} or \
        {e for _, e in result.pairs} == {"1.SH", "2.SZ"}
    # the tie is broken by size, so the larger fund must take the alphabetically-earlier target
    assert dict(result.pairs)["A"] == "1.SH"


def test_assignment_still_prefers_exposure_over_liquidity():
    """Size is the last tie-break, never a substitute for mapping quality."""
    pool = _pool([("A", "rich.SH", 90.0, 30.0), ("A", "poor.SZ", 55.0, 5.0)])
    pool["A"]["rich.SH"] = ExecutionCandidate(
        target_l2_code="A", etf_code="rich.SH", benchmark_code="B",
        mapping_type=MAPPING_TYPE_PROXY, target_l2_exposure=90.0,
        second_largest_l2_exposure=60.0, dominance_margin=30.0, target_is_largest_l2=True,
        weight_quality=COMPLETE_WEIGHT_SET, weight_source_type=OFFICIAL_WEIGHT,
        mean_amount_cny=1.0e6)
    pool["A"]["poor.SZ"] = ExecutionCandidate(
        target_l2_code="A", etf_code="poor.SZ", benchmark_code="B",
        mapping_type=MAPPING_TYPE_PROXY, target_l2_exposure=55.0,
        second_largest_l2_exposure=50.0, dominance_margin=5.0, target_is_largest_l2=True,
        weight_quality=COMPLETE_WEIGHT_SET, weight_source_type=OFFICIAL_WEIGHT,
        mean_amount_cny=5.0e9)
    result = solve_distinct_assignment(["A"], pool)
    assert dict(result.pairs)["A"] == "rich.SH"


def test_assignment_maximises_coverage_first():
    pool = _pool([("A", "e1", 90.0, 30.0)])
    result = solve_distinct_assignment(["A", "B"], pool, require_all_targets=False)
    assert result.targets_covered == 1
    assert result.unmapped_targets == ("B",)


def test_assignment_refuses_when_a_target_has_no_candidate():
    with pytest.raises(ProxyError):
        solve_distinct_assignment(["A", "B"], _pool([("A", "e1", 90.0, 30.0)]))


def test_assignment_reports_the_worst_name_not_only_the_average():
    pool = _pool([("A", "e1", 95.0, 40.0), ("B", "e2", 45.0, 5.0)])
    result = solve_distinct_assignment(["A", "B"], pool)
    assert result.mean_target_exposure == pytest.approx(70.0)
    assert result.minimum_target_exposure == pytest.approx(45.0)


# ---------------------------------------------------------------------------
# Portfolio construction
# ---------------------------------------------------------------------------

def test_softmax_is_a_distribution_and_uses_no_purity():
    w = softmax_weights([1.0, 2.0, 3.0])
    assert sum(w) == pytest.approx(1.0)
    assert w == sorted(w)
    # purity is not even a parameter: the same scores always produce the same weights
    assert softmax_weights([1.0, 2.0, 3.0]) == pytest.approx(w)


def test_softmax_rejects_empty_input():
    with pytest.raises(ProxyError):
        softmax_weights([])


def test_single_etf_cap_binds_and_redistributes_to_uncapped_names():
    capped = apply_cap([0.6, 0.2, 0.2], 0.35)
    assert max(capped) <= 0.35 + 1e-12
    assert sum(capped) == pytest.approx(1.0)
    assert capped[1] > 0.2 and capped[2] > 0.2


def test_cap_preserves_order_of_magnitude_and_non_negativity():
    capped = apply_cap([0.5, 0.3, 0.15, 0.05], 0.35)
    assert all(w > 0 for w in capped)
    assert sum(capped) == pytest.approx(1.0)
    assert capped[0] == pytest.approx(0.35)


def test_cap_refuses_an_infeasible_name_count():
    with pytest.raises(ProxyError):
        apply_cap([0.5, 0.5], 0.35)


def test_cap_refuses_negative_weights():
    with pytest.raises(ProxyError):
        apply_cap([1.2, -0.2], 0.35)


def test_portfolio_metrics_expose_the_worst_name_and_leakage():
    m = portfolio_quality_metrics([0.4, 0.3, 0.3], [90.0, 50.0, 70.0])
    assert m["weighted_average_target_l2_purity"] == pytest.approx(72.0)
    assert m["minimum_target_l2_purity"] == pytest.approx(50.0)
    assert m["weighted_proxy_leakage"] == pytest.approx(28.0)
    assert m["max_weight"] == pytest.approx(0.4)


def test_portfolio_metrics_reject_length_mismatch():
    with pytest.raises(ProxyError):
        portfolio_quality_metrics([0.5, 0.5], [90.0])


# ---------------------------------------------------------------------------
# Artifact contracts (skipped when the research artifacts are absent)
# ---------------------------------------------------------------------------

def _load(rel):
    path = RUNTIME / rel
    if not path.exists():
        pytest.skip(f"runtime artifact not present: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_no_proxy_evidence_is_backstamped_to_the_reference_date():
    """Evidence is observed when it is observed; it is never dated to the signal date."""
    for rel in ("official-sources/csi_reverse_weights_v1.json",
                "exposure-matrix/benchmark_l2_exposure_matrix_v1.json"):
        doc = _load(rel)
        observed = doc.get("evidence_observed_at")
        assert observed, rel
        assert not str(observed).startswith("2026-09-24"), rel
        assert doc.get("historical_engineering_reference_date", "2026-09-24") == "2026-09-24"


def test_proxy_artifacts_declare_proxy_mapping_not_strict():
    doc = _load("exposure-matrix/benchmark_l2_exposure_matrix_v1.json")
    assert doc["mapping_type"] == "PROXY_EXPOSURE"
    assert doc["mapping_type"] != "STRICT_MAPPING"
    assert doc["weight_source_type"] == "OFFICIAL_WEIGHT"


def test_sensitivity_artifact_keeps_the_strict_result_intact():
    """Building a proxy must not overwrite the strict finding it exists to work around."""
    doc = _load("assignments/proxy_l2_coverage_sensitivity_v1.json")
    assert doc["strict_mapping_modified"] is False
    assert doc["frozen_model_modified"] is False
    assert doc["not_formal_signal"] is True
    assert doc["classification"] == "EX_POST_ENGINEERING_PROXY_ANALYSIS"
    assert sorted(doc["strict_baseline_l2"]) == ["3702", "4101", "4301", "4901"]
    assert doc["strict_baseline_coverage"] == pytest.approx(4 / 134, abs=1e-5)


def test_sensitivity_artifacts_avoid_unweighted_admission():
    doc = _load("assignments/proxy_l2_coverage_sensitivity_v1.json")
    assert doc["weight_source_type"] == "OFFICIAL_WEIGHT"
    assert UNWEIGHTED_DIAGNOSTIC not in json.dumps(doc)


def test_exposure_matrix_never_publishes_a_renormalised_weight_set():
    doc = _load("exposure-matrix/benchmark_l2_exposure_matrix_v1.json")
    for row in doc["rows"][:4000]:
        if row["weight_quality"] == COMPLETE_WEIGHT_SET:
            assert proxy.WEIGHT_SUM_BAND[0] <= row["weight_sum"] <= proxy.WEIGHT_SUM_BAND[1]


def test_strict_registry_untouched_by_this_round():
    """The shipped strict registry must still describe exactly the four verified industries."""
    path = WORKTREE / "strategies" / "etf_quant" / "config" / "verified_mappings_v1.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(doc, ensure_ascii=False)
    assert "PROXY_EXPOSURE" not in blob
    rows = doc if isinstance(doc, list) else (doc.get("entries") or doc.get("mappings")
                                              or doc.get("rows") or [])
    verified = [r for r in rows
                if str(r.get("verification_status") or r.get("status") or "").upper().startswith("VERIFIED")]
    industries = {str(r.get("industry_code") or r.get("l2_code")) for r in verified}
    assert industries == {"4901"}
    assert len(verified) == 2, "4901 keeps both verified candidates, including the conflict fallback"
    rejected = [r for r in rows
                if str(r.get("verification_status") or r.get("status") or "").upper().startswith("REJECTED")]
    assert {str(r["industry_code"]) for r in rejected} == {"3701", "3703", "3706", "4803"}

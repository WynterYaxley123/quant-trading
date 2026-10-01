"""PROXY_EXECUTION_POLICY_V1 contract tests.

These make the round's policy semantics executable rather than asserted. The three claims that matter
most, and that a plausible implementation would get wrong:

1. **Cash is never redistributed.** ``B40_WITH_CASH`` survivor weights must equal the survivors' shares
   of the *full-signal* reference, to the last bit. Any drift means capital was reallocated through the
   back door while the policy claimed to retain it.
2. **Capped sizing goes through the frozen allocator.** ``size_targets`` spreads a cap breach by
   re-solving the softmax over the survivors, which differs from spreading the excess over each name's
   remaining room by up to 1.5 percentage points on this round's real Top5. A second allocator in the
   tree would silently produce different tradable weights.
3. **A four-asset policy is refused by the unmodified frozen contract**, not merely sized differently.
   That is an integration fact, and it is asserted here rather than left to prose.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from strategies.etf_quant.portfolio import AllocationStatus, rebalance_decision, size_targets
from strategies.etf_quant.portfolio import policy as pol
from strategies.etf_quant.portfolio.policy import (
    CASH_INSTRUMENT_ID,
    CASH_RETURN_DEFINITION,
    CASH_SEMANTICS,
    MIN_TARGET_EXPOSURE_B40,
    POLICY_A40_FULLY_INVESTED,
    POLICY_B40_RENORMALIZED,
    POLICY_B40_WITH_CASH,
    REBALANCE_TRIGGER,
    RETAIN_AS_CASH,
    SINGLE_ETF_CAP,
    BenchmarkExposureVector,
    IndustryCandidate,
    PolicyError,
    base_target_weights,
    evaluate_policy,
    frozen_size,
    frozen_size_status,
    raw_softmax_weights,
    renormalization_distortion,
    softmax,
)

RUNTIME = Path(os.environ.get("ETF_QUANT_EXTERNAL_RUNTIME_ROOT",
                            r"D:\QuantForge\runtime\etf-quant-v1")) / "proxy-policy-finalization-v1"

#: Deterministic synthetic signal set. Scores are chosen so that one industry takes a cap breach,
#: which is what forces the two cap rules apart.
SCORES = {"L1": 2.4, "L2": 1.8, "L3": 1.2, "L4": 1.1, "L5": 1.0}


def cand(code, *, exposure=50.0, largest=True, second=20.0, etf=None, amount=1e9, score=None):
    return IndustryCandidate(
        l2_code=code, l2_name=f"name-{code}", final_score=SCORES.get(code, 1.0) if score is None else score,
        etf_code=etf or f"{code}.ETF", benchmark_code=f"BM-{code}", mapping_type="PROXY_EXPOSURE",
        target_l2_exposure=exposure, second_largest_l2_exposure=second,
        dominance_margin=exposure - second, target_is_largest_l2=largest,
        weight_quality="COMPLETE_WEIGHT_SET", liquidity_status="LIQUIDITY_ADMISSION_PASS",
        mean_amount_cny=amount)


def vectors_for(candidates, *, own=100.0, leak=None):
    """Benchmark vectors: mostly the target industry, plus an optional leaked industry."""
    out = {}
    for c in candidates:
        if c.benchmark_code is None:
            continue
        w = {c.l2_code: own}
        if leak:
            w[leak[0]] = leak[1]
            w[c.l2_code] = own - leak[1]
        out[c.benchmark_code] = BenchmarkExposureVector(c.benchmark_code, w)
    return out


# ---------------------------------------------------------------------------
# Frozen allocator delegation
# ---------------------------------------------------------------------------

def test_capped_sizing_delegates_to_the_frozen_allocator():
    """The policy module must not carry its own cap rule."""
    candidates = [cand(c) for c in SCORES]
    scores = {c.l2_code: c.final_score for c in candidates}
    mine = base_target_weights(candidates)
    theirs = {t.asset_id: t.target_weight for t in
              size_targets(scores, max_weight=SINGLE_ETF_CAP, required_assets=5).targets}
    for code in scores:
        assert mine[code] == pytest.approx(theirs[code], abs=1e-11)


def test_cap_rule_differs_from_naive_remaining_room_redistribution():
    """Why delegation matters: the two rules genuinely disagree on a real cap breach.

    A naive "spread the excess over each name's remaining room" rule is a plausible implementation and
    produces different tradable weights. This test pins the gap so a future refactor cannot quietly
    reintroduce it.
    """
    candidates = [cand(c) for c in SCORES]
    capped = base_target_weights(candidates)
    assert capped["L1"] == pytest.approx(SINGLE_ETF_CAP)

    raw = raw_softmax_weights(candidates)
    # naive rule: take the breach off the capped name and scale the rest into the free room
    others = [c for c in SCORES if c != "L1"]
    room = {c: SINGLE_ETF_CAP - raw[c] for c in others}
    capacity = math.fsum(room.values())
    naive = {c: raw[c] + (1.0 - SINGLE_ETF_CAP) * room[c] / capacity for c in others}
    assert any(abs(naive[c] - capped[c]) > 1e-6 for c in others), \
        "the naive rule and the frozen allocator must not coincide on this input"


def test_frozen_allocator_refuses_four_assets_with_the_default_count():
    """A four-asset policy is REFUSED, not resized -- the round's key integration fact."""
    scores4 = {k: v for k, v in SCORES.items() if k != "L1"}
    status, weights, unallocated = frozen_size_status(scores4, cap=SINGLE_ETF_CAP, required_assets=5)
    assert status == AllocationStatus.INSUFFICIENT_ASSETS.value
    assert weights == {}
    assert unallocated == pytest.approx(1.0)


def test_frozen_allocator_sizes_four_assets_once_the_policy_declares_it():
    scores4 = {k: v for k, v in SCORES.items() if k != "L1"}
    status, weights, unallocated = frozen_size_status(scores4, cap=SINGLE_ETF_CAP, required_assets=4)
    assert status == AllocationStatus.READY.value
    assert sum(weights.values()) == pytest.approx(1.0)
    assert unallocated == pytest.approx(0.0, abs=1e-12)


def test_frozen_rebalance_contract_rejects_a_four_member_set():
    """The frozen rebalance rule asserts five members, so a four-asset policy needs an extension."""
    with pytest.raises(ValueError):
        rebalance_decision(("A", "B", "C", "D", "E"), ("A", "B", "C", "D"))


def test_frozen_size_raises_rather_than_returning_a_zero_portfolio():
    scores4 = {k: v for k, v in SCORES.items() if k != "L1"}
    with pytest.raises(PolicyError):
        frozen_size(scores4, cap=SINGLE_ETF_CAP, required_assets=5)


# ---------------------------------------------------------------------------
# B40 admission
# ---------------------------------------------------------------------------

def test_b40_threshold_boundary_is_inclusive():
    exact = cand("L1", exposure=MIN_TARGET_EXPOSURE_B40, second=0.0)
    under = cand("L1", exposure=MIN_TARGET_EXPOSURE_B40 - 1e-9, second=0.0)
    assert exact.passes_b40 is True
    assert under.passes_b40 is False
    assert under.b40_rejection_reason() == pol.REASON_TARGET_EXPOSURE_BELOW_THRESHOLD


def test_b40_rejects_a_non_largest_target():
    c = cand("L1", exposure=60.0, largest=False, second=70.0)
    assert c.passes_b40 is False
    assert c.b40_rejection_reason() == pol.REASON_TARGET_NOT_LARGEST_L2


def test_b40_rejects_incomplete_weight_evidence():
    c = IndustryCandidate(
        l2_code="L1", l2_name="x", final_score=1.0, etf_code="E", benchmark_code="B",
        mapping_type="PROXY_EXPOSURE", target_l2_exposure=90.0, second_largest_l2_exposure=5.0,
        dominance_margin=85.0, target_is_largest_l2=True, weight_quality="INCOMPLETE_WEIGHT_SET",
        liquidity_status="LIQUIDITY_ADMISSION_PASS", mean_amount_cny=1e9)
    assert c.passes_b40 is False
    assert c.b40_rejection_reason() == pol.REASON_WEIGHT_SET_INCOMPLETE


def test_a40_admits_a_non_largest_target_and_b40_does_not():
    """The single behavioural difference between the A and B shapes."""
    candidates = [cand(c, largest=(c != "L1")) for c in SCORES]
    vectors = vectors_for(candidates)
    a = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, vectors)
    b = evaluate_policy(POLICY_B40_RENORMALIZED, candidates, vectors)
    assert "L1" in a.etf_weights
    assert "L1" not in b.etf_weights
    assert any(code == "L1" and reason == pol.REASON_TARGET_NOT_LARGEST_L2 for code, reason in
               [(c.l2_code, r) for c, r in b.skipped])


# ---------------------------------------------------------------------------
# The three policies
# ---------------------------------------------------------------------------

def _four_plus_one():
    """Four B40-eligible industries plus one that fails only the largest-L2 test."""
    candidates = [cand("L1", exposure=44.83, largest=False, second=49.43)]
    candidates += [cand(c) for c in ("L2", "L3", "L4", "L5")]
    return candidates, vectors_for(candidates, own=50.0, leak=("LEAK", 50.0))


def test_a40_fully_invested_has_no_cash_and_uses_every_asset():
    candidates, vectors = _four_plus_one()
    r = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, vectors)
    assert r.cash_weight == 0.0
    assert len(r.etf_weights) == 5
    assert math.fsum(r.etf_weights.values()) == pytest.approx(1.0)


def test_b40_with_cash_retains_exactly_the_forfeited_reference_weight():
    """The central cash claim, to the last bit."""
    candidates, vectors = _four_plus_one()
    reference = base_target_weights(candidates)
    r = evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors)
    assert r.cash_weight == pytest.approx(reference["L1"], abs=1e-11)
    assert r.forfeited_weights["L1"] == pytest.approx(reference["L1"], abs=1e-11)
    for code in ("L2", "L3", "L4", "L5"):
        assert r.etf_weights[code] == pytest.approx(reference[code], abs=1e-11)


def test_b40_with_cash_does_not_redistribute():
    """Survivor weights are the reference weights, NOT a re-softmax over the survivor set."""
    candidates, vectors = _four_plus_one()
    reference = base_target_weights(candidates)
    cash = evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors)
    renorm = evaluate_policy(POLICY_B40_RENORMALIZED, candidates, vectors)
    survivors = ("L2", "L3", "L4", "L5")
    for code in survivors:
        assert cash.etf_weights[code] == pytest.approx(reference[code], abs=1e-11)
    # renormalisation must actually inflate, otherwise the two policies would be indistinguishable
    assert all(renorm.etf_weights[c] > reference[c] for c in survivors)
    assert renorm.cash_weight == 0.0


def test_risk_plus_cash_equals_one_for_every_policy():
    candidates, vectors = _four_plus_one()
    for policy in (POLICY_A40_FULLY_INVESTED, POLICY_B40_RENORMALIZED, POLICY_B40_WITH_CASH):
        r = evaluate_policy(policy, candidates, vectors)
        assert r.risk_asset_weight + r.cash_weight == pytest.approx(1.0, abs=1e-9)
        assert r.metrics["sum_risk_plus_cash"] == pytest.approx(1.0, abs=1e-9)


def test_cash_weight_equals_sum_of_skipped_reference_weights():
    candidates, vectors = _four_plus_one()
    reference = base_target_weights(candidates)
    r = evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors)
    expected = math.fsum(reference[c.l2_code] for c, _ in r.skipped)
    assert r.cash_weight == pytest.approx(expected, abs=1e-11)


def test_cap_still_binds_after_renormalisation():
    candidates, vectors = _four_plus_one()
    r = evaluate_policy(POLICY_B40_RENORMALIZED, candidates, vectors)
    assert max(r.etf_weights.values()) <= SINGLE_ETF_CAP + 1e-12
    assert r.metrics["cap_respected"] is True


def test_cap_and_sum_hold_for_many_random_signal_sets():
    """Deterministic sweep: the cap must never produce a weights vector that violates its contract."""
    for bump in (0.0, 0.5, 1.0, 2.0, 3.0):
        for drop in (0, 1, 2):
            codes = ["L1", "L2", "L3", "L4", "L5"][: 5 - drop]
            candidates = [cand(c, score=SCORES[c] + (bump if c == "L1" else 0.0)) for c in codes]
            weights = base_target_weights(candidates)
            assert math.fsum(weights.values()) == pytest.approx(1.0, abs=1e-9)
            assert max(weights.values()) <= SINGLE_ETF_CAP + 1e-12
            assert all(w > 0 for w in weights.values())


def test_renormalization_distortion_quantifies_the_uplift():
    candidates, vectors = _four_plus_one()
    reference = base_target_weights(candidates)
    renorm = evaluate_policy(POLICY_B40_RENORMALIZED, candidates, vectors)
    d = renormalization_distortion(reference, renorm.etf_weights)
    assert set(d["rows"]) == {"L2", "L3", "L4", "L5"}
    assert d["total_uplift"] == pytest.approx(reference["L1"], abs=1e-9)
    assert d["max_relative_uplift"] > 0


def test_no_survivor_is_an_error_not_an_empty_portfolio():
    candidates = [cand("L1", largest=False, second=90.0)]
    vectors = vectors_for(candidates)
    with pytest.raises(PolicyError):
        evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors)
    with pytest.raises(PolicyError):
        evaluate_policy(POLICY_B40_RENORMALIZED, candidates, vectors)


# ---------------------------------------------------------------------------
# Actual exposure / leakage
# ---------------------------------------------------------------------------

def test_actual_exposure_includes_leakage_from_every_held_etf():
    candidates = [cand("L1", exposure=60.0), cand("L2", exposure=60.0)]
    vectors = {
        "BM-L1": BenchmarkExposureVector("BM-L1", {"L1": 60.0, "LEAK": 40.0}),
        "BM-L2": BenchmarkExposureVector("BM-L2", {"L2": 60.0, "LEAK": 40.0}),
    }
    # cap=1.0: this test is about exposure arithmetic, and the frozen allocator rightly refuses a
    # two-asset set under the 35% cap (2 x 0.35 < 1).
    r = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, vectors, cap=1.0)
    assert r.actual_l2_exposure["LEAK"] == pytest.approx(0.40, abs=1e-9)
    assert r.metrics["largest_unintended_l2_code"] == "LEAK"
    assert r.metrics["largest_unintended_l2_weight"] == pytest.approx(0.40, abs=1e-9)


def test_incidental_target_exposure_is_not_counted_as_delivery():
    """A signalled industry the policy did NOT buy can still appear through leakage. That is not
    delivery of the signal, and conflating the two would let leakage masquerade as execution."""
    candidates = [cand("L1", largest=False, second=90.0), cand("L2", exposure=50.0)]
    vectors = {
        "BM-L1": BenchmarkExposureVector("BM-L1", {"L1": 40.0, "OTHER": 60.0}),
        "BM-L2": BenchmarkExposureVector("BM-L2", {"L2": 50.0, "L1": 50.0}),
    }
    r = evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors, cap=1.0)
    assert "L1" not in r.etf_weights
    assert "L1" in r.metrics["incidental_target_exposure"]
    assert r.metrics["incidental_target_weight_total"] > 0


def test_fidelity_gap_is_actual_minus_nominal():
    candidates = [cand("L1", exposure=44.83, largest=False, second=49.43)] + \
                 [cand(c, exposure=50.0) for c in ("L2", "L3", "L4", "L5")]
    vectors = {
        "BM-L1": BenchmarkExposureVector("BM-L1", {"L1": 44.83, "3705": 49.43, "rest": 5.74}),
        "BM-L2": BenchmarkExposureVector("BM-L2", {"L2": 50.0, "rest": 50.0}),
        "BM-L3": BenchmarkExposureVector("BM-L3", {"L3": 50.0, "rest": 50.0}),
        "BM-L4": BenchmarkExposureVector("BM-L4", {"L4": 50.0, "rest": 50.0}),
        "BM-L5": BenchmarkExposureVector("BM-L5", {"L5": 50.0, "rest": 50.0}),
    }
    a = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, vectors)
    # the A shape buys L1 but only ~45% of that money lands in L1
    assert a.fidelity_gap["L1"] < 0
    assert a.actual_l2_exposure["3705"] > 0.10


def test_unintended_exposure_is_zero_for_a_perfect_instrument():
    candidates = [cand("L1", exposure=100.0, second=0.0)]
    vectors = {"BM-L1": BenchmarkExposureVector("BM-L1", {"L1": 100.0})}
    r = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, vectors, cap=1.0)
    assert r.metrics["largest_unintended_l2_weight"] == 0.0
    assert r.metrics["weighted_target_l2_purity"] == pytest.approx(100.0)
    assert r.metrics["weighted_leakage"] == pytest.approx(0.0)


def test_purity_never_enters_the_alpha_weights():
    """Two instruments with identical scores but different purity must receive identical weight."""
    good = [cand("L1", exposure=90.0), cand("L2", exposure=90.0)]
    bad = [cand("L1", exposure=41.0, second=40.0), cand("L2", exposure=41.0, second=40.0)]
    vectors = vectors_for(good)
    a = evaluate_policy(POLICY_A40_FULLY_INVESTED, good, vectors, cap=1.0)
    b = evaluate_policy(POLICY_A40_FULLY_INVESTED, bad, vectors, cap=1.0)
    assert a.etf_weights == b.etf_weights


def test_liquidity_never_enters_the_alpha_weights():
    rich = [cand("L1", amount=5e9), cand("L2", amount=5e9)]
    poor = [cand("L1", amount=1e6), cand("L2", amount=1e6)]
    vectors = vectors_for(rich)
    a = evaluate_policy(POLICY_A40_FULLY_INVESTED, rich, vectors, cap=1.0)
    b = evaluate_policy(POLICY_A40_FULLY_INVESTED, poor, vectors, cap=1.0)
    assert a.etf_weights == b.etf_weights


# ---------------------------------------------------------------------------
# Cash semantics
# ---------------------------------------------------------------------------

def test_cash_is_not_an_asset_class():
    candidates, vectors = _four_plus_one()
    r = evaluate_policy(POLICY_B40_WITH_CASH, candidates, vectors)
    d = r.as_dict()
    assert d["cash_instrument_id"] == CASH_INSTRUMENT_ID
    assert d["cash_semantics"] == CASH_SEMANTICS
    assert d["cash_return_definition"] == CASH_RETURN_DEFINITION
    assert CASH_SEMANTICS == "UNALLOCATED_EXECUTION_CAPACITY"
    assert CASH_RETURN_DEFINITION == "UNDEFINED_IN_THIS_ROUND"
    assert CASH_INSTRUMENT_ID not in r.etf_weights, "cash must never appear among ETF holdings"
    assert len(r.etf_weights) == len(r.executed)


def test_cash_redistribution_is_declared_as_forbidden():
    assert pol.RETAIN_AS_CASH != pol.REDISTRIBUTE_TO_SURVIVORS
    assert RETAIN_AS_CASH == "RETAIN_AS_CASH"


def test_rebalance_trigger_names_executability_transitions():
    """A one-off data gap must not leave the account permanently under-invested.

    The rule refines the frozen ``EXECUTABLE_ETF_SET_CHANGE_ONLY`` rather than replacing it, and is
    deliberately implemented as a sibling function: the frozen ``rebalance_decision`` asserts an
    exactly-five-member set, and that assertion is what validates identity on the strict path, so
    relaxing it in place would trade an identity guarantee for a convenience.
    """
    assert REBALANCE_TRIGGER == "EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1"
    assert pol.REBALANCE_TRIGGER_FROZEN_PREDECESSOR == "EXECUTABLE_ETF_SET_CHANGE_ONLY"
    assert pol.REBALANCE_SIBLING_FUNCTION == "rebalance_decision_v2"
    assert pol.MAPPING_SELECTION_SIBLING_FUNCTION == "select_mappings_partial"


def test_cash_contract_constants_match_the_cash_policy_contract():
    assert pol.CASH_WEIGHT_FIELD == "unallocated_execution_capacity_weight"
    assert pol.CASH_RETURN_MODEL == "UNDEFINED_NOT_MODELLED_THIS_ROUND"
    assert pol.EXECUTION_REDISTRIBUTION_ENABLED is False
    assert pol.RENORMALISATION_MODE == "NEVER_RENORMALISE_ACROSS_EXECUTION_FILTER"
    assert pol.REDISTRIBUTED_WEIGHT_LITERAL == "0"
    assert pol.CASH_ORDER_OUTCOME == "NO_ORDER_UNEXECUTABLE_SIGNAL"


def test_an_industry_becoming_executable_changes_the_member_set():
    """Executability flip must be a member-set change, hence a rebalance."""
    before = ["L2", "L3", "L4", "L5"]
    after = ["L1", "L2", "L3", "L4", "L5"]
    assert set(before) != set(after)
    # and the frozen contract refuses the four-member set outright, which is why it needs extending
    with pytest.raises(ValueError):
        rebalance_decision(tuple(after), tuple(before))


# ---------------------------------------------------------------------------
# Model integrity
# ---------------------------------------------------------------------------

def test_the_model_ranking_is_never_modified_by_a_policy():
    candidates, vectors = _four_plus_one()
    for policy in (POLICY_A40_FULLY_INVESTED, POLICY_B40_RENORMALIZED, POLICY_B40_WITH_CASH):
        r = evaluate_policy(policy, candidates, vectors)
        assert [c.l2_code for c in r.candidates] == [c.l2_code for c in candidates]
        skipped_codes = [c.l2_code for c, _ in r.skipped]
        # an unexecutable industry stays in the candidate set; it is skipped for execution only
        for code in skipped_codes:
            assert code in [c.l2_code for c in r.candidates]


def test_softmax_is_a_distribution_and_is_uncapped():
    w = softmax([1.0, 2.0, 3.0])
    assert sum(w) == pytest.approx(1.0)
    assert max(w) > SINGLE_ETF_CAP  # the uncapped reference may breach; the allocator is what caps


def test_softmax_rejects_empty_input():
    with pytest.raises(PolicyError):
        softmax([])


# ---------------------------------------------------------------------------
# Artifact contracts (skipped when the runtime artifacts are absent)
# ---------------------------------------------------------------------------

def _load(rel):
    path = RUNTIME / rel
    if not path.exists():
        pytest.skip(f"runtime artifact not present: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_policy_contract_declares_no_model_or_strict_change():
    contract = _load("policies/policy_comparison_v1.json")
    assert contract["policies"]["B40_WITH_CASH"]["cash_weight"] == pytest.approx(0.35, abs=1e-9)
    assert contract["b40_rule"]["target_must_be_largest"] is True
    assert contract["not_formal_signal"] is True
    assert contract["classification"] == "EX_POST_ENGINEERING_PROXY_ANALYSIS"


def test_cash_policy_artifact_keeps_strict_result_intact():
    doc = _load("policies/policy_comparison_v1.json")
    assert doc["policies"]["B40_WITH_CASH"]["cash_weight"] > 0
    assert doc["policies"]["A40_FULLY_INVESTED"]["cash_weight"] == 0.0
    assert doc["policies"]["B40_RENORMALIZED"]["cash_weight"] == 0.0
    # strict precedence: 4901 must be the strict mapping on 399975
    for pol_name in ("A40_FULLY_INVESTED", "B40_RENORMALIZED", "B40_WITH_CASH"):
        execs = {e["l2_code"]: e for e in doc["policies"][pol_name]["executed"]}
        if "4901" in execs:
            assert execs["4901"]["mapping_type"] == "STRICT_MAPPING"

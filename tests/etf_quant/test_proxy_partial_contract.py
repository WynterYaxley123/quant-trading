"""Approved B40-with-cash is opt-in; frozen strict APIs retain their behavior."""
import pytest

from strategies.etf_quant.mapping.partial import select_mappings_partial
from strategies.etf_quant.portfolio import AllocationStatus, RebalanceStatus, rebalance_decision, size_targets
from strategies.etf_quant.portfolio.partial import rebalance_decision_v2
from strategies.etf_quant.portfolio.policy import (
    BenchmarkExposureVector, IndustryCandidate, POLICY_B40_WITH_CASH,
    evaluate_policy, base_target_weights,
)


SIGNALS = (("3706", 2.4), ("3703", 1.8), ("4901", 1.2), ("4803", 1.1), ("3701", 1.0))


def candidate(code, score, *, etf=None, mapping_type="PROXY_EXPOSURE", exposure=50.0,
              second=20.0, largest=True, quality="COMPLETE_WEIGHT_SET",
              liquidity="LIQUIDITY_ADMISSION_PASS", amount=1e7):
    return IndustryCandidate(code, code, score, etf or code + ".SH", "BM-" + code,
        mapping_type, exposure, second, exposure - second, largest, quality, liquidity, amount)


def pools():
    result = {}
    for code, score in SIGNALS:
        result[code] = [candidate(code, score)]
    result["3706"] = [candidate("3706", 2.4, exposure=44.83, second=49.43, largest=False)]
    result["4901"] = [candidate("4901", 1.2, mapping_type="STRICT_MAPPING", exposure=100., second=0.),
                       candidate("4901", 1.2, etf="PROXY.SH", exposure=99.)]
    return result


def select(p):
    return select_mappings_partial(SIGNALS, p, execution_policy=POLICY_B40_WITH_CASH)


def test_frozen_default_count_and_five_member_rebalance_unchanged():
    assert size_targets({str(i): 1.0 for i in range(4)}).status is AllocationStatus.INSUFFICIENT_ASSETS
    with pytest.raises(ValueError):
        rebalance_decision((), ("A", "B", "C", "D"))
    assert rebalance_decision((), ("A", "B", "C", "D", "E")) is RebalanceStatus.REQUIRED


def test_partial_requires_explicit_opt_in_and_preserves_strict_precedence():
    with pytest.raises(ValueError):
        select_mappings_partial(SIGNALS, pools(), execution_policy="STRICT")
    selected = select(pools())
    assert len(selected) == 5
    assert [c.l2_code for c in selected] == [x[0] for x in SIGNALS]
    assert selected[0].etf_code is None
    assert selected[0].mapping_type == "CASH_UNEXECUTABLE_SIGNAL"
    assert selected[2].mapping_type == "STRICT_MAPPING"
    assert selected[2].etf_code != "PROXY.SH"


def test_cash_not_redistributed_and_no_synthetic_instrument():
    selected = select(pools())
    vectors = {c.benchmark_code: BenchmarkExposureVector(c.benchmark_code, {c.l2_code: 100.0})
               for c in selected if c.etf_code}
    result = evaluate_policy(POLICY_B40_WITH_CASH, list(selected), vectors)
    reference = base_target_weights(list(selected))
    assert result.cash_weight == pytest.approx(reference["3706"])
    assert result.cash_weight + result.risk_asset_weight == pytest.approx(1.0)
    assert "CASH" not in result.etf_weights
    assert result.etf_weights == {c.l2_code: pytest.approx(reference[c.l2_code])
                                  for c in selected if c.etf_code}


@pytest.mark.parametrize("quality,liquidity,amount", [
    ("INCOMPLETE_WEIGHT_SET", "LIQUIDITY_ADMISSION_PASS", 1e7),
    ("COMPLETE_WEIGHT_SET", "BLOCKED", 1e7),
    ("COMPLETE_WEIGHT_SET", "LIQUIDITY_ADMISSION_PASS", float("nan")),
    ("COMPLETE_WEIGHT_SET", "LIQUIDITY_ADMISSION_PASS", None),
])
def test_incomplete_or_unliquid_proxy_fails_closed(quality, liquidity, amount):
    p = pools()
    p["3703"] = [candidate("3703", 1.8, quality=quality, liquidity=liquidity, amount=amount)]
    selected = select(p)
    assert selected[1].etf_code is None


def test_strict_failure_cannot_downgrade_to_proxy():
    p = pools()
    p["4901"][0] = candidate("4901", 1.2, mapping_type="STRICT_MAPPING", exposure=100.,
                              second=0., liquidity="BLOCKED")
    assert select(p)[2].etf_code is None


def test_all_five_unexecutable_retain_full_cash_without_an_order_asset():
    p = {code: [] for code, _ in SIGNALS}
    selected = select(p)
    result = evaluate_policy(POLICY_B40_WITH_CASH, list(selected), {})
    assert result.executed == ()
    assert result.etf_weights == {}
    assert result.risk_asset_weight == 0
    assert result.cash_weight == pytest.approx(1.0)
    assert all(c.etf_code is None for c in selected)


def test_malformed_numeric_evidence_fails_closed():
    p = pools()
    p["3703"] = [candidate("3703", 1.8, amount="unverified")]
    assert select(p)[1].etf_code is None
    p["3703"] = [candidate("3703", 1.8, exposure=float("nan"))]
    assert select(p)[1].etf_code is None


def test_one_etf_cannot_fake_two_members():
    p = pools()
    p["3703"] = [candidate("3703", 1.8, etf="SAME.SH")]
    p["4803"] = [candidate("4803", 1.1, etf="SAME.SH")]
    selected = select(p)
    assert selected[1].etf_code == "SAME.SH"
    assert selected[3].etf_code is None


def test_execution_member_transitions_both_directions_and_cash_is_not_member():
    policy = POLICY_B40_WITH_CASH
    four = ("A", "B", "C", "D")
    five = (*four, "E")
    assert rebalance_decision_v2(five, four, execution_policy=policy) is RebalanceStatus.REQUIRED
    assert rebalance_decision_v2(four, five, execution_policy=policy) is RebalanceStatus.REQUIRED
    assert rebalance_decision_v2(four, tuple(reversed(four)), execution_policy=policy) is RebalanceStatus.NO_REBALANCE
    with pytest.raises(ValueError):
        rebalance_decision_v2(four, (*four, "CASH"), execution_policy=policy)
    with pytest.raises(ValueError):
        rebalance_decision_v2(four, four, execution_policy="STRICT")

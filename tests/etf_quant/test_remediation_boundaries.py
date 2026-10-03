"""Synthetic boundary regressions; no formal lifecycle or external evidence."""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.evidence.schema import ConstituentRow, EvidenceError, parse_instant
from strategies.etf_quant.mapping.proxy import ProxyError, build_benchmark_exposure
from strategies.etf_quant.portfolio.policy import (
    POLICY_A40_FULLY_INVESTED,
    IndustryCandidate,
    PolicyError,
    evaluate_policy,
)
from strategies.etf_quant.runtime.exports import decode_table, encode_table

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/etf-quant-runner"))
from docker_mounts import MountInputError, bind_mount, reference_name


def candidate(code: str) -> IndustryCandidate:
    return IndustryCandidate(
        code,
        None,
        1.0,
        "ETF-" + code,
        "BM-" + code,
        "PROXY_EXPOSURE",
        41.0,
        49.0,
        -8.0,
        False,
        "COMPLETE_WEIGHT_SET",
        "LIQUIDITY_ADMISSION_PASS",
        1e6,
    )


@pytest.mark.parametrize("amount", [None, 0.0, -1.0, float("nan"), float("inf"), True])
def test_a40_rejects_invalid_liquidity_without_changing_valid_weights(amount):
    good = candidate("L1")
    bad = replace(candidate("L2"), mean_amount_cny=amount)
    result = evaluate_policy(POLICY_A40_FULLY_INVESTED, [good, bad], {}, cap=1.0)
    assert result.executed == (good,)
    assert result.skipped == ((bad, "NO_LIQUID_ETF"),)
    assert result.etf_weights == {"L1": 1.0}


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"liquidity_status": "BLOCKED"}, "NO_LIQUID_ETF"),
        ({"weight_quality": "INCOMPLETE_WEIGHT_SET"}, "WEIGHT_SET_INCOMPLETE"),
        ({"benchmark_code": None}, "NO_CANDIDATE"),
    ],
)
def test_a40_admission_fails_closed(changes, reason):
    bad = replace(candidate("L1"), **changes)
    assert bad.a40_rejection_reason() == reason
    with pytest.raises(PolicyError, match="A40_FULLY_INVESTED_NO_SURVIVOR"):
        evaluate_policy(POLICY_A40_FULLY_INVESTED, [bad], {}, cap=1.0)


def test_a40_preserves_dominance_exemption_and_determinism():
    candidates = [candidate("L1"), candidate("L2")]
    one = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, {}, cap=1.0)
    two = evaluate_policy(POLICY_A40_FULLY_INVESTED, candidates, {}, cap=1.0)
    assert one == two
    assert one.executed == tuple(candidates)
    assert one.etf_weights == {"L1": 0.5, "L2": 0.5}


@pytest.mark.parametrize("count", ["2", "oops", True, 1.5, 0, -1, float("inf")])
def test_proxy_count_is_an_explicit_domain_error(count):
    with pytest.raises(ProxyError, match="constituent_count_declared"):
        build_benchmark_exposure(
            benchmark_code="BM",
            benchmark_name="BM",
            constituent_date="2026-01-01",
            weight_source_type="OFFICIAL_WEIGHT",
            constituents=[],
            stock_to_l2={},
            constituent_count_declared=count,
        )


@pytest.mark.parametrize("weight", [None, True, "broken", float("nan"), float("inf")])
def test_constituent_weight_is_validated_before_float_conversion(weight):
    with pytest.raises(EvidenceError):
        ConstituentRow("000001", weight)


@pytest.mark.parametrize(
    "value", [True, False, np.bool_(True), np.bool_(False), pd.array([True], dtype="boolean")[0]]
)
def test_boolean_serialization_preserves_explicit_values(value):
    body = encode_table([{"flag": value}], ["flag"])
    frame = decode_table(body, ["flag"], {"flag": "bool"})
    assert bool(frame.flag.iloc[0]) == bool(value)


@pytest.mark.parametrize("value", [None, pd.NA, "True", 1, 0])
def test_boolean_missing_or_coerced_values_cannot_become_evidence(value):
    with pytest.raises(ValueError, match="explicit boolean"):
        decode_table(encode_table([{"flag": value}], ["flag"]), ["flag"], {"flag": "bool"})


def test_unparseable_historical_reason_token_is_preserved():
    with pytest.raises(EvidenceError) as caught:
        parse_instant("invalid", "observed_at")
    assert caught.value.details == {"field": "observed_at", "reason": "UNPARSEABLE"}


@pytest.mark.parametrize("value", ["a,b", "a:b", "a b", 'a"b', "a'b", "../ref", "a..b", "a/b", ""])
def test_mount_reference_grammar_rejects_fragments(value):
    with pytest.raises(MountInputError):
        reference_name(value)


def test_mount_reference_valid_and_space_in_path_stays_in_one_argument():
    assert reference_name("reference-v1.0_ab") == "reference-v1.0_ab"
    assert bind_mount(Path("/external/a b"), "/reference", readonly=True) == [
        "--mount",
        "type=bind,source=/external/a b,target=/reference,readonly",
    ]
    with pytest.raises(MountInputError):
        bind_mount(Path("/external/a,readonly=false"), "/reference", readonly=True)

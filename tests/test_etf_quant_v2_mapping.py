"""Mapping admission and collision behavior from synthetic facts only."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from strategies.etf_quant.portfolio.policy import IndustryCandidate, evaluate_policy
from strategies.etf_quant_v2.mapping import (
    DIRECT,
    PROXY,
    candidate_pools,
    canonical_class,
    evidence_admitted,
    liquidity_amount,
    select_mappings,
)

NOW = datetime(2026, 10, 8, 16, tzinfo=timezone(timedelta(hours=8)))


def row():
    return {
        "industry_code": "I0",
        "etf_code": "510001.SH",
        "tracking_index": "000001",
        "mapping_class": PROXY,
        "available_at": "2026-10-04T12:00:00+08:00",
        "evidence_date": "2026-09-30",
        "membership_date": "2026-09-24",
        "target_exposure": 45.0,
        "second_exposure": 30.0,
        "unknown_exposure": 0.0,
        "complete_weights": True,
        "active": True,
        "target_is_largest": True,
        "weight_source_sha256": "a" * 64,
        "product_source_sha256": "b" * 64,
        "confidence": "PRIMARY_COMPLETE",
        "weight_source_url": "https://www.cnindex.com.cn/",
    }


@pytest.mark.parametrize("threshold,expected", [(30, True), (40, True), (50, False)])
def test_thresholds(threshold, expected):
    assert evidence_admitted(row(), NOW, threshold) is expected


@pytest.mark.parametrize(
    "change",
    [
        {"target_is_largest": False},
        {"complete_weights": False},
        {"available_at": "2026-10-09T12:00:00+08:00"},
        {"evidence_date": "2026-07-01"},
        {"membership_date": "2026-07-01"},
        {"active": False},
        {"unknown_exposure": 20.0},
        {"weight_source_sha256": "unverified"},
        {"target_exposure": 10.0, "etf_name": "Industry exact name"},
    ],
)
def test_names_do_not_bypass_evidence(change):
    assert not evidence_admitted(row() | change, NOW, 40)


def test_direct_requires_complete_containment():
    direct = row() | {
        "mapping_class": DIRECT,
        "target_exposure": 100,
        "second_exposure": 0,
        "complete_constituent_containment": True,
    }
    assert evidence_admitted(direct, NOW, 40)
    assert not evidence_admitted(direct | {"complete_constituent_containment": False}, NOW, 40)


def candidate(code, etf, amount):
    return IndustryCandidate(
        code,
        None,
        0.0,
        etf,
        "000001",
        "PROXY_EXPOSURE",
        45,
        30,
        15,
        True,
        "COMPLETE_WEIGHT_SET",
        "LIQUIDITY_ADMISSION_PASS",
        amount,
    )


def test_liquidity_ranking_tie_collisions_and_cash_preserve_slots():
    ranked = [(f"I{i}", 0.0) for i in range(5)]
    pools = {
        "I0": (candidate("I0", "ETF_B", 200), candidate("I0", "ETF_A", 200)),
        "I1": (candidate("I1", "ETF_A", 1000), candidate("I1", "ETF_C", 100)),
        "I2": (candidate("I2", "ETF_A", 1000),),
    }
    selected = select_mappings(ranked, pools)
    assert [c.etf_code for c in selected] == ["ETF_A", "ETF_C", None, None, None]
    result = evaluate_policy("B40_WITH_CASH", list(selected), {})
    assert result.cash_weight == pytest.approx(0.6)
    assert result.etf_weights == {"I0": 0.2, "I1": 0.2}


def test_liquidity_requires_every_official_session_and_amount():
    days = [date(2026, 9, 1) + timedelta(days=i) for i in range(20)]
    bars = [
        {"trade_date": str(day), "open": 1.0, "volume": 100, "amount": 1000, "finalized": True}
        for day in days
    ]
    assert liquidity_amount(bars, days, days[-1]) == 1000
    bars[-1]["amount"] = None
    assert liquidity_amount(bars, days, days[-1]) is None
    assert liquidity_amount(bars[:-1], days, days[-1]) is None


def test_compatibility_aliases_and_missing_liquidity():
    assert canonical_class("STRICT_MAPPING") == DIRECT
    assert canonical_class("PROXY_EXPOSURE") == PROXY
    assert not candidate_pools({"proxy_threshold": 40, "entries": [row()]}, {}, NOW)


def test_v1_registry_is_independent_and_byte_frozen():
    root = Path(__file__).resolve().parents[1]
    assert (
        sha256(
            (root / "strategies/etf_quant/config/verified_mappings_v1.json").read_bytes()
        ).hexdigest()
        == "37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37"
    )
    assert (root / "strategies/etf_quant_v2/config/mapping-registry.json").resolve() != (
        root / "strategies/etf_quant/config/verified_mappings_v1.json"
    ).resolve()

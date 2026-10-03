"""Fail-closed mapping, provenance identity and ordering regressions."""

from dataclasses import replace
from datetime import datetime, time, timezone
from types import SimpleNamespace

import pytest

from benchmarks.fixtures import liquidity
from strategies.etf_quant.data.tradability import next_session
from strategies.etf_quant.domain import IndustryRanking
from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.mapping.pit import PITEvidenceBook, PITRecord, select_pit_mappings
from strategies.etf_quant.mapping.proxy import (
    COMPLETE_WEIGHT_SET,
    MAPPING_TYPE_PROXY,
    MAPPING_TYPE_STRICT,
    OFFICIAL_WEIGHT,
    ExecutionCandidate,
    build_benchmark_exposure,
    select_execution_candidate,
    solve_distinct_assignment,
)


def candidate(etf="510000.SH", **changes):
    base = ExecutionCandidate(
        "4901",
        etf,
        "SYN",
        MAPPING_TYPE_PROXY,
        80.0,
        20.0,
        60.0,
        True,
        COMPLETE_WEIGHT_SET,
        OFFICIAL_WEIGHT,
        1e6,
        "LIQUIDITY_ADMISSION_PASS",
    )
    return replace(base, **changes)


@pytest.mark.parametrize(
    "status,amount",
    [
        ("LIQUIDITY_ADMISSION_FAIL", 1e6),
        (None, 1e6),
        ("malformed", 1e6),
        ("LIQUIDITY_ADMISSION_PASS", None),
        ("LIQUIDITY_ADMISSION_PASS", float("nan")),
        ("LIQUIDITY_ADMISSION_PASS", float("inf")),
        ("LIQUIDITY_ADMISSION_PASS", 0),
        ("LIQUIDITY_ADMISSION_PASS", -1),
        ("LIQUIDITY_ADMISSION_PASS", True),
        ("LIQUIDITY_ADMISSION_PASS", "1000000"),
    ],
)
def test_zero_liquid_pool_fails_closed_with_reason(status, amount):
    bad = candidate(liquidity_status=status, mean_amount_cny=amount)
    assert select_execution_candidate([bad]) is None
    assert bad.liquidity_rejection_reason == "LIQUIDITY_ADMISSION_BLOCKED"


def test_liquidity_mixed_pool_deterministic_ties_and_strict_precedence():
    a, b = candidate("510000.SH"), candidate("510001.SH")
    bad = candidate("510002.SH", liquidity_status="LIQUIDITY_ADMISSION_FAIL", mean_amount_cny=1e12)
    assert select_execution_candidate([b, bad, a]) == a
    assert select_execution_candidate([a, bad, b]) == a
    strict = replace(bad, mapping_type=MAPPING_TYPE_STRICT)
    assert select_execution_candidate([strict, a]) is None


def test_partial_assignment_respects_all_quality_priorities():
    pools = {
        "A": {
            "same": candidate("same", target_l2_code="A", dominance_margin=5, mean_amount_cny=1000)
        },
        "B": {
            "same": candidate("same", target_l2_code="B", dominance_margin=40, mean_amount_cny=100)
        },
    }
    result = solve_distinct_assignment(["A", "B"], pools, require_all_targets=False)
    assert result.pairs == (("B", "same"),)


def test_provenance_binds_to_exact_selected_benchmark_and_not_last_etf_record():
    p = liquidity(1)
    now = datetime.combine(p.cutoff, time(18), timezone.utc)
    p.created_at = now
    taxonomy = default_taxonomy()
    codes = list(taxonomy.named_industry_codes)[:5]
    records = []
    for benchmark, weight in (("BEST", 80.0), ("LAST", 50.0)):
        exposure = build_benchmark_exposure(
            benchmark_code=benchmark,
            benchmark_name="SYNTHETIC",
            constituents=[
                {"security_code": "a", "weight_pct": weight},
                {"security_code": "b", "weight_pct": 100 - weight},
            ],
            stock_to_l2={"a": codes[0], "b": codes[1]},
            weight_source_type=OFFICIAL_WEIGHT,
            constituent_count_declared=2,
        )
        records.append(
            PITRecord(
                codes[0],
                "510000.SH",
                benchmark,
                benchmark,
                now,
                now,
                now,
                p.cutoff,
                p.cutoff,
                p.sessions[-1],
                exposure,
                benchmark,
                benchmark.lower() * 16,
            )
        )
    # The execution calendar must expose a future session; extend validity accordingly.
    from datetime import timedelta

    execution = p.cutoff + timedelta(days=1)
    p.sessions = (*p.sessions, execution)
    records = [replace(r, valid_through=execution) for r in records]
    registry = SimpleNamespace(entries=(), taxonomy_identity=taxonomy.identity)
    ranks = tuple(IndustryRanking(i + 1, c, 5.0 - i) for i, c in enumerate(codes))
    for ordered in (records, list(reversed(records))):
        result = select_pit_mappings(
            registry, ranks, p, PITEvidenceBook(tuple(ordered), "synthetic"), signal_at=now
        )
        selected = result["selected"][0]
        assert selected["tracking_index_code"] == "BEST"
        assert selected["evidence_id"] == "BEST" and selected["etf_name"] == "BEST"


def test_unsorted_sessions_choose_chronological_t_plus_one():
    from datetime import date

    signal = date(2024, 1, 2)
    assert next_session([date(2024, 1, 5), date(2024, 1, 3), signal], signal) == date(2024, 1, 3)

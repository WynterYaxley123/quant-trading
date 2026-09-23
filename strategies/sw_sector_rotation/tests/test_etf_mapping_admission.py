"""Offline evidence and temporal safeguards; no strategy execution."""

from dataclasses import replace

import pytest

from src.data.providers.etf_local import valid_daily_open
from strategies.sw_sector_rotation.src.portfolio.sector_etf_mapping import (
    MappingEvidence, daily_mapping_availability, mapping_admission,
    match_etfs_for_sectors, resolve_primary_mapping, validate_mapping_evidence,
)


CATALOG = {"801055": "工业金属", "801053": "贵金属"}


def unknown(code="801053"):
    return MappingEvidence(code, CATALOG[code])


def valid(code="801055", etf="sh512400"):
    return MappingEvidence(
        sector_code=code, sector_name=CATALOG[code],
        etf_code=etf, etf_name="有色金属ETF", market=etf[:2],
        tracking_index_code="930708", tracking_index_name="示例跟踪指数",
        mapping_status="VALIDATED",
        mapping_effective_from="2021-01-01",
        etf_listing_date="2021-02-01",
        source_provider="issuer", source_url="https://issuer.example/factsheet",
        source_retrieved_at="2026-09-20T12:00:00+08:00",
        evidence_type="issuer_factsheet", is_primary=True,
    )


BAR = {
    "etf_code": "sh512400", "date": "2021-02-02",
    "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1,
}


def bar_on(day):
    return {**BAR, "date": day}


def test_explicit_unknown_rows_and_sector_identity():
    validate_mapping_evidence([valid(), unknown()], CATALOG)
    with pytest.raises(ValueError, match="显式"):
        validate_mapping_evidence([], CATALOG)
    with pytest.raises(ValueError, match="全部"):
        validate_mapping_evidence([valid()], CATALOG)
    with pytest.raises(ValueError, match="代码/名称"):
        validate_mapping_evidence([valid(), replace(unknown(), sector_name="错误")], CATALOG)


def test_etf_code_and_primary_uniqueness():
    with pytest.raises(ValueError, match="市场前缀"):
        validate_mapping_evidence([replace(valid(), etf_code="512400"), unknown()], CATALOG)
    with pytest.raises(ValueError, match="不唯一"):
        validate_mapping_evidence([valid(), valid(etf="sh512660"), unknown()], CATALOG)


def test_multiple_candidates_must_be_explicit():
    a = replace(valid(), mapping_status="MULTIPLE_CANDIDATES", is_primary=False)
    b = replace(a, etf_code="sh512660")
    validate_mapping_evidence([a, b, unknown()], CATALOG)
    assert resolve_primary_mapping([a, b], "801055", "2024-01-01") is None
    with pytest.raises(ValueError, match="MULTIPLE_CANDIDATES"):
        validate_mapping_evidence([a, replace(b, mapping_status="SOURCE_INSUFFICIENT"), unknown()], CATALOG)


def test_verified_provenance_and_time_required():
    for field in ("tracking_index_code", "mapping_effective_from", "etf_listing_date",
                  "source_provider", "source_url", "source_retrieved_at", "evidence_type"):
        with pytest.raises(ValueError, match="缺关系、时点或来源"):
            validate_mapping_evidence([replace(valid(), **{field: None}), unknown()], CATALOG)
    with pytest.raises(ValueError, match="SHA256"):
        validate_mapping_evidence([replace(valid(), source_file="raw.pdf"), unknown()], CATALOG)
    with pytest.raises(ValueError, match="早于"):
        validate_mapping_evidence([replace(valid(), mapping_effective_to="2020-01-01"), unknown()], CATALOG)
    with pytest.raises(ValueError, match="日期"):
        validate_mapping_evidence([replace(valid(), etf_listing_date="20210201"), unknown()], CATALOG)


def test_no_mapping_before_effective_date_or_after_end():
    r = replace(valid(), mapping_effective_to="2021-12-31")
    assert resolve_primary_mapping([r], "801055", "2020-12-31") is None
    assert resolve_primary_mapping([r], "801055", "2021-06-01") == r
    assert resolve_primary_mapping([r], "801055", "2022-01-01") is None


def test_nonoverlapping_primary_change_is_deterministic():
    old = replace(valid(), mapping_effective_to="2021-12-31")
    new = replace(valid(etf="sh512660"), mapping_effective_from="2022-01-01",
                  etf_listing_date="2021-02-01")
    validate_mapping_evidence([old, new, unknown()], CATALOG)
    assert resolve_primary_mapping([old, new], "801055", "2021-12-31") == old
    assert resolve_primary_mapping([old, new], "801055", "2022-01-01") == new
    # A relationship switch between signal and execution cannot borrow either bar.
    assert not daily_mapping_availability([old, new], "801055", "2021-12-31",
                                          execution_date="2022-01-03",
                                          bar={**bar_on("2022-01-03"), "etf_code": "sh512660"},
                                          sector_bar_valid=True)["is_executable"]


def test_no_execution_before_listing_even_with_a_bar():
    r = valid()
    result = daily_mapping_availability([r], "801055", "2021-01-15",
                                        execution_date="2021-01-18", bar=bar_on("2021-01-18"),
                                        sector_bar_valid=True)
    assert result["is_mapping_active"] is True
    assert result["is_listed"] is False
    assert result["is_executable"] is False
    assert daily_mapping_availability([r], "801055", "2021-02-01",
                                      execution_date="2021-02-02", bar=BAR,
                                      sector_bar_valid=True)["is_executable"]


@pytest.mark.parametrize("bar", [
    None, {"open": 0, "high": 1.2, "low": 0.9, "close": 1.1},
    {"open": float("nan"), "high": 1.2, "low": 0.9, "close": 1.1},
    {"open": 1.0, "high": 0.9, "low": 0.8, "close": 1.1},
    {"open": 1.0, "high": 1.1, "low": -1.0, "close": 1.1},
])
def test_missing_or_invalid_bar_never_tradable(bar):
    assert valid_daily_open(bar) is False
    if bar is not None:
        bar = {**BAR, **bar}
    result = daily_mapping_availability([valid()], "801055", "2021-02-01",
                                        execution_date="2021-02-02", bar=bar,
                                        sector_bar_valid=True)
    assert result["is_executable"] is False


def test_sector_factor_gap_is_separate_from_etf_execution():
    result = daily_mapping_availability([valid()], "801055", "2021-02-01",
                                        execution_date="2021-02-02", bar=BAR,
                                        sector_bar_valid=False)
    assert result["is_etf_executable"] is True
    assert result["sector_bar_valid"] is False
    assert result["is_executable"] is False


def test_shared_etf_does_not_create_duplicate_orders_or_change_weight_helper():
    rows = [valid(), valid(code="801053")]
    validate_mapping_evidence(rows, CATALOG)
    assert resolve_primary_mapping(rows, "801053", "2021-02-01").etf_code == "sh512400"
    result = match_etfs_for_sectors(
        [("工业金属", 2.0), ("贵金属", 1.0)],
        {"工业金属": {"code": "512400"}, "贵金属": {"code": "512400"}},
    )
    assert len(result) == 1
    assert result[0]["score"] == 2.0


def test_admission_never_ready_from_unknown_or_partial_mapping():
    assert mapping_admission([unknown("801055"), unknown()], CATALOG, [0, 0]) == "ETF_MAPPING_NOT_ADMISSIBLE"
    assert mapping_admission([valid(), unknown()], CATALOG, [1, 1]) == "ETF_MAPPING_PARTIAL"


def test_no_future_backfill_when_listing_is_later_than_local_history():
    r = valid()
    assert not daily_mapping_availability([r], "801055", "2021-01-31",
                                          execution_date="2021-02-01", bar=bar_on("2021-02-01"),
                                          sector_bar_valid=True)["is_executable"]
    assert daily_mapping_availability([r], "801055", "2021-02-02",
                                      execution_date="2021-02-03", bar=bar_on("2021-02-03"),
                                      sector_bar_valid=True)["is_executable"]


def test_same_day_execution_and_missing_next_session_rejected():
    with pytest.raises(ValueError, match="晚于"):
        daily_mapping_availability([valid()], "801055", "2021-02-02",
                                   execution_date="2021-02-02", bar=BAR, sector_bar_valid=True)
    with pytest.raises(ValueError, match="不得提供"):
        daily_mapping_availability([valid()], "801055", "2021-02-02",
                                   execution_date=None, bar=BAR, sector_bar_valid=True)
    assert not daily_mapping_availability([valid()], "801055", "2021-02-02",
                                          execution_date=None, bar=None,
                                          sector_bar_valid=True)["is_executable"]


def test_bar_must_belong_to_selected_etf_and_next_session():
    for bad in (BAR, {**bar_on("2021-02-03"), "etf_code": "sh512660"}):
        result = daily_mapping_availability([valid()], "801055", "2021-02-02",
                                            execution_date="2021-02-03", bar=bad,
                                            sector_bar_valid=True)
        assert not result["has_bar"]
        assert not result["is_executable"]

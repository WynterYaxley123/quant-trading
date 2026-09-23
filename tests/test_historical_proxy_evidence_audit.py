"""Offline temporal/provenance tests; no market-data or network dependency."""

from dataclasses import replace
import socket

import pytest

from scripts.data.admit_shenwan_etf_mapping import (
    ProxyAdmissionEvidence, historical_proxy_admissible,
)
from scripts.data.audit_historical_proxy_evidence import (
    ROOT, EvidenceIntegrityFailure, audit, numeric_purity, point_status,
    verify_inputs,
)


def test_snapshot_and_publication_are_distinct_and_future_is_not_usable():
    assert point_status("2025-06-13", "2025-06-30", "2025-08-29") == "FUTURE_EVIDENCE"
    assert point_status("2025-06-30", "2025-06-30", "2025-08-29") == (
        "EX_POST_INTERVAL_VALIDATION_POINT_ONLY")
    assert point_status("2025-08-29", "2025-06-30", "2025-08-29") == (
        "PAST_SNAPSHOT_NOT_YET_AVAILABLE")
    assert point_status("2025-09-01", "2025-06-30", "2025-08-29") == (
        "PAST_SNAPSHOT_AVAILABLE_NO_INTERVAL_PROOF")


def test_same_day_publication_without_intraday_proof_is_not_ex_ante():
    assert point_status("2025-06-30", "2025-06-30", "2025-06-30") == (
        "EX_POST_INTERVAL_VALIDATION_POINT_ONLY")
    row = ProxyAdmissionEvidence(
        etf_code="synthetic", sector_code="801081",
        composition_as_of_date="2025-06-30", composition_available_at="2025-06-30",
        composition_source_type="OFFICIAL_ETF_PERIODIC_REPORT_INDEX_SLEEVE",
    )
    assert not historical_proxy_admissible(row, "2025-06-30")
    assert not historical_proxy_admissible(replace(row, available_before_signal=True), "2025-06-30")


def test_purity_is_independent_of_publication_and_returns():
    base = {
        "constituent_count": "100", "candidate_l2_count": "95",
        "candidate_l2_weight_share": "95", "unclassified_count": "0",
        "other_l2_count": "5", "official_publication_date": "2099-01-01",
        "strategy_return": "1000000",  # neither field is consulted
    }
    assert numeric_purity(base)
    assert not numeric_purity({**base, "candidate_l2_count": "60", "other_l2_count": "40"})
    assert not numeric_purity({**base, "candidate_l2_weight_share": "89.99"})
    assert not numeric_purity({**base, "unclassified_count": "1"})


@pytest.fixture(scope="module")
def actual_audit():
    return audit(ROOT)


def test_publication_inventory_provenance_and_classification(actual_audit):
    summary, publications, _ = actual_audit
    assert summary["manifest_verified_file_count"] == 67
    assert summary["publication_date_complete_count"] == 12
    assert summary["source_sidecar_as_of_mislabeled_count"] == 6
    assert summary["source_sidecar_as_of_missing_count"] == 6
    assert summary["snapshot_as_of_dates"] == [
        "2024-12-31", "2025-06-30", "2025-12-31"]
    assert all(row["official_publication_date"] > row["snapshot_as_of_date"]
               for row in publications)
    assert all(row["source_sha256"] and row["source_url"] for row in publications)
    assert all(row["classification_basis"] == "FIXED_CLASSIFICATION_COMPARISON"
               for row in publications)
    assert summary["strict_pit"] is False


def test_1436_is_not_trading_coverage(actual_audit):
    summary, _, sessions = actual_audit
    assert summary["hermes_reported_coverage_days"] == 1436
    assert summary["calendar_days_inclusive"] == 360
    assert summary["entity_calendar_days_inclusive"] == 1440
    assert summary["trading_session_count"] == 239
    assert summary["etf_session_denominator"] == len(sessions) == 956
    assert summary["ex_ante_point_coverage_entity_sessions"] == 0
    assert summary["ex_post_diagnostic_point_entity_sessions"] == 8
    assert summary["ex_ante_strict_admissible_entity_sessions"] == 0


def test_point_snapshots_do_not_validate_whole_interval(actual_audit):
    summary, _, sessions = actual_audit
    for code in ("512480", "512880", "159852", "159883"):
        rows = [r for r in sessions if r["etf_code"] == code]
        assert len(rows) == 239
        assert sum(r["ex_post_point_diagnostic"] for r in rows) == 2
        assert not any(r["ex_ante_point_coverage"] for r in rows)
        assert not any(r["proxy_admissible_at_t"] for r in rows)
        assert summary["per_etf"][code]["earliest_ex_ante_proxy_admissible_date"] is None
        assert next(r for r in rows if r["date"] == "2025-06-13")["evidence_status_at_t"] == (
            "FUTURE_EVIDENCE")
        assert next(r for r in rows if r["date"] == "2025-06-30")["evidence_status_at_t"] == (
            "EX_POST_INTERVAL_VALIDATION_POINT_ONLY")


def test_relationship_known_at_time_is_not_continuity(actual_audit):
    summary, _, sessions = actual_audit
    for code in ("512480", "512880", "159852", "159883"):
        start = next(r for r in sessions if r["etf_code"] == code and r["date"] == "2025-04-02")
        assert start["relationship_document_known_at_t"] is True
        assert start["relationship_continuity_known_at_t"] is False
        assert start["proxy_admissible_at_t"] is False
        assert summary["per_etf"][code]["can_use_on_2025_04_02"] is False


def test_512880_and_159852_purity_do_not_bypass_temporal_gate(actual_audit):
    summary, publications, _ = actual_audit
    first_512880 = next(r for r in publications if r["etf_code"] == "512880"
                        and r["snapshot_as_of_date"] == "2024-12-31")
    assert first_512880["candidate_weight_share"] == 94.47
    assert first_512880["unclassified_count"] == 1
    assert first_512880["numeric_purity_pass"] is False
    assert summary["per_etf"]["512880"]["numeric_purity_pass_snapshots"] == 2
    assert summary["per_etf"]["159852"]["numeric_purity_pass_snapshots"] == 0
    assert summary["per_etf"]["159883"]["numeric_purity_pass_snapshots"] == 0
    assert summary["per_etf"]["512480"]["numeric_purity_pass_snapshots"] == 3


def test_announcement_precedes_close_effectiveness_but_not_full_composition(actual_audit):
    summary, _, _ = actual_audit
    assert [(r["announcement_date"], r["effective_at_close"], r["first_affected_session"])
            for r in summary["announcement_events"]] == [
                ("2024-11-29", "2024-12-13", "2024-12-16"),
                ("2025-05-30", "2025-06-13", "2025-06-16"),
                ("2025-11-28", "2025-12-12", "2025-12-15"),
                ("2026-05-29", "2026-06-12", "2026-06-15"),
            ]
    assert all(not row["index_specific_full_constituents_proven"]
               for row in summary["announcement_events"])


def test_no_fixed_proxy_interval_or_formal_execution(actual_audit):
    summary, _, _ = actual_audit
    assert summary["direct_mapping_result"] == "ETF_MAPPING_NOT_ADMISSIBLE"
    assert summary["fixed_proxy_research_start"] is None
    assert summary["fixed_proxy_research_end"] is None
    assert summary["proxy_ex_ante_candidate_start"] is None
    assert summary["proxy_ex_ante_candidate_end"] is None
    assert summary["formal_executable_universe_count"] == 0
    assert summary["status"] == "PROXY MAPPING NOT ADMISSIBLE"


def test_manifest_hash_failure_stops_before_admission(monkeypatch):
    from scripts.data import audit_historical_proxy_evidence as module

    monkeypatch.setattr(module, "_sha256", lambda path: "invalid")
    with pytest.raises(EvidenceIntegrityFailure, match="DATA_EVIDENCE_INTEGRITY_FAILURE"):
        verify_inputs(ROOT)


def test_audit_never_calls_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    summary, _, _ = audit(ROOT)
    assert summary["trading_session_count"] == 239

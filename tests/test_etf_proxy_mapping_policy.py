"""Offline, synthetic point-in-time checks for derived ETF execution proxies."""

from dataclasses import replace

from scripts.data.admit_shenwan_etf_mapping import (
    ProxyAdmissionEvidence,
    current_proxy_status,
    historical_proxy_admissible,
)

DATE = "2025-04-02"


def complete_proxy() -> ProxyAdmissionEvidence:
    """A hypothetical complete record, not evidence for any real ETF."""
    return ProxyAdmissionEvidence(
        etf_code="test",
        sector_code="801081",
        methodology_official=True,
        methodology_historical_version_confirmed=True,
        methodology_available_at="2025-01-01",
        methodology_valid_from="2025-01-01",
        methodology_valid_to="2025-06-30",
        composition_source_type="FULL_INDEX_CONSTITUENTS_WITH_WEIGHTS",
        composition_source_official=True,
        composition_as_of_date="2025-01-01",
        composition_available_at="2025-01-01",
        composition_valid_from="2025-01-01",
        composition_valid_to="2025-06-30",
        constituent_count=100,
        count_share=95,
        weight_share=96,
        other_l2_count=5,
        unclassified_count=0,
        relationship_documented_from="2020-01-01",
        relationship_effective_from="2020-01-01",
        relationship_continuity_status="PROVEN_CONTINUOUS",
        relationship_evidence_available_at="2020-01-01",
        relationship_continuity_proven_at="2025-01-01",
        relationship_continuity_valid_through="2025-06-30",
        index_change_event_found=False,
        sw_classification_status="HISTORICAL_PIT",
        sw_classification_valid_from="2025-01-01",
        sw_classification_valid_to="2025-06-30",
        sw_classification_available_at="2025-01-01",
    )


def test_proxy_and_direct_mapping_are_distinct():
    record = complete_proxy()
    assert historical_proxy_admissible(record, DATE)
    assert not historical_proxy_admissible(replace(record, mapping_kind="DIRECT_MAPPING"), DATE)
    assert not historical_proxy_admissible(replace(record, official_direct_equivalence=True), DATE)


def test_future_snapshot_and_future_publication_never_validate_past_date():
    record = complete_proxy()
    assert not historical_proxy_admissible(
        replace(
            record,
            composition_as_of_date="2026-09-23",
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            composition_available_at="2026-09-23",
        ),
        DATE,
    )


def test_snapshot_does_not_create_an_undocumented_interval():
    record = complete_proxy()
    assert not historical_proxy_admissible(
        replace(
            record,
            composition_valid_from=None,
            composition_valid_to=None,
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            composition_valid_to="2025-04-01",
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            composition_valid_to=None,
        ),
        DATE,
    )


def test_same_day_evidence_requires_proven_before_signal_availability():
    record = complete_proxy()
    same_day = replace(record, composition_available_at=DATE)
    assert not historical_proxy_admissible(same_day, DATE)
    assert historical_proxy_admissible(replace(same_day, available_before_signal=True), DATE)


def test_pcf_top10_and_missing_constituents_are_not_full_index_evidence():
    record = complete_proxy()
    for source_type in (
        "ETF_REPLICATION_BASKET_PROXY",
        "TOP10_ONLY_PROXY",
        "NO_CONSTITUENT_EVIDENCE",
    ):
        assert not historical_proxy_admissible(
            replace(
                record,
                composition_source_type=source_type,
            ),
            DATE,
        )
    assert not historical_proxy_admissible(replace(record, weight_share=None), DATE)


def test_formal_concentration_and_classification_gates():
    record = complete_proxy()
    assert not historical_proxy_admissible(replace(record, count_share=89.99), DATE)
    assert not historical_proxy_admissible(replace(record, weight_share=89.99), DATE)
    assert not historical_proxy_admissible(replace(record, other_l2_count=11), DATE)
    assert not historical_proxy_admissible(replace(record, unclassified_count=1), DATE)
    assert not historical_proxy_admissible(
        replace(
            record,
            methodology_historical_version_confirmed=False,
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            methodology_available_at="2026-09-23",
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            sw_classification_status="FIXED_CLASSIFICATION_RESEARCH",
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            sw_classification_available_at="2026-09-23",
        ),
        DATE,
    )


def test_documented_relationship_or_no_change_search_is_not_continuity():
    record = complete_proxy()
    assert not historical_proxy_admissible(
        replace(
            record,
            relationship_effective_from=None,
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            relationship_continuity_status="EARLIEST_RELATIONSHIP_CONFIRMED_CONTINUITY_INCOMPLETE",
            index_change_event_found=False,
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            relationship_continuity_proven_at="2026-09-23",
        ),
        DATE,
    )
    assert not historical_proxy_admissible(
        replace(
            record,
            relationship_continuity_valid_through="2025-04-01",
        ),
        DATE,
    )
    # A listing date or earliest document date is never silently substituted.
    assert not historical_proxy_admissible(
        replace(
            record,
            relationship_effective_from=None,
            relationship_documented_from="2020-01-01",
        ),
        DATE,
    )


def test_current_observed_strength_is_only_descriptive():
    record = complete_proxy()
    pcf = replace(
        record,
        composition_source_type="ETF_REPLICATION_BASKET_PROXY",
        count_share=91.95,
        weight_share=None,
        other_l2_count=7,
        constituent_count=87,
        sw_classification_status="FIXED_CLASSIFICATION_RESEARCH",
    )
    assert current_proxy_status(pcf) == "PROXY_CURRENT_STRONG"
    assert not historical_proxy_admissible(pcf, DATE)
    top10 = replace(
        record,
        composition_source_type="TOP10_ONLY_PROXY",
        constituent_count=10,
        count_share=80,
        weight_share=87.5,
        other_l2_count=2,
    )
    assert current_proxy_status(top10) == "PROXY_CURRENT_STRONG"
    assert not historical_proxy_admissible(top10, DATE)
    mixed = replace(pcf, constituent_count=50, count_share=64, other_l2_count=18)
    assert current_proxy_status(mixed) == "PROXY_CURRENT_MIXED"
    assert not historical_proxy_admissible(mixed, DATE)
    absent = replace(
        record,
        composition_source_type="NO_CONSTITUENT_EVIDENCE",
        composition_source_official=False,
        constituent_count=0,
    )
    assert current_proxy_status(absent) == "PROXY_CURRENT_INSUFFICIENT"
    assert not historical_proxy_admissible(absent, DATE)


def test_policy_evaluation_never_calls_network(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert historical_proxy_admissible(complete_proxy(), DATE)

"""Unit contracts for the production PIT evidence layer.

These tests are pure: no network, no runtime artifacts, no sealed data. They pin
the four properties the runtime adapter cannot check for itself -- provenance,
completeness, attribution and forward-only availability -- plus the time traps
that a future Shadow run would otherwise be exposed to.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.evidence import (  # noqa: E402
    AVAILABILITY_FORWARD_ONLY, B40MappingEvidence, B40_MIN_TARGET_EXPOSURE,
    CLASSIFICATION_CONFLICT, CLASSIFICATION_OFFICIAL,
    CLASSIFICATION_UNCLASSIFIED, ClassificationRow, ClassificationSnapshot, ConstituentRow,
    EVIDENCE_SCHEMA_VERSION, EvidenceError, PinnedSource, SourcePin, TrackingRelation,
    WEIGHT_COMPLETE, WEIGHT_INCOMPLETE, WeightVector,
    adapter_classification_source_document, adapter_weight_source_document,
    build_classification_rows, build_classification_snapshot,
    build_tracking_relations_from_sse_catalog,
    build_weight_vector_from_constituent_rows, canonical_bytes, decide_b40_mapping,
    derive_l2_exposure, envelope, exposure_package, mapping_package, package_hash,
    parse_weight_pct, sha256_bytes, sha256_json, tracking_package, weight_package,
    write_package)

TAXONOMY = default_taxonomy()
L2_A = TAXONOMY.named_industry_codes[0]
L2_B = TAXONOMY.named_industry_codes[1]
L1_A = L2_A[:2] + "00"
L1_B = L2_B[:2] + "00"

OBSERVED = "2026-09-30T18:00:00+08:00"
AVAILABLE = "2026-09-30T18:05:00+08:00"
PUBLISHED = "2026-09-30T17:00:00+08:00"
CSI_URL = "https://www.csindex.com.cn/csindex-home/indexInfo/index-sample-information"
SWS_URL = "https://www.swsresearch.com/institute-sw/api/index_publish/current/"


def _source(**overrides) -> PinnedSource:
    payload = {
        "relative_path": "weights/000300_weights_v1.json", "source_url": CSI_URL,
        "source_publication_at": PUBLISHED, "evidence_observed_at": OBSERVED,
        "source_retrieved_at": OBSERVED, "source_sha256": "a" * 64,
        "content_type": "application/json;charset=UTF-8", "byte_length": 1234,
    }
    payload.update(overrides)
    return PinnedSource(**payload)


def _rows(pairs) -> list[dict]:
    return [{"security_code": code, "weight_pct": weight} for code, weight in pairs]


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------

def test_weight_parse_never_treats_a_placeholder_as_zero():
    assert parse_weight_pct("2.53%") == pytest.approx(2.53)
    assert parse_weight_pct(" 60 ") == pytest.approx(60.0)
    assert parse_weight_pct(3.5) == pytest.approx(3.5)
    for placeholder in (None, "", "-", "--", "- -", "—", "N/A", "n/a", True, False,
                        float("nan"), float("inf"), "abc"):
        assert parse_weight_pct(placeholder) is None


def test_complete_vector_requires_count_and_sum_agreement():
    vector = build_weight_vector_from_constituent_rows(
        benchmark_code="000300", benchmark_name="沪深300", provider="CSI",
        weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
        observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=2,
        rows=_rows([("600519", 60.0), ("000001", 40.0)]), valid_from="2026-09-30",
        source_publication_at=PUBLISHED, sources=(_source(),))
    assert vector.weight_quality == WEIGHT_COMPLETE
    assert vector.weight_sum == pytest.approx(100.0)


def test_short_weight_sum_stays_incomplete_and_is_never_renormalised():
    vector = build_weight_vector_from_constituent_rows(
        benchmark_code="000300", benchmark_name="沪深300", provider="CSI",
        weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
        observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=3,
        rows=_rows([("600519", 30.0), ("000001", 24.0)]), valid_from="2026-09-30",
        sources=(_source(),))
    assert vector.weight_quality == WEIGHT_INCOMPLETE
    assert vector.weight_sum == pytest.approx(54.0)  # not scaled to 100


def test_missing_constituent_weight_is_incomplete_not_zero():
    vector = build_weight_vector_from_constituent_rows(
        benchmark_code="000300", benchmark_name="沪深300", provider="CSI",
        weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
        observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=3,
        rows=_rows([("600519", 60.0), ("000001", 40.0)]) + [
            {"security_code": "600000", "weight_pct": "- -"}],
        valid_from="2026-09-30", sources=(_source(),))
    assert vector.weight_quality == WEIGHT_INCOMPLETE
    assert vector.constituent_count == 2
    assert any("UNPARSED_WEIGHT_ROWS=1" == note for note in vector.notes)


def _time_blocker(reason: str = ""):
    """A time-rule violation always surfaces as EVIDENCE_TIME_BLOCKER with a reason."""
    return pytest.raises(EvidenceError, match="EVIDENCE_TIME_BLOCKER")


def test_duplicate_security_in_a_vector_is_refused():
    with pytest.raises(EvidenceError, match="EVIDENCE_WEIGHT_BLOCKER") as error:
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
            observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=2,
            rows=_rows([("600519", 60.0), ("600519", 40.0)]), valid_from="2026-09-30",
            sources=(_source(),))
    assert error.value.details["reason"] == "DUPLICATE_SECURITY"
    with _time_blocker("EMPTY_VALIDITY"):
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
            observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=1,
            rows=_rows([("600519", 100.0)]), valid_from="2026-09-30", valid_to="2026-09-30",
            sources=(_source(),))


# ---------------------------------------------------------------------------
# time semantics
# ---------------------------------------------------------------------------

def test_availability_may_never_precede_observation():
    with _time_blocker("AVAILABLE_BEFORE_OBSERVED") as error:
        _source(evidence_observed_at="2026-09-30T18:00:00+08:00",
                evidence_available_at="2026-09-30T17:00:00+08:00")
    assert error.value.details["reason"] == "AVAILABLE_BEFORE_OBSERVED"
    with _time_blocker("AVAILABLE_BEFORE_OBSERVED") as error:
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
            observed_at="2026-09-30T18:00:00+08:00",
            available_at="2026-09-30T17:00:00+08:00", declared_constituent_count=1,
            rows=_rows([("600519", 100.0)]), valid_from="2026-09-30", sources=(_source(),))
    assert error.value.details["reason"] == "AVAILABLE_BEFORE_OBSERVED"


def test_publication_may_never_follow_observation():
    with _time_blocker("PUBLICATION_AFTER_OBSERVATION"):
        _source(source_publication_at="2026-10-01T09:00:00+08:00")
    with _time_blocker("PUBLICATION_AFTER_OBSERVATION"):
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
            observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=1,
            rows=_rows([("600519", 100.0)]), valid_from="2026-09-30",
            source_publication_at="2026-10-01T09:00:00+08:00", sources=(_source(),))


def test_naive_timestamp_is_refused_outright():
    with _time_blocker("TIMEZONE_REQUIRED"):
        _source(evidence_observed_at="2026-09-30T18:00:00")
    with _time_blocker("TIMEZONE_REQUIRED"):
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
            observed_at="2026-09-30T18:00:00", available_at=AVAILABLE,
            declared_constituent_count=1, rows=_rows([("600519", 100.0)]),
            valid_from="2026-09-30", sources=(_source(),))


def test_effective_date_after_availability_is_refused():
    """The trap the task calls out explicitly.

    Effective 2026-08-31, observed 2026-09-30, decision 2026-09-24. A record may
    never claim availability before the bytes were actually observed, so a vector
    whose described date post-dates its own availability is refused.
    """
    with _time_blocker("EFFECTIVE_DATE_AFTER_AVAILABILITY"):
        build_weight_vector_from_constituent_rows(
            benchmark_code="000300", benchmark_name="x", provider="CSI",
            weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-12-31",
            observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=1,
            rows=_rows([("600519", 100.0)]), valid_from="2026-09-30", sources=(_source(),))


def test_forward_only_availability_is_the_observation_instant():
    vector = build_weight_vector_from_constituent_rows(
        benchmark_code="000300", benchmark_name="x", provider="CSI",
        weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
        observed_at=OBSERVED, available_at=AVAILABLE, declared_constituent_count=1,
        rows=_rows([("600519", 100.0)]), valid_from="2026-09-30", sources=(_source(),))
    decision = datetime.fromisoformat("2026-09-24T18:00:00+08:00")
    assert vector.available_at > decision, "evidence must not be usable at 2026-09-24"
    earlier = datetime.fromisoformat("2026-09-30T17:59:00+08:00")
    assert vector.available_at > earlier, "evidence must not be usable before observation"


# ---------------------------------------------------------------------------
# official provenance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://www.csindex.com.cn/x",                       # not https
    "https://csindex.com.cn.evil.invalid/x",            # suffix spoof
    "https://evil.invalid/x",                           # foreign publisher
    "https://www.csindex.com.cn",                       # no path
    "https://www.csindex.com.cn/",                      # no path
    "https://user@www.csindex.com.cn/x",                # userinfo
    "https://www.csindex.com.cn:8443/x",                # port
])
def test_only_official_https_publishers_may_be_pinned(url):
    with pytest.raises(EvidenceError, match="EVIDENCE_OFFICIAL_SOURCE_BLOCKER"):
        _source(source_url=url)


@pytest.mark.parametrize("host", [
    "www.csindex.com.cn", "www.cnindex.com.cn", "query.sse.com.cn", "www.szse.cn",
    "www.swsresearch.com", "csindex.com.cn",
])
def test_every_official_publisher_is_accepted(host):
    assert _source(source_url=f"https://{host}/path/to/file.json").source_url


def test_source_path_may_not_escape_the_pinned_root():
    for path in ("../secrets.json", "/etc/passwd", "a\\b.json", "a/../b.json"):
        with pytest.raises(EvidenceError, match="EVIDENCE_OFFICIAL_SOURCE_BLOCKER"):
            _source(relative_path=path)


def test_pin_is_immutable_and_detects_tampering(tmp_path):
    pin = SourcePin(tmp_path / "sources")
    body = b'{"constituents":[]}'
    first = pin.pin_bytes(relative_path="weights/a.json", body=body, source_url=CSI_URL,
                          evidence_observed_at=OBSERVED, source_retrieved_at=OBSERVED)
    again = pin.pin_bytes(relative_path="weights/a.json", body=body, source_url=CSI_URL,
                          evidence_observed_at=OBSERVED, source_retrieved_at=OBSERVED)
    assert first.source_sha256 == again.source_sha256
    with pytest.raises(EvidenceError, match="IMMUTABILITY"):
        pin.pin_bytes(relative_path="weights/a.json", body=b'{"constituents":[1]}',
                      source_url=CSI_URL, evidence_observed_at=OBSERVED,
                      source_retrieved_at=OBSERVED)
    assert pin.verify()["ok"] is True
    (tmp_path / "sources" / "weights__a.json").write_bytes(b'{"tampered":true}')
    assert pin.verify()["ok"] is False


def test_pinned_bytes_are_stored_flat_and_hash_their_own_bytes(tmp_path):
    """The runtime adapter refuses a pinned filename containing a separator.

    A nested audit path is therefore flattened on write while remaining the audit
    identity, so both the adapter and a reviewer can find the same bytes.
    """
    pin = SourcePin(tmp_path / "sources")
    body = canonical_bytes({"constituents": [{"security_code": "600519", "weight_pct": 60.0}]})
    source = pin.pin_bytes(relative_path="weights/b.json", body=body, source_url=CSI_URL,
                           evidence_observed_at=OBSERVED, source_retrieved_at=OBSERVED)
    assert source.source_sha256 == sha256_bytes(body)
    assert source.relative_path == "weights__b.json"
    assert "/" not in source.relative_path and "\\" not in source.relative_path
    assert (tmp_path / "sources" / "weights__b.json").read_bytes() == body
    assert not (tmp_path / "sources" / "weights").exists()


def test_a_stored_name_that_would_escape_is_refused(tmp_path):
    pin = SourcePin(tmp_path / "sources")
    with pytest.raises(EvidenceError, match="EVIDENCE_OFFICIAL_SOURCE_BLOCKER") as error:
        pin.pin_bytes(relative_path="weights/c.json", stored_name="sub/c.json",
                      body=b"{}", source_url=CSI_URL, evidence_observed_at=OBSERVED,
                      source_retrieved_at=OBSERVED)
    assert error.value.details["reason"] == "STORED_NAME_MUST_BE_FLAT"


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def _classification_rows(pairs, *, quality=CLASSIFICATION_OFFICIAL):
    return tuple(ClassificationRow(
        security_code=code, shenwan_l1_code=code[:2] + "00", shenwan_l1_name="L1",
        shenwan_l2_code=l2, shenwan_l2_name=TAXONOMY.name_of(l2),
        taxonomy_version="SWCLASS2021", classification_effective_from="2026-09-30",
        evidence_observed_at=OBSERVED, evidence_available_at=AVAILABLE,
        classification_quality=quality) for code, l2 in pairs)


def _snapshot(rows) -> ClassificationSnapshot:
    return build_classification_snapshot(
        snapshot_id="SWS_L2_CURRENT_SNAPSHOT_20260930", rows=rows, observed_at=OBSERVED,
        available_at=AVAILABLE,
        sources=(_source(relative_path="sws/class.json", source_url=SWS_URL),))


def test_classification_must_use_a_sealed_taxonomy_code():
    with pytest.raises(Exception):
        ClassificationRow(
            security_code="600519", shenwan_l1_code="9900", shenwan_l1_name="x",
            shenwan_l2_code="9999", shenwan_l2_name="x", taxonomy_version="SWCLASS2021",
            classification_effective_from="2026-09-30", evidence_observed_at=OBSERVED,
            evidence_available_at=AVAILABLE)


def test_duplicate_classification_rows_are_refused():
    rows = _classification_rows([("600519", L2_A)])
    with pytest.raises(EvidenceError, match="DUPLICATE"):
        _snapshot(rows + rows)


def _vector(pairs, *, declared=None) -> WeightVector:
    rows = _rows(pairs)
    return build_weight_vector_from_constituent_rows(
        benchmark_code="000300", benchmark_name="x", provider="CSI",
        weight_source_type="OFFICIAL_WEIGHT", constituent_effective_date="2026-08-31",
        observed_at=OBSERVED, available_at=AVAILABLE,
        declared_constituent_count=declared if declared is not None else len(rows),
        rows=rows, valid_from="2026-09-30", sources=(_source(),))


def test_missing_classification_fails_closed():
    vector = _vector([("600519", 60.0), ("000001", 40.0)])
    snapshot = _snapshot(_classification_rows([("600519", L2_A)]))
    with pytest.raises(EvidenceError) as error:
        derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                           derivation_code_hash="b" * 64)
    assert error.value.code == "CLASSIFICATION_INCOMPLETE"


def test_classification_conflict_fails_closed():
    vector = _vector([("600519", 100.0)])
    conflicting = _classification_rows([("600519", L2_A)])
    conflicted_row = ClassificationRow(
        security_code="600519", shenwan_l1_code="9900", shenwan_l1_name="x",
        shenwan_l2_code=L2_A, shenwan_l2_name=TAXONOMY.name_of(L2_A),
        taxonomy_version="SWCLASS2021", classification_effective_from="2026-09-30",
        evidence_observed_at=OBSERVED, evidence_available_at=AVAILABLE,
        classification_quality=CLASSIFICATION_CONFLICT)
    snapshot = _snapshot((conflicted_row,))
    with pytest.raises(EvidenceError) as error:
        derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                           derivation_code_hash="b" * 64)
    assert error.value.code == "CLASSIFICATION_CONFLICT"


def test_unclassified_security_fails_closed():
    vector = _vector([("600519", 100.0)])
    snapshot = _snapshot(_classification_rows([("600519", L2_A)],
                                              quality=CLASSIFICATION_UNCLASSIFIED))
    with pytest.raises(EvidenceError) as error:
        derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                           derivation_code_hash="b" * 64)
    assert error.value.code == "CLASSIFICATION_INCOMPLETE"


# ---------------------------------------------------------------------------
# derived exposure
# ---------------------------------------------------------------------------

def test_derived_exposure_is_the_weighted_industry_sum():
    vector = _vector([("600519", 60.0), ("000001", 25.0), ("600000", 15.0)])
    snapshot = _snapshot(_classification_rows(
        [("600519", L2_A), ("000001", L2_A), ("600000", L2_B)]))
    exposure = derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                                  derivation_code_hash="b" * 64)
    assert exposure.exposure(L2_A) == pytest.approx(85.0)
    assert exposure.exposure(L2_B) == pytest.approx(15.0)
    assert exposure.is_largest(L2_A) is True
    assert exposure.unmapped_weight == 0.0
    assert exposure.largest_l2 == (L2_A, 85.0)


def test_production_available_at_is_the_maximum_of_every_input():
    vector = _vector([("600519", 100.0)])
    snapshot = _snapshot(_classification_rows([("600519", L2_A)]))
    exposure = derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                                  derivation_code_hash="b" * 64)
    assert exposure.production_available_at >= vector.available_at
    assert exposure.production_available_at >= snapshot.available_at
    assert exposure.production_available_at >= datetime.fromisoformat(AVAILABLE)
    assert exposure.availability_semantics == AVAILABILITY_FORWARD_ONLY


def test_derivation_cannot_predate_its_inputs():
    vector = _vector([("600519", 100.0)])
    snapshot = _snapshot(_classification_rows([("600519", L2_A)]))
    with _time_blocker("DERIVED_BEFORE_INPUT") as error:
        derive_l2_exposure(weights=vector, snapshot=snapshot,
                           derived_at="2026-09-30T09:00:00+08:00",
                           derivation_code_hash="b" * 64)
    assert error.value.details["reason"] == "DERIVED_BEFORE_INPUT"


def test_incomplete_weight_vector_cannot_produce_exposure():
    vector = _vector([("600519", 30.0), ("000001", 24.0)])
    assert vector.weight_quality == WEIGHT_INCOMPLETE
    snapshot = _snapshot(_classification_rows([("600519", L2_A), ("000001", L2_A)]))
    with pytest.raises(EvidenceError) as error:
        derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                           derivation_code_hash="b" * 64)
    assert error.value.code == "NO_OFFICIAL_COMPLETE_WEIGHT_VECTOR"


# ---------------------------------------------------------------------------
# B40 admission
# ---------------------------------------------------------------------------

def _shadow(*, a_weight=60.0, b_weight=40.0, a_is_second=False):
    """A two-security vector with an explicit, unambiguous industry split.

    Security ``600519`` carries ``a_weight`` and security ``000001`` carries
    ``b_weight``. Both are normally attributed to the same industry :data:`L2_A`,
    which makes the largest industry trivially the only industry; pass
    ``a_is_second=True`` to attribute them to :data:`L2_A` and :data:`L2_B`
    respectively, which is how the dominance rules are exercised.
    """
    rows = [("600519", a_weight), ("000001", b_weight)]
    vector = _vector(rows)
    mapping = [("600519", L2_A), ("000001", L2_B if a_is_second else L2_A)]
    snapshot = _snapshot(_classification_rows(mapping))
    return derive_l2_exposure(weights=vector, snapshot=snapshot, derived_at=AVAILABLE,
                              derivation_code_hash="b" * 64)


def test_b40_admits_only_above_threshold_and_largest():
    exposure = _shadow(a_weight=60.0, b_weight=40.0)
    assert exposure.exposure(L2_A) == pytest.approx(100.0)
    assert exposure.is_largest(L2_A) is True
    admitted = decide_b40_mapping(
        exposure=exposure, target_l2_code=L2_A, etf_code="510300.SH", etf_name="x",
        available_from=datetime.fromisoformat(AVAILABLE))
    assert admitted.admission_status == "ADMITTED"
    assert admitted.target_l2_exposure >= B40_MIN_TARGET_EXPOSURE
    assert admitted.passes_b40 is True


def test_b40_rejects_below_threshold():
    exposure = _shadow(a_weight=39.0, b_weight=61.0, a_is_second=True)
    assert exposure.exposure(L2_A) == pytest.approx(39.0)
    assert exposure.exposure(L2_B) == pytest.approx(61.0)
    mapping = decide_b40_mapping(
        exposure=exposure, target_l2_code=L2_A, etf_code="510300.SH", etf_name="x",
        available_from=datetime.fromisoformat(AVAILABLE))
    assert mapping.target_l2_exposure == pytest.approx(39.0)
    assert "TARGET_EXPOSURE_BELOW_THRESHOLD" in mapping.rejection_reason
    assert mapping.passes_b40 is False


def test_b40_rejects_target_that_is_not_largest():
    exposure = _shadow(a_weight=45.0, b_weight=55.0, a_is_second=True)
    assert exposure.is_largest(L2_A) is False
    mapping = decide_b40_mapping(
        exposure=exposure, target_l2_code=L2_A, etf_code="510300.SH", etf_name="x",
        available_from=datetime.fromisoformat(AVAILABLE))
    assert mapping.target_is_largest is False
    assert "TARGET_NOT_LARGEST_L2" in mapping.rejection_reason
    assert mapping.passes_b40 is False


def test_b40_mapping_available_from_is_never_before_the_exposure():
    exposure = _shadow(a_weight=100.0, b_weight=0.0)
    later = datetime.fromisoformat(AVAILABLE) + timedelta(days=1)
    mapping = decide_b40_mapping(
        exposure=exposure, target_l2_code=exposure.largest_l2[0], etf_code="510300.SH",
        etf_name="x", available_from=later)
    assert mapping.available_at == later
    assert mapping.available_at >= exposure.production_available_at


# ---------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------

def test_package_hash_covers_everything_but_itself():
    document = envelope("TEST_IDENTITY", {"value": 1})
    assert document["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert document["package_hash"] == package_hash(document)
    tampered = dict(document, value=2)
    assert package_hash(tampered) != document["package_hash"]


def test_package_write_is_append_only(tmp_path):
    path = tmp_path / "pkg.json"
    document = tracking_package(relation=_relation())
    write_package(path, document)
    write_package(path, document)  # identical rewrite is a no-op
    with pytest.raises(EvidenceError, match="IMMUTABILITY"):
        write_package(path, dict(document, relation="changed"))


def _relation() -> TrackingRelation:
    return TrackingRelation(
        exchange="SSE", etf_code="510300.SH", etf_name="沪深300ETF",
        benchmark_code="000300", benchmark_name="沪深300", index_provider="CSI",
        listing_status="LISTED", listing_date="2012-05-28",
        source_type="EXCHANGE_FUND_CATALOG", official_source_url=CSI_URL,
        source_publication_at=None, evidence_observed_at=OBSERVED,
        evidence_available_at=AVAILABLE, raw_source_hash="c" * 64, valid_from="2026-09-30")


def test_tracking_relation_requires_listing_status_and_official_source():
    assert _relation().listing_status == "LISTED"
    with pytest.raises(EvidenceError):
        TrackingRelation(
            exchange="SSE", etf_code="510300.SH", etf_name="x", benchmark_code="000300",
            benchmark_name="x", index_provider="CSI", listing_status="MAYBE",
            listing_date=None, source_type="EXCHANGE_FUND_CATALOG", official_source_url=CSI_URL,
            source_publication_at=None, evidence_observed_at=OBSERVED,
            evidence_available_at=AVAILABLE, raw_source_hash="c" * 64, valid_from="2026-09-30")


def test_sse_catalog_rows_without_a_tracked_index_are_skipped_not_invented():
    source = _source(relative_path="exchange/sse.json", source_url=CSI_URL)
    rows = [
        {"fundCode": "510300", "secNameFull": "沪深300ETF", "INDEX_CODE": "000300",
         "INDEX_NAME": "沪深300", "listingDate": "20120528"},
        {"fundCode": "518880", "secNameFull": "黄金ETF", "INDEX_CODE": "",
         "INDEX_NAME": "", "listingDate": "20130729"},
        {"fundCode": "999999", "secNameFull": "bad", "INDEX_CODE": "000001",
         "INDEX_NAME": "x", "listingDate": "not-a-date"},
    ]
    relations = build_tracking_relations_from_sse_catalog(
        catalog_rows=rows, observed_at=OBSERVED, available_at=AVAILABLE, source=source,
        valid_from="2026-09-30")
    assert [r.etf_code for r in relations] == ["510300.SH", "999999.SH"]
    assert relations[0].listing_date == "2012-05-28"
    assert relations[1].listing_date is None, "an unparsable date is missing, not guessed"


# ---------------------------------------------------------------------------
# adapter hand-off documents
# ---------------------------------------------------------------------------

def test_weight_source_document_carries_the_keys_the_adapter_cross_checks():
    rows = (ConstituentRow(security_code="600519", weight_pct=60.0),
            ConstituentRow(security_code="000001", weight_pct=40.0))
    body = adapter_weight_source_document(
        benchmark_code="000300", constituent_effective_date="2026-08-31", rows=rows,
        declared_constituent_count=2)
    document = json.loads(body.decode("utf-8"))
    assert document["declared_constituent_count"] == 2
    assert document["constituents"] == [{"security_code": "600519", "weight_pct": 60.0},
                                        {"security_code": "000001", "weight_pct": 40.0}]
    assert len({row["security_code"] for row in document["constituents"]}) == 2


def test_classification_source_document_matches_the_adapter_row_shape():
    rows = _classification_rows([("600519", L2_A)])
    body = adapter_classification_source_document(rows=rows, effective_date="2026-09-30",
                                                 available_at=AVAILABLE)
    document = json.loads(body.decode("utf-8"))
    row = document["classifications"][0]
    for key in ("security_code", "l2_code", "effective_date", "available_at"):
        assert key in row, key
    assert row["security_code"] == "600519"
    assert row["l2_code"] == L2_A


def test_envelope_identity_is_stable():
    assert tracking_package(relation=_relation())["identity"] == "ETF_TRACKING_RELATION_EVIDENCE_V1"
    vector = _vector([("600519", 100.0)])
    assert weight_package(weights=vector)["identity"] == "BENCHMARK_CONSTITUENT_WEIGHT_EVIDENCE_V1"
    assert sha256_json({"a": 1}) == sha256_bytes(canonical_bytes({"a": 1}))


def test_exposure_and_mapping_packages_are_hashable_and_immutable():
    exposure = _shadow(a_weight=100.0, b_weight=0.0)
    mapping = decide_b40_mapping(
        exposure=exposure, target_l2_code=exposure.largest_l2[0], etf_code="510300.SH",
        etf_name="x", available_from=datetime.fromisoformat(AVAILABLE))
    assert isinstance(mapping, B40MappingEvidence)
    assert mapping.production_available_at
    document = exposure_package(exposure=exposure)
    assert document["identity"] == "BENCHMARK_L2_EXPOSURE_PIT_PACKAGE_V1"
    assert document["package_hash"] == package_hash(document)
    mapping_document = mapping_package(mapping=mapping)
    assert mapping_document["identity"] == "B40_MAPPING_EVIDENCE_V1"
    assert mapping_document["package_hash"] == package_hash(mapping_document)


def test_timezone_offsets_are_preserved_not_normalised():
    source = _source(evidence_observed_at="2026-09-30T18:00:00+08:00",
                     source_retrieved_at="2026-09-30T10:00:00+00:00",
                     source_publication_at="2026-09-30T09:00:00+00:00")
    assert source.evidence_observed_at.endswith("+08:00")
    assert source.source_retrieved_at.endswith("+00:00")


# ---------------------------------------------------------------------------
# Provenance kind: an extraction is never passed off as provider bytes
# ---------------------------------------------------------------------------

def test_a_verbatim_source_needs_no_upstream_lineage():
    from strategies.etf_quant.evidence import (KIND_DOCUMENTED_EXTRACTION,
                                               KIND_VERBATIM_PROVIDER_BYTES, RawSourceRecord)
    record = RawSourceRecord(
        relative_path="exchange/sse.json", stored_name="exchange__sse.json",
        source_url="https://query.sse.com.cn/commonSoaQuery.do", source_sha256="a" * 64,
        byte_length=10, content_type="application/json",
        source_retrieved_at=OBSERVED, evidence_observed_at=OBSERVED,
        source_publication_at=None, kind=KIND_VERBATIM_PROVIDER_BYTES)
    assert record.as_dict()["kind"] == KIND_VERBATIM_PROVIDER_BYTES
    assert record.as_dict()["derived_from"] == []


def test_an_extraction_without_named_upstream_sources_is_refused():
    """This is the defect an independent audit found and this rule prevents."""
    from strategies.etf_quant.evidence import KIND_DOCUMENTED_EXTRACTION, RawSourceRecord
    with pytest.raises(EvidenceError, match="EVIDENCE_OFFICIAL_SOURCE_BLOCKER") as error:
        RawSourceRecord(
            relative_path="weights/a.json", stored_name="weights__a.json", source_url=CSI_URL,
            source_sha256="a" * 64, byte_length=10, content_type="application/json",
            source_retrieved_at=OBSERVED, evidence_observed_at=OBSERVED,
            source_publication_at=None, kind=KIND_DOCUMENTED_EXTRACTION)
    assert error.value.details["reason"] == "EXTRACTION_WITHOUT_UPSTREAM"


def test_an_extraction_with_upstream_sources_is_accepted_and_labelled():
    from strategies.etf_quant.evidence import KIND_DOCUMENTED_EXTRACTION, RawSourceRecord
    upstream = ({"capture": "raw_members/801012.json", "sha256": "b" * 64},)
    record = RawSourceRecord(
        relative_path="weights/a.json", stored_name="weights__a.json", source_url=CSI_URL,
        source_sha256="a" * 64, byte_length=10, content_type="application/json",
        source_retrieved_at=OBSERVED, evidence_observed_at=OBSERVED,
        source_publication_at=None, kind=KIND_DOCUMENTED_EXTRACTION,
        derived_from=upstream)
    payload = record.as_dict()
    assert payload["kind"] == KIND_DOCUMENTED_EXTRACTION
    assert payload["derived_from"] == [dict(upstream[0])]


def test_the_manifest_counts_both_kinds_separately(tmp_path):
    from strategies.etf_quant.evidence import KIND_DOCUMENTED_EXTRACTION
    pin = SourcePin(tmp_path / "sources")
    pin.pin_bytes(relative_path="exchange/sse.json", body=b'{"pageHelp":{"data":[]}}',
                  source_url=CSI_URL, evidence_observed_at=OBSERVED,
                  source_retrieved_at=OBSERVED)
    pin.pin_bytes(relative_path="weights/a.json", body=b'{"constituents":[]}',
                  source_url=CSI_URL, evidence_observed_at=OBSERVED,
                  source_retrieved_at=OBSERVED, kind=KIND_DOCUMENTED_EXTRACTION,
                  derived_from=({"capture": "exchange__sse.json", "sha256": "c" * 64},))
    manifest_path = pin.write_manifest(tmp_path / "manifest.json")
    manifest = json.loads(manifest_path.read_bytes().decode("utf-8"))
    assert manifest["source_count"] == 2
    assert manifest["verbatim_provider_bytes"] == 1
    assert manifest["documented_extractions"] == 1
    assert "reproducibility_note" in manifest


# ---------------------------------------------------------------------------
# Classification effective dates come from the provider, not from the build
# ---------------------------------------------------------------------------

def test_official_per_security_effective_dates_are_used_when_supplied():
    rows = build_classification_rows(
        assignments={"600519": (L1_A, "a", L2_A, TAXONOMY.name_of(L2_A)),
                     "000001": (L1_B, "b", L2_B, TAXONOMY.name_of(L2_B))},
        observed_at=OBSERVED, available_at=AVAILABLE, effective_from="2026-09-30",
        effective_dates={"600519": "2021-12-13", "000001": "2022-01-18"})
    by_code = {row.security_code: row for row in rows}
    assert by_code["600519"].classification_effective_from == "2021-12-13"
    assert by_code["000001"].classification_effective_from == "2022-01-18"


def test_a_provider_date_cannot_post_date_the_snapshot():
    """A provider date later than the fallback would make a row effective after the
    snapshot it belongs to, which cannot be represented honestly."""
    rows = build_classification_rows(
        assignments={"600519": (L1_A, "a", L2_A, TAXONOMY.name_of(L2_A))},
        observed_at=OBSERVED, available_at=AVAILABLE, effective_from="2026-09-30",
        effective_dates={"600519": "2027-01-01"})
    assert rows[0].classification_effective_from == "2026-09-30"


def test_a_security_without_a_provider_date_falls_back_and_is_countable():
    rows = build_classification_rows(
        assignments={"600519": (L1_A, "a", L2_A, TAXONOMY.name_of(L2_A)),
                     "000001": (L1_B, "b", L2_B, TAXONOMY.name_of(L2_B))},
        observed_at=OBSERVED, available_at=AVAILABLE, effective_from="2026-09-30",
        effective_dates={"600519": "2021-12-13"})
    stated = [row for row in rows if row.classification_effective_from == "2021-12-13"]
    defaulted = [row for row in rows if row.classification_effective_from == "2026-09-30"]
    assert len(stated) == 1 and len(defaulted) == 1

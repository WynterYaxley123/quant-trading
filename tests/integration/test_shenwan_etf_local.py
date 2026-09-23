"""Frozen-local-data audit only; no network, download, import or backtest."""

from pathlib import Path

import pytest

from scripts.data.admit_shenwan_etf_mapping import _load_official_evidence, build
from src.data.providers.etf_local import read_local_etf_snapshot
from src.data.loaders.shenwan_sector_loader import load_sector_catalog


@pytest.mark.integration
def test_frozen_local_etf_metadata_does_not_claim_listing_date():
    metadata, bars = read_local_etf_snapshot(Path("data/hikyuu"))
    assert len(metadata) == 8
    assert set(metadata["etf_code"]) == {
        "sh510300", "sh510500", "sh512400", "sh512660", "sh588000",
        "sz159745", "sz159915", "sz159934",
    }
    assert metadata["listing_date"].isna().all()
    assert metadata["bar_count"].sum() == len(bars)
    assert metadata["local_data_end"].eq("2026-09-18").all()


@pytest.mark.integration
def test_offline_etf_admission_reports_evidence_gap(tmp_path):
    report = build(
        sector_dir=Path("data/processed/shenwan"),
        hikyuu_dir=Path("data/hikyuu"),
        output_dir=tmp_path,
    )
    assert report["status"] == "ETF_MAPPING_NOT_ADMISSIBLE"
    assert report["mapping_admission"] == "ETF_MAPPING_NOT_ADMISSIBLE"
    assert report["evidence_integrity"] == "PASS"
    assert report["official_document_count"] == report["manifest_document_count"] == 29
    assert report["catalog_provenance_match_count"] == report["catalog_etf_count"] == 22
    assert report["raw_etf_integrity_count"] == 21
    assert report["raw_etf_total_rows"] == 40445
    assert report["official_listing_complete_count"] == 22
    assert report["tracking_index_name_complete_count"] == 22
    assert report["mapping_effective_from_complete_count_official"] == 0
    assert report["official_evidence_status_counts"] == {
        "VALIDATED": 0, "PARTIAL_EVIDENCE": 6,
        "NOT_DIRECT_MAPPING": 15, "CONFLICT": 1, "UNVERIFIED": 0,
    }
    assert report["partial_candidate_sector_count"] == 6
    assert report["partial_candidate_notice"] == "CANDIDATE ONLY; NOT ADMITTED FOR BACKTEST"
    assert report["level2_sector_count"] == 124
    assert report["mapped_sector_count"] == 0
    assert report["strict_validated_coverage_ratio"] == 0
    assert report["latest_executable_sector_count"] == 0
    assert report["historical_executable_max"] == 0
    assert report["etf_159915"]["local_hikyuu_bar_count"] == 3589
    assert report["etf_159915"]["independent_raw_refresh"] is False
    assert report["sector_data_admission"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert report["strict_pit"] is False
    assert report["candidate_session_count"] == 239
    assert report["sector_plus_etf_candidate_start"] is None
    assert report["sector_plus_etf_candidate_end"] is None
    assert (tmp_path / "etf_mapping_evidence.csv").is_file()
    assert (tmp_path / "etf_daily_availability.csv").is_file()
    assert (tmp_path / "etf_daily_coverage.csv").is_file()


@pytest.mark.integration
def test_reconciled_field_provenance_and_legacy_reviews_are_kept_separate():
    catalog = load_sector_catalog(Path("data/processed/shenwan"))
    codes = {str(r.sector_code): str(r.sector_name) for r in catalog.itertuples()}
    evidence = _load_official_evidence(
        Path("."), Path("data/processed/shenwan_etf_mapping"), codes,
    )
    assert len(evidence["sources"]) == 29
    assert len(evidence["legacy"]) == 25
    assert len(evidence["reference"]) == 48
    reviews = {(r["legacy_sector_name"], r["legacy_etf_code"]): r for r in evidence["legacy"]}
    assert reviews[("计算机设备", "159852")]["final_evidence_status"] == "NOT_DIRECT_MAPPING"
    assert reviews[("IT服务Ⅱ", "159852")]["final_evidence_status"] == "NOT_DIRECT_MAPPING"
    assert reviews[("电网设备", "159616")]["final_evidence_status"] == "CONFLICT"
    assert reviews[("装修建材", "159745")]["legacy_conflict_type"] == "MANAGER_NAME_CONFLICT"
    assert reviews[("银行", "512800")]["legacy_conflict_type"] == "LEGACY_SECTOR_NOT_IN_CANONICAL_L2_CATALOG"
    assert any(r["official_evidence_status"] == "UNVERIFIED_OUTSIDE_INVESTIGATED_UNIVERSE"
               for r in evidence["reference"])

"""Frozen-local-data audit only; no network, download, import or backtest."""

from pathlib import Path

import pytest

from scripts.data.admit_shenwan_etf_mapping import build
from src.data.providers.etf_local import read_local_etf_snapshot


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
    assert report["status"] == "ETF_DATA_GAP"
    assert report["mapping_admission"] == "ETF_MAPPING_NOT_ADMISSIBLE"
    assert report["level2_sector_count"] == 124
    assert report["mapped_sector_count"] == 0
    assert report["sector_data_admission"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert report["strict_pit"] is False
    assert report["candidate_session_count"] == 239
    assert report["sector_plus_etf_candidate_start"] is None
    assert report["sector_plus_etf_candidate_end"] is None
    assert (tmp_path / "etf_mapping_evidence.csv").is_file()
    assert (tmp_path / "etf_daily_availability.csv").is_file()
    assert (tmp_path / "etf_daily_coverage.csv").is_file()

"""Pure offline checks: official Layer-1 evidence is not Layer-2 admission."""

from scripts.data.admit_shenwan_etf_mapping import _evidence_diagnostics


def _row(code, status, sector=""):
    return {
        "etf_code": code,
        "etf_name": f"ETF {code}",
        "fund_manager": "official manager",
        "tracking_index_code": "",
        "tracking_index_name": "official index",
        "tracking_relationship": "CURRENT_RELATIONSHIP_ONLY",
        "official_listing_date": "2021-01-05",
        "fund_establishment_date": "2020-12-31",
        "mapping_effective_from": "",
        "mapping_effective_to": "",
        "sector_code": sector,
        "sector_name": "软件开发" if sector else "",
        "evidence_status": status,
    }


def test_partial_layer1_listing_does_not_prove_historical_layer2_mapping():
    evidence = {
        "catalog": [
            _row("159852", "PARTIAL_EVIDENCE", "801104"),
            _row("510300", "NOT_DIRECT_MAPPING"),
            _row("159616", "CONFLICT"),
        ],
        "integrity": {"disk_pdf_count": 3, "manifest_file_count": 3},
        "sources": [{}, {}, {}],
        "raw_file_count": 2,
        "raw_total_rows": 5,
        "legacy": [{"final_evidence_status": "NOT_DIRECT_MAPPING"}],
        "reference": [{"official_evidence_status": "UNVERIFIED_OUTSIDE_INVESTIGATED_UNIVERSE"}],
    }
    result = _evidence_diagnostics(evidence, {"801104": "软件开发", "801103": "IT服务Ⅱ"})
    assert result["official_listing_complete_count"] == 3
    assert result["mapping_effective_from_complete_count_official"] == 0
    assert result["official_evidence_status_counts"]["VALIDATED"] == 0
    assert result["partial_candidate_sector_count"] == 1
    assert result["partial_candidate_coverage_ratio"] == 0.5
    assert "NOT ADMITTED FOR BACKTEST" in result["partial_candidate_notice"]
    assert result["partial_candidates"][0]["layer2_evidence"] == "NOT_PROVEN"
    assert result["partial_candidates"][0]["layer1_evidence"] == "CURRENT_RELATIONSHIP_ONLY"
    assert result["partial_candidates"][0]["mapping_effective_from"] is None
    assert result["reference_review_treatment"].startswith("REFERENCE ONLY")

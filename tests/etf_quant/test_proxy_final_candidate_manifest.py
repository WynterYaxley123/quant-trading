"""Metadata-only candidate integrity; never reads market rows or sealed research."""

from __future__ import annotations

import hashlib
import json
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json"


def test_final_proxy_candidate_integrity_reread():
    candidate = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert candidate["schema_version"] == "1.0.0"
    assert candidate["candidate_status"] == "READY_FOR_FUTURE_SHADOW"
    assert candidate["policy_approved"] is True
    assert candidate["policy"] == "B40_WITH_CASH"
    assert candidate["execution_policy"] == "B40_WITH_CASH"
    assert candidate["ready_for_shadow"] is True
    assert candidate["shadow_epoch_created"] is False
    # Forward-only: the evidence freezes at 2026-09-29/30, so shadow can only
    # ever start on a future eligible signal cycle -- never at 2026-09-24.
    assert candidate["production_ready_from"] == "READY_FOR_NEXT_ELIGIBLE_FUTURE_SIGNAL_CYCLE"
    assert candidate["production_pit_evidence_available_from"] == "2026-09-29T23:05:26+09:00"
    assert candidate["production_pit_evidence_ready"] is True
    assert candidate["technical_shadow_readiness"] == "PASS"
    assert candidate["etf_quant_proxy_ready_for_shadow"] is True
    assert candidate["minimum_target_exposure"] == 0.4
    assert candidate["target_must_be_largest"] is True
    assert candidate["strict_precedence"] is True
    assert candidate["historical_reference_only"] is True
    assert candidate["top5_signal"] == ["3706", "3703", "4901", "4803", "3701"]
    assert candidate["h30463"]["evidence_status"] == "UNRESOLVED_FAIL_CLOSED"
    assert candidate["3706_execution_result"] == "CASH_UNEXECUTABLE_SIGNAL"
    assert candidate["cash_policy"]["redistributed_weight"] == 0
    assert candidate["cash_policy"]["return_model"] is None
    assert candidate["cash_policy"]["is_etf_member"] is False
    assert candidate["cash_redistribution"] is False
    assert candidate["pit_evidence_contract"]["historical_reference_may_not_be_backdated"] is True
    assert candidate["dry_run_result"]["certified"] is True
    assert candidate["dry_run_result"]["new_formal_business_records"] == 0
    rows = candidate["reference_mapping"]
    assert [row["l2_code"] for row in rows] == candidate["top5_signal"]
    assert rows[0]["etf_code"] is None and rows[0]["cash_retained_weight"] == 0.35
    assert len({row["etf_code"] for row in rows if row["etf_code"]}) == 4
    assert all(row["target_exposure_percent"] >= 40 for row in rows if row["etf_code"])
    assert all(
        row["liquidity_status"] == "LIQUIDITY_ADMISSION_PASS" for row in rows if row["etf_code"]
    )
    assert isclose(
        sum(row["executed_etf_weight"] for row in rows),
        candidate["risk_asset_weight"],
        abs_tol=1e-11,
    )
    assert isclose(
        sum(row["cash_retained_weight"] for row in rows), candidate["cash_weight"], abs_tol=1e-11
    )
    assert isclose(candidate["risk_asset_weight"] + candidate["cash_weight"], 1.0)
    assert all(value is False for value in candidate["security_assertions"].values())
    for item in candidate["source_integrity"].values():
        if isinstance(item, dict) and "path" in item:
            body = (ROOT / item["path"]).read_bytes()
            expected = item.get("sha256", item.get("containing_file_sha256"))
            if item["path"] == "strategies/etf_quant/runtime/shadow.py":
                # Candidate pins the certified B40 baseline, NOT the authorized
                # additive T0 lifecycle extension. Neither Candidate nor the
                # baseline hash is rewritten to make this extension pass.
                assert (
                    expected == "0bc5605d93b8a29fa670b3b9c97c5b8ba79234fe0b28dfaa84639e2c347050a1"
                )
                extension = json.loads(
                    (ROOT / "reports/etf_quant/autonomous_code_integrity_v1.json").read_bytes()
                )
                assert (
                    extension["candidate_sha256"]
                    == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
                )
                assert (
                    extension["certified_baseline_sha"]
                    == "dd96a3ae2b84e1c93bc15f2a748e213d7446ae1b"
                )
                assert hashlib.sha256(body).hexdigest() == extension["files"][item["path"]]
            else:
                assert hashlib.sha256(body).hexdigest() == expected
    original = json.loads(
        (ROOT / candidate["source_integrity"]["reference_portfolio"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert original["top5_signal"] == candidate["top5_signal"]
    assert (
        original["actual_l2_exposure"]["4802"]
        == candidate["largest_unintended_l2"]["account_weight"]
    )
    for row in rows[1:]:
        source = next(r for r in original["per_industry_mapping"] if r["l2_code"] == row["l2_code"])
        assert source["etf_code"] == row["etf_code"]
        assert source["mapping_type"] == row["mapping_type"]
        assert source["weight"] == row["executed_etf_weight"]
        assert source["target_l2_exposure"] == row["target_exposure_percent"]


def test_runtime_readiness_metadata_cannot_claim_unadmitted_production_evidence():
    readiness = json.loads(
        (ROOT / "reports/etf_quant/codex_b40_cash_runtime_readiness_v1.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert (
        readiness["technical_shadow_readiness"] == candidate["technical_shadow_readiness"] == "PASS"
    )
    assert readiness["etf_quant_proxy_ready_for_shadow"] is candidate["ready_for_shadow"] is True
    assert readiness["shadow_epoch_created"] is candidate["shadow_epoch_created"] is False
    assert readiness["formal_business_records_created"] == 0
    assert (
        readiness["production_ready_from"]
        == candidate["production_ready_from"]
        == "READY_FOR_NEXT_ELIGIBLE_FUTURE_SIGNAL_CYCLE"
    )
    assert (
        readiness["gates"]["production_official_pit_evidence_pack"] == "PASS_REAL_PACKAGE_ADMITTED"
    )
    assert (
        readiness["candidate_manifest"]["sha256"]
        == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    )
    assert (
        candidate["source_integrity"]["pit_adapter"]["sha256"]
        == hashlib.sha256((ROOT / "strategies/etf_quant/mapping/pit.py").read_bytes()).hexdigest()
    )

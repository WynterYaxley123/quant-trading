"""Summary generation uses synthetic evidence only and preserves public spelling."""

import hashlib
import json

import pytest

from scripts.etf_quant import build_production_pit_manifest as builder


@pytest.fixture
def synthetic_reports(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    reports = runtime / "reports"
    reports.mkdir(parents=True)
    (runtime / "adapter-tests").mkdir()
    monkeypatch.setattr(builder, "RUNTIME", runtime)
    monkeypatch.setattr(builder, "REPORTS", reports)
    monkeypatch.setattr(builder, "PACKAGES", runtime / "packages")
    monkeypatch.setattr(builder, "REPO", tmp_path / "repo")
    registry = {
        key: "synthetic"
        for key in (
            "registry_id",
            "identity",
            "created_at",
            "production_available_from",
            "availability_semantics",
            "schema_version",
            "builder_code_hash",
            "derivation_code_hash",
            "classification_snapshot_id",
        )
    }
    registry.update(cneqity_pin={"commit": "synthetic-pin"}, counts={}, known_limitations=[])
    for name, content in {
        "production_pit_evidence_registry_v1.json": registry,
        "production_pit_current_top5_status_v1.json": {"summary": {}, "industries": []},
        "raw_source_manifest_v1.json": {
            "source_count": 1,
            "total_bytes": 1,
            "sources": [{"source_sha256": "synthetic"}],
        },
        "classification_cross_check_v1.json": {"status": "synthetic"},
    }.items():
        (reports / name).write_text(json.dumps(content))
    (runtime / "adapter-tests/production_evidence_book_v1.json").write_text(
        json.dumps({"records": [{"available_at": "2026-09-25T00:00:00+00:00"}]})
    )
    return reports


def test_summary_needs_no_unused_build_report_and_keeps_public_pin_contract(synthetic_reports):
    assert not (synthetic_reports / "build_report_v1.json").exists()
    assert builder.main() == 0
    result = json.loads(
        (synthetic_reports / "deepseek_production_pit_evidence_manifest_v1.json").read_text()
    )
    assert result["registry"]["cneqity_pin"] == {"commit": "synthetic-pin"}
    assert "cnequity_pin" not in result["registry"]
    assert result["evidence_packages"]["adapter_book_records"] == 1
    assert result["evidence_packages"]["benchmark_weight_packages"] == 0
    assert result["raw_hash_manifest_digest"] == hashlib.sha256(b'["synthetic"]').hexdigest()
    assert result["no_backfill"]["earliest_availability_in_book"] == "2026-09-25T00:00:00+00:00"
    assert result["formal_business_records_created"] == 0
    assert result["shadow_epoch_created"] is False
    committed = builder.REPO / "reports/etf_quant/deepseek_production_pit_evidence_manifest_v1.json"
    assert (
        committed.read_bytes()
        == (synthetic_reports / "deepseek_production_pit_evidence_manifest_v1.json").read_bytes()
    )


def test_summary_still_requires_registry_contract_fields(synthetic_reports):
    registry_path = synthetic_reports / "production_pit_evidence_registry_v1.json"
    registry = json.loads(registry_path.read_text())
    del registry["availability_semantics"]
    registry_path.write_text(json.dumps(registry))
    with pytest.raises(KeyError, match="availability_semantics"):
        builder.main()

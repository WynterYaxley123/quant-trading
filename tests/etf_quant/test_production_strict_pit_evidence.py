"""Production STRICT evidence: the mechanical constituent-set containment proof.

Pure unit tests for the strict derivation, plus the two wall-clock guards that
keep observation instants honest, plus real-package verification against the
already-built immutable production artifacts (skipped loudly when absent).

These tests prove the strict condition mechanically -- every constituent
classified, every classification equal to the target L2 -- and prove it fails
closed on exactly the gaps that must never be papered over: one out-of-bounds
constituent, one missing classification, one future observation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from strategies.etf_quant.domain.industry_level import default_taxonomy
from strategies.etf_quant.evidence.schema import (
    REJECTION_CLASSIFICATION_INCOMPLETE,
    REJECTION_NO_OFFICIAL_WEIGHT,
    REJECTION_NOT_YET_AVAILABLE,
    WEIGHT_COMPLETE,
    WEIGHT_INCOMPLETE,
    B40MappingEvidence,
    EvidenceError,
)
from strategies.etf_quant.evidence.strict import (
    CONTAINMENT_IDENTITY,
    REJECTION_CONTAINMENT,
    ContainmentProof,
    derive_strict_mapping_evidence,
    prove_constituent_containment,
)

TAXONOMY = default_taxonomy()
L2_A = TAXONOMY.named_industry_codes[0]
L2_B = TAXONOMY.named_industry_codes[1]

TZ = timezone(timedelta(hours=8))
AVAILABLE = "2026-09-30T18:05:00+08:00"
AFTER = datetime(2026, 10, 1, 9, 0, tzinfo=TZ)
BEFORE = datetime(2026, 9, 30, 18, 4, 59, tzinfo=TZ)
HASHES = ("a" * 64, "b" * 64)

RUNTIME = (
    Path(os.environ.get("ETF_QUANT_EXTERNAL_RUNTIME_ROOT", r"D:\QuantForge\runtime\etf-quant-v1"))
    / "production-pit-evidence-v1"
)
PACKAGES = RUNTIME / "packages"
SUMMARY = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "etf_quant"
    / "production_strict_pit_evidence_summary_v1.json"
)
BUILD_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "etf_quant"
    / "build_production_pit_evidence.py"
)


def _derive(**overrides):
    payload = {
        "benchmark_code": "399975",
        "target_l2_code": L2_A,
        "target_l2_name": TAXONOMY.name_of(L2_A),
        "etf_code": "512880.SH",
        "etf_name": "证券ETF",
        "constituents": ["600030", "000776"],
        "stock_to_l2": {"600030": L2_A, "000776": L2_A},
        "target_l2_exposure": 100.0,
        "target_is_largest": True,
        "unmapped_weight": 0.0,
        "weight_quality": WEIGHT_COMPLETE,
        "production_available_at": AVAILABLE,
        "input_package_hashes": HASHES,
        "available_from": AVAILABLE,
    }
    payload.update(overrides)
    return derive_strict_mapping_evidence(**payload)


# ---------------------------------------------------------------------------
# constituent-set containment
# ---------------------------------------------------------------------------


def test_full_containment_is_proven():
    proof = prove_constituent_containment(
        constituents=["600030", "000776", "300750"],
        stock_to_l2={"600030": L2_A, "000776": L2_A, "300750": L2_A},
        target_l2_code=L2_A,
    )
    assert isinstance(proof, ContainmentProof)
    assert proof.proven is True
    assert proof.reason is None
    assert proof.classified_count == proof.constituent_count == 3


def test_one_out_of_bounds_constituent_rejects_containment():
    proof = prove_constituent_containment(
        constituents=["600030", "000776", "600519"],
        stock_to_l2={"600030": L2_A, "000776": L2_A, "600519": L2_B},
        target_l2_code=L2_A,
    )
    assert proof.proven is False
    assert proof.reason == REJECTION_CONTAINMENT
    assert proof.out_of_bounds == ("600519",)


def test_a_zero_weight_out_of_bounds_constituent_still_breaks_containment():
    """100% exposure alone never proves strict: membership is per constituent."""
    proof = prove_constituent_containment(
        constituents=["600030", "000776", "600519"],
        stock_to_l2={"600030": L2_A, "000776": L2_A, "600519": L2_B},
        target_l2_code=L2_A,
    )
    record = _derive(
        constituents=["600030", "000776", "600519"],
        stock_to_l2={"600030": L2_A, "000776": L2_A, "600519": L2_B},
        target_l2_exposure=100.0,
        decision_at=AFTER,
    )
    assert proof.proven is False
    assert record.admission_status == "REJECTED"
    assert REJECTION_CONTAINMENT in record.rejection_reason


def test_one_missing_classification_rejects_containment():
    proof = prove_constituent_containment(
        constituents=["600030", "000776", "920982"],
        stock_to_l2={"600030": L2_A, "000776": L2_A},
        target_l2_code=L2_A,
    )
    assert proof.proven is False
    assert proof.reason == REJECTION_CLASSIFICATION_INCOMPLETE
    assert proof.unclassified == ("920982",)


def test_empty_constituent_set_proves_nothing():
    proof = prove_constituent_containment(constituents=[], stock_to_l2={}, target_l2_code=L2_A)
    assert proof.proven is False
    assert proof.reason == REJECTION_NO_OFFICIAL_WEIGHT


def test_target_must_be_a_real_code():
    with pytest.raises(EvidenceError):
        prove_constituent_containment(
            constituents=["600030"], stock_to_l2={"600030": L2_A}, target_l2_code=""
        )


# ---------------------------------------------------------------------------
# strict mapping evidence derivation
# ---------------------------------------------------------------------------


def test_all_conditions_hold_admits_a_strict_mapping():
    record = _derive(decision_at=AFTER)
    assert record.mapping_type == "STRICT_MAPPING"
    assert record.admission_status == "ADMITTED"
    assert record.rejection_reason is None
    assert record.target_l2_exposure == 100.0
    assert record.target_is_largest is True
    assert record.production_available_at.startswith("2026-09-30")


def test_future_evidence_is_rejected_at_the_decision_instant():
    record = _derive(decision_at=BEFORE)
    assert record.admission_status == "REJECTED"
    assert REJECTION_NOT_YET_AVAILABLE in record.rejection_reason


def test_incomplete_weight_set_is_rejected():
    record = _derive(weight_quality=WEIGHT_INCOMPLETE, decision_at=AFTER)
    assert record.admission_status == "REJECTED"
    assert REJECTION_NO_OFFICIAL_WEIGHT in record.rejection_reason


def test_unmapped_weight_is_rejected():
    record = _derive(unmapped_weight=0.5, decision_at=AFTER)
    assert record.admission_status == "REJECTED"
    assert REJECTION_CLASSIFICATION_INCOMPLETE in record.rejection_reason


def test_missing_classification_is_rejected():
    record = _derive(
        constituents=["600030", "920982"], stock_to_l2={"600030": L2_A}, decision_at=AFTER
    )
    assert record.admission_status == "REJECTED"
    assert REJECTION_CLASSIFICATION_INCOMPLETE in record.rejection_reason


def test_availability_is_the_maximum_of_the_declared_inputs():
    record = _derive(available_from="2026-10-02T09:00:00+08:00", decision_at=AFTER)
    # The later of the two declared instants governs; a decision before it fails.
    assert record.production_available_at == "2026-10-02T09:00:00+08:00"
    assert record.admission_status == "REJECTED"
    assert REJECTION_NOT_YET_AVAILABLE in record.rejection_reason


def test_input_hashes_are_carried_and_deduplicated():
    record = _derive(input_package_hashes=[HASHES[0], HASHES[0], HASHES[1]])
    assert record.input_package_hashes == HASHES


def test_derived_record_is_the_schema_type_not_a_parallel_one():
    record = _derive()
    assert isinstance(record, B40MappingEvidence)


def test_proof_identity_is_stable():
    assert CONTAINMENT_IDENTITY == "PRODUCTION_STRICT_CONSTITUENT_CONTAINMENT_V1"


# ---------------------------------------------------------------------------
# wall-clock guards: an observation instant this system is not entitled to assert
# ---------------------------------------------------------------------------


def _load_build_module():
    """Load the build script for its guard functions; keep sys.path clean."""
    spec = importlib.util.spec_from_file_location("production_pit_build", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        added = [item for item in sys.path if item not in before]
        for item in added:
            sys.path.remove(item)
    return module


def test_observation_may_not_precede_the_last_real_retrieval(monkeypatch):
    build = _load_build_module()
    now = datetime.now(timezone.utc).astimezone()
    retrieved = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    from scripts.etf_quant import production_pit_lineage

    monkeypatch.setattr(
        production_pit_lineage, "latest_real_retrieval", lambda: (retrieved, "unit-test-ledger")
    )
    with pytest.raises(SystemExit, match="REFUSING TO BACKDATE"):
        build.assert_observed_after_every_retrieval(
            (now - timedelta(hours=2)).isoformat(timespec="seconds")
        )


def test_observation_may_not_sit_in_the_future(monkeypatch):
    build = _load_build_module()
    now = datetime.now(timezone.utc).astimezone()
    retrieved = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    from scripts.etf_quant import production_pit_lineage

    monkeypatch.setattr(
        production_pit_lineage, "latest_real_retrieval", lambda: (retrieved, "unit-test-ledger")
    )
    with pytest.raises(SystemExit, match="REFUSING A FUTURE OBSERVATION"):
        build.assert_observed_after_every_retrieval(
            (now + timedelta(hours=3)).isoformat(timespec="seconds")
        )


def test_observation_between_retrieval_and_wall_clock_is_accepted(monkeypatch):
    build = _load_build_module()
    now = datetime.now(timezone.utc).astimezone()
    retrieved = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    claimed = (now - timedelta(minutes=30)).isoformat(timespec="seconds")
    from scripts.etf_quant import production_pit_lineage

    monkeypatch.setattr(
        production_pit_lineage, "latest_real_retrieval", lambda: (retrieved, "unit-test-ledger")
    )
    moment, origin = build.assert_observed_after_every_retrieval(claimed)
    assert moment == retrieved
    assert origin == "unit-test-ledger"


# ---------------------------------------------------------------------------
# real immutable production packages (skipped loudly when absent)
# ---------------------------------------------------------------------------


def _require_packages():
    if not (PACKAGES / "classification" / "SWS_L2_CURRENT_SNAPSHOT_20260929.json").exists():
        pytest.skip("production packages not built")


def _stock_to_l2():
    doc = json.loads(
        (PACKAGES / "classification" / "SWS_L2_CURRENT_SNAPSHOT_20260929.json").read_bytes()
    )
    return {row["security_code"]: row["shenwan_l2_code"] for row in doc["snapshot"]["rows"]}


@pytest.mark.external_runtime
def test_real_399975_is_fully_contained_in_4901():
    _require_packages()
    weights = json.loads((PACKAGES / "weights" / "399975_weights_v1.json").read_bytes())["vector"]
    codes = [row["security_code"] for row in weights["rows"]]
    proof = prove_constituent_containment(
        constituents=codes, stock_to_l2=_stock_to_l2(), target_l2_code="4901"
    )
    assert proof.proven is True, proof.reason
    assert proof.constituent_count == weights["declared_constituent_count"]


@pytest.mark.external_runtime
def test_real_931412_is_fully_contained_in_4901():
    _require_packages()
    weights = json.loads((PACKAGES / "weights" / "931412_weights_v1.json").read_bytes())["vector"]
    codes = [row["security_code"] for row in weights["rows"]]
    proof = prove_constituent_containment(
        constituents=codes, stock_to_l2=_stock_to_l2(), target_l2_code="4901"
    )
    assert proof.proven is True, proof.reason


@pytest.mark.external_runtime
def test_real_000300_is_not_a_strict_4901_instrument():
    """A broad benchmark must never prove strict containment."""
    _require_packages()
    path = PACKAGES / "weights" / "000300_weights_v1.json"
    if not path.exists():
        pytest.skip("000300 weight package not built")
    weights = json.loads(path.read_bytes())["vector"]
    codes = [row["security_code"] for row in weights["rows"]]
    proof = prove_constituent_containment(
        constituents=codes, stock_to_l2=_stock_to_l2(), target_l2_code="4901"
    )
    assert proof.proven is False
    assert proof.reason == REJECTION_CONTAINMENT


@pytest.mark.external_runtime
def test_summary_artifact_is_metadata_only_and_self_consistent():
    _require_packages()
    if not SUMMARY.exists():
        pytest.skip("strict summary not generated")
    summary = json.loads(SUMMARY.read_bytes())
    assert summary["identity"] == CONTAINMENT_IDENTITY
    assert summary["counts"]["containment_proven"] > 0
    for entry in summary["entries"]:
        assert "rows" not in entry and "constituents" not in entry, entry["benchmark_code"]
    # Recompute one entry's verdict from the packages and require agreement.
    target = next(e for e in summary["entries"] if e["benchmark_code"] == "399975")
    weights = json.loads((PACKAGES / "weights" / "399975_weights_v1.json").read_bytes())["vector"]
    proof = prove_constituent_containment(
        constituents=[row["security_code"] for row in weights["rows"]],
        stock_to_l2=_stock_to_l2(),
        target_l2_code=target["target_l2_code"],
    )
    assert proof.proven is target["containment_proven"] is True
    assert target["verified_strict_rows"], "4901 must be backed by verified registry rows"

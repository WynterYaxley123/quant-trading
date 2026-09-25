"""Preregistration-only guards; no model fit or formal result generation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from research import horizon_specific_alpha_hypothesis_v1_protocol as protocol
from research import horizon_specific_alpha_hypothesis_v1_selection as selection
from research.factor_set_v2_protocol import (
    FAMILY_MEMBERS, FAMILY_PROCESSING_ORDER, FROZEN_FACTOR_ORDER,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_protocol_hash_and_exact_config_identity(tmp_path):
    payload = protocol.verify_protocol()
    config = payload["configExactContent"]
    assert protocol.protocol_hash() == protocol.FROZEN_PROTOCOL_HASH
    assert config["researchType"] == "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1"
    assert config["schemaVersion"] == 1
    assert config["diagnosticSource"] == "ALPHA_STABILITY_REGIME_AUDIT_V1"
    assert config["phase"] == "DEVELOPMENT"
    assert config["developmentIds"] == "E001-E100"
    assert config["universe"] == "U0_FIXED_124" and config["sectorCount"] == 124
    assert config["validationSealed"] is True
    assert config["finalOosSealed"] is True
    assert config["developmentReuseWarning"] is True
    assert "NOT_INDEPENDENT_VALIDATION_OR_OOS" in config["researchInterpretation"]
    assert config["h40EvidenceQualityWarning"] is True
    assert payload["sourceSha256"] == selection.SOURCE_SHA256
    assert payload["frozenConstants"]["exactCandidates"] == {
        k: list(v) for k, v in protocol.EXACT_CANDIDATES.items()}

    target = tmp_path / protocol.CONFIG_RELPATH
    target.parent.mkdir(parents=True)
    drifted = json.loads((_root() / protocol.CONFIG_RELPATH).read_text())
    drifted["alpha"] = 0.02
    target.write_text(json.dumps(drifted))
    with pytest.raises(ValueError, match="CONFIG_DRIFT_BLOCKER"):
        protocol.load_config(tmp_path)


def test_document_and_trace_are_in_protocol_identity(tmp_path):
    # Copy only the frozen identity inputs, alter one protocol byte, and verify drift.
    for rel in (protocol.CONFIG_RELPATH, protocol.PROTOCOL_RELPATH, protocol.TRACE_RELPATH,
                "research/horizon_specific_alpha_hypothesis_v1_selection.py"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((_root() / rel).read_bytes())
    doc = tmp_path / protocol.PROTOCOL_RELPATH
    doc.write_bytes(doc.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        protocol.verify_protocol(tmp_path)


def test_development_scope_and_sealed_phases():
    protocol.guard_scope("development", [1, 50, 100])
    for phase, ids in (("development", [101]), ("validation", [221]),
                       ("final_oos", [401]), ("purge_1", [101]),
                       ("development", [])):
        with pytest.raises((PermissionError, ValueError)):
            protocol.guard_scope(phase, ids)


def test_frozen_factor_universe_families_and_budget():
    config = protocol.load_config()
    factors = list(FROZEN_FACTOR_ORDER)
    assert len(factors) == len(set(factors)) == 19
    assert config["factors"] == config["factorPipelineOrder"] == factors
    assert config["familyProcessingOrder"] == list(FAMILY_PROCESSING_ORDER)
    assert config["factorFamilies"] == {k: list(v) for k, v in FAMILY_MEMBERS.items()}
    assert config["candidateBudget"] == {
        "perHorizon": 2, "total": 6,
        "archetypes": ["SINGLE_STABLE", "COMPACT_STABLE"],
        "maxCompactFactors": 6, "maxPerFamily": 1, "backfill": False,
    }
    assert tuple(config["candidateIds"]) == protocol.CANDIDATE_IDS
    assert len(config["candidates"]) == 6
    family_of = {factor: family for family, members in FAMILY_MEMBERS.items()
                 for factor in members}
    for candidate_id, spec in config["candidates"].items():
        horizon = int(candidate_id.split("_")[0][1:])
        assert spec["horizon"] == horizon
        assert spec["factorList"] == list(protocol.EXACT_CANDIDATES[candidate_id])
        assert set(spec["factorList"]) <= set(factors)
        assert spec["factorList"] == [f for f in factors if f in spec["factorList"]]
        assert len(spec["factorList"]) == (1 if candidate_id.endswith("_S")
                                           else len(set(family_of[f] for f in spec["factorList"])))
        assert len(spec["factorList"]) <= 6
        assert spec["archetype"] == ("SINGLE_STABLE" if candidate_id.endswith("_S")
                                    else "COMPACT_STABLE")


def test_selection_rank_only_uses_existing_temporal_metrics():
    config = protocol.load_config()
    assert config["stabilityRankFields"] == list(selection.RANK_FIELDS)
    assert config["redundancyThreshold"] == selection.REDUNDANCY_THRESHOLD == 0.8
    assert selection.RANK_FIELDS == (
        "hard_flip_rate_ascending", "raw_sign_agreement_rate_descending",
        "transfer_spearman_descending", "frozen_pipeline_index_ascending")
    forbidden = ("return", "spread", "sharpe", "drawdown", "mean_evaluation_rankic")
    assert all(not any(word in field for word in forbidden)
               for field in selection.RANK_FIELDS)


def test_selection_determinism_exact_lists_and_redundancy():
    first = selection.derive_selection()
    second = selection.derive_selection()
    assert first == second
    assert first["candidates"] == {k: list(v) for k, v in protocol.EXACT_CANDIDATES.items()}
    assert list(first["trace"]) == ["10", "40", "120"]
    assert all(len(t["ranked"]) == 19 for t in first["trace"].values())
    family_of = {f: family for family, members in FAMILY_MEMBERS.items() for f in members}
    for h, trace in first["trace"].items():
        keys = [(r["hardFlipRate"], -r["rawSignAgreementRate"],
                 -r["transferSpearman"], r["pipelineIndex"])
                for r in trace["ranked"]]
        assert keys == sorted(keys)
        assert [r["rank"] for r in trace["ranked"]] == list(range(1, 20))
        assert {r["factor"] for r in trace["ranked"]} == set(FROZEN_FACTOR_ORDER)
        assert all(r["family"] == family_of[r["factor"]] for r in trace["ranked"])
        assert first["candidates"][f"H{h}_S"] == [trace["ranked"][0]["factor"]]
        selected = trace["compactSelectionOrder"]
        assert len(selected) <= 6 == len(FAMILY_PROCESSING_ORDER)
        assert len({family_of[f] for f in selected}) == len(selected)
        assert trace["compactPipelineOrder"] == first["candidates"][f"H{h}_C"]
        assert all(row["decision"] in ("SELECTED", "REDUNDANT")
                   for row in trace["compactAdmission"])
        for row in trace["compactAdmission"]:
            if row["decision"] == "REDUNDANT":
                assert row["conflicts"]
                assert all(abs(item["rho"]) >= 0.8 for item in row["conflicts"])


def test_source_hashes_and_historical_metadata_unchanged():
    root = _root()
    for rel, expected in selection.SOURCE_SHA256.items():
        assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == expected
    metadata = {
        "iteration1_20260924_163607_787266_utc": "25a9a637f9a3c7c48750057551b1975e780e8ffe212274d276550b479e5ee526",
        "factor_alpha_audit_20260925_071934_967164_utc": "ec7692a815559be09c87d4833c18472357b70c6efee28022d4ed1163776a894a",
        "factor_set_v2_20260925_090958_520718_utc": "481febeb025854f4555d896de82fabfe43ff5594fb0fd6766de33ffa3dd1f908",
        "alpha_stability_regime_audit_20260925_103645_877103_utc": "d1e7b9ba941a3ab58f97e9cdfe8a3ab05d1071012fe08bbe488a65ed358d0b11",
    }
    base = root / "reports/research/shenwan_sector_index"
    for run, expected in metadata.items():
        assert hashlib.sha256((base / run / "metadata.json").read_bytes()).hexdigest() == expected


def test_neutral_training_direction_warning_uses_frozen_transition_artifact():
    path = (_root() / "reports/research/shenwan_sector_index/"
            "alpha_stability_regime_audit_20260925_103645_877103_utc/"
            "factor_transfer_transition.csv")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "8c890818ef18104b51f1b0c6ec793bcbd2d048432e060429dda661173704da3f")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for factor, horizon, expected_neutral in (("p5", "10", 100),
                                               ("vc", "40", 100),
                                               ("vc", "120", 99)):
        relevant = [r for r in rows if r["factor"] == factor and r["horizon"] == horizon]
        assert sum(int(r["count"]) for r in relevant) == 100
        assert sum(int(r["count"]) for r in relevant
                   if r["train_direction"] == "NEUTRAL") == expected_neutral


def test_incomplete_diagnostic_fails_closed(tmp_path, monkeypatch):
    source_rel = selection.ALPHA_REL
    source = (_root() / source_rel).read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    # Preserve a valid checksum for the altered fixture: the row gap itself must block.
    target = tmp_path / source_rel
    target.parent.mkdir(parents=True)
    target.write_text("".join(lines[:-1]), encoding="utf-8")
    corr_target = tmp_path / selection.FACTOR_REL
    corr_target.parent.mkdir(parents=True)
    corr_target.write_bytes((_root() / selection.FACTOR_REL).read_bytes())
    monkeypatch.setitem(selection.SOURCE_SHA256, source_rel,
                        hashlib.sha256(target.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="HORIZON_STABILITY_EVIDENCE_INCOMPLETE"):
        selection.derive_selection(tmp_path)


def test_selection_rejects_source_hash_drift(tmp_path):
    target = tmp_path / selection.ALPHA_REL
    target.parent.mkdir(parents=True)
    target.write_text("not a formal artifact", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash drift"):
        selection.derive_selection(tmp_path)


def test_model_target_top5_and_prohibitions():
    c = protocol.load_config()
    assert c["control"]["factorList"] == list(FROZEN_FACTOR_ORDER)
    assert c["control"]["source"] == "ITERATION1_D2"
    assert c["control"]["comparison"] == "SAME_HORIZON_ONLY"
    assert c["model"] == "NUMPY_RIDGE" and c["alpha"] == 0.01
    assert c["fitIntercept"] is True
    assert c["preprocessing"] == "RAW_NO_STANDARDIZATION"
    assert c["target"] == "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert c["trainWindow"] == "6_CALENDAR_MONTHS"
    assert c["trainWindowAnchor"] == "PER_HORIZON_LEGAL_LABEL_CUTOFF"
    assert c["minTrainingDays"] == 30
    assert c["evaluationLabel"] == "ABSOLUTE_FORWARD_RETURN_COMMON_CALENDAR_T_PLUS_H"
    assert c["topK"] == 5
    assert c["topKRule"] == "PREDICTION_DESCENDING_SECTOR_CODE_ASCENDING"
    assert c["spreadRule"] == "TOP5_ABSOLUTE_FORWARD_RETURN_MINUS_UNIVERSE_ABSOLUTE_FORWARD_RETURN"
    assert c["primaryMetrics"] == ["MEAN_RANKIC", "MEAN_TOP5_MINUS_UNIVERSE_SPREAD"]
    for flag in ("noFusion", "noCrossHorizonWinner", "noParameterSearch",
                 "noSignFlip", "noNewFactors", "noFormalResultsInPreregistration"):
        assert c[flag] is True


def test_frozen_blocks_and_advancement_gates():
    c = protocol.load_config()
    assert c["blocks"] == [{"id": f"B{i}", "first": 25 * (i - 1) + 1,
                             "last": 25 * i} for i in range(1, 5)]
    assert c["level1Rule"] == "CANDIDATE_MEAN_RANKIC_GT_0_AND_MEAN_SPREAD_GT_0"
    assert c["level2Rule"].startswith("SAME_HORIZON_C0_PARETO_STRICT")
    assert c["temporalStabilityGate"] == {
        "positiveRankIcBlocksAtLeast": 3,
        "rankIcStrictlyBelowMinus002BlocksAtMost": 1,
        "redFlagThreshold": -0.02,
    }
    blocks = {"B1": 0.1, "B2": 0.2, "B3": 0.01, "B4": -0.02}
    base = dict(candidate_horizon=40, control_horizon=40,
                mean_rankic=0.11, mean_spread=0.02,
                c0_mean_rankic=0.10, c0_mean_spread=0.02,
                block_mean_rankic=blocks)
    assert protocol.advancement_status(**base) == "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
    assert protocol.advancement_status(**{**base, "mean_rankic": 0}) == "HORIZON_NOT_ADVANCED"
    assert protocol.advancement_status(**{**base, "mean_spread": 0}) == "HORIZON_NOT_ADVANCED"
    assert protocol.advancement_status(**{**base, "mean_rankic": 0.10,
                                         "mean_spread": 0.021}) == "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
    assert protocol.advancement_status(**{**base, "mean_spread": 0.019}) == "HORIZON_NOT_ADVANCED"
    assert protocol.advancement_status(**{**base, "block_mean_rankic": {
        "B1": 0.1, "B2": 0.2, "B3": 0.0, "B4": -0.02}}) == "TEMPORAL_STABILITY_GATE_FAIL"
    assert protocol.advancement_status(**{**base, "block_mean_rankic": {
        "B1": 0.1, "B2": 0.2, "B3": 0.01, "B4": -0.020001}}) == "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
    with pytest.raises(ValueError, match="SAME_HORIZON_C0_REQUIRED"):
        protocol.advancement_status(**{**base, "control_horizon": 120})
    with pytest.raises(ValueError, match="METRIC_INCOMPLETE"):
        protocol.advancement_status(**{**base, "block_mean_rankic": {"B1": 0.1}})


def test_simplicity_gate_strict_and_nonstatistical():
    c = protocol.load_config()
    assert c["simplicityPreference"] == {
        "whenBothAdvance": True, "absoluteMeanRankIcDeltaLt": 0.01,
        "absoluteMeanSpreadDeltaLt": 0.01, "prefer": "SINGLE_STABLE",
        "statisticalSignificanceClaim": False,
    }
    advanced = "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
    base = dict(single_status=advanced, compact_status=advanced,
                single_mean_rankic=0.1, compact_mean_rankic=0.105,
                single_mean_spread=0.02, compact_mean_spread=0.025)
    assert protocol.prefer_single_if_near_tie(**base)
    assert not protocol.prefer_single_if_near_tie(**{**base, "compact_status": "HORIZON_NOT_ADVANCED"})
    assert not protocol.prefer_single_if_near_tie(**{**base, "compact_mean_rankic": 0.12})
    assert not protocol.prefer_single_if_near_tie(**{**base, "compact_mean_spread": 0.04})


def test_selection_is_prereg_only_and_does_not_create_result_directory():
    # The permanent test checks the helper's lifecycle, not whether a later
    # separately authorized formal result has appeared in the repository.
    root = _root() / "reports/research/shenwan_sector_index"
    patterns = ("horizon_specific_alpha_*", "horizon_specific_v1_*", "hs_alpha_v1_*")
    before = sorted(p.name for pattern in patterns for p in root.glob(pattern))
    selection.derive_selection()
    protocol.verify_protocol()
    after = sorted(p.name for pattern in patterns for p in root.glob(pattern))
    assert after == before
    assert not hasattr(selection, "run_formal")
    assert not hasattr(protocol, "run_formal")

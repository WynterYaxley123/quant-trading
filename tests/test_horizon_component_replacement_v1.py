"""Preregistration-only guards for Horizon Component Replacement V1.

No fused output, no RankIC/Spread, no formal result is produced here.
Fusion/evaluation semantics are pinned against the REAL frozen
implementations (fuse_periods / evaluate_date), never reimplemented.
Result-leak behavior is lifecycle-aware: unit tests use tmp_path fixtures
only and never require the real reports tree to stay empty forever.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import horizon_component_replacement_v1_protocol as protocol
from research.sector_development_baseline import evaluate_date
from research.sector_universe_feasibility import prediction_metric_contract
from strategies.sw_sector_rotation.src.model.model import (
    FUSION_WEIGHTS, CrossSectionalRidgeModel, RankingResult,
)
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors

REPO = Path(__file__).resolve().parents[1]
MANIFEST_COMPONENTS = ("C0_H10", "C0_H40", "C0_H120", "H10_C", "H40_S")
REQUIRED_SOURCE_FIELDS = (
    "sourceResearchType", "sourceResultCommit", "sourceProtocolHash",
    "sourceRunPath", "sourceRerunPath", "candidateId", "horizon", "factorList",
    "predictionsArtifact", "predictionsSha256", "metricsArtifact",
    "metricsSha256", "firstRerunIdentical", "sourceCurrentExistenceVerified",
)


def _config() -> dict:
    return protocol.load_config(REPO)


def _sources() -> dict:
    return protocol.load_sources(REPO)


# --- identity, budget, mappings (items 1, 5-17, 21-22, 37-39) ---------------

def test_research_type_exact_and_sealed_phases():
    config = _config()
    assert protocol.RESEARCH_TYPE == "HORIZON_COMPONENT_REPLACEMENT_V1"
    assert config["researchType"] == "HORIZON_COMPONENT_REPLACEMENT_V1"
    assert config["phase"] == "PREREGISTERED"
    assert config["developmentIds"] == "E001-E100"
    assert config["validationSealed"] is True and config["finalOosSealed"] is True
    assert config["universe"] == "U0_FIXED_124"
    protocol.guard_scope("development", [1, 50, 100])
    for phase, ids in (("development", [101]), ("validation", [221]),
                       ("final_oos", [401]), ("purge_1", [101]), ("development", [])):
        with pytest.raises((PermissionError, ValueError)):
            protocol.guard_scope(phase, ids)


def test_candidate_budget_ids_and_component_mappings_exact():
    config = _config()
    assert config["candidateBudget"]["totalSchemes"] == 3
    assert config["candidateBudget"]["newHypotheses"] == 2
    assert config["candidateBudget"]["backfill"] is False
    assert tuple(config["candidateIds"]) == protocol.CANDIDATE_IDS == (
        "F0_CONTROL", "F1_H10_REPLACEMENT", "F2_H10_H40_REPLACEMENT")
    assert config["componentMappings"] == protocol.COMPONENT_MAPPINGS
    assert protocol.COMPONENT_MAPPINGS["F0_CONTROL"] == {
        "h10": "C0_H10", "h40": "C0_H40", "h120": "C0_H120"}
    assert protocol.COMPONENT_MAPPINGS["F1_H10_REPLACEMENT"] == {
        "h10": "H10_C", "h40": "C0_H40", "h120": "C0_H120"}
    assert protocol.COMPONENT_MAPPINGS["F2_H10_H40_REPLACEMENT"] == {
        "h10": "H10_C", "h40": "H40_S", "h120": "C0_H120"}
    assert "F_H40_ONLY" not in config["candidateIds"]  # no H40-only candidate
    assert config["candidateBudget"]["noH40OnlyCandidate"] is True


def test_exact_factor_lists_and_h120_stays_c0():
    config = _config()
    assert tuple(config["factorLists"]["H10_C"]) == ("d10", "p5", "align", "vc", "dd20")
    assert tuple(config["factorLists"]["H40_S"]) == ("vc",)
    assert tuple(config["factorLists"]["C0_H10"]) == protocol.FROZEN_FACTORS_19
    assert tuple(config["factorLists"]["C0_H40"]) == protocol.FROZEN_FACTORS_19
    assert tuple(config["factorLists"]["C0_H120"]) == protocol.FROZEN_FACTORS_19
    assert config["componentMappings"]["F0_CONTROL"]["h120"] == "C0_H120"
    assert config["componentMappings"]["F1_H10_REPLACEMENT"]["h120"] == "C0_H120"
    assert config["componentMappings"]["F2_H10_H40_REPLACEMENT"]["h120"] == "C0_H120"
    assert config["candidateBudget"]["noH120Replacement"] is True
    for mapping in config["componentMappings"].values():
        assert "H120_C" not in mapping.values() and "H120_S" not in mapping.values()
    for factors in config["factorLists"].values():
        assert set(factors) <= set(protocol.FROZEN_FACTORS_19)  # no new factor
        assert len(set(factors)) == len(factors)
    assert config["noNewFactor"] is True and config["noSignFlip"] is True


def test_fusion_weights_exact_sum_and_search_flags():
    config = _config()
    assert config["fusionWeights"] == {"h10": 0.25, "h40": 0.5, "h120": 0.25}
    assert config["fusionWeights"] == protocol.FUSION_WEIGHTS
    assert abs(sum(protocol.FUSION_WEIGHTS.values()) - 1.0) < 1e-15
    assert dict(FUSION_WEIGHTS) == {"short": 0.25, "medium": 0.5, "long": 0.25}
    for flag in ("noWeightSearch", "noDynamicFusion", "noDropHorizon",
                 "noParameterSearch", "noModelSearch", "noComponentSearch"):
        assert config[flag] is True
    assert config["fusionSemantics"]["promptRawLinearCombinationSuperseded"] is True
    assert config["fusionSemantics"]["zScore"].startswith("PER_DATE_CROSS_SECTIONAL")
    assert config["topK"] == 5


# --- source manifest (items 23-26) -----------------------------------------

def test_source_manifest_complete_and_matches_protocol():
    sources = _sources()
    assert set(sources["components"]) == set(MANIFEST_COMPONENTS)
    for name in MANIFEST_COMPONENTS:
        entry = sources["components"][name]
        for field in REQUIRED_SOURCE_FIELDS:
            assert field in entry, (name, field)
        assert entry["firstRerunIdentical"] is True
        assert entry["sourceCurrentExistenceVerified"] is True
        assert entry["sourceResultCommit"] == protocol.SOURCE_RESULT_COMMIT
        assert entry["sourceProtocolHash"] == protocol.SOURCE_PROTOCOL_HASH
    assert sources["sourceResultCommit"] == "de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62"
    assert sources["sourceHandoffCommit"] == "98dfe5c9c256fe31339a2c3ca63ea1753180a7cc"
    assert sources["reportsTrackedInGit"] is False
    assert set(sources["f0ReferenceArtifacts"]) >= {
        "runId", "perDatePredictions", "predictions", "aggregateMetrics", "perDateMetrics"}
    assert sources["componentScaleAudit"]["rawComponentScaleDependenceWarning"] is False
    assert sources["alignment"]["allComponentsSameGrid"] is True
    payload = protocol.verify_protocol(REPO)
    assert payload["sourceManifestSha256"] == hashlib.sha256(
        (REPO / protocol.SOURCES_RELPATH).read_bytes()).hexdigest()
    assert payload["configExactContent"] == _config()


def test_source_artifacts_exist_and_hashes_reproduce():
    sources = _sources()
    missing = [entry["predictionsArtifact"] for entry in sources["components"].values()
               if not (REPO / entry["predictionsArtifact"]).exists()]
    if missing:
        pytest.skip(f"generated source artifacts not present: {missing[:1]}")
    for name, entry in sources["components"].items():
        for artifact_key, hash_key in (("predictionsArtifact", "predictionsSha256"),
                                       ("metricsArtifact", "metricsSha256")):
            actual = hashlib.sha256((REPO / entry[artifact_key]).read_bytes()).hexdigest()
            assert actual == entry[hash_key], name
    for entry in sources["f0ReferenceArtifacts"].values():
        if isinstance(entry, dict):
            assert (REPO / entry["path"]).exists()
            assert hashlib.sha256((REPO / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]


def test_first_rerun_source_identity_and_historical_artifacts_unchanged():
    sources = _sources()
    run = REPO / sources["sourceRunPath"]
    rerun = REPO / sources["sourceRerunPath"]
    if not run.exists() or not rerun.exists():
        pytest.skip("source run directories not present")
    for name, entry in sources["components"].items():
        for key in ("predictionsArtifact", "metricsArtifact"):
            first_path = REPO / entry[key]
            first_bytes = first_path.read_bytes()
            rerun_path = rerun / first_path.relative_to(run)
            assert hashlib.sha256(rerun_path.read_bytes()).hexdigest() == \
                hashlib.sha256(first_bytes).hexdigest(), (name, key)
    expected_meta = {
        "iteration1_20260924_163607_787266_utc":
            "25a9a637f9a3c7c48750057551b1975e780e8ffe212274d276550b479e5ee526",
        "factor_alpha_audit_20260925_071934_967164_utc":
            "ec7692a815559be09c87d4833c18472357b70c6efee28022d4ed1163776a894a",
        "factor_set_v2_20260925_090958_520718_utc":
            "481febeb025854f4555d896de82fabfe43ff5594fb0fd6766de33ffa3dd1f908",
        "alpha_stability_regime_audit_20260925_103645_877103_utc":
            "d1e7b9ba941a3ab58f97e9cdfe8a3ab05d1071012fe08bbe488a65ed358d0b11",
    }
    base = REPO / "reports/research/shenwan_sector_index"
    for run_id, digest in expected_meta.items():
        path = base / run_id / "metadata.json"
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


# --- advancement rules (items 27-34) ---------------------------------------

BLOCKS_OK = {"B1": 0.1, "B2": 0.2, "B3": 0.01, "B4": -0.01}
HORIZIC_OK = {"10": 0.1, "40": 0.1, "120": 0.1}


def _decision(candidate_id="F1_H10_REPLACEMENT", **overrides):
    base = dict(candidate_id=candidate_id, weighted_rankic=0.11, weighted_spread=0.02,
                f0_rankic=0.10, f0_spread=0.02,
                rankic_by_horizon=dict(HORIZIC_OK),
                block_weighted_rankic=dict(BLOCKS_OK))
    if candidate_id == "F2_H10_H40_REPLACEMENT":
        base.update(f1_rankic=0.105, f1_spread=0.021, weighted_spread=0.022)
    base.update(overrides)
    return protocol.advancement_decision(**base)


def test_level1_rule_exact_strict_inequalities():
    assert _decision()["level1"] == "LEVEL1_PASS"
    zero_rankic = _decision(weighted_rankic=0.0, weighted_spread=0.021)
    assert zero_rankic["level1"] == "LEVEL1_FAIL"
    assert zero_rankic["advancementStatus"] == "FUSION_NOT_ADVANCED"
    zero_spread = _decision(weighted_rankic=0.11, weighted_spread=0.0)
    assert zero_spread["level1"] == "LEVEL1_FAIL"
    assert protocol.pareto_relative(candidate_rankic=0.10, candidate_spread=0.021,
                                    reference_rankic=0.10, reference_spread=0.02)


def test_f1_vs_f0_relative_gate_exact():
    ok = _decision()
    assert ok["vsF0"] == "VS_F0_PASS" and ok["frozenGateResult"] == "FUSION_ADVANCED_FOR_FURTHER_REVIEW"
    assert ok["advancementStatus"] == "FUSION_ADVANCED_FOR_FURTHER_REVIEW"
    fail_rankic = _decision(weighted_rankic=0.10, weighted_spread=0.02)
    assert fail_rankic["vsF0"] == "VS_F0_FAIL"
    assert fail_rankic["frozenGateResult"] == "F1_RELATIVE_GATE_FAIL"
    assert fail_rankic["advancementStatus"] == "FUSION_NOT_ADVANCED"
    option_b = _decision(weighted_rankic=0.10, weighted_spread=0.03)
    assert option_b["vsF0"] == "VS_F0_PASS" and option_b["level1"] == "LEVEL1_PASS"


def test_f2_vs_f0_and_vs_f1_gates_exact():
    ok = _decision("F2_H10_H40_REPLACEMENT")
    assert ok["vsF0"] == "VS_F0_PASS" and ok["vsF1"] == "VS_F1_PASS"
    assert ok["advancementStatus"] == "FUSION_ADVANCED_FOR_FURTHER_REVIEW"
    vs_f0_fail = _decision("F2_H10_H40_REPLACEMENT", weighted_rankic=0.09,
                           weighted_spread=0.02)
    assert vs_f0_fail["vsF0"] == "VS_F0_FAIL"
    assert vs_f0_fail["frozenGateResult"] == "F2_VS_F0_GATE_FAIL"
    vs_f1_fail = _decision("F2_H10_H40_REPLACEMENT", weighted_rankic=0.104,
                           weighted_spread=0.0205)
    assert vs_f1_fail["vsF0"] == "VS_F0_PASS" and vs_f1_fail["vsF1"] == "VS_F1_FAIL"
    assert vs_f1_fail["frozenGateResult"] == "H40_INCREMENTAL_REPLACEMENT_NOT_SUPPORTED"
    assert vs_f1_fail["advancementStatus"] == "FUSION_NOT_ADVANCED"
    with pytest.raises(ValueError, match="INCOMPLETE"):
        protocol.advancement_decision(
            candidate_id="F2_H10_H40_REPLACEMENT", weighted_rankic=0.11,
            weighted_spread=0.02, f0_rankic=0.10, f0_spread=0.02,
            rankic_by_horizon=HORIZIC_OK, block_weighted_rankic=BLOCKS_OK)


def test_horizon_red_flag_minus_002_strict():
    assert protocol.HORIZON_RED_FLAG_THRESHOLD == -0.02
    red, flagged = protocol.horizon_red_flag({"10": 0.1, "40": -0.03, "120": 0.1})
    assert red is True and flagged == ["40"]
    edge, edge_flagged = protocol.horizon_red_flag({"10": 0.1, "40": -0.02, "120": 0.1})
    assert edge is False and edge_flagged == []  # strictly below -0.02
    blocked = _decision(rankic_by_horizon={"10": 0.1, "40": -0.05, "120": 0.1})
    assert blocked["horizonRedFlag"] is True
    assert blocked["frozenGateResult"] == "HORIZON_RED_FLAG"
    assert blocked["advancementStatus"] == "FUSION_NOT_ADVANCED"


def test_blocks_exact_and_temporal_gate():
    assert protocol.BLOCKS == (("B1", 1, 25), ("B2", 26, 50), ("B3", 51, 75), ("B4", 76, 100))
    assert _config()["blocks"] == [{"id": b, "first": f, "last": l}
                                   for b, f, l in protocol.BLOCKS]
    assert protocol.temporal_gate(BLOCKS_OK) is True
    assert protocol.temporal_gate({"B1": 0.1, "B2": 0.2, "B3": 0.0, "B4": -0.02}) is False
    assert protocol.temporal_gate({"B1": 0.1, "B2": 0.2, "B3": 0.01, "B4": -0.020001}) is True
    assert protocol.temporal_gate({"B1": -0.01, "B2": 0.2, "B3": 0.01, "B4": -0.015}) is False
    assert protocol.temporal_gate({"B1": 0.05, "B2": 0.2, "B3": 0.01, "B4": -0.015}) is True
    assert protocol.temporal_gate({"B1": -0.03, "B2": -0.04, "B3": 0.01, "B4": 0.02}) is False
    failed = _decision(block_weighted_rankic={"B1": 0.1, "B2": -0.03, "B3": -0.05, "B4": 0.01})
    assert failed["temporalStability"] == "TEMPORAL_FAIL"
    assert failed["frozenGateResult"] == "FUSION_TEMPORAL_STABILITY_GATE_FAIL"
    assert failed["advancementStatus"] == "FUSION_NOT_ADVANCED"
    assert _config()["blockMetrics"]["spreadBlocksReportedNotGated"] is True


def test_minimal_replacement_preference_strict_and_nonstatistical():
    config = _config()
    pref = config["minimalReplacementPreference"]
    assert pref["prefer"] == "F1_H10_REPLACEMENT"
    assert pref["label"] == "MINIMAL_REPLACEMENT_PREFERENCE"
    assert pref["statisticalSignificanceClaim"] is False
    advanced = protocol.STATUS_ADVANCED
    assert protocol.prefer_minimal_replacement(
        f1_status=advanced, f2_status=advanced,
        f1_rankic=0.10, f2_rankic=0.105, f1_spread=0.02, f2_spread=0.025)
    assert not protocol.prefer_minimal_replacement(
        f1_status=advanced, f2_status=protocol.STATUS_NOT_ADVANCED,
        f1_rankic=0.10, f2_rankic=0.105, f1_spread=0.02, f2_spread=0.025)
    assert not protocol.prefer_minimal_replacement(
        f1_status=advanced, f2_status=advanced,
        f1_rankic=0.10, f2_rankic=0.12, f1_spread=0.02, f2_spread=0.025)
    assert not protocol.prefer_minimal_replacement(
        f1_status=advanced, f2_status=advanced,
        f1_rankic=0.10, f2_rankic=0.105, f1_spread=0.02, f2_spread=0.04)
    assert protocol.MINIMAL_TIE_BAND == 0.01


def test_status_labels_control_and_forbidden_labels():
    control = protocol.advancement_decision(
        candidate_id="F0_CONTROL", weighted_rankic=0.1, weighted_spread=0.1,
        f0_rankic=0.1, f0_spread=0.1, rankic_by_horizon=HORIZIC_OK,
        block_weighted_rankic=BLOCKS_OK)
    assert control["advancementStatus"] == protocol.STATUS_CONTROL
    assert control["vsF0"] == "NOT_APPLICABLE"
    assert _config()["advancementStatusLabels"] == [
        protocol.STATUS_CONTROL, protocol.STATUS_ADVANCED, protocol.STATUS_NOT_ADVANCED]
    allowed = set(_config()["advancementStatusLabels"] + _config()["gateSubstatusLabels"])
    for forbidden in protocol.FORBIDDEN_RESULT_LABELS:
        assert all(forbidden not in label for label in allowed)
    with pytest.raises(ValueError, match="UNKNOWN_CANDIDATE"):
        protocol.advancement_decision(
            candidate_id="F9_EXTRA", weighted_rankic=0.1, weighted_spread=0.1,
            f0_rankic=0.0, f0_spread=0.0, rankic_by_horizon=HORIZIC_OK,
            block_weighted_rankic=BLOCKS_OK)


# --- fusion semantics pinned against the REAL implementation ---------------

def _rank_result(period: str, scores: dict) -> RankingResult:
    return RankingResult(period=period, forward_days={"short": 10, "medium": 40,
                                                      "long": 120}[period],
                         predict_date=pd.Timestamp("2025-04-02"),
                         train_start=pd.Timestamp("2024-01-01"),
                         train_end=pd.Timestamp("2024-12-01"),
                         n_train_dates=30, n_train_samples=100, scores=scores)


def test_fusion_semantics_match_frozen_zscore_formula():
    model = CrossSectionalRidgeModel()
    codes = [f"C{i:03d}" for i in range(20)]
    raw = {
        "short": {c: 0.001 * i for i, c in enumerate(codes)},
        "medium": {c: -0.02 * i + 0.5 for i, c in enumerate(codes)},
        "long": {c: 0.1 * ((i % 5) - 2) for i, c in enumerate(codes)},
    }
    results = {p: _rank_result(p, scores) for p, scores in raw.items()}
    fused = model.fuse_periods(results)
    expected = {}
    for i, code in enumerate(codes):
        total = 0.0
        for period, weight in FUSION_WEIGHTS.items():
            vals = np.array([raw[period][c] for c in codes], dtype=float)
            magnitude = max(float(np.max(np.abs(vals))), 1.0)
            vals = vals / magnitude
            std = vals.std()
            z = (vals - vals.mean()) / std if std > 1e-12 / magnitude else np.zeros_like(vals)
            total += weight * float(z[i])
        expected[code] = total
    expected_ranked = sorted(expected.items(), key=lambda kv: (-kv[1], kv[0]))
    assert [code for code, _ in fused] == [code for code, _ in expected_ranked]
    np.testing.assert_allclose([v for _, v in fused],
                               [v for _, v in expected_ranked], rtol=0, atol=1e-15)
    # tie-break: equal fused scores fall back to sector code ascending
    tied = model.fuse_periods({
        p: _rank_result(p, {c: 1.0 for c in codes}) for p in FUSION_WEIGHTS})
    assert [code for code, _ in tied] == sorted(codes)


def test_fusion_is_affine_invariant_per_component():
    model = CrossSectionalRidgeModel()
    codes = [f"C{i:03d}" for i in range(30)]
    rng = np.random.default_rng(7)
    base = {p: {c: float(rng.normal()) for c in codes} for p in FUSION_WEIGHTS}
    rescaled = {}
    for idx, period in enumerate(FUSION_WEIGHTS):
        scale = 10.0 ** idx * 3.7
        offset = -12.5 * (idx + 1)
        rescaled[period] = {c: scale * base[period][c] + offset for c in codes}
    fused_base = model.fuse_periods({p: _rank_result(p, s) for p, s in base.items()})
    fused_rescaled = model.fuse_periods(
        {p: _rank_result(p, s) for p, s in rescaled.items()})
    assert [c for c, _ in fused_base] == [c for c, _ in fused_rescaled]


def test_fusion_degenerate_component_contributes_zero():
    model = CrossSectionalRidgeModel()
    codes = [f"C{i:03d}" for i in range(10)]
    constant = {c: 2.0 for c in codes}
    varying = {c: float(i) for i, c in enumerate(codes)}
    fused = model.fuse_periods({
        "short": _rank_result("short", constant),
        "medium": _rank_result("medium", varying),
        "long": _rank_result("long", varying),
    })
    reference = model.fuse_periods({
        "short": _rank_result("short", {c: 0.0 for c in codes}),
        "medium": _rank_result("medium", varying),
        "long": _rank_result("long", varying),
    })
    assert [c for c, _ in fused] == [c for c, _ in reference]


def test_evaluation_contract_uses_fused_top5_and_weighted_metrics():
    codes = [f"C{i:03d}" for i in range(124)]
    signal = "2025-04-02"
    scores = {h: {c: float(124 - i) for i, c in enumerate(codes)} for h in (10, 40, 120)}
    labels = {h: {c: float(i) * 0.001 for i, c in enumerate(codes)} for h in (10, 40, 120)}
    fused_ranking = rank_sectors({c: float(124 - i) for i, c in enumerate(codes)})
    rows = evaluate_date(1, signal, codes, scores, fused_ranking, labels)
    assert len(rows) == len(prediction_metric_contract()["metric_names"]) == 15
    by_name = {row["metric"]: row for row in rows}
    top5_mean = float(np.mean([labels[10][c] for c, _ in fused_ranking[:5]]))
    universe_mean = float(np.mean(list(labels[10].values())))
    assert by_name["Top5_forward_return_10"]["value"] == pytest.approx(top5_mean)
    assert by_name["Universe_forward_return_10"]["value"] == pytest.approx(universe_mean)
    assert by_name["Top5_minus_universe_10"]["value"] == pytest.approx(
        top5_mean - universe_mean)
    # Top5 comes from the FUSED ranking even when a horizon's own top5 differs
    rotated = list(fused_ranking[5:10]) + list(fused_ranking[:5]) + list(fused_ranking[10:])
    rows2 = evaluate_date(2, signal, codes, scores, rotated, labels)
    by_name2 = {row["metric"]: row for row in rows2}
    assert by_name2["Top5_forward_return_10"]["value"] == pytest.approx(
        float(np.mean([labels[10][c] for c, _ in rotated[:5]])))
    weighted_rankic = 0.25 * by_name["RankIC_10"]["value"] + \
        0.50 * by_name["RankIC_40"]["value"] + 0.25 * by_name["RankIC_120"]["value"]
    assert weighted_rankic == pytest.approx(-1.0, abs=1e-12)  # score desc vs label asc
    assert _config()["evaluationContract"]["weightedRankIc"].startswith("0.25*meanRankIc10")


# --- warnings immutable (items 35-37) + prohibitions (38-39) ---------------

def test_warnings_immutable_and_development_reuse_disclosure():
    config = _config()
    assert config["h40WeakEvidenceWarning"] is True
    assert config["h40WarningImmutable"] == "H40_NO_STRONG_STABILITY_EVIDENCE=true"
    assert config["neutralityCaveat"] is True
    assert config["neutralityCaveatImmutable"] == "NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true"
    assert config["developmentReuseWarning"] is True
    doc = (REPO / protocol.PROTOCOL_RELPATH).read_text(encoding="utf-8")
    for text in ("H40_NO_STRONG_STABILITY_EVIDENCE=true",
                 "NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT=true",
                 "DEVELOPMENT_REUSE_WARNING=true", "NOT independent validation",
                 "Fusion scale invariance"):
        assert text in doc, text
    trace = (REPO / protocol.TRACE_RELPATH).read_text(encoding="utf-8")
    assert "HORIZON_NOT_ADVANCED" in trace and "MINIMAL_REPLACEMENT" in doc


def test_no_parameter_no_model_search_flags_and_next_gate_values():
    config = _config()
    assert config["noParameterSearch"] is True and config["noModelSearch"] is True
    assert tuple(config["nextResearchGateAllowedValues"]) == protocol.NEXT_RESEARCH_GATE_VALUES
    assert "PARAMETER_RESEARCH_READY" not in config["nextResearchGateAllowedValues"]
    assert "VALIDATION_READY" not in config["nextResearchGateAllowedValues"]
    assert config["sourceResultCommit"] == protocol.SOURCE_RESULT_COMMIT
    assert config["sourceHandoffCommit"] == protocol.SOURCE_HANDOFF_COMMIT
    assert config["f0ReproducibilityDesign"]["gatesBeforeF1F2Evaluation"] is True
    assert config["componentSourcePolicy"]["retrainingForbidden"] is True


# --- protocol hash / config identity / determinism (items 40-43) -----------

def test_protocol_hash_frozen_and_config_sources_identity():
    payload = protocol.verify_protocol(REPO)
    assert protocol.FROZEN_PROTOCOL_HASH == (
        "4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7")
    assert protocol.protocol_hash(REPO) == protocol.FROZEN_PROTOCOL_HASH
    assert payload["frozenConstants"]["componentMappings"] == protocol.COMPONENT_MAPPINGS
    assert payload["frozenConstants"]["fusionWeights"] == protocol.FUSION_WEIGHTS
    assert payload["documentIdentity"]["protocol"]["path"] == protocol.PROTOCOL_RELPATH
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        protocol.verify_protocol(_tampered_root(protocol.PROTOCOL_RELPATH))
    with pytest.raises(ValueError, match="CONFIG_DRIFT_BLOCKER"):
        protocol.load_config(_tampered_root(protocol.CONFIG_RELPATH))
    with pytest.raises(ValueError, match="SOURCES_DRIFT_BLOCKER"):
        protocol.load_sources(_tampered_root(protocol.SOURCES_RELPATH))


def _tampered_root(relpath: str) -> Path:
    """Copy identity inputs to tmp_path and semantically alter one file."""
    import tempfile
    root = Path(tempfile.mkdtemp())
    for rel in (protocol.CONFIG_RELPATH, protocol.SOURCES_RELPATH,
                protocol.PROTOCOL_RELPATH, protocol.TRACE_RELPATH):
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((REPO / rel).read_bytes())
    target = root / relpath
    if target.suffix == ".json":
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["phase"] = "TAMPERED"
        target.write_text(json.dumps(payload), encoding="utf-8")
    else:
        target.write_bytes(target.read_bytes() + b"\n")
    return root


def test_deterministic_serialization():
    first = protocol.protocol_payload(REPO)
    second = protocol.protocol_payload(REPO)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert protocol.protocol_hash(REPO) == protocol.protocol_hash(REPO)
    assert protocol.load_config(REPO) == protocol.load_config(REPO)
    assert protocol.load_sources(REPO) == protocol.load_sources(REPO)


# --- lifecycle-aware result leak guard (items 44-45) ------------------------

def test_result_leak_guard_lifecycle_aware_synthetic(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    scan = protocol.result_leak_scan(empty)
    assert scan["clean"] is True and scan["leaks"] == []
    protocol.guard_no_formal_results(empty)  # empty root -> PASS
    missing = protocol.result_leak_scan(tmp_path / "does_not_exist")
    assert missing["clean"] is True  # absent root is not a leak
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / "horizon_component_replacement_v1_20260101_000000_000000_utc").mkdir()
    scan_fake = protocol.result_leak_scan(fake)
    assert scan_fake["clean"] is False
    assert scan_fake["leaks"] == ["horizon_component_replacement_v1_20260101_000000_000000_utc"]
    with pytest.raises(ValueError, match="PREREGISTRATION_RESULT_LEAK_BLOCKER"):
        protocol.guard_no_formal_results(fake)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "factor_alpha_audit_20260925_071934_967164_utc").mkdir()
    (unrelated / "horizon_specific_alpha_v1_20260925_130230_272283_utc").mkdir()
    scan_old = protocol.result_leak_scan(unrelated)
    assert scan_old["clean"] is True  # older formal results never block
    second_pattern = tmp_path / "second"
    second_pattern.mkdir()
    (second_pattern / "fusion_replacement_v1_20260101_000000_000000_utc").mkdir()
    with pytest.raises(ValueError, match="PREREGISTRATION_RESULT_LEAK_BLOCKER"):
        protocol.guard_no_formal_results(second_pattern)


def test_no_formal_result_created_by_this_module(tmp_path):
    # Lifecycle property: running the guards and payload builders never
    # creates result directories anywhere.
    root = tmp_path / "reports"
    root.mkdir()
    protocol.guard_no_formal_results(root)
    protocol.verify_protocol(REPO)
    protocol.load_config(REPO)
    protocol.load_sources(REPO)
    assert list(root.iterdir()) == []
    assert not hasattr(protocol, "run_formal")
    assert not hasattr(protocol, "fuse_formal")

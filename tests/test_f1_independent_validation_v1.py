"""Frozen contracts only; all training/evaluation/lifecycle values synthetic.

No test asserts perpetual absence in the real reports tree. The live leak
gate is a separate explicit invocation. Real Validation values are forbidden.
"""
from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from research import f1_independent_validation_v1_protocol as protocol
from strategies.sw_sector_rotation.src.common.temporal_integrity import temporal_boundaries, training_window

REPO = Path(__file__).resolve().parents[1]


def documents():
    return protocol.verify_protocol(REPO)


@pytest.fixture
def calendar():
    # Pure artificial trading sessions, not any Shenwan/Validation data.
    full = pd.bdate_range("2020-01-01", periods=700)
    eligible = full[180:640]
    return full, eligible


def source(calendar, *, origin, signal=250, horizon=10, **kwargs):
    full, eligible = calendar
    return protocol.training_source_admission(
        calendar=full, eligible_calendar=eligible, signal_date=eligible[signal - 1],
        observation_date=eligible[origin - 1], horizon=horizon,
        valid_target=kwargs.get("valid_target", True), valid_features=kwargs.get("valid_features", True))


def opened_record():
    return {"validationOpened": True, "validationState": "OBSERVED",
            "validationFirstOpenedAt": "2020-01-01T00:00:00+00:00",
            "validationProtocolHash": protocol.FROZEN_PROTOCOL_HASH,
            "candidateDefinitionHash": protocol.FROZEN_CANDIDATE_HASH,
            "validationPhaseDefinitionHash": protocol.FROZEN_PHASE_HASH,
            "splitPolicyHash": protocol.SPLIT_POLICY_HASH,
            "executionGitCommit": "1" * 40, "candidateSourceCommit": protocol.SOURCE_RESULT_COMMIT,
            "finalOos": "SEALED"}


def decision(**kwargs):
    args = dict(v1_rankic=0.1, v1_spread=0.03, v0_rankic=0.05, v0_spread=0.02,
                rankic_by_horizon={10: 0.1, 40: 0.1, 120: 0.1},
                block_rankic={"VB1": 0.1, "VB2": 0.1, "VB3": -0.02})
    args.update(kwargs)
    return protocol.validation_decision(**args)


def test_frozen_identity_and_seal():
    payload = documents()
    cfg, candidate = payload["config"], payload["candidate"]
    assert cfg["researchType"] == candidate["researchType"] == "F1_INDEPENDENT_VALIDATION_V1"
    assert cfg["phase"] == "PREREGISTERED" and cfg["scope"] == "PREREGISTRATION_ONLY"
    assert cfg["validationExecutionMode"] == "FROZEN_ALGORITHM_WALK_FORWARD"
    assert cfg["previousBlocker"] == "VALIDATION_PURGE_TRAINING_SEMANTICS_BLOCKER"
    assert cfg["resolution"] == "HUMAN_REVIEW_DECISION"
    assert cfg["blockerResolvedBeforeValidationOpen"] is True
    protocol.assert_preregistration_seal(cfg["seal"])
    assert candidate["candidateCount"] == candidate["controlCount"] == 1


def test_exact_candidate_control_factor_order_and_budget():
    definition = documents()["candidate"]
    f19 = list(protocol.source_protocol.FROZEN_FACTORS_19)
    assert definition["candidate"]["id"] == "V1_F1_CANDIDATE"
    assert definition["control"]["id"] == "V0_CONTROL"
    assert definition["candidate"]["components"] == {"h10": "H10_C", "h40": "C0_H40", "h120": "C0_H120"}
    assert definition["control"]["components"] == {"h10": "C0_H10", "h40": "C0_H40", "h120": "C0_H120"}
    assert definition["candidate"]["factors"]["h10"] == ["d10", "p5", "align", "vc", "dd20"]
    assert definition["candidate"]["factors"]["h40"] == definition["candidate"]["factors"]["h120"] == f19
    assert all(v == f19 for v in definition["control"]["factors"].values())
    assert {"F2_H10_H40_REPLACEMENT", "H40_S", "H120_S", "H120_C"} <= set(definition["forbiddenCandidates"])


def test_model_target_fusion_and_non_tradable_contract():
    common = documents()["candidate"]["common"]
    assert common["model"] == "NumPyRidge" and common["alpha"] == .01
    assert common["xPreprocessing"] == "NONE_RAW_X_NO_TRAIN_STANDARDIZATION"
    assert common["trainingWindowCalendarMonths"] == 6 and common["minimumValidTrainingDates"] == 30
    assert common["trainingWindowAnchor"] == "PER_HORIZON_LABEL_CUTOFF"
    assert common["trainingTarget"] == "SAME_TRAINING_DATE_CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert common["evaluationLabel"] == "ABSOLUTE_FORWARD_RETURN"
    assert common["fusion"] == "PER_DATE_PER_HORIZON_CROSS_SECTIONAL_ZSCORE_POPULATION_STD_DDOF_0"
    assert common["fusionWeights"] == {"h10": .25, "h40": .5, "h120": .25}
    assert common["topK"] == 5 and common["ranking"] == "FUSED_SCORE_DESCENDING"
    assert common["tieBreak"] == "SECTOR_CODE_ASCENDING"
    assert common["top5"] == "FIRST_FIVE_OF_FUSED_RANKING"
    assert common["strictPit"] is False and common["classification"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert common["executable"] is common["tradable"] is False


def test_split_derived_blocks_dates_and_purge_admission():
    split = documents()["split"]
    assert split["splitPolicyHash"] == protocol.SPLIT_POLICY_HASH
    assert split["validationOrdinalIds"] == list(range(221, 281))
    assert split["blocks"] == protocol.derive_validation_blocks() == [
        {"id": "VB1", "first": 221, "last": 240},
        {"id": "VB2", "first": 241, "last": 260},
        {"id": "VB3", "first": 261, "last": 280}]
    assert len(split["knownDateByOrdinal"]) == split["validationAvailableCountAtPreregistration"] == 19
    assert all(split["knownDateByOrdinal"].get(str(n)) is None for n in range(240, 281))
    assert split["unknownDates"]["date"] is None
    assert split["purge1"]["evaluationEligible"] is False
    assert split["purge1"]["trainingSourceEligible"] is True
    assert split["purge1"]["requiresMatureLabel"] is split["purge1"]["requiresAsOfCutoff"] is True
    assert split["earlierValidationObservations"]["futureTrainingEligible"] is True
    assert split["earlierValidationObservations"]["researchAdaptationAllowed"] is False
    assert split["purge2"]["futureFinalOosTrainingEligibility"] == "UNDECIDED_REQUIRES_SEPARATE_FINAL_OOS_PREREGISTRATION"


def test_snapshot_prohibitions_policies_and_opening_contract():
    cfg = documents()["config"]
    assert all(cfg["searchProhibitions"].values())
    data = cfg["dataSnapshotPolicy"]
    assert data["strictPit"] is False and data["futureSnapshotId"] is None
    assert data["disclosure"] == "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST"
    assert "APPEND_ONLY_UNCHANGED" in data["appendPolicy"]
    assert "ALL_60" in data["futureRunAvailability"]
    assert "POST_VALIDATION_DEVELOPMENT" in cfg["failurePolicy"]
    assert "SEPARATE_FINAL_OOS_PREREGISTRATION_REQUIRED" in cfg["passPolicy"]
    assert cfg["futureOpening"]["explicitAuthorizationRequired"] is True
    assert cfg["futureOpening"]["runnerDefaultOpen"] is False
    assert cfg["futureOpening"]["oneWay"] == "UNSEEN_TO_OBSERVED_NEVER_RESET"
    assert cfg["operationalException"]["researchEnvironmentChanged"] is False
    assert cfg["operationalException"]["hostPortPublicationChanged"] is True
    assert cfg["operationalException"]["currentHostMappings"] == {"19200": 9200, "19201": 9201}


def test_hashes_and_deterministic_serialization():
    payload = documents()
    assert protocol.candidate_definition_hash(REPO) == protocol.FROZEN_CANDIDATE_HASH
    assert protocol.validation_phase_definition_hash(REPO) == protocol.FROZEN_PHASE_HASH
    assert protocol.protocol_hash(REPO) == protocol.FROZEN_PROTOCOL_HASH
    assert protocol.canonical_hash({"a": 1, "b": 2}) == protocol.canonical_hash({"b": 2, "a": 1})
    with pytest.raises(ValueError):
        protocol.canonical_hash({"value": float("nan")})
    assert payload["config"]["source"]["resultCommit"] == protocol.SOURCE_RESULT_COMMIT
    assert payload["config"]["source"]["handoffCommit"] == protocol.SOURCE_HANDOFF_COMMIT


@pytest.mark.parametrize("filename,key,value", [
    (protocol.CANDIDATE_PATH, "candidateCount", 2),
    (protocol.CANDIDATE_PATH, "candidate.id", "F2_H10_H40_REPLACEMENT"),
    (protocol.CANDIDATE_PATH, "candidate.factors.h10", ["d10"]),
    (protocol.CANDIDATE_PATH, "candidate.components.h40", "H40_S"),
    (protocol.CANDIDATE_PATH, "candidate.components.h120", "H120_C"),
    (protocol.CANDIDATE_PATH, "common.alpha", .1),
    (protocol.CANDIDATE_PATH, "common.trainingWindowCalendarMonths", 3),
    (protocol.CANDIDATE_PATH, "common.minimumValidTrainingDates", 20),
    (protocol.CANDIDATE_PATH, "common.trainingTarget", "ABSOLUTE_FORWARD_RETURN"),
    (protocol.CANDIDATE_PATH, "common.xPreprocessing", "STANDARDIZE"),
    (protocol.CANDIDATE_PATH, "common.fusionWeights.h10", .5),
    (protocol.CANDIDATE_PATH, "common.topK", 10),
    (protocol.CANDIDATE_PATH, "common.tieBreak", "DESCENDING"),
    (protocol.CONFIG_PATH, "searchProhibitions.validationPerformanceAdaptation", False),
    (protocol.CONFIG_PATH, "gates.temporal.positiveWeightedRankIcBlocksAtLeast", 1),
    (protocol.CONFIG_PATH, "gates.horizonRedFlag.threshold", -.03),
    (protocol.SPLIT_PATH, "purge1.trainingSourceEligible", False),
    (protocol.SPLIT_PATH, "earlierValidationObservations.futureTrainingEligible", False),
])
def test_semantic_drift_fails_closed(tmp_path, filename, key, value):
    for name in (protocol.CONFIG_PATH, protocol.CANDIDATE_PATH, protocol.SPLIT_PATH,
                 protocol.DOCUMENT_PATH, protocol.TRACE_PATH):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / name).read_bytes())
    path = tmp_path / filename
    data = json.loads(path.read_text())
    cursor = data
    fields = key.split(".")
    for k in fields[:-1]:
        cursor = cursor[k]
    cursor[fields[-1]] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="SEMANTIC_CONFLICT"):
        protocol.verify_protocol(tmp_path)


def test_purge1_maturity_and_rolling_window(calendar):
    assert source(calendar, origin=200, signal=221)["accepted"] is True
    assert source(calendar, origin=219, signal=221)["reason"] == "UNMATURED_LABEL"
    assert source(calendar, origin=101, signal=280)["reason"] == "OUTSIDE_ROLLING_WINDOW"
    assert source(calendar, origin=200, signal=221, valid_target=False)["reason"] == "INVALID_TARGET"
    assert source(calendar, origin=200, signal=221, valid_features=False)["reason"] == "INVALID_FEATURES"


@pytest.mark.parametrize("origin", [250, 251, 280, 401])
def test_current_and_future_origins_never_train(calendar, origin):
    assert source(calendar, origin=origin)["reason"] == "NOT_STRICTLY_HISTORICAL"


def test_earlier_validation_matures_independently_by_horizon(calendar):
    assert source(calendar, origin=230, signal=235)["reason"] == "UNMATURED_LABEL"
    assert source(calendar, origin=230, signal=250, horizon=10)["accepted"] is True
    assert source(calendar, origin=230, signal=250, horizon=120)["reason"] == "UNMATURED_LABEL"
    # Existing <= rule: equality at label end is legal after the signal close.
    assert source(calendar, origin=240, signal=250, horizon=10)["accepted"] is True


def test_existing_temporal_boundaries_and_minimum_are_reused(calendar):
    full, eligible = calendar
    signal, origins = eligible[249], eligible[100:260]
    boundary = temporal_boundaries(full[:int(full.get_loc(signal)) + 1], signal, 10, 6)
    audit = protocol.training_audit_contract_fixture(
        calendar=full, eligible_calendar=eligible, signal_date=signal, horizon=10,
        observation_dates=origins, valid_target_dates=origins, valid_feature_dates=origins)
    expected = training_window([d for d in origins if d < signal], boundary, 30)
    assert audit["acceptedTrainingDates"] == [str(d.date()) for d in expected]
    assert audit["futureLeakCount"] == 0 and audit["rejectedUnmaturedCount"] == 9
    assert audit["latestAcceptedTrainingDate"] == str(eligible[239].date())
    assert audit["latestAcceptedLabelEndDate"] == str(signal.date())
    assert sum(audit["phaseSourceCounts"].values()) == audit["acceptedTrainingDateCount"]
    assert audit["phaseSourceCounts"]["purge1"] > 0 and audit["phaseSourceCounts"]["earlierValidation"] == 20
    assert set(documents()["config"]["trainingAuditContract"]["requiredFields"]) <= set(audit)
    small = protocol.training_audit_contract_fixture(
        calendar=full, eligible_calendar=eligible, signal_date=signal, horizon=10,
        observation_dates=origins[-31:-30], valid_target_dates=origins, valid_feature_dates=origins)
    assert small["acceptedTrainingDateCount"] == 0 and small["status"] == "INSUFFICIENT_TRAINING_DATA"


def test_training_helpers_do_not_load_values_or_fit(calendar, monkeypatch):
    from strategies.sw_sector_rotation.src.model.model import NumPyRidge
    def forbidden(*args, **kwargs):
        raise AssertionError("no price reads, labels or model fitting during preregistration")
    monkeypatch.setattr(pd, "read_csv", forbidden)
    monkeypatch.setattr(NumPyRidge, "fit", forbidden)
    before = protocol.candidate_definition_hash(REPO)
    assert source(calendar, origin=230)["accepted"] is True
    assert protocol.candidate_definition_hash(REPO) == before
    with pytest.raises(TypeError):
        protocol.training_source_admission(calendar=calendar[0], eligible_calendar=calendar[1],
            signal_date=calendar[1][249], observation_date=calendar[1][229], horizon=10,
            valid_target=True, valid_features=True, validation_performance=.9)


@pytest.mark.parametrize("ordinal", [101, 200, 220, 281, 400, 401, 460])
def test_purge_and_oos_never_evaluated_even_with_validation_authorization(ordinal):
    with pytest.raises(PermissionError):
        protocol.guard_validation_evaluation("validation", [ordinal], opened_record(), explicit_authorization=True)


def test_default_seal_and_final_oos_guard():
    seal = documents()["config"]["seal"]
    with pytest.raises(PermissionError):
        protocol.guard_validation_evaluation("validation", [221], seal)
    with pytest.raises(PermissionError):
        protocol.validate_opening_transition(seal, opened_record())
    with pytest.raises(PermissionError):
        protocol.guard_validation_evaluation("final_oos", [401], opened_record(), explicit_authorization=True)
    protocol.validate_opening_transition(seal, opened_record(), explicit_authorization=True)
    protocol.guard_validation_evaluation("validation", list(range(221, 281)), opened_record(), explicit_authorization=True)


def test_one_way_opening_synthetic_lifecycle(tmp_path):
    seal, opened = documents()["config"]["seal"], opened_record()
    protocol.validate_opening_transition(seal, opened, explicit_authorization=True)
    # This persistence is a synthetic fixture, never the live seal or ledger.
    path = tmp_path / "synthetic-opening-record.json"
    path.write_text(json.dumps(opened))
    observed = json.loads(path.read_text())
    protocol.validate_opening_transition(observed, deepcopy(observed))
    with pytest.raises(PermissionError, match="CANNOT_RESET"):
        protocol.validate_opening_transition(observed, seal, explicit_authorization=True)
    rewritten = deepcopy(observed)
    rewritten["validationFirstOpenedAt"] = "2021-01-01T00:00:00+00:00"
    with pytest.raises(PermissionError, match="CANNOT_RESET"):
        protocol.validate_opening_transition(observed, rewritten, explicit_authorization=True)


@pytest.mark.parametrize("field", ["validationProtocolHash", "candidateDefinitionHash", "validationPhaseDefinitionHash",
                                  "splitPolicyHash", "executionGitCommit", "candidateSourceCommit", "validationFirstOpenedAt", "finalOos"])
def test_opening_record_integrity(field):
    proposed = opened_record()
    proposed[field] = "invalid"
    with pytest.raises(ValueError):
        protocol.validate_opening_transition(documents()["config"]["seal"], proposed, explicit_authorization=True)


def test_runtime_result_leak_lifecycle_uses_only_synthetic_files(tmp_path):
    assert protocol.assert_no_validation_results(tmp_path)["clean"]
    folder = tmp_path / "f1_independent_validation_v1_synthetic"
    folder.mkdir()
    (folder / "predictions.csv").write_text("synthetic-placeholder\n")
    with pytest.raises(PermissionError, match="INDEPENDENCE_ALREADY_COMPROMISED"):
        protocol.assert_no_validation_results(tmp_path)
    # Normal protocol tests still pass after synthetic formal results exist.
    documents()


@pytest.mark.parametrize("metadata", [
    {"phase": "VALIDATION", "validation": "SEALED", "finalOos": "SEALED"},
    {"phase": "DEVELOPMENT", "validation": "SEALED", "finalOos": "SEALED", "validationOpened": True},
    {"phase": "FINAL_OOS", "validation": "OBSERVED", "finalOos": "OPEN"},
])
def test_metadata_leak_cannot_hide_under_neutral_run_name(tmp_path, metadata):
    folder = tmp_path / "neutral_name"
    folder.mkdir()
    (folder / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(PermissionError):
        protocol.assert_no_validation_results(tmp_path)


def test_unknown_performance_and_malformed_metadata_fail_closed(tmp_path):
    (tmp_path / "aggregate_metrics.json").write_text("{}")
    assert protocol.result_leak_scan(tmp_path)["clean"] is False
    (tmp_path / "metadata.json").write_text("malformed")
    assert protocol.result_leak_scan(tmp_path)["clean"] is False


@pytest.mark.parametrize("overrides,reason", [
    ({"v1_rankic": 0}, "VALIDATION_LEVEL1_FAIL"),
    ({"v1_spread": 0}, "VALIDATION_LEVEL1_FAIL"),
    ({"v1_rankic": .05, "v1_spread": .02}, "VALIDATION_RELATIVE_GATE_FAIL"),
    ({"v1_rankic": .1, "v1_spread": .01}, "VALIDATION_RELATIVE_GATE_FAIL"),
    ({"rankic_by_horizon": {10: -.020001, 40: .1, 120: .1}}, "VALIDATION_HORIZON_RED_FLAG"),
    ({"block_rankic": {"VB1": .1, "VB2": 0, "VB3": -.02}}, "VALIDATION_TEMPORAL_STABILITY_FAIL"),
    ({"block_rankic": {"VB1": .1, "VB2": -.03, "VB3": -.03}}, "VALIDATION_TEMPORAL_STABILITY_FAIL"),
])
def test_each_gate_blocks_unique_pass(overrides, reason):
    result = decision(**overrides)
    assert result["status"] == "VALIDATION_FAIL" and reason in result["failureReasons"]
    assert result["nextEligibleAction"] == "POST_VALIDATION_DEVELOPMENT" and result["finalOos"] == "SEALED"


@pytest.mark.parametrize("overrides", [
    {}, {"v1_rankic": .05, "v1_spread": .03}, {"v1_rankic": .1, "v1_spread": .02},
    {"rankic_by_horizon": {10: -.02, 40: .1, 120: .1}},
    {"block_rankic": {"VB1": .1, "VB2": .1, "VB3": -.03}},
])
def test_strict_relative_and_threshold_boundaries_pass_only_as_defined(overrides):
    result = decision(**overrides)
    assert result["status"] == "VALIDATION_PASS"
    assert result["nextEligibleAction"] == "FINAL_OOS_PREREGISTRATION_ELIGIBLE"
    assert result["executable"] is result["tradable"] is False and result["finalOos"] == "SEALED"


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True])
def test_missing_or_nonfinite_primary_never_passes(value):
    with pytest.raises(ValueError, match="METRIC_INCOMPLETE"):
        decision(v1_rankic=value)


def test_missing_horizon_or_block_never_passes():
    with pytest.raises(ValueError):
        decision(rankic_by_horizon={10: .1, 40: .1})
    with pytest.raises(ValueError):
        decision(block_rankic={"VB1": .1, "VB2": .1})

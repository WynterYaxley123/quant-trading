"""Factor Set V2 protocol and lifecycle-aware historical integrity gates.

The preregistration result-leak rule is tested on temporary directories;
existing formal results are validated through Git lineage and provenance.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess

import pytest

from research import factor_set_v2_protocol as protocol
from research.factor_set_v2_preregistration_guard import assert_no_v2_formal_results

FROZEN_ORDER = (
    "d5", "d10", "d20", "d60", "d120", "p5", "p10", "p20", "p60", "p120",
    "align", "v5", "v20", "vc", "rev5", "rev10", "dd20", "dd60", "rsi",
)
REPO = Path(__file__).resolve().parents[1]
PREREG_COMMIT = "b836f27e33987ea3d987b8683a38acc442cb2cdd"
RESULT_COMMIT = "8803f618e4a7a5ea5c65d550ecf71063182782e6"
FROZEN_PATHS = (
    "docs/research/shenwan_factor_set_v2_preregistration.md",
    "research/configs/factor_set_v2_candidates.json",
    "research/factor_set_v2_protocol.py",
)
D2_SUMMARY = (REPO / "reports/research/shenwan_sector_index"
              / "iteration1_20260924_163607_787266_utc/candidate_summary.json")


def _config() -> dict:
    return protocol.load_candidate_config(REPO)


def _candidate(cid: str) -> dict:
    return next(row for row in _config()["candidates"] if row["candidateId"] == cid)


def test_c0_is_exact_d2_control_with_frozen_settings():
    control = _config()["control"]
    assert control["candidateId"] == "C0" and control["isControl"] is True
    assert control["sourceCandidate"] == "D2"
    assert tuple(control["factorList"]) == FROZEN_ORDER and control["factorCount"] == 19
    assert control["target"] == "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert control["preprocessing"] == "NONE_RAW" and control["alpha"] == 0.01
    assert control["trainWindow"] == "6 calendar months"
    assert control["horizons"] == [10, 40, 120] and control["fusion"] == [0.25, 0.5, 0.25]
    assert control["topK"] == 5
    assert control["countsAgainstNewBudget"] is False
    assert control["frozenMetrics"] == protocol.FROZEN_C0_METRICS


def test_c0_frozen_metrics_match_existing_d2_artifact_read_only():
    if not D2_SUMMARY.exists():  # fresh checkout without generated artifacts
        pytest.skip("Iteration-1 D2 artifact not present on disk")
    summary = json.loads(D2_SUMMARY.read_text(encoding="utf-8"))
    row = next(r for r in summary["comparison"] if r["candidate"] == "D2")
    frozen = protocol.FROZEN_C0_METRICS
    assert row["Weighted_RankIC"] == frozen["weightedRankIc"]
    assert row["Weighted_Spread"] == frozen["weightedSpread"]
    for horizon in (10, 40, 120):
        assert row[f"RankIC_{horizon}"] == frozen["rankIcByHorizon"][str(horizon)]
        assert row[f"Spread_{horizon}"] == frozen["spreadByHorizon"][str(horizon)]


def test_candidate_budget_capped_and_not_backfilled():
    config = _config()
    assert config["candidateBudget"]["maxNewCandidates"] == 4
    assert config["candidateBudget"]["totalWithControl"] == 5
    assert config["candidateBudget"]["closedAfterPreregistration"] is True
    assert config["candidateBudget"]["adaptiveSearch"] == "FORBIDDEN"
    assert len(config["candidates"]) == 3 <= 4  # V2-C NOT_ADMISSIBLE; slot not back-filled
    assert len(config["candidates"]) + 1 <= 5
    assert [row["candidateId"] for row in config["excludedCandidates"]] == ["V2_C"]
    assert config["excludedCandidates"][0]["status"] == "NOT_ADMISSIBLE"


def test_exact_candidate_factor_lists_frozen_and_counts():
    assert protocol.CANDIDATE_IDS == ("V2_A", "V2_B", "V2_D")
    assert protocol.CANDIDATE_FACTORS["V2_A"] == ("v20",)
    assert protocol.CANDIDATE_FACTORS["V2_B"] == ("v5", "v20")
    assert protocol.CANDIDATE_FACTORS["V2_D"] == ("d20", "p60", "align", "v20", "rev5", "dd20")
    assert _candidate("V2_A")["factorList"] == ["v20"] and _candidate("V2_A")["factorCount"] == 1
    assert _candidate("V2_B")["factorList"] == ["v5", "v20"] and _candidate("V2_B")["factorCount"] == 2
    v2d = _candidate("V2_D")
    assert v2d["factorList"] == ["d20", "p60", "align", "v20", "rev5", "dd20"]
    assert v2d["factorCount"] == 6
    assert 3 <= v2d["factorCount"] <= protocol.V2_D_HARD_CAP == 6


def test_factor_order_valid_deterministic_and_duplicate_free():
    for cid in protocol.CANDIDATE_IDS:
        factors = tuple(_candidate(cid)["factorList"])
        assert all(name in FROZEN_ORDER for name in factors)
        assert len(set(factors)) == len(factors)  # no duplicate factor
        positions = [FROZEN_ORDER.index(name) for name in factors]
        assert positions == sorted(positions)  # deterministic frozen pipeline order
    assert protocol.factor_indices(["v5", "v20"]) == (11, 12)
    assert protocol.factor_indices(["d20", "p60", "align", "v20", "rev5", "dd20"]) == (
        2, 8, 10, 12, 14, 16)
    with pytest.raises(ValueError, match="FACTOR_NAME_INVALID"):
        protocol.factor_indices(["v20", "not_a_factor"])
    with pytest.raises(ValueError, match="DUPLICATE|INVALID"):
        protocol.factor_indices(["v20", "v20"])
    with pytest.raises(ValueError, match="NOT_DETERMINISTIC"):
        protocol.factor_indices(["v20", "v5"])


def test_one_shared_factor_set_across_all_horizons():
    for cid in protocol.CANDIDATE_IDS:
        row = _candidate(cid)
        assert "factorListByHorizon" not in row and "horizonFactorSets" not in row
        assert row["horizons"] == [10, 40, 120]
        assert row["fusion"] == [0.25, 0.5, 0.25]
    assert _config()["frozenSettings"]["sharedFactorSetAcrossHorizons"] is True


def test_raw_x_excess_target_alpha_window_horizons_fusion_topk():
    settings = _config()["frozenSettings"]
    assert settings["preprocessing"] == "NONE_RAW"
    assert settings["target"] == "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert settings["model"] == "NumPyRidge" and settings["alpha"] == 0.01
    assert settings["trainWindowCalendarMonths"] == 6
    assert settings["trainWindowAnchor"] == "per_horizon_label_cutoff"
    assert settings["minimumValidTrainingDays"] == 30
    assert settings["horizons"] == [10, 40, 120]
    assert settings["fusion"] == [0.25, 0.5, 0.25]
    assert settings["fusionDefinition"] == "0.25*pred10 + 0.50*pred40 + 0.25*pred120"
    assert settings["topK"] == 5 and settings["topKSelection"] == "FUSED_SCORE_TOP5"
    assert settings["universe"] == "U0_FIXED_124" and settings["sectorCount"] == 124
    for cid in protocol.CANDIDATE_IDS:
        row = _candidate(cid)
        assert row["preprocessing"] == "NONE_RAW" and row["target"] == settings["target"]
        assert row["model"] == "NumPyRidge" and row["alpha"] == 0.01
        assert row["trainWindow"] == "6 calendar months"
        assert row["horizons"] == [10, 40, 120] and row["fusion"] == [0.25, 0.5, 0.25]
        assert row["topK"] == 5


def test_development_only_guards_and_sealed_phases():
    config = _config()
    assert config["seals"] == {"developmentOnly": True, "validationSealed": True,
                               "finalOosSealed": True, "noParameterSearch": True,
                               "noSignFlip": True}
    protocol.guard_factor_set_v2_scope("development", [1, 50, 100])
    with pytest.raises(PermissionError, match="PURGED_ORDINAL_ACCESS_ERROR"):
        protocol.guard_factor_set_v2_scope("development", [101])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_factor_set_v2_scope("development", [221])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_factor_set_v2_scope("development", [401])
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        protocol.guard_factor_set_v2_scope("validation", [221])
    payload = protocol.factor_set_v2_payload(REPO)
    assert payload["research_identity"]["validation_access"] == "SEALED"
    assert payload["research_identity"]["final_oos_access"] == "SEALED"


def test_no_sign_inversion_or_sign_fields_anywhere():
    config = _config()
    assert protocol._has_banned_sign_key(config) is False
    assert protocol._has_banned_sign_key({"sign": -1}) is True
    tampered = json.loads(json.dumps(config))
    tampered["candidates"][0]["sign"] = -1
    with pytest.raises(ValueError, match="SIGN_MANIPULATION_FORBIDDEN"):
        protocol._validate_config(tampered)
    for banned in ("sign_flip_or_inversion", "sign_normalization", "per_horizon_factor_sets",
                   "alpha_tuning", "model_tuning", "adaptive_candidate_addition"):
        assert banned in config["prohibitions"]


def test_redundancy_rule_encoded_and_candidates_respect_it():
    config = _config()
    rule = config["redundancyRule"]
    assert rule["threshold"] == protocol.REDUNDANCY_THRESHOLD == 0.80
    frozen = [(a, b, v) for a, b, v in protocol.FROZEN_HIGH_REDUNDANCY_PAIRS]
    assert [(r["factorA"], r["factorB"], r["meanSpearman"]) for r in rule["highRedundancyPairs"]] == frozen
    assert len(frozen) == 16
    assert protocol.is_high_redundancy("d20", "p20") is True
    assert protocol.is_high_redundancy("p20", "d20") is True  # unordered pair
    assert protocol.is_high_redundancy("v5", "v20") is False  # 0.6298 premise
    assert protocol.is_high_redundancy("align", "d20") is False
    v2d = _candidate("V2_D")["factorList"]
    for i, a in enumerate(v2d):
        for b in v2d[i + 1:]:
            assert protocol.is_high_redundancy(a, b) is False, (a, b)
    assert rule["v2dInternalPairsAllBelowThreshold"] is True
    assert _candidate("V2_B")["premise"]["v5_v20_mean_daily_spearman"] == (
        protocol.V2_B_PREMISE_V5_V20_SPEARMAN)
    assert _candidate("V2_B")["premise"]["belowThreshold"] is True


def test_v2d_regime_labels_and_selection_trace_consistency():
    v2d = _candidate("V2_D")
    assert tuple(v2d["regimeUnstableFactors"]) == protocol.V2_D_REGIME_UNSTABLE == (
        "d20", "p60", "align", "rev5", "dd20")
    assert "v20" not in v2d["regimeUnstableFactors"]
    assert v2d["regimeUnstableJustification"]
    skipped = [step for step in v2d["selectionTrace"] if step["decision"] == "SKIPPED_HIGH_REDUNDANCY"]
    assert [step["tried"] for step in skipped] == ["p20", "rsi", "rev10"]
    for step in skipped:
        pair = (step["tried"], {"p20": "d20", "rsi": "d20", "rev10": "d20"}[step["tried"]])
        assert protocol.is_high_redundancy(*pair) is True
    selected = [step["tried"] for step in v2d["selectionTrace"]
                if step["decision"] == "SELECTED"]
    assert selected == list(v2d["factorList"])
    config = _config()
    assert config["regimeRule"]["blocks"] == [list(b) for b in protocol.STABILITY_BLOCKS]
    assert config["regimeRule"]["label"] == "REGIME_UNSTABLE"


def test_advancement_and_simplicity_rules_frozen():
    config = _config()
    advancement = config["advancementRule"]
    assert advancement["horizonRedFlag"]["threshold"] == protocol.ADVANCEMENT["horizonRedFlagRankIc"] == -0.02
    assert advancement["horizonRedFlag"]["frozenBeforeResults"] is True
    assert advancement["validationAdmission"] is False
    assert advancement["advancedStatus"] == "V2_ADVANCED_FOR_FURTHER_REVIEW"
    assert advancement["level2RelativeToC0"]["requireAtLeastOne"] is True
    simplicity = config["simplicityRule"]
    assert simplicity["SIMPLICITY_PREFERENCE"] is True
    assert simplicity["rankIcTieBand"] == 0.01 and simplicity["spreadTieBand"] == 0.01
    metrics = config["metrics"]
    assert metrics["winnerSelectionByMaxValue"] == "FORBIDDEN"
    for required in ("weightedRankIc", "weightedSpread", "medianRankIc10",
                     "stabilityAcrossDevelopmentBlocks", "extremeDateSensitivity",
                     "candidateSimplicityFactorCount"):
        assert required in metrics["comparisonSet"]
    assert config["extremeDateSensitivity"]["extremeDatesEachTail"] == 5
    assert config["extremeDateSensitivity"]["descriptiveOnly"] is True


def test_protocol_hash_frozen_and_config_matches_protocol():
    payload = protocol.verify_frozen_factor_set_v2_protocol(base=REPO)
    assert protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH == (
        "3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4")
    assert protocol.factor_set_v2_protocol_hash(payload) == (
        protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH)
    assert payload["candidate_config_path"] == "research/configs/factor_set_v2_candidates.json"
    assert payload["candidate_config"] == _config()
    assert payload["frozen_settings"] == protocol.FROZEN_SETTINGS
    assert payload["control_identity"]["frozenMetrics"] == protocol.FROZEN_C0_METRICS
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        protocol.verify_frozen_factor_set_v2_protocol(supplied_hash="0" * 64, base=REPO)
    with pytest.raises(ValueError, match="CANDIDATE_LIST_MISMATCH"):
        protocol._validate_config(_tampered(lambda c: c["candidates"][1].update(
            {"factorList": ["v20"], "factorCount": 1})))


def _tampered(edit) -> dict:
    config = json.loads(json.dumps(protocol.load_candidate_config(REPO)))
    edit(config)
    return config


def test_config_validation_rejects_budget_settings_and_order_drift():
    with pytest.raises(ValueError, match="BUDGET_VIOLATION"):
        protocol._validate_config(_tampered(lambda c: c["candidates"].append(
            {"candidateId": "V2_E", "factorList": ["rsi"], "factorCount": 1,
             "target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN", "preprocessing": "NONE_RAW",
             "model": "NumPyRidge", "alpha": 0.01, "trainWindow": "6 calendar months",
             "horizons": [10, 40, 120], "fusion": [0.25, 0.5, 0.25], "topK": 5})))
    with pytest.raises(ValueError, match="SETTINGS_MISMATCH"):
        protocol._validate_config(_tampered(lambda c: c["candidates"][0].update({"alpha": 1.0})))
    with pytest.raises(ValueError, match="REDUNDANCY_RULE_MISMATCH"):
        protocol._validate_config(_tampered(lambda c: c["redundancyRule"].update({"threshold": 0.9})))
    with pytest.raises(ValueError, match="CONTROL_IDENTITY_MISMATCH"):
        protocol._validate_config(_tampered(lambda c: c["control"].update({"sourceCandidate": "D0"})))


def test_preregistration_result_leak_guard_lifecycle(tmp_path):
    root = tmp_path / "reports"
    assert_no_v2_formal_results(root)  # A fresh checkout is legal.
    root.mkdir()
    (root / "iteration1_older_formal_run").mkdir()
    assert_no_v2_formal_results(root)  # Earlier, unrelated results are legal.
    for name in (
        "factor_set_v2_20990101_000000_utc",
        "iteration2_synthetic_result",
        "v2_candidate_synthetic_result",
    ):
        entry = root / name
        entry.mkdir()
        with pytest.raises(ValueError, match="PREREGISTRATION_RESULT_LEAK_BLOCKER"):
            assert_no_v2_formal_results(root)
        entry.rmdir()


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={REPO}", *args], cwd=REPO,
        text=True, capture_output=True, check=False,
    )


def test_v2_historical_preregistration_precedes_result_and_protocol_is_immutable():
    lineage = _git("merge-base", "--is-ancestor", PREREG_COMMIT, RESULT_COMMIT)
    assert lineage.returncode == 0, f"V2_PREREGISTRATION_LINEAGE_BLOCKER: {lineage.stderr}"
    changed = _git("diff", "--name-only", PREREG_COMMIT, RESULT_COMMIT,
                   "--", *FROZEN_PATHS)
    assert changed.returncode == 0 and not changed.stdout.strip(), (
        f"V2_PROTOCOL_IMMUTABILITY_BLOCKER: {changed.stdout} {changed.stderr}"
    )


def test_existing_v2_results_have_frozen_provenance_read_only():
    root = REPO / "reports/research/shenwan_sector_index"
    if not root.exists():
        pytest.skip("generated V2 reports not present on disk")
    runs = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("factor_set_v2_"))
    assert runs, "V2_RESULT_PROVENANCE_BLOCKER: no formal V2 run found"
    expected_factors = {"C0": list(FROZEN_ORDER), "V2_A": ["v20"],
                        "V2_B": ["v5", "v20"],
                        "V2_D": ["d20", "p60", "align", "v20", "rev5", "dd20"]}
    for run in runs:
        metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["run_id"] == run.name
        assert metadata["preregistrationCommit"] == PREREG_COMMIT
        assert metadata["protocolHash"] == protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH
        assert metadata["candidateIds"] == list(expected_factors)
        assert metadata["candidateFactorLists"] == expected_factors
        assert "V2_C" not in metadata["candidateIds"]
        assert not (run / "V2_C").exists()
        for relative, expected_hash in metadata["content_sha256"].items():
            assert hashlib.sha256((run / relative).read_bytes()).hexdigest() == expected_hash, (
                f"V2_RESULT_PROVENANCE_BLOCKER: {run.name}/{relative}"
            )


def test_payload_is_result_free_and_hypotheses_are_labeled():
    payload = protocol.factor_set_v2_payload(REPO)
    assert payload["research_identity"]["POST_AUDIT_DEVELOPMENT_RESEARCH"] is True
    assert payload["research_identity"]["NOT_INDEPENDENT_VALIDATION"] is True
    assert payload["research_identity"]["NOT_OOS_EVIDENCE"] is True
    assert payload["candidate_config"]["researchFlags"]["NO_V2_FORMAL_RESULTS_THIS_ROUND"] is True
    assert payload["audit_type"] == "FACTOR_SET_V2_PREREGISTRATION"
    for row in payload["candidate_config"]["candidates"]:
        assert not set(row) & {"metrics", "results", "performance", "rankIc", "weightedRankIc"}
        assert all("POST-AUDIT" in tag or tag.startswith("Q") for tag in row["hypothesisTags"])
        assert row["hypothesisTags"]  # every candidate discloses its post-audit origin

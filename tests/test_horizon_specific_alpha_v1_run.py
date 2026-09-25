"""Synthetic-only gates for the frozen Horizon-Specific Alpha V1 runner.

No market data is loaded here. The runner's horizon-local execution,
identity gates, integrity recompute and artifact discipline are exercised
on synthetic fixtures only.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from research import horizon_specific_alpha_hypothesis_v1_protocol as protocol
from research import horizon_specific_alpha_v1_run as runner
from research import sector_development_baseline as baseline

CODES = [f"C{i:03d}" for i in range(124)]
N_CODES = 124


def test_preregistration_commit_and_protocol_hash_identity():
    assert runner.PREREGISTRATION_COMMIT == "4d0ee982a0cd4ff1efe76c9fee4c2de807643ac2"
    assert protocol.FROZEN_PROTOCOL_HASH == (
        "d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4")
    payload = protocol.verify_protocol()
    assert payload["frozenConstants"]["exactCandidates"] == {
        k: list(v) for k, v in protocol.EXACT_CANDIDATES.items()}
    assert runner.RESEARCH_TYPE == "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1"


def test_exact_scheme_identity_horizon_assignment_and_no_extra_candidate():
    specs = runner.scheme_specs()
    assert [spec["schemeId"] for spec in specs] == [
        "C0_H10", "C0_H40", "C0_H120",
        "H10_S", "H10_C", "H40_S", "H40_C", "H120_S", "H120_C"]
    by_id = {spec["schemeId"]: spec for spec in specs}
    assert by_id["H10_S"] == {"schemeId": "H10_S", "isControl": False, "horizon": 10,
                              "archetype": "SINGLE_STABLE", "factorList": ["p5"]}
    assert by_id["H10_C"]["factorList"] == ["d10", "p5", "align", "vc", "dd20"]
    assert by_id["H40_S"]["factorList"] == ["vc"] and by_id["H40_S"]["horizon"] == 40
    assert by_id["H40_C"]["factorList"] == ["d120", "p60", "align", "vc", "rev5", "dd20"]
    assert by_id["H120_S"]["factorList"] == ["vc"] and by_id["H120_S"]["horizon"] == 120
    assert by_id["H120_C"]["factorList"] == ["d5", "p20", "vc", "rev10", "dd60", "rsi"]
    for horizon in (10, 40, 120):
        control = by_id[f"C0_H{horizon}"]
        assert control["isControl"] is True and control["horizon"] == horizon
        assert control["factorList"] == list(protocol.FROZEN_FACTOR_ORDER)
        assert len(control["factorList"]) == 19
    for spec in specs[3:]:
        positions = [protocol.FROZEN_FACTOR_ORDER.index(f) for f in spec["factorList"]]
        assert positions == sorted(positions)  # deterministic pipeline order
        assert len(set(spec["factorList"])) == len(spec["factorList"])


def test_no_extra_candidate_and_no_fusion_paths():
    config = protocol.load_config()
    assert config["noFusion"] is True and config["noCrossHorizonWinner"] is True
    assert runner.METRIC_NAMES == ("IC", "RankIC", "Top5_return", "Universe_return", "Spread")
    assert "fused_score" not in runner.PREDICTION_COLUMNS
    assert "fused_rank" not in runner.PREDICTION_COLUMNS
    assert not hasattr(runner, "FUSION_WEIGHTS")
    assert not hasattr(runner, "weighted_rankic")


def test_horizon_local_metrics_top5_tie_break_and_missingness():
    scores = {code: float(N_CODES - i) for i, code in enumerate(CODES)}
    labels = {code: float(i) * 0.001 for i, code in enumerate(CODES)}
    top5 = [code for code, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    metrics = runner.horizon_local_metrics(scores, labels, top5)
    assert metrics["Top5_return"] == pytest.approx(np.mean([labels[c] for c in top5]))
    assert metrics["Universe_return"] == pytest.approx(np.mean(list(labels.values())))
    assert metrics["Spread"] == pytest.approx(
        metrics["Top5_return"] - metrics["Universe_return"])
    assert metrics["RankIC"] == pytest.approx(-1.0, abs=1e-12)  # score desc vs label asc
    tied = {code: 1.0 for code in CODES}
    tied_top5 = sorted(CODES)[:5]  # sector code ascending tie-break
    tied_metrics = runner.horizon_local_metrics(tied, labels, tied_top5)
    assert tied_metrics["null_reason"] == "zero_cross_sectional_variance"
    assert tied_metrics["IC"] is None and tied_metrics["RankIC"] is None
    incomplete = {code: 1.0 for code in CODES[:100]}
    bad = runner.horizon_local_metrics(incomplete, labels, tied_top5)
    assert bad["null_reason"] == "incomplete_fixed_universe_score_or_label"
    assert bad["Spread"] is None


def test_aggregate_statistics_and_block_slicing():
    rows = []
    for ordinal in range(1, 101):
        for name in runner.METRIC_NAMES:
            rows.append({"candidate": "H10_S", "horizon": 10, "ordinal": ordinal,
                         "signal_date": f"D{ordinal:03d}", "metric": name,
                         "value": (ordinal ** 2) / 10000.0, "null_reason": None,
                         "valid_sector_count": N_CODES})
    per_date = pd.DataFrame(rows, columns=runner.PER_DATE_COLUMNS)
    aggregates = runner.aggregate_scheme_metrics(per_date)
    expected = np.mean([(o ** 2) / 10000.0 for o in range(1, 101)])
    assert aggregates["RankIC"]["mean"] == pytest.approx(expected)
    assert aggregates["RankIC"]["median"] == pytest.approx(
        np.median([(o ** 2) / 10000.0 for o in range(1, 101)]))
    assert aggregates["RankIC"]["std"] == pytest.approx(
        np.std([(o ** 2) / 10000.0 for o in range(1, 101)], ddof=0))  # population std
    assert aggregates["RankIC"]["validDates"] == 100
    blocks = runner.block_metrics_for(per_date)
    assert list(blocks) == ["B1", "B2", "B3", "B4"]
    assert (blocks["B1"]["first"], blocks["B1"]["last"]) == (1, 25)
    assert blocks["B2"]["rankicMean"] == pytest.approx(
        np.mean([(o ** 2) / 10000.0 for o in range(26, 51)]))
    assert blocks["B3"]["spreadMean"] == pytest.approx(
        np.mean([(o ** 2) / 10000.0 for o in range(51, 76)]))
    assert blocks["B4"]["validDates"] == 25


def test_evaluate_gates_level1_level2_temporal_and_same_horizon_control():
    block_ok = {"B1": 0.1, "B2": 0.2, "B3": 0.01, "B4": -0.01}
    gates = runner.evaluate_gates(0.11, 0.02, 0.10, 0.02, block_ok, 40)
    assert gates == {"frozenGateResult": runner.STATUS_ADVANCED,
                     "advancementStatus": runner.STATUS_ADVANCED,
                     "level1": "LEVEL1_PASS", "level2": "LEVEL2_PASS",
                     "temporalStability": "TEMPORAL_STABILITY_PASS"}
    l1_fail = runner.evaluate_gates(0.11, -0.01, 0.10, 0.02, block_ok, 40)
    assert l1_fail["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    assert l1_fail["level1"] == "LEVEL1_FAIL"
    l2_fail = runner.evaluate_gates(0.05, 0.02, 0.10, 0.02, block_ok, 40)
    assert l2_fail["level2"] == "LEVEL2_FAIL"
    assert l2_fail["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    temporal = runner.evaluate_gates(0.11, 0.02, 0.10, 0.02,
                                     {"B1": 0.1, "B2": -0.03, "B3": -0.05, "B4": 0.01}, 40)
    assert temporal["frozenGateResult"] == runner.FROZEN_TEMPORAL_FAIL
    assert temporal["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    assert temporal["temporalStability"] == "TEMPORAL_STABILITY_FAIL"
    strict = runner.evaluate_gates(0.10, 0.021, 0.10, 0.02, block_ok, 120)
    assert strict["level2"] == "LEVEL2_PASS" and strict["advancementStatus"] == runner.STATUS_ADVANCED
    tie = runner.evaluate_gates(0.11, 0.0, 0.10, 0.02, block_ok, 10)
    assert tie["level1"] == "LEVEL1_FAIL"  # strictly-greater rule, never >=
    with pytest.raises(ValueError, match="SAME_HORIZON_C0_REQUIRED"):
        protocol.advancement_status(candidate_horizon=10, control_horizon=40,
                                    mean_rankic=0.1, mean_spread=0.1,
                                    c0_mean_rankic=0.0, c0_mean_spread=0.0,
                                    block_mean_rankic=block_ok)


def test_simplicity_preference_labels_and_warnings_persistence():
    advanced = runner.STATUS_ADVANCED
    rows = [
        {"schemeId": "H10_S", "advancementStatus": advanced, "meanRankIc": 0.10,
         "meanSpread": 0.02, "simplicityPreference": "NOT_APPLICABLE"},
        {"schemeId": "H10_C", "advancementStatus": advanced, "meanRankIc": 0.105,
         "meanSpread": 0.025, "simplicityPreference": "NOT_APPLICABLE"},
    ]
    labels = runner.apply_simplicity_preference(rows)
    assert labels["H10_S"] == "PREFERRED_BY_SIMPLICITY"
    assert labels["H10_C"] == "NOT_TRIGGERED"
    rows[1]["advancementStatus"] = runner.STATUS_NOT_ADVANCED
    labels = runner.apply_simplicity_preference(rows)
    assert labels["H10_S"] == "NOT_TRIGGERED" and labels["H10_C"] == "NOT_TRIGGERED"
    rows[1]["advancementStatus"] = advanced
    rows[1]["meanRankIc"] = 0.12  # not a near tie
    labels = runner.apply_simplicity_preference(rows)
    assert labels["H10_S"] == "NOT_TRIGGERED"
    assert runner.warnings_for("H40_S", 40) == [
        "NO_STRONG_STABILITY_EVIDENCE",
        "NEUTRALITY_CAVEAT_ZERO_HARD_FLIP_MAY_BE_NEUTRAL_TRAINING_DIRECTION",
        "DEVELOPMENT_REUSE_WARNING"]
    assert runner.warnings_for("H40_C", 40) == [
        "NO_STRONG_STABILITY_EVIDENCE", "DEVELOPMENT_REUSE_WARNING"]
    assert runner.warnings_for("H120_S", 120) == [
        "NEUTRALITY_CAVEAT_ZERO_HARD_FLIP_MAY_BE_NEUTRAL_TRAINING_DIRECTION",
        "DEVELOPMENT_REUSE_WARNING"]
    assert runner.warnings_for("H120_C", 120) == ["DEVELOPMENT_REUSE_WARNING"]
    config = protocol.load_config()
    assert config["h40EvidenceQualityWarning"] is True
    assert config["developmentReuseWarning"] is True


def test_result_label_restrictions_and_metadata_identity():
    gate = {"gate": "PASS", "branch": runner.EXPECTED_BRANCH,
            "git_head": runner.PREREGISTRATION_COMMIT,
            "docker_image_id": baseline.EXPECTED_IMAGE_ID,
            "development_first_date": "2025-04-02", "development_last_date": "2025-08-26"}
    summary = {
        "researchType": runner.RESEARCH_TYPE,
        "preregistrationCommit": runner.PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "candidates": [{"schemeId": "H10_S",
                        "advancementStatus": runner.STATUS_NOT_ADVANCED}],
        "notices": ["DEVELOPMENT ONLY", "DEVELOPMENT_REUSE_WARNING=true"],
    }
    metadata = runner.build_metadata(gate, summary, "horizon_specific_alpha_v1_test", {}, None)
    assert metadata["researchType"] == "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1"
    assert metadata["preregistrationCommit"] == runner.PREREGISTRATION_COMMIT
    assert metadata["protocolHash"] == protocol.FROZEN_PROTOCOL_HASH
    assert metadata["noFusion"] is True
    assert metadata["DEVELOPMENT_REUSE_WARNING"] is True
    assert metadata["INDEPENDENT_VALIDATION"] is False and metadata["OOS"] is False
    assert metadata["validation"] == "SEALED" and metadata["finalOos"] == "SEALED"
    assert metadata["strictPit"] is False and metadata["executable"] is False
    assert metadata["tradable"] is False
    assert metadata["classification"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert metadata["target"] == "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert metadata["preprocessing"] == "RAW_NO_STANDARDIZATION"
    assert metadata["model"] == "NUMPY_RIDGE" and metadata["alpha"] == 0.01
    assert metadata["trainWindow"] == "6_CALENDAR_MONTHS" and metadata["minTrainingDays"] == 30
    assert metadata["developmentIds"] == "E001-E100" and metadata["universe"] == "U0"
    assert metadata["candidateIds"] == list(protocol.CANDIDATE_IDS)
    assert metadata["candidateHorizon"]["H120_C"] == 120
    assert metadata["candidateFactorLists"]["H10_C"] == ["d10", "p5", "align", "vc", "dd20"]
    statuses = [runner.STATUS_ADVANCED, runner.STATUS_NOT_ADVANCED, runner.STATUS_CONTROL]
    for forbidden in runner.FORBIDDEN_RESULT_LABELS:
        assert all(forbidden not in status for status in statuses)


def _synthetic_outputs() -> dict:
    outputs = {}
    label = np.arange(N_CODES, dtype=float) * 0.001
    for spec in runner.scheme_specs():
        scheme = spec["schemeId"]
        horizon = spec["horizon"]
        pred_rows, metric_rows, training_rows = [], [], []
        for ordinal in range(1, 101):
            for i, code in enumerate(CODES):
                pred_rows.append({
                    "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                    "signal_date": f"D{ordinal:03d}", "sector_code": code,
                    "sector_name": code, "prediction_score": float(N_CODES - i),
                    "cross_sectional_rank": i + 1, "top5": i < 5,
                    "realized_forward_return": label[i],
                    "label_end": f"D{ordinal + horizon:03d}", "exclusion_reason": None,
                    "training_observations": 1240, "training_valid_days": 30,
                    "training_label_cutoff": f"D{ordinal:03d}",
                })
            # Constant synthetic cross-section: metrics implied by the
            # prediction rows above (score desc vs label asc -> -1).
            values = {"IC": -1.0, "RankIC": -1.0, "Top5_return": 0.002,
                      "Universe_return": 0.0615, "Spread": -0.0595}
            for name in runner.METRIC_NAMES:
                metric_rows.append({
                    "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                    "signal_date": f"D{ordinal:03d}", "metric": name,
                    "value": values[name], "null_reason": None,
                    "valid_sector_count": N_CODES,
                })
            training_rows.append({
                "candidate": scheme, "horizon": horizon, "ordinal": ordinal,
                "signal_date": f"D{ordinal:03d}", "status": "success", "reason": None,
                "train_start": "2024-01-01", "label_cutoff": "2024-12-01",
                "first_train_origin": "2024-01-02", "last_train_origin": "2024-11-30",
                "last_train_label_end": "2024-12-20", "training_candidate_days": 30,
                "training_valid_days": 30, "training_observations": 1240,
                "valid_sector_count": 124, "leakage_checks": 1240,
            })
        predictions = pd.DataFrame(pred_rows, columns=runner.PREDICTION_COLUMNS)
        per_date = pd.DataFrame(metric_rows, columns=runner.PER_DATE_COLUMNS)
        outputs[scheme] = runner.SchemeOutput(
            predictions=predictions, per_date_metrics=per_date,
            aggregate_metrics=runner.aggregate_scheme_metrics(per_date),
            block_metrics=runner.block_metrics_for(per_date),
            training_diagnostics=pd.DataFrame(training_rows, columns=runner.TRAINING_COLUMNS),
            data_quality_diagnostics={"attempted_development_dates": 100,
                                      "successful_dates": 100, "no_fusion": True},
            transformation_diagnostics={
                "x_preprocessing": "RAW_NO_STANDARDIZATION",
                "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"},
        )
    return outputs


def _synthetic_summary() -> dict:
    candidates = []
    for spec in runner.scheme_specs()[3:]:
        candidates.append({
            "schemeId": spec["schemeId"], "isControl": False,
            "horizon": spec["horizon"], "factorList": spec["factorList"],
            "factorCount": len(spec["factorList"]),
            "advancementStatus": runner.STATUS_NOT_ADVANCED,
            "frozenGateResult": runner.STATUS_NOT_ADVANCED,
            "level1": "LEVEL1_FAIL", "level2": "LEVEL2_FAIL",
            "temporalStability": "TEMPORAL_STABILITY_PASS",
            "simplicityPreference": "NOT_TRIGGERED",
            "meanRankIc": 0.1, "meanSpread": 0.01, "warnings": ["DEVELOPMENT_REUSE_WARNING"],
        })
    return {
        "researchType": runner.RESEARCH_TYPE,
        "preregistrationCommit": runner.PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "noFusion": True, "developmentReuseWarning": True,
        "control": [{"schemeId": "C0_H10", "advancementStatus": runner.STATUS_CONTROL}],
        "candidates": candidates,
        "c0Reproduction": {"status": "PASS"},
        "notices": ["DEVELOPMENT ONLY", "DEVELOPMENT_REUSE_WARNING=true",
                    "NOT INDEPENDENT VALIDATION", "NOT OOS"],
    }


def test_metric_recompute_and_advancement_integrity():
    outputs = _synthetic_outputs()
    recomputed = runner.recompute_from_predictions(
        {scheme: output.predictions for scheme, output in outputs.items()})
    report = runner.verify_metric_integrity(outputs, recomputed)
    assert report["status"] == "PASS" and report["maxAbsDiff"] <= 1e-12
    tampered = outputs["H10_S"]
    bad_aggregate = json.loads(json.dumps(outputs["H10_S"].aggregate_metrics))
    bad_aggregate["RankIC"]["mean"] += 0.5
    outputs_bad = dict(outputs)
    outputs_bad["H10_S"] = runner.SchemeOutput(
        predictions=tampered.predictions, per_date_metrics=tampered.per_date_metrics,
        aggregate_metrics=bad_aggregate, block_metrics=tampered.block_metrics,
        training_diagnostics=tampered.training_diagnostics,
        data_quality_diagnostics=tampered.data_quality_diagnostics,
        transformation_diagnostics=tampered.transformation_diagnostics)
    with pytest.raises(ValueError, match="HORIZON_SPECIFIC_METRIC_INTEGRITY_BLOCKER"):
        runner.verify_metric_integrity(outputs_bad, recomputed)
    c0_values = {
        f"C0_H{h}": {"meanRankIc": recomputed[f"C0_H{h}"]["aggregates"]["RankIC"]["mean"],
                     "meanSpread": recomputed[f"C0_H{h}"]["aggregates"]["Spread"]["mean"]}
        for h in protocol.HORIZONS}
    rows = []
    for spec in runner.scheme_specs()[3:]:
        horizon = spec["horizon"]
        ref = recomputed[spec["schemeId"]]
        block_rankic = {block_id: values["rankicMean"]
                        for block_id, values in ref["blocks"].items()}
        rows.append({
            "schemeId": spec["schemeId"], "isControl": False, "horizon": horizon,
            **runner.evaluate_gates(
                ref["aggregates"]["RankIC"]["mean"],
                ref["aggregates"]["Spread"]["mean"],
                c0_values[f"C0_H{horizon}"]["meanRankIc"],
                c0_values[f"C0_H{horizon}"]["meanSpread"], block_rankic, horizon),
        })
    integrity = runner.verify_advancement_integrity(rows, recomputed, c0_values)
    assert integrity["status"] == "PASS" and integrity["checkedCandidates"] == 6
    rows[0]["advancementStatus"] = runner.STATUS_ADVANCED
    with pytest.raises(ValueError, match="ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER"):
        runner.verify_advancement_integrity(rows, recomputed, c0_values)


def test_top5_identity_and_tie_break_exact():
    outputs = _synthetic_outputs()
    report = runner.top5_identity_check(outputs)
    assert report["status"] == "PASS" and report["sampleCount"] == 2 * 3 * 9
    assert report["tieBreak"] == "sector_code_ascending"
    broken = _synthetic_outputs()
    frame = broken["H40_C"].predictions
    mask = (frame["ordinal"] == 1) & (frame["sector_code"] == "C000")
    frame.loc[mask, "top5"] = False
    with pytest.raises(ValueError, match="TOP5_IDENTITY_BLOCKER"):
        runner.top5_identity_check(broken)


def _synthetic_world(n_dates: int = 530, n_codes: int = 12):
    index = pd.bdate_range("2024-01-01", periods=n_dates)
    codes = [f"C{i:03d}" for i in range(n_codes)]
    frames = {}
    for c_i, code in enumerate(codes):
        t = np.arange(n_dates, dtype=float)
        close = 10.0 + 0.01 * t + 0.05 * np.sin(t / 7.0 + c_i)
        frames[code] = pd.DataFrame({
            "open": close * 0.999, "high": close * 1.002, "low": close * 0.998,
            "close": close, "volume": np.full(n_dates, 1e6),
            "amount": np.full(n_dates, 1e7), "is_valid_ohlc": np.ones(n_dates, dtype=bool),
        }, index=index)
    return index, frames, codes


def test_factor_identity_gate_passes_on_match_and_blocks_on_drift():
    from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
    index, frames, codes = _synthetic_world()
    development_dates = index[300:400]
    factors = tuple(protocol.FROZEN_FACTOR_ORDER)
    stashed = {}
    for ordinal in runner.IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        for code in codes[:runner.IDENTITY_SAMPLE_SECTOR_COUNT]:
            values = compute_all_price_features(
                baseline._source_frame(frames[code], frames[code].index[0], signal),
                include_rsrs=False,
            ).loc[signal, list(factors)]
            stashed[(ordinal, code)] = {f: float(values[f]) for f in factors}
    report = runner.factor_identity_gate(stashed, frames, index, development_dates, codes)
    assert report["status"] == "PASS" and report["sampleCount"] == 3 * 19 * 10
    assert report["maxAbsDiff"] <= runner.FACTOR_IDENTITY_TOLERANCE
    stashed[(1, codes[0])][factors[0]] += 1e-3
    with pytest.raises(ValueError, match="FACTOR_IDENTITY_BLOCKER"):
        runner.factor_identity_gate(stashed, frames, index, development_dates, codes)


def test_target_identity_gate_passes_on_match_and_blocks_on_drift():
    index, frames, codes = _synthetic_world()
    development_dates = index[300:400]
    labels_by_h = {}
    artifact_rows = []
    for horizon in protocol.HORIZONS:
        series = {}
        for code in codes:
            close = frames[code]["close"]
            series[code] = pd.Series({index[i]: float(close.iloc[i + horizon])
                                      / float(close.iloc[i]) - 1.0
                                      for i in range(len(index) - horizon)})
        labels_by_h[horizon] = series
    for ordinal in runner.IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        signal_i = int(index.get_loc(signal))
        for horizon in protocol.HORIZONS:
            endpoint = index[signal_i + horizon]
            for code in codes[:runner.IDENTITY_SAMPLE_SECTOR_COUNT]:
                artifact_rows.append({
                    "ordinal": ordinal, "horizon": horizon, "sector_code": code,
                    "realized_forward_return": float(labels_by_h[horizon][code].loc[signal]),
                    "label_end": str(endpoint.date())})
    d2 = pd.DataFrame(artifact_rows)
    report = runner.target_identity_gate(labels_by_h, frames, index, development_dates,
                                         codes, d2)
    assert report["status"] == "PASS" and report["sampleCount"] == 3 * 3 * 10
    assert report["maxAbsDiffDirectArithmetic"] <= runner.TARGET_IDENTITY_TOLERANCE
    drifted = {h: {c: s.copy() for c, s in series.items()} for h, series in labels_by_h.items()}
    drifted[10][codes[0]].loc[development_dates[0]] += 1e-6
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(drifted, frames, index, development_dates, codes, d2)
    wrong_end = pd.DataFrame(artifact_rows)
    wrong_end.loc[0, "label_end"] = "1999-01-01"
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(labels_by_h, frames, index, development_dates,
                                    codes, wrong_end)


def test_training_window_identity_gate_exact_fields():
    rows = []
    for ordinal in range(1, 101):
        for horizon in protocol.HORIZONS:
            rows.append({"ordinal": ordinal, "horizon": horizon,
                         "train_start": "2024-01-01", "label_cutoff": "2024-12-01",
                         "first_train_origin": "2024-01-02",
                         "last_train_origin": "2024-11-30",
                         "last_train_label_end": "2024-12-20",
                         "training_candidate_days": 30, "training_valid_days": 30,
                         "training_observations": 1240, "valid_sector_count": 124})
    mine = pd.DataFrame(rows)
    reference = mine.copy()
    report = runner.training_window_identity_gate(mine, reference)
    assert report["status"] == "PASS" and report["sampleCount"] == 5 * 3 * 9
    single = mine[mine["horizon"] == 10]
    report_single = runner.training_window_identity_gate(single, reference)
    assert report_single["sampledHorizons"] == [10]
    assert report_single["sampleCount"] == 5 * 9  # horizon-local frame regression
    drifted = reference.copy()
    drifted.loc[drifted["ordinal"] == 50, "training_valid_days"] = 29
    with pytest.raises(ValueError, match="TRAINING_WINDOW_IDENTITY_BLOCKER"):
        runner.training_window_identity_gate(mine, drifted)


def test_c0_reproduction_prediction_identity_and_blocker():
    outputs = _synthetic_outputs()
    artifact_rows = []
    for horizon in protocol.HORIZONS:
        source = outputs[f"C0_H{horizon}"].predictions
        for row in source.itertuples(index=False):
            artifact_rows.append({
                "ordinal": row.ordinal, "horizon": horizon,
                "sector_code": row.sector_code,
                "prediction_score": row.prediction_score,
                "cross_sectional_rank": row.cross_sectional_rank,
                "realized_forward_return": row.realized_forward_return,
                "label_end": row.label_end})
    reference = {
        "predictions": pd.DataFrame(artifact_rows),
        "aggregate": {
            f"IC_{h}": {"mean": outputs[f"C0_H{h}"].aggregate_metrics["IC"]["mean"],
                        "valid_dates": 100} for h in protocol.HORIZONS},
    }
    for h in protocol.HORIZONS:
        reference["aggregate"][f"RankIC_{h}"] = {
            "mean": outputs[f"C0_H{h}"].aggregate_metrics["RankIC"]["mean"],
            "valid_dates": 100}
        reference["aggregate"][f"Top5_minus_universe_{h}"] = {
            "mean": outputs[f"C0_H{h}"].aggregate_metrics["Spread"]["mean"],
            "valid_dates": 100}
    report = runner.c0_reproduction_report(outputs, reference)
    assert report["status"] == "PASS" and report["maxAbsDiff"] <= 1e-12
    for horizon in protocol.HORIZONS:
        assert report["perHorizon"][str(horizon)]["predictionRankMismatches"] == 0
        assert report["perHorizon"][str(horizon)]["legacyFusedTop5SpreadSemantic"] == (
            "FUSED_TOP5_LEGACY_SEMANTICS_NOT_COMPARABLE_TO_HORIZON_LOCAL_TOP5")
    tampered = pd.DataFrame(artifact_rows)
    tampered.loc[0, "prediction_score"] += 1.0
    with pytest.raises(ValueError, match="C0_REPRODUCTION_BLOCKER"):
        runner.c0_reproduction_report(outputs, {**reference, "predictions": tampered})


def test_write_run_artifact_schema_determinism_and_sealed_guard(tmp_path):
    outputs = _synthetic_outputs()
    summary = _synthetic_summary()
    blocks = pd.DataFrame([{
        "candidate": "H10_S", "horizon": 10, "block": "B1", "first": 1, "last": 25,
        "valid_dates": 25, "rankic_mean": 0.1, "rankic_median": 0.1, "spread_mean": 0.01}])
    integrity = {"factorIdentity": {"status": "PASS"}, "targetIdentity": {"status": "PASS"}}
    gate = {"gate": "PASS", "branch": runner.EXPECTED_BRANCH,
            "git_head": runner.PREREGISTRATION_COMMIT,
            "docker_image_id": baseline.EXPECTED_IMAGE_ID,
            "development_first_date": "2025-04-02", "development_last_date": "2025-08-26"}
    first = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate)
    assert set(p.name for p in first.iterdir() if p.is_file()) == (
        set(runner.RUN_ARTIFACT_NAMES) | {"metadata.json"})
    assert set(f"{d.name}/{p.name}" for d in first.iterdir() if d.is_dir()
               for p in d.iterdir()) == {
        f"{spec['schemeId']}/{name}" for spec in runner.scheme_specs()
        for name in runner.SCHEME_ARTIFACT_NAMES}
    meta1 = json.loads((first / "metadata.json").read_text(encoding="utf-8"))
    second = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate)
    meta2 = json.loads((second / "metadata.json").read_text(encoding="utf-8"))
    assert meta1["content_sha256"] == meta2["content_sha256"]
    repeated = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate,
                                repeat_of=first)
    meta3 = json.loads((repeated / "metadata.json").read_text(encoding="utf-8"))
    assert meta3["determinism"] == "PASS_CONTENT_SHA256_IDENTICAL"
    assert meta3["determinism_repeat_of"] == meta1["run_id"]
    drift = tmp_path / "drift"
    (drift / "H10_S").mkdir(parents=True)
    (drift / "metadata.json").write_text(json.dumps({
        "content_sha256": {**meta1["content_sha256"], "block_stability.csv": "0" * 64},
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH}), encoding="utf-8")
    with pytest.raises(ValueError, match="HORIZON_SPECIFIC_DETERMINISM_BLOCKER"):
        runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate, repeat_of=drift)
    sealed = outputs["H10_S"].per_date_metrics.copy()
    sealed.loc[0, "ordinal"] = 101
    broken = dict(outputs)
    source = outputs["H10_S"]
    broken["H10_S"] = runner.SchemeOutput(
        predictions=source.predictions, per_date_metrics=sealed,
        aggregate_metrics=source.aggregate_metrics, block_metrics=source.block_metrics,
        training_diagnostics=source.training_diagnostics,
        data_quality_diagnostics=source.data_quality_diagnostics,
        transformation_diagnostics=source.transformation_diagnostics)
    with pytest.raises(PermissionError):
        runner.write_run(tmp_path, broken, summary, blocks, integrity, gate)

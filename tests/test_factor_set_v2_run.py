"""Synthetic-only gates for the frozen Factor Set V2 formal runner.

No Development data is loaded here: the runner's judgment, integrity and
artifact logic is exercised on synthetic fixtures only.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from research import factor_set_v2_protocol as protocol
from research import factor_set_v2_run as runner
from research import development_iteration1_protocol as iteration1_protocol
from research import sector_development_baseline as baseline
from research.sector_universe_feasibility import prediction_metric_contract
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features

METRIC_NAMES = prediction_metric_contract()["metric_names"]
N_CODES = 124
CODES = [f"C{i:03d}" for i in range(N_CODES)]


def test_preregistration_commit_and_frozen_hash_constants():
    assert runner.PREREGISTRATION_COMMIT == "b836f27e33987ea3d987b8683a38acc442cb2cdd"
    assert runner.EXPERIMENT == "FACTOR_SET_V2"
    assert runner.D2_PREDICTIONS_SHA256 == (
        "b2191cdcf907d3217a14b494eac36325f473f285392784e118e17cadd13dbb17")
    assert runner.D2_AGGREGATE_SHA256 == (
        "cc7f9b5712c0f072ea74d1d9634bb990e3f29e2819e6e6cddff27933b17c86b4")
    protocol.verify_frozen_factor_set_v2_protocol()
    assert runner.STATUS_CONTROL == "CONTROL_NOT_A_CANDIDATE"


def test_scheme_specs_exact_order_and_v2c_forbidden(monkeypatch):
    specs = runner.scheme_specs()
    assert [(s["schemeId"], s["factorList"]) for s in specs] == [
        ("C0", list(protocol.FROZEN_FACTOR_ORDER)),
        ("V2_A", ["v20"]),
        ("V2_B", ["v5", "v20"]),
        ("V2_D", ["d20", "p60", "align", "v20", "rev5", "dd20"]),
    ]
    assert [s["isControl"] for s in specs] == [True, False, False, False]
    assert all(len(set(s["factorList"])) == len(s["factorList"]) for s in specs)
    config = json.loads(json.dumps(protocol.load_candidate_config()))
    config["candidates"].append({"candidateId": "V2_C", "factorList": ["rsi"], "factorCount": 1})
    monkeypatch.setattr(protocol, "load_candidate_config", lambda: config)
    with pytest.raises(ValueError, match="V2_C_FORBIDDEN"):
        runner.scheme_specs()
    config["candidates"][-1] = {"candidateId": "V2_E", "factorList": ["rsi"], "factorCount": 1}
    with pytest.raises(ValueError, match="CANDIDATE_BUDGET_VIOLATION"):
        runner.scheme_specs()


def test_weighted_metrics_frozen_weights():
    means = {"RankIC_10": 0.1, "RankIC_40": 0.2, "RankIC_120": 0.3,
             "Top5_minus_universe_10": 0.01, "Top5_minus_universe_40": 0.02,
             "Top5_minus_universe_120": 0.03}
    metrics = runner.weighted_metrics(means)
    assert metrics["weightedRankIc"] == pytest.approx(0.25 * 0.1 + 0.50 * 0.2 + 0.25 * 0.3)
    assert metrics["weightedSpread"] == pytest.approx(0.25 * 0.01 + 0.50 * 0.02 + 0.25 * 0.03)
    assert metrics["rankIcByHorizon"] == {"10": 0.1, "40": 0.2, "120": 0.3}


def test_excess_target_is_same_date_cross_sectional_demean():
    origins = pd.to_datetime(["2025-01-02"] * 3 + ["2025-01-03"] * 2)
    raw = np.array([1.0, 3.0, 5.0, 10.0, 20.0])
    target = iteration1_protocol.cross_sectional_excess_training_target(raw, origins, horizon=40)
    np.testing.assert_allclose(target, [-2.0, 0.0, 2.0, -5.0, 5.0])
    for date in origins.unique():
        assert abs(float(target[origins == date].mean())) < 1e-12
    np.testing.assert_array_equal(raw, [1.0, 3.0, 5.0, 10.0, 20.0])  # raw never mutated


def test_advancement_level1_level2_and_red_flag():
    c0 = {"weightedRankIc": 0.05, "weightedSpread": 0.02}

    def means(rankic, spread, h40=None):
        out = {}
        for h in (10, 40, 120):
            out[f"RankIC_{h}"] = rankic if h40 is None or h != 40 else h40
            out[f"Top5_minus_universe_{h}"] = spread
        return out

    below = runner.evaluate_advancement(means(0.01, 0.001), c0)
    assert below["level1"] is True and below["level2"] is False
    assert below["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    option_a = runner.evaluate_advancement(means(0.06, 0.03), c0)
    assert option_a["level2Option"] == "A"
    assert option_a["advancementStatus"] == runner.STATUS_ADVANCED
    option_b = runner.evaluate_advancement(means(0.05, 0.04), c0)
    assert option_b["level2Option"] == "B"
    assert option_b["advancementStatus"] == runner.STATUS_ADVANCED
    negative = runner.evaluate_advancement(means(-0.01, -0.001), c0)
    assert negative["level1"] is False and negative["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    red = runner.evaluate_advancement(means(0.25, 0.03, h40=-0.03), c0)
    assert red["level1"] is True and red["level2"] is True
    assert red["horizonRedFlag"] is True and red["redFlagHorizons"] == [40]
    assert red["advancementStatus"] == runner.STATUS_NOT_ADVANCED
    edge = runner.evaluate_advancement(means(0.05, 0.03), c0)  # rankic equal to C0
    assert edge["level2Option"] == "B" and edge["advancementStatus"] == runner.STATUS_ADVANCED
    for result in (below, option_a, option_b, negative, red, edge):
        assert result["advancementStatus"] in (runner.STATUS_ADVANCED, runner.STATUS_NOT_ADVANCED)


def test_simplicity_preference_tie_break_discipline():
    a = {"candidateId": "V2_A", "factorCount": 1, "weightedRankIc": 0.090,
         "weightedSpread": 0.037}
    b = {"candidateId": "V2_B", "factorCount": 2, "weightedRankIc": 0.095,
         "weightedSpread": 0.040}
    d = {"candidateId": "V2_D", "factorCount": 6, "weightedRankIc": 0.200,
         "weightedSpread": 0.100}
    tied = runner.simplicity_preference([a, b])
    assert tied["triggered"] is True and tied["preferred"] == "V2_A"
    not_tied = runner.simplicity_preference([a, d])
    assert not_tied["triggered"] is False and not_tied["preferred"] is None
    mixed = runner.simplicity_preference([a, b, d])
    assert mixed["triggered"] is True and mixed["preferred"] == "V2_A"
    same_count = {"candidateId": "V2_B", "factorCount": 1, "weightedRankIc": 0.091,
                  "weightedSpread": 0.038}
    equal = runner.simplicity_preference([same_count, a])
    assert equal["preferred"] == "V2_A"  # equal count -> lower candidate ID order
    assert runner.simplicity_preference([])["triggered"] is False


def _synthetic_per_date() -> pd.DataFrame:
    rows = []
    for name in METRIC_NAMES:
        horizon = int(name.rsplit("_", 1)[1])
        for ordinal in range(1, 101):
            rows.append({"ordinal": ordinal, "signal_date": f"D{ordinal:03d}",
                         "horizon": horizon, "metric": name,
                         "value": (ordinal ** 2) / 10000.0, "null_reason": None,
                         "valid_sector_count": N_CODES})
    return pd.DataFrame(rows, columns=baseline.PER_DATE_COLUMNS)


def test_block_stability_rows_use_frozen_blocks():
    per_date = _synthetic_per_date()
    rows = runner.block_stability_rows("V2_A", per_date)
    assert len(rows) == 3 * 4
    first = next(r for r in rows if r["horizon"] == 10 and r["block"] == 1)
    expected = np.mean([(o ** 2) / 10000.0 for o in range(1, 26)])
    assert first["rankic_mean"] == pytest.approx(expected)
    assert first["rankic_median"] == pytest.approx(np.median([(o ** 2) / 10000.0
                                                             for o in range(1, 26)]))
    assert first["spread_mean"] == pytest.approx(expected)
    assert first["valid_dates"] == 25
    assert [(r["block"], r["block_ordinal_start"], r["block_ordinal_end"]) for r in rows[:4]] == [
        (1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 100)]
    assert protocol.STABILITY_BLOCKS == ((1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 100))


def test_extreme_date_sensitivity_frozen_method():
    per_date = _synthetic_per_date()
    universe = {o: float(o) for o in range(1, 101)}
    result = runner.extreme_date_sensitivity(per_date, universe)
    assert result["excludedOrdinals"] == [1, 2, 3, 4, 5, 96, 97, 98, 99, 100]
    assert result["remainingDates"] == 90
    assert result["method"].startswith("exclude_5_lowest_and_5_highest")
    assert result["sensitivityWeightedRankIc"] == pytest.approx(
        result["full"]["weightedRankIc"] - result["extremeExcluded"]["weightedRankIc"])
    assert result["sensitivityWeightedSpread"] == pytest.approx(
        result["full"]["weightedSpread"] - result["extremeExcluded"]["weightedSpread"])
    assert result["descriptiveOnly"] is True


def _synthetic_outputs() -> dict:
    outputs = {}
    label = np.arange(N_CODES, dtype=float) * 0.001
    for spec in runner.scheme_specs():
        scheme = spec["schemeId"]
        pred_rows = []
        for ordinal in range(1, 101):
            for horizon in (10, 40, 120):
                for i, code in enumerate(CODES):
                    pred_rows.append({
                        "ordinal": ordinal, "signal_date": f"D{ordinal:03d}",
                        "sector_code": code, "sector_name": code, "horizon": horizon,
                        "prediction_score": float(N_CODES - i),
                        "cross_sectional_rank": i + 1,
                        "fused_score": float(N_CODES - i), "fused_rank": i + 1,
                        "top5": i < 5, "realized_forward_return": label[i],
                        "label_end": f"D{ordinal + horizon:03d}", "exclusion_reason": None,
                        "training_observations": 100, "training_valid_days": 30,
                        "training_label_cutoff": f"D{ordinal:03d}",
                    })
        predictions = pd.DataFrame(pred_rows, columns=baseline.PREDICTION_COLUMNS)
        per_date = _synthetic_per_date()
        outputs[scheme] = runner.SchemeOutput(
            predictions=predictions,
            per_date_metrics=per_date,
            aggregate_metrics=baseline.aggregate_metrics(per_date),
            training_diagnostics=pd.DataFrame([{
                "ordinal": 1, "signal_date": "D001", "horizon": 10, "status": "success",
                "reason": None, "train_start": "x", "label_cutoff": "x",
                "first_train_origin": "x", "last_train_origin": "x",
                "last_train_label_end": "x", "training_candidate_days": 30,
                "training_valid_days": 30, "training_observations": 3720,
                "valid_sector_count": 124, "missing_factor_exclusions": 0,
                "missing_label_exclusions": 0, "numerical_failures": 0,
                "leakage_checks": 3720}], columns=baseline.TRAINING_COLUMNS),
            data_quality_diagnostics={"attempted_development_dates": 100,
                                      "successful_dates": 100},
            transformation_diagnostics={"x_preprocessing": "NONE_RAW",
                                        "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"},
        )
    return outputs


def _synthetic_summary() -> dict:
    candidates = []
    for spec in runner.scheme_specs()[1:]:
        candidates.append({
            "candidateId": spec["schemeId"], "factorList": spec["factorList"],
            "factorCount": len(spec["factorList"]), "isControl": False,
            "advancementStatus": runner.STATUS_NOT_ADVANCED,
            "weightedRankIc": 0.1, "weightedSpread": 0.02,
        })
    return {
        "experiment": runner.EXPERIMENT,
        "protocolHash": protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH,
        "preregistrationCommit": runner.PREREGISTRATION_COMMIT,
        "selectionBias": {
            "POST_AUDIT_DEVELOPMENT_RESEARCH": True,
            "NOT_INDEPENDENT_VALIDATION": True, "NOT_OOS_EVIDENCE": True,
        },
        "control": {"candidateId": "C0", "advancementStatus": runner.STATUS_CONTROL},
        "candidates": candidates,
        "c0Reproduction": {"status": "PASS"},
        "notices": ["POST-AUDIT DEVELOPMENT RESEARCH", "NOT INDEPENDENT VALIDATION"],
    }


def _synthetic_gate() -> dict:
    return {"gate": "PASS", "branch": runner.EXPECTED_BRANCH,
            "git_head": "b836f27e33987ea3d987b8683a38acc442cb2cdd",
            "docker_image_id": baseline.EXPECTED_IMAGE_ID,
            "development_first_date": "2025-04-02", "development_last_date": "2025-08-26"}


def test_write_run_artifact_schema_deterministic_and_drift(tmp_path):
    outputs = _synthetic_outputs()
    summary = _synthetic_summary()
    blocks = pd.DataFrame(runner.block_stability_rows("V2_A", _synthetic_per_date()))
    integrity = {"factorIdentity": {"status": "PASS"}, "targetIdentity": {"status": "PASS"}}
    gate = _synthetic_gate()
    first = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate)
    expected = {f"{spec['schemeId']}/{name}" for spec in runner.scheme_specs()
                for name in runner.CANDIDATE_ARTIFACT_NAMES}
    expected |= set(runner.RUN_ARTIFACT_NAMES) | {"metadata.json"}
    assert set(p.name for p in first.iterdir() if p.is_file()) == (
        set(runner.RUN_ARTIFACT_NAMES) | {"metadata.json"})
    assert set(f"{d.name}/{p.name}" for d in first.iterdir() if d.is_dir()
               for p in d.iterdir()) == {
        f"{spec['schemeId']}/{name}" for spec in runner.scheme_specs()
        for name in runner.CANDIDATE_ARTIFACT_NAMES}
    meta1 = json.loads((first / "metadata.json").read_text(encoding="utf-8"))
    assert set(meta1["content_sha256"]) == {
        f"{spec['schemeId']}/{name}" for spec in runner.scheme_specs()
        for name in runner.CANDIDATE_ARTIFACT_NAMES} | set(runner.RUN_ARTIFACT_NAMES)
    second = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate)
    meta2 = json.loads((second / "metadata.json").read_text(encoding="utf-8"))
    assert meta1["content_sha256"] == meta2["content_sha256"]
    repeated = runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate,
                                repeat_of=first)
    meta3 = json.loads((repeated / "metadata.json").read_text(encoding="utf-8"))
    assert meta3["determinism"] == "PASS_CONTENT_SHA256_IDENTICAL"
    assert meta3["determinism_repeat_of"] == meta1["run_id"]
    drift = tmp_path / "drift"
    (drift / "V2_A").mkdir(parents=True)
    (drift / "metadata.json").write_text(json.dumps({
        "content_sha256": {**meta1["content_sha256"], "block_stability.csv": "0" * 64},
        "protocolHash": protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH}), encoding="utf-8")
    with pytest.raises(ValueError, match="DETERMINISM_BLOCKER"):
        runner.write_run(tmp_path, outputs, summary, blocks, integrity, gate, repeat_of=drift)


def test_write_run_rejects_sealed_ordinals_and_bad_labels(tmp_path):
    outputs = _synthetic_outputs()
    summary = _synthetic_summary()
    blocks = pd.DataFrame(runner.block_stability_rows("V2_A", _synthetic_per_date()))
    integrity = {"factorIdentity": {"status": "PASS"}}
    gate = _synthetic_gate()
    sealed = outputs["V2_A"].per_date_metrics.copy()
    sealed.loc[0, "ordinal"] = 101
    broken = dict(outputs)
    broken["V2_A"] = runner.SchemeOutput(
        predictions=outputs["V2_A"].predictions, per_date_metrics=sealed,
        aggregate_metrics=outputs["V2_A"].aggregate_metrics,
        training_diagnostics=outputs["V2_A"].training_diagnostics,
        data_quality_diagnostics=outputs["V2_A"].data_quality_diagnostics,
        transformation_diagnostics=outputs["V2_A"].transformation_diagnostics)
    with pytest.raises(PermissionError):
        runner.write_run(tmp_path, broken, summary, blocks, integrity, gate)
    bad_summary = _synthetic_summary()
    bad_summary["candidates"][0]["advancementStatus"] = "V2_WINNER_PRODUCTION"
    with pytest.raises(ValueError, match="RESULT_LABEL_VIOLATION"):
        runner.write_run(tmp_path, outputs, bad_summary, blocks, integrity, gate)


def test_build_metadata_frozen_settings_and_bias_flags():
    metadata = runner.build_metadata(_synthetic_gate(), _synthetic_summary(),
                                     "factor_set_v2_test", {}, None)
    assert metadata["experiment"] == "FACTOR_SET_V2"
    assert metadata["preregistrationCommit"] == runner.PREREGISTRATION_COMMIT
    assert metadata["protocolHash"] == protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH
    assert metadata["target"] == "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
    assert metadata["preprocessing"] == "NONE_RAW" and metadata["alpha"] == 0.01
    assert metadata["trainWindow"] == "6 calendar months"
    assert metadata["horizons"] == [10, 40, 120] and metadata["fusion"] == [0.25, 0.5, 0.25]
    assert metadata["topKSemantics"].startswith("highest_five_fused_scores")
    assert metadata["validation"] == "SEALED" and metadata["finalOos"] == "SEALED"
    assert metadata["strictPit"] is False and metadata["executable"] is False
    assert metadata["tradable"] is False
    assert metadata["classification"] == "FIXED_CLASSIFICATION_RESEARCH"
    assert metadata["POST_AUDIT_DEVELOPMENT_RESEARCH"] is True
    assert metadata["NO_INDEPENDENT_VALIDATION"] is True
    assert metadata["candidateIds"] == ["C0", "V2_A", "V2_B", "V2_D"]
    assert metadata["candidateFactorLists"]["V2_D"] == ["d20", "p60", "align", "v20", "rev5", "dd20"]


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
    index, frames, codes = _synthetic_world()
    development_dates = index[300:400]
    factors = tuple(dict.fromkeys(f for spec in runner.scheme_specs() for f in spec["factorList"]))
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
    assert report["status"] == "PASS"
    assert report["sampledFactors"] == list(protocol.FROZEN_FACTOR_ORDER)  # superset incl. all V2 factors
    assert report["comparisons"] == 3 * len(factors) * 10
    stashed[(1, codes[0])][factors[0]] += 1e-3
    with pytest.raises(ValueError, match="FACTOR_IDENTITY_BLOCKER"):
        runner.factor_identity_gate(stashed, frames, index, development_dates, codes)


def test_target_identity_gate_passes_on_match_and_blocks_on_drift():
    index, frames, codes = _synthetic_world()
    development_dates = index[300:400]
    labels_by_h = {}
    artifact_rows = []
    for horizon in protocol.FROZEN_SETTINGS["horizons"]:
        series = {}
        for code in codes:
            close = frames[code]["close"]
            values = {}
            for i in range(len(index) - horizon):
                values[index[i]] = float(close.iloc[i + horizon]) / float(close.iloc[i]) - 1.0
            series[code] = pd.Series(values)
        labels_by_h[horizon] = series
    for ordinal in runner.IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        signal_i = int(index.get_loc(signal))
        for horizon in protocol.FROZEN_SETTINGS["horizons"]:
            endpoint = index[signal_i + horizon]
            for code in codes[:runner.IDENTITY_SAMPLE_SECTOR_COUNT]:
                artifact_rows.append({
                    "ordinal": ordinal, "horizon": horizon, "sector_code": code,
                    "realized_forward_return": float(labels_by_h[horizon][code].loc[signal]),
                    "label_end": str(endpoint.date())})
    d2 = pd.DataFrame(artifact_rows)
    report = runner.target_identity_gate(labels_by_h, frames, index, development_dates,
                                         codes, d2)
    assert report["status"] == "PASS" and report["comparisons"] == 3 * 3 * 10
    assert report["maxAbsDiffDirectArithmetic"] <= runner.TARGET_IDENTITY_TOLERANCE
    assert report["maxAbsDiffD2ControlArtifact"] <= runner.TARGET_IDENTITY_TOLERANCE
    drifted = {h: {c: s.copy() for c, s in series.items()} for h, series in labels_by_h.items()}
    drifted[10][codes[0]].loc[development_dates[0]] += 1e-6
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(drifted, frames, index, development_dates, codes, d2)
    wrong_end = pd.DataFrame(artifact_rows)
    wrong_end.loc[0, "label_end"] = "1999-01-01"
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(labels_by_h, frames, index, development_dates,
                                    codes, wrong_end)


def test_metric_integrity_recompute_and_blocker():
    rows = []
    label = np.arange(N_CODES, dtype=float)
    for ordinal in range(1, 101):
        for horizon in (10, 40, 120):
            for i, code in enumerate(CODES):
                rows.append({"ordinal": ordinal, "horizon": horizon, "sector_code": code,
                             "prediction_score": label[i], "realized_forward_return": label[i],
                             "top5": i < 5})
    predictions = pd.DataFrame(rows)
    summary_row = {
        "candidateId": "V2_A", "factorCount": 1, "isControl": False,
        "weightedRankIc": 1.0, "weightedSpread": -59.5,
        "rankIcByHorizon": {"10": 1.0, "40": 1.0, "120": 1.0},
        "spreadByHorizon": {"10": -59.5, "40": -59.5, "120": -59.5},
    }
    report = runner.verify_metric_integrity({"V2_A": predictions}, [summary_row])
    assert report["status"] == "PASS" and report["maxAbsDiff"] <= 1e-12
    bad = dict(summary_row, weightedRankIc=0.5)
    with pytest.raises(ValueError, match="METRIC_INTEGRITY_BLOCKER"):
        runner.verify_metric_integrity({"V2_A": predictions}, [bad])


def test_result_labels_and_selection_bias_in_summary():
    summary = _synthetic_summary()
    statuses = [row["advancementStatus"] for row in summary["candidates"]]
    assert set(statuses) <= {runner.STATUS_ADVANCED, runner.STATUS_NOT_ADVANCED}
    assert summary["control"]["advancementStatus"] == runner.STATUS_CONTROL
    for forbidden in runner.FORBIDDEN_RESULT_LABELS:
        assert all(forbidden not in status for status in statuses + [runner.STATUS_CONTROL])
    assert summary["selectionBias"]["POST_AUDIT_DEVELOPMENT_RESEARCH"] is True
    assert summary["selectionBias"]["NOT_INDEPENDENT_VALIDATION"] is True
    assert summary["selectionBias"]["NOT_OOS_EVIDENCE"] is True

"""Synthetic preregistration gates; never compute formal E001-E100 results."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from research import alpha_stability_regime_audit_v1_protocol as protocol
from research import alpha_stability_regime_audit_v1_run as runner
from research import factor_alpha_audit_v1_protocol as factor_audit
from research import sector_development_baseline as baseline
from strategies.sw_sector_rotation.src.model.model import NumPyRidge


def test_protocol_hash_config_order_and_scope(tmp_path):
    payload = protocol.verify_protocol()
    assert protocol.protocol_hash() == protocol.FROZEN_PROTOCOL_HASH
    assert payload["configExactContent"]["auditType"] == protocol.AUDIT_TYPE
    assert tuple(payload["configExactContent"]["factorOrder"]) == baseline.EXPECTED_FEATURES
    assert list(protocol.SCHEMES) == ["C0", "V2_A", "V2_B", "V2_D"]
    assert protocol.SCHEMES["C0"] == tuple(baseline.EXPECTED_FEATURES)
    assert protocol.SCHEMES["V2_A"] == ("v20",)
    assert protocol.SCHEMES["V2_B"] == ("v5", "v20")
    assert protocol.SCHEMES["V2_D"] == ("d20", "p60", "align", "v20", "rev5", "dd20")
    assert "V2_C" not in protocol.SCHEMES
    assert protocol.HORIZONS == (10, 40, 120)
    assert protocol.LAGS == (1, 5, 10, 20)
    assert protocol.BLOCKS == (("B1", 1, 25), ("B2", 26, 50),
                               ("B3", 51, 75), ("B4", 76, 100))
    assert protocol.MIN_PAIRS == 30 and protocol.CANCELLATION_EPS == 1e-12
    assert payload["configExactContent"]["noFactorSelection"] is True
    assert payload["configExactContent"]["noParameterSearch"] is True
    assert payload["configExactContent"]["noNewCandidate"] is True
    assert payload["configExactContent"]["validationSealed"] is True
    assert payload["configExactContent"]["finalOosSealed"] is True
    protocol.guard_scope("development", [1, 50, 100])
    with pytest.raises(PermissionError):
        protocol.guard_scope("development", [101])
    with pytest.raises(PermissionError):
        protocol.guard_scope("validation", [221])
    with pytest.raises(PermissionError):
        protocol.guard_scope("final_oos", [401])
    config = json.loads(protocol.config_path().read_text(encoding="utf-8"))
    config["directionThreshold"] = 0.03
    target = tmp_path / protocol.CONFIG_RELPATH
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="CONFIG_DRIFT_BLOCKER"):
        protocol.load_config(tmp_path)


@pytest.mark.parametrize("value,expected", [
    (0.0200001, "POSITIVE"), (0.02, "NEUTRAL"), (0.0, "NEUTRAL"),
    (-0.02, "NEUTRAL"), (-0.0200001, "NEGATIVE"), (None, None),
])
def test_direction_threshold_exact(value, expected):
    assert protocol.direction(value) == expected


def test_hard_flip_raw_sign_and_fixed_blocks():
    assert protocol.hard_flip(0.03, -0.03) is True
    assert protocol.hard_flip(-0.03, 0.03) is True
    assert protocol.hard_flip(0.03, -0.02) is False
    assert protocol.hard_flip(None, 0.03) is None
    assert protocol.raw_sign_agreement(0.0, 0.0) is True
    assert protocol.raw_sign_agreement(0.0, 0.01) is False
    assert protocol.beta_evaluation_hard_flip(0.001, -0.03) is True
    assert protocol.beta_evaluation_hard_flip(-0.001, 0.03) is True
    assert protocol.beta_evaluation_hard_flip(0.001, 0.0) is False
    assert [protocol.block_id(n) for n in (1, 25, 26, 50, 51, 75, 76, 100)] == [
        "B1", "B1", "B2", "B2", "B3", "B3", "B4", "B4"]


def test_transition_matrix_complete_and_sign_persistence():
    paired = pd.DataFrame({
        "train_direction": ["POSITIVE", "POSITIVE", "NEGATIVE", "NEUTRAL"],
        "evaluation_direction": ["NEGATIVE", "POSITIVE", "POSITIVE", "NEUTRAL"],
    })
    matrix = runner.transition_matrix_rows(paired, "v20", 40)
    assert len(matrix) == 9
    assert sum(row["count"] for row in matrix) == 4
    lookup = {(row["train_direction"], row["evaluation_direction"]): row["count"]
              for row in matrix}
    assert lookup[("POSITIVE", "NEGATIVE")] == 1
    assert lookup[("NEGATIVE", "POSITIVE")] == 1
    assert lookup[("NEUTRAL", "NEUTRAL")] == 1
    assert lookup[("NEGATIVE", "NEGATIVE")] == 0
    changes, persistence = runner._adjacent_sign_stats([1.0, 1.0, -1.0, -1.0])
    assert changes == 1 and persistence == pytest.approx(2 / 3)


def test_cancellation_diversification_and_correlation_definitions():
    assert runner.cancellation_ratio(np.array([1.0, -1.0])) == pytest.approx(1.0)
    assert runner.cancellation_ratio(np.array([1.0])) == pytest.approx(0.0, abs=1e-11)
    assert runner.cancellation_ratio(np.array([0.0, 0.0])) == 1.0
    assert runner.diversification_ratio(np.column_stack((
        np.arange(40, dtype=float), np.arange(40, dtype=float)))) == pytest.approx(1.0)
    assert runner.diversification_ratio(np.column_stack((
        np.arange(40, dtype=float), -np.arange(40, dtype=float)))) == pytest.approx(0.0)
    x = np.arange(40, dtype=float)
    assert protocol.cross_sectional_spearman(x, -x) == pytest.approx(-1.0)
    assert protocol.cross_sectional_spearman(x[:29], x[:29]) is None


def test_legal_training_dates_cutoff_and_no_shift():
    calendar = pd.date_range("2025-01-01", periods=40, freq="B")
    boundary = SimpleNamespace(train_start=calendar[2], label_cutoff=calendar[35])
    first = pd.DataFrame({"fwd10": np.ones(40)}, index=calendar)
    second = first.copy()
    second.loc[calendar[9], "fwd10"] = np.nan
    candidates, legal = runner.legal_training_dates(
        {"a": first, "b": second}, calendar, boundary, 10)
    assert candidates == list(calendar[2:36])
    assert legal == [d for d in candidates if d != calendar[9]]
    assert calendar[36] not in legal
    assert len(legal) >= 30


def test_training_mean_rankic_min_pairs_and_evaluation_rankic():
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    x = np.tile(np.arange(40, dtype=float), (30, 1))
    y = x.copy()
    cube = np.zeros((30, 40, 19), dtype=float)
    cube[:, :, 12] = x  # frozen v20 index
    relation = runner._training_relationship(cube, y, dates, 10, {})[12]
    assert relation["train_valid_dates"] == 30
    assert relation["train_mean_rankic"] == pytest.approx(1.0)
    assert relation["train_mean_ic"] == pytest.approx(1.0)
    assert factor_audit.cross_sectional_ic(x[0], -y[0])["rankic"] == pytest.approx(-1.0)
    assert factor_audit.cross_sectional_ic(x[0, :29], y[0, :29])["skipped"] is True


def test_autocorrelation_lags_and_overlapping_label_caveat():
    values = [float(i) for i in range(30)]
    for lag in protocol.LAGS:
        assert protocol.lag_autocorrelation(values, lag) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="UNREGISTERED"):
        protocol.lag_autocorrelation(values, 2)
    assert "NOT INDEPENDENT OBSERVATIONS" in (Path(__file__).resolve().parents[1]
        / "docs/research/shenwan_alpha_stability_regime_audit_v1.md").read_text(encoding="utf-8")


def test_coefficient_reproduction_scale_and_contribution_identity():
    x_train = np.column_stack((np.arange(1, 61, dtype=float),
                               np.sin(np.arange(1, 61, dtype=float))))
    target = 0.2 * x_train[:, 0] - 0.3 * x_train[:, 1]
    x_predict = np.column_stack((np.arange(1, 41, dtype=float),
                                 np.cos(np.arange(1, 41, dtype=float))))
    fitted = NumPyRidge(alpha=0.01).fit(x_train, target)
    scores = fitted.predict(x_predict)
    codes = [f"S{i:03d}" for i in range(40)]
    reference = {(1, 40, code): float(score) for code, score in zip(codes, scores)}
    coeff, factor_rows, sector_rows, _, diff, reconstruction = (
        runner._coefficient_contributions("V2_B", 1, "2025-01-01", 40,
                                          ("v5", "v20"), x_train, x_predict,
                                          target, reference, codes))
    assert diff == pytest.approx(0.0)
    assert reconstruction < 1e-10
    assert coeff[0]["scale_adjusted_beta"] == pytest.approx(
        coeff[0]["beta"] * np.std(x_train[:, 0], ddof=0))
    assert sum(row["absolute_share"] for row in factor_rows) == pytest.approx(1.0)
    assert all(0 <= row["cancellation_ratio"] <= 1 for row in sector_rows)
    assert 0 <= factor_rows[0]["diversification_ratio"] <= 1 + 1e-12
    wrong = dict(reference)
    wrong[(1, 40, codes[0])] += 0.01
    with pytest.raises(ValueError, match="RIDGE_COEFFICIENT_IDENTITY_BLOCKER"):
        runner._coefficient_contributions("V2_B", 1, "2025-01-01", 40,
                                          ("v5", "v20"), x_train, x_predict,
                                          target, wrong, codes)


def test_v2a_single_factor_cancellation_sanity():
    x_train = np.arange(1, 51, dtype=float).reshape(-1, 1)
    y = x_train[:, 0] * 0.1
    x_predict = np.arange(1, 41, dtype=float).reshape(-1, 1)
    codes = [f"S{i:03d}" for i in range(40)]
    reference = {(1, 10, code): float(score) for code, score in zip(
        codes, NumPyRidge(alpha=0.01).fit(x_train, y).predict(x_predict))}
    _, _, sectors, correlations, _, _ = runner._coefficient_contributions(
        "V2_A", 1, "2025-01-01", 10, ("v20",), x_train, x_predict,
        y, reference, codes)
    assert correlations == []
    assert max(row["cancellation_ratio"] for row in sectors) < 1e-10


def test_artifact_schema_is_frozen_and_no_formal_result_before_prereg_commit():
    assert set(runner.TABLE_NAMES) == {
        "factor_transfer_daily.csv", "factor_transfer_summary.csv",
        "factor_transfer_transition.csv", "factor_rankic_autocorrelation.csv",
        "factor_block_transfer.csv", "coefficient_daily.csv",
        "coefficient_stability_summary.csv", "coefficient_alignment_summary.csv",
        "contribution_daily_summary.csv", "contribution_sector_daily.csv",
        "contribution_factor_summary.csv", "contribution_correlation.csv",
        "contribution_block_summary.csv", "horizon_stability_summary.csv",
    }
    # Synthetic guard only: permanent tests must pass after the formal run.
    assert protocol.verify_protocol()["selectionBias"].startswith("POST-V2")


def test_v2_reference_rejects_tampered_model_metric_source(tmp_path):
    content_hashes = {}
    for scheme in protocol.SCHEMES:
        folder = tmp_path / scheme
        folder.mkdir()
        for name in ("predictions.csv", "training_diagnostics.csv", "per_date_metrics.csv"):
            source = folder / name
            source.write_text("ordinal,horizon\n1,10\n", encoding="utf-8")
            content_hashes[f"{scheme}/{name}"] = hashlib.sha256(source.read_bytes()).hexdigest()
    (tmp_path / "metadata.json").write_text(json.dumps({
        "protocolHash": "3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4",
        "candidateIds": list(protocol.SCHEMES), "phase": "DEVELOPMENT",
        "content_sha256": content_hashes,
    }), encoding="utf-8")
    runner._read_v2_reference(tmp_path)
    (tmp_path / "C0" / "per_date_metrics.csv").write_text(
        "ordinal,horizon\n1,40\n", encoding="utf-8")
    with pytest.raises(ValueError, match="V2_REFERENCE_ARTIFACT_HASH_BLOCKER"):
        runner._read_v2_reference(tmp_path)


def test_formal_result_leak_gate_pre_run_and_exact_rerun(tmp_path):
    runner.assert_formal_result_state(tmp_path)
    first = tmp_path / "alpha_stability_regime_audit_20990101_000000_utc"
    first.mkdir()
    with pytest.raises(ValueError, match="PREREGISTRATION_RESULT_LEAK_BLOCKER"):
        runner.assert_formal_result_state(tmp_path)
    runner.assert_formal_result_state(tmp_path, first)
    extra = tmp_path / "alpha_stability_regime_audit_20990102_000000_utc"
    extra.mkdir()
    with pytest.raises(ValueError, match="PREREGISTRATION_RESULT_LEAK_BLOCKER"):
        runner.assert_formal_result_state(tmp_path, first)


def test_synthetic_full_grid_summary_integrity_and_determinism(tmp_path):
    """No real Development data: exercise the complete artifact pipeline."""
    v2_root = tmp_path / "synthetic_v2"
    for scheme in protocol.SCHEMES:
        folder = v2_root / scheme
        folder.mkdir(parents=True)
        pd.DataFrame([
            {"ordinal": ordinal, "horizon": horizon,
             "metric": f"RankIC_{horizon}", "value": 0.1}
            for ordinal in range(1, 101) for horizon in protocol.HORIZONS
        ]).to_csv(folder / "per_date_metrics.csv", index=False)
    raw = {"factor_transfer_daily.csv": [], "coefficient_daily.csv": [],
           "contribution_daily_summary.csv": [], "contribution_sector_daily.csv": [],
           "contribution_correlation_daily": []}
    for ordinal in range(1, 101):
        block = protocol.block_id(ordinal)
        for horizon in protocol.HORIZONS:
            for factor in protocol.FACTOR_ORDER:
                raw["factor_transfer_daily.csv"].append({
                    "ordinal": ordinal, "signal_date": "2025-01-01", "block": block,
                    "factor": factor, "horizon": horizon,
                    "train_mean_ic": 0.1, "train_median_ic": 0.1,
                    "train_mean_rankic": 0.1, "train_median_rankic": 0.1,
                    "train_valid_dates": 30, "evaluation_ic": 0.2,
                    "evaluation_rankic": 0.2, "evaluation_valid_pairs": 124,
                    "train_direction": "POSITIVE", "evaluation_direction": "POSITIVE",
                    "raw_sign_agreement": True, "hard_flip": False,
                })
            for scheme, factors in protocol.SCHEMES.items():
                for factor in factors:
                    raw["coefficient_daily.csv"].append({
                        "scheme": scheme, "ordinal": ordinal, "signal_date": "2025-01-01",
                        "horizon": horizon, "factor": factor, "beta": 0.1,
                        "training_feature_std": 2.0, "scale_adjusted_beta": 0.2,
                        "train_mean_rankic": 0.1, "evaluation_rankic": 0.2,
                        "beta_vs_train_sign_agreement": True,
                        "beta_vs_evaluation_sign_agreement": True,
                        "beta_to_evaluation_hard_flip": False,
                    })
                    raw["contribution_daily_summary.csv"].append({
                        "scheme": scheme, "ordinal": ordinal,
                        "signal_date": "2025-01-01", "horizon": horizon,
                        "block": block, "factor": factor,
                        "contribution_std": 1.0, "mean_abs_contribution": 1.0,
                        "absolute_share": 1.0 / len(factors),
                        "diversification_ratio": 0.5,
                    })
                for sector_number in range(124):
                    raw["contribution_sector_daily.csv"].append({
                        "scheme": scheme, "ordinal": ordinal,
                        "signal_date": "2025-01-01", "horizon": horizon,
                        "block": block, "sector_code": f"S{sector_number:03d}",
                        "absolute_component_sum": 1.0,
                        "cancellation_ratio": 0.2,
                        "total_centered_prediction": 0.8,
                    })
    raw["contribution_correlation_daily"] = [
        {"scheme": "C0", "ordinal": 1, "horizon": 10,
         "factor_a": "d5", "factor_b": "d5", "spearman": 1.0}]
    tables = runner.summarize_tables(raw, v2_root)
    assert len(tables["factor_transfer_summary.csv"]) == 57
    assert len(tables["factor_transfer_transition.csv"]) == 57 * 9
    assert len(tables["factor_block_transfer.csv"]) == 57 * 4
    assert len(tables["coefficient_stability_summary.csv"]) == 28 * 3
    assert len(tables["contribution_block_summary.csv"]) == 4 * 3 * 5
    identities = {"synthetic": {"status": "PASS"}}
    context = {"firstDate": "2025-01-01", "lastDate": "2025-01-01",
               "sectorCount": 124, "factorCount": 19, "trainingRelationCacheEntries": 0}
    result = runner.AuditResult(tables, runner.build_summary(tables, identities, context),
                                identities, context)
    gate = {"gitCommit": "synthetic", "preregistrationCommit": "synthetic",
            "sectorSnapshotId": "synthetic", "splitPolicyHash": "synthetic",
            "firstDate": "2025-01-01", "lastDate": "2025-01-01",
            "dockerImageId": "synthetic"}
    output_root = tmp_path / "synthetic_reports"
    first = runner.write_run(output_root, result, gate)
    assert runner.verify_artifact_integrity(first)["status"] == "PASS"
    second = runner.write_run(output_root, result, gate, repeat_of=first)
    assert json.loads((first / "metadata.json").read_text(encoding="utf-8"))[
        "contentSha256"] == json.loads((second / "metadata.json").read_text(encoding="utf-8"))[
            "contentSha256"]
    corrupted = pd.read_csv(second / "factor_transfer_summary.csv")
    corrupted.loc[0, "hard_flip_count"] += 1
    corrupted.to_csv(second / "factor_transfer_summary.csv", index=False)
    with pytest.raises(ValueError, match="ALPHA_STABILITY_METRIC_INTEGRITY_BLOCKER"):
        runner.verify_artifact_integrity(second)

"""Synthetic-only gates for the authorized Factor Alpha Audit V1 runner."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from research import factor_alpha_audit_v1_protocol as protocol
from research import factor_alpha_audit_v1_run as runner
from research import sector_development_baseline as baseline
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features

SMALL_FACTORS = ("f0", "f1", "f2", "f3", "f4")
SMALL_HORIZONS = (10, 40)
N_CODES = 40
N_DATES = 100


def _codes(n: int = N_CODES) -> list[str]:
    return [f"C{i:03d}" for i in range(n)]


def _synthetic_matrices():
    """f0: stable positive; f1: sign flip after date 75; f2: constant; f3: gaps;
    f4: perfectly co-monotone with f0 (redundant)."""
    codes = _codes()
    idx = np.arange(N_CODES, dtype=float)
    factor_matrix = np.zeros((N_DATES, N_CODES, len(SMALL_FACTORS)))
    for d in range(N_DATES):
        factor_matrix[d, :, 0] = idx
        factor_matrix[d, :, 1] = idx if d < 75 else -idx
        factor_matrix[d, :, 2] = 5.0
        factor_matrix[d, :, 3] = idx
        factor_matrix[d, :, 4] = 2.0 * idx
    factor_matrix[:10, :5, 3] = np.nan  # missing factor observations, never imputed
    labels_10 = np.tile(idx, (N_DATES, 1))
    labels_40 = np.tile(2.0 * idx, (N_DATES, 1))
    labels_40[:5, :3] = np.nan  # missing labels, never imputed
    return codes, factor_matrix, {10: labels_10, 40: labels_40}


def _build_small_tables(monkeypatch):
    monkeypatch.setattr(runner, "FACTOR_ORDER", SMALL_FACTORS)
    monkeypatch.setattr(runner, "HORIZONS", SMALL_HORIZONS)
    codes, factor_matrix, label_matrix = _synthetic_matrices()
    dates = pd.bdate_range("2025-04-02", periods=N_DATES)
    return runner.build_tables(factor_matrix, label_matrix, dates, codes)


def test_build_tables_grids_signed_results_and_blocks(monkeypatch):
    tables = _build_small_tables(monkeypatch)
    daily = tables["factor_daily_metrics.csv"]
    summary = tables["factor_horizon_summary.csv"]
    blocks = tables["factor_stability_blocks.csv"]
    assert len(daily) == 100 * len(SMALL_FACTORS) * len(SMALL_HORIZONS)
    assert len(summary) == len(SMALL_FACTORS) * len(SMALL_HORIZONS)
    assert len(blocks) == len(SMALL_FACTORS) * len(SMALL_HORIZONS) * 4
    rows = list(zip(daily["factor"], daily["horizon"]))
    assert rows == [(f, h) for f in SMALL_FACTORS for h in SMALL_HORIZONS
                    for _ in range(N_DATES)]  # frozen deterministic row order
    assert list(daily["ordinal"][:100]) == list(range(1, 101))
    f0 = summary[(summary["factor"] == "f0") & (summary["horizon"] == 10)].iloc[0]
    assert f0["rankic_mean"] == pytest.approx(1.0, abs=1e-12)  # signed, never flipped
    assert f0["positive_rankic_dates"] == 100 and f0["negative_rankic_dates"] == 0
    assert pd.isna(f0["rankic_t_stat_descriptive"])  # zero spread: no t, never faked
    f1 = summary[(summary["factor"] == "f1") & (summary["horizon"] == 10)].iloc[0]
    assert f1["rankic_mean"] == pytest.approx(0.5, abs=1e-12)  # 75 x +1, 25 x -1
    assert f1["positive_rankic_dates"] == 75 and f1["negative_rankic_dates"] == 25
    assert f1["rankic_t_stat_descriptive"] is not None  # DESCRIPTIVE ONLY, still signed
    f2 = summary[(summary["factor"] == "f2") & (summary["horizon"] == 10)].iloc[0]
    assert f2["valid_dates"] == 0 and pd.isna(f2["rankic_mean"])  # zero variance skipped
    f1_blocks = blocks[(blocks["factor"] == "f1") & (blocks["horizon"] == 10)]
    assert list(f1_blocks["block"]) == [1, 2, 3, 4]
    assert list(f1_blocks["rankic_mean"]) == [1.0, 1.0, 1.0, -1.0]
    assert list(f1_blocks["same_sign_block_count"]) == [3] * 4
    assert list(f1_blocks["full_development_sign"]) == ["positive"] * 4
    f0_blocks = blocks[(blocks["factor"] == "f0") & (blocks["horizon"] == 10)]
    assert list(f0_blocks["same_sign_block_count"]) == [4] * 4


def test_build_tables_quantiles_coverage_and_missingness(monkeypatch):
    tables = _build_small_tables(monkeypatch)
    qsummary = tables["factor_quantile_summary.csv"]
    coverage = tables["factor_coverage.csv"]
    f0 = qsummary[(qsummary["factor"] == "f0") & (qsummary["horizon"] == 10)].iloc[0]
    assert f0["q1_mean"] == pytest.approx(np.mean([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]))
    assert f0["q5_mean"] == pytest.approx(np.mean([32.0, 33.0, 34.0, 35.0, 36.0, 37.0, 38.0, 39.0]))
    assert f0["q5_minus_q1_mean"] == pytest.approx(32.0, abs=1e-12)
    assert f0["quantile_monotonicity"] == pytest.approx(1.0, abs=1e-12)
    f1 = qsummary[(qsummary["factor"] == "f1") & (qsummary["horizon"] == 10)].iloc[0]
    assert f1["q5_minus_q1_mean"] == pytest.approx(16.0, abs=1e-12)  # 75 x +32, 25 x -32
    f3 = coverage[(coverage["factor"] == "f3") & (coverage["horizon"] == 10)].iloc[0]
    assert f3["missing_factor_observations"] == 50  # 10 dates x 5 sectors, counted not filled
    assert f3["valid_factor_observations"] == 100 * N_CODES - 50
    assert f3["valid_sectors_min"] == N_CODES - 5 and f3["valid_sectors_max"] == N_CODES
    f0_h40 = coverage[(coverage["factor"] == "f0") & (coverage["horizon"] == 40)].iloc[0]
    assert f0_h40["valid_factor_label_pairs"] == 100 * N_CODES - 15  # 5 dates x 3 labels missing
    assert f0_h40["skipped_ic_dates"] == 0
    f2 = coverage[(coverage["factor"] == "f2") & (coverage["horizon"] == 10)].iloc[0]
    assert f2["skipped_ic_dates"] == 100
    assert f2["valid_factor_label_pairs"] == 100 * N_CODES  # finite pairs counted, IC still skipped


def test_build_tables_correlation_redundancy_flags_and_deterministic_bytes(monkeypatch):
    tables = _build_small_tables(monkeypatch)
    corr = tables["factor_correlation_spearman.csv"]
    flags = tables["factor_redundancy_flags.csv"]
    assert len(corr) == len(SMALL_FACTORS) ** 2  # matrix keeps the diagonal
    diagonal = corr[corr["factor_a"] == corr["factor_b"]]
    assert diagonal["flagged_redundant"].eq(False).all()  # never flags self-pairs
    assert sorted(flags[["factor_a", "factor_b"]].values.tolist()) == [
        ["f0", "f3"], ["f0", "f4"], ["f3", "f4"]]
    pair = corr[(corr["factor_a"] == "f0") & (corr["factor_b"] == "f4")].iloc[0]
    assert pair["mean_daily_spearman"] == pytest.approx(1.0, abs=1e-12)
    assert pair["valid_dates"] == 100 and bool(pair["flagged_redundant"])
    constant = corr[(corr["factor_a"] == "f2") & (corr["factor_b"] == "f0")].iloc[0]
    assert pd.isna(constant["mean_daily_spearman"]) and constant["valid_dates"] == 0
    again = _build_small_tables(monkeypatch)
    for name, frame in tables.items():
        assert baseline._csv_bytes(frame) == baseline._csv_bytes(again[name])


def _synthetic_world(n_dates: int = 530, n_codes: int = 12):
    index = pd.bdate_range("2024-01-01", periods=n_dates)
    codes = _codes(n_codes)
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
    factor_matrix = np.zeros((100, len(codes), len(protocol.FACTOR_ORDER)))
    for ordinal in protocol.IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        for c_i, code in enumerate(codes):
            values = compute_all_price_features(
                baseline._source_frame(frames[code], frames[code].index[0], signal),
                include_rsrs=False,
            ).loc[signal, list(protocol.FACTOR_ORDER)].to_numpy(dtype=float)
            factor_matrix[ordinal - 1, c_i, :] = values
    report = runner.factor_identity_gate(factor_matrix, frames, index, development_dates, codes)
    assert report["status"] == "PASS" and report["comparisons"] == 3 * 19 * 10
    assert report["max_abs_diff"] <= protocol.FACTOR_IDENTITY_TOLERANCE
    factor_matrix[0, 0, 0] += 1e-3
    with pytest.raises(ValueError, match="FACTOR_IDENTITY_BLOCKER"):
        runner.factor_identity_gate(factor_matrix, frames, index, development_dates, codes)


def test_target_identity_gate_passes_on_match_and_blocks_on_drift(tmp_path, monkeypatch):
    index, frames, codes = _synthetic_world()
    development_dates = index[300:400]
    label_matrix = {h: np.full((100, len(codes)), np.nan) for h in protocol.HORIZONS}
    artifact_rows = []
    for ordinal in protocol.IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        signal_i = int(index.get_loc(signal))
        for horizon in protocol.HORIZONS:
            endpoint = index[signal_i + horizon]
            for c_i, code in enumerate(codes):
                close = frames[code]["close"]
                value = float(close.loc[endpoint]) / float(close.loc[signal]) - 1.0
                label_matrix[horizon][ordinal - 1, c_i] = value
                artifact_rows.append({"ordinal": ordinal, "horizon": horizon,
                                      "sector_code": code,
                                      "realized_forward_return": value,
                                      "label_end": str(endpoint.date())})
    d0_dir = tmp_path / "D0"
    d0_dir.mkdir()
    payload = pd.DataFrame(artifact_rows).to_csv(
        index=False, float_format="%.17g", lineterminator="\n").encode("utf-8")
    (d0_dir / "predictions.csv").write_bytes(payload)
    monkeypatch.setattr(runner, "ITERATION1_D0_PREDICTIONS_SHA256",
                        hashlib.sha256(payload).hexdigest())
    report = runner.target_identity_gate(label_matrix, frames, index, development_dates,
                                         codes, d0_dir)
    assert report["status"] == "PASS" and report["comparisons"] == 3 * 3 * 10
    assert report["max_abs_diff_direct_arithmetic"] <= protocol.TARGET_IDENTITY_TOLERANCE
    assert report["max_abs_diff_d0_control_artifact"] <= protocol.TARGET_IDENTITY_TOLERANCE
    drifted = {h: values.copy() for h, values in label_matrix.items()}
    drifted[10][0, 0] += 1e-6
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(drifted, frames, index, development_dates, codes, d0_dir)
    wrong_endpoint = pd.DataFrame(artifact_rows)
    wrong_endpoint.loc[0, "label_end"] = "1999-01-01"
    bad_bytes = wrong_endpoint.to_csv(index=False, float_format="%.17g",
                                      lineterminator="\n").encode("utf-8")
    (d0_dir / "predictions.csv").write_bytes(bad_bytes)
    monkeypatch.setattr(runner, "ITERATION1_D0_PREDICTIONS_SHA256",
                        hashlib.sha256(bad_bytes).hexdigest())
    with pytest.raises(ValueError, match="TARGET_IDENTITY_BLOCKER"):
        runner.target_identity_gate(label_matrix, frames, index, development_dates,
                                    codes, d0_dir)


def _small_output(monkeypatch) -> runner.AuditOutput:
    tables = _build_small_tables(monkeypatch)
    metadata = {
        "researchLabel": "SECTOR_INDEX_RESEARCH_ONLY", "phase": "DEVELOPMENT",
        "auditType": protocol.AUDIT_TYPE, "gitCommit": "0" * 40,
        "protocolHash": protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH,
        "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
        "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
        "factorOrder": list(SMALL_FACTORS), "horizons": list(SMALL_HORIZONS),
        "developmentEligibleIds": "E001-E100",
        "minimumValidSectorPairs": 30, "quantileCount": 5,
        "redundancyThreshold": 0.80, "strictPit": False,
        "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "executable": False, "tradable": False,
        "validation": "SEALED", "finalOos": "SEALED",
        "NO_PARAMETER_SELECTION": True, "NO_FACTOR_SELECTION": True,
        "DIAGNOSTIC_ONLY": True,
    }
    return runner.AuditOutput(
        daily_metrics=tables["factor_daily_metrics.csv"],
        horizon_summary=tables["factor_horizon_summary.csv"],
        quantile_daily=tables["factor_quantile_daily.csv"],
        quantile_summary=tables["factor_quantile_summary.csv"],
        stability_blocks=tables["factor_stability_blocks.csv"],
        correlation=tables["factor_correlation_spearman.csv"],
        redundancy_flags=tables["factor_redundancy_flags.csv"],
        coverage=tables["factor_coverage.csv"],
        audit_summary={"audit_type": protocol.AUDIT_TYPE,
                       "headlines": runner.headline_rows(tables["factor_horizon_summary.csv"]),
                       "notices": ["DEVELOPMENT ONLY", "DIAGNOSTIC ONLY"]},
        metadata=metadata,
    )


def test_write_run_is_deterministic_and_repeat_detects_drift(tmp_path, monkeypatch):
    output = _small_output(monkeypatch)
    first = runner.write_run(tmp_path, output)
    second = runner.write_run(tmp_path, output)
    assert set(p.name for p in first.iterdir()) == set(runner.ARTIFACT_NAMES) | {"metadata.json"}
    meta1 = json.loads((first / "metadata.json").read_text(encoding="utf-8"))
    meta2 = json.loads((second / "metadata.json").read_text(encoding="utf-8"))
    assert meta1["content_sha256"] == meta2["content_sha256"]  # byte-stable data artifacts
    repeated = runner.write_run(tmp_path, output, repeat_of=first)
    meta3 = json.loads((repeated / "metadata.json").read_text(encoding="utf-8"))
    assert meta3["determinism"] == "PASS_CONTENT_SHA256_IDENTICAL"
    assert meta3["determinism_repeat_of"] == meta1["run_id"]
    drift = tmp_path / "drift"
    drift.mkdir()
    fake = b"factor,horizon\nFAKE,10\n"
    (drift / "factor_coverage.csv").write_bytes(fake)
    (drift / "metadata.json").write_text(json.dumps({
        "content_sha256": {**meta2["content_sha256"],
                           "factor_coverage.csv": hashlib.sha256(fake).hexdigest()},
        "protocolHash": protocol.FROZEN_FACTOR_ALPHA_AUDIT_V1_PROTOCOL_HASH}),
        encoding="utf-8")
    with pytest.raises(ValueError, match="FACTOR_AUDIT_DETERMINISM_BLOCKER"):
        runner.write_run(tmp_path, output, repeat_of=drift)


def test_write_run_rejects_invalid_identity_or_incomplete_grid(tmp_path, monkeypatch):
    output = _small_output(monkeypatch)
    bad_meta = dict(output.metadata, executable=True)
    with pytest.raises(ValueError, match="RESEARCH_PROTOCOL_VIOLATION"):
        runner.write_run(tmp_path, runner.AuditOutput(
            daily_metrics=output.daily_metrics, horizon_summary=output.horizon_summary,
            quantile_daily=output.quantile_daily, quantile_summary=output.quantile_summary,
            stability_blocks=output.stability_blocks, correlation=output.correlation,
            redundancy_flags=output.redundancy_flags, coverage=output.coverage,
            audit_summary=output.audit_summary, metadata=bad_meta))
    truncated = pd.DataFrame(columns=output.daily_metrics.columns)
    with pytest.raises(ValueError, match="RESEARCH_PROTOCOL_VIOLATION"):
        runner.write_run(tmp_path, runner.AuditOutput(
            daily_metrics=truncated, horizon_summary=output.horizon_summary,
            quantile_daily=output.quantile_daily, quantile_summary=output.quantile_summary,
            stability_blocks=output.stability_blocks, correlation=output.correlation,
            redundancy_flags=output.redundancy_flags, coverage=output.coverage,
            audit_summary=output.audit_summary, metadata=output.metadata))

"""Offline tests for the Development-only runner, never real performance."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import sector_development_baseline as baseline
from research.sector_development_protocol import prediction_metric_contract
from strategies.sw_sector_rotation.src.factors.sector_rotation import TRAIN_FEATURES_PRICE
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA, DEFAULT_TOP_N, DEFAULT_TRAIN_MONTHS, FORWARD_WINDOWS,
    FUSION_WEIGHTS, MIN_TRAIN_DATES,
)


@pytest.fixture
def synthetic_cross_section():
    codes = [f"{i:06d}" for i in range(124)]
    scores = {code: float(i) for i, code in enumerate(codes)}
    fused = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return codes, {h: scores for h in FORWARD_WINDOWS.values()}, fused, {
        h: {code: float(i) / 1000 for i, code in enumerate(codes)}
        for h in FORWARD_WINDOWS.values()
    }


def test_frozen_feature_names_and_order():
    assert tuple(TRAIN_FEATURES_PRICE) == baseline.EXPECTED_FEATURES
    assert len(TRAIN_FEATURES_PRICE) == 19
    assert TRAIN_FEATURES_PRICE[-1] == "rsi"  # Existing RSI14 implementation/column.


def test_frozen_model_and_fusion_constants():
    assert DEFAULT_ALPHA == 0.01
    assert dict(FORWARD_WINDOWS) == {"short": 10, "medium": 40, "long": 120}
    assert dict(FUSION_WEIGHTS) == {"short": 0.25, "medium": 0.5, "long": 0.25}
    assert DEFAULT_TOP_N == 5
    assert DEFAULT_TRAIN_MONTHS == 6
    assert MIN_TRAIN_DATES == 30


def test_exact_15_metric_names_and_direction(synthetic_cross_section):
    rows = baseline.evaluate_date(1, "2025-04-02", *synthetic_cross_section)
    assert len(rows) == 15
    assert [row["metric"] for row in rows] == prediction_metric_contract()["metric_names"]
    assert all(row["valid_sector_count"] == 124 for row in rows)
    lookup = {row["metric"]: row["value"] for row in rows}
    for horizon in (10, 40, 120):
        assert lookup[f"IC_{horizon}"] == pytest.approx(1.0)
        assert lookup[f"RankIC_{horizon}"] == pytest.approx(1.0)
        assert lookup[f"Top5_minus_universe_{horizon}"] > 0


@pytest.mark.parametrize("sealed_ordinal", [221, 239, 280, 401, 460])
def test_sealed_phase_metric_request_rejected(sealed_ordinal, synthetic_cross_section):
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        baseline.evaluate_date(sealed_ordinal, "2026-03-03", *synthetic_cross_section)


def test_missing_sector_label_nulls_horizon_without_shrinking(synthetic_cross_section):
    codes, scores, fused, labels = synthetic_cross_section
    labels[40] = dict(labels[40])
    labels[40][codes[0]] = None
    rows = baseline.evaluate_date(1, "2025-04-02", codes, scores, fused, labels)
    medium = [row for row in rows if row["horizon"] == 40]
    assert len(medium) == 5
    assert all(row["value"] is None and row["valid_sector_count"] == 123 for row in medium)
    assert all(row["null_reason"] == "incomplete_fixed_universe_score_or_label" for row in medium)


def test_missing_fused_sector_nulls_all_top5_dependent_metrics(synthetic_cross_section):
    codes, scores, fused, labels = synthetic_cross_section
    rows = baseline.evaluate_date(1, "2025-04-02", codes, scores, fused[:-1], labels)
    assert len(rows) == 15
    assert all(row["value"] is None for row in rows)


def test_zero_cross_sectional_variance_is_null_not_zero(synthetic_cross_section):
    codes, scores, fused, labels = synthetic_cross_section
    scores = dict(scores)
    scores[10] = {code: 1.0 for code in codes}
    rows = baseline.evaluate_date(1, "2025-04-02", codes, scores, fused, labels)
    lookup = {row["metric"]: row for row in rows}
    assert lookup["IC_10"]["value"] is None
    assert lookup["RankIC_10"]["value"] is None
    assert lookup["IC_10"]["null_reason"] == "zero_cross_sectional_variance"
    assert lookup["Top5_forward_return_10"]["value"] is not None


def test_rankic_uses_average_tie_ranks(synthetic_cross_section):
    codes, scores, fused, labels = synthetic_cross_section
    scores = dict(scores)
    scores[10] = dict(scores[10])
    scores[10][codes[0]] = scores[10][codes[1]]
    labels = dict(labels)
    labels[10] = dict(labels[10])
    labels[10][codes[0]] = labels[10][codes[1]]
    rows = baseline.evaluate_date(1, "2025-04-02", codes, scores, fused, labels)
    assert next(row["value"] for row in rows if row["metric"] == "RankIC_10") == pytest.approx(1.0)


def test_aggregate_uses_all_100_dates_and_exact_names():
    names = prediction_metric_contract()["metric_names"]
    rows = [
        {"ordinal": ordinal, "metric": name, "value": float(ordinal)}
        for ordinal in range(1, 101) for name in names
    ]
    aggregate = baseline.aggregate_metrics(pd.DataFrame(rows))
    assert list(aggregate) == names
    assert all(item["valid_dates"] == 100 and item["null_dates"] == 0
               for item in aggregate.values())
    assert aggregate["IC_10"]["mean"] == pytest.approx(50.5)
    assert aggregate["IC_10"]["median"] == pytest.approx(50.5)
    assert aggregate["IC_10"]["std"] == pytest.approx(np.std(np.arange(1, 101), ddof=0))


def test_aggregate_rejects_sealed_or_incomplete_grid():
    names = prediction_metric_contract()["metric_names"]
    rows = [{"ordinal": ordinal, "metric": name, "value": 0.0}
            for ordinal in range(1, 101) for name in names]
    rows[-1]["ordinal"] = 221
    with pytest.raises(ValueError, match="non-Development"):
        baseline.aggregate_metrics(pd.DataFrame(rows))


def test_every_candidate_training_row_must_have_realized_label():
    calendar = pd.bdate_range("2024-01-01", periods=250)
    signal = calendar[200]
    horizon = 40
    good_origins = calendar[150:161]
    assert baseline.assert_training_labels_realized(
        calendar, good_origins, signal, horizon, 124) == 11 * 124
    with pytest.raises(ValueError, match="RESEARCH_LEAKAGE_BLOCKER"):
        baseline.assert_training_labels_realized(
            calendar, calendar[161:162], signal, horizon, 124)


def test_gate_rejects_wrong_image_before_data_access(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline, "_git", lambda repo, *args: (
        baseline.EXPECTED_BRANCH if args[0] == "branch" else
        "commit" if args[0] == "rev-parse" else ""))
    monkeypatch.setattr(baseline, "audit_local_policy", lambda path: (_ for _ in ()).throw(
        AssertionError("data should not be read")))
    with pytest.raises(ValueError, match="ENVIRONMENT_STABILITY_BLOCKER"):
        baseline.pre_run_gate(tmp_path, tmp_path, "wrong")


def test_gate_rejects_dirty_worktree(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline, "_git", lambda repo, *args: (
        baseline.EXPECTED_BRANCH if args[0] == "branch" else
        "commit" if args[0] == "rev-parse" else " M data/file"))
    with pytest.raises(ValueError, match="RESEARCH_BASELINE_STATE_MISMATCH"):
        baseline.pre_run_gate(tmp_path, tmp_path, baseline.EXPECTED_IMAGE_ID)


def test_gate_rejects_hash_and_snapshot_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline, "_git", lambda repo, *args: (
        baseline.EXPECTED_BRANCH if args[0] == "branch" else
        "commit" if args[0] == "rev-parse" else ""))
    actual = json.loads(Path("data/processed/shenwan/sector_admission.json").read_text())
    monkeypatch.setattr(baseline, "audit_local_policy", lambda path: {
        "split_policy_hash": "wrong", "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "synthetic_portfolio_config_hash": None, "data_snapshot_id": actual["data_snapshot_id"],
    })
    with pytest.raises(ValueError, match="RESEARCH_PROTOCOL_HASH_MISMATCH"):
        baseline.pre_run_gate(tmp_path, tmp_path, baseline.EXPECTED_IMAGE_ID)
    monkeypatch.setattr(baseline, "audit_local_policy", lambda path: {
        "split_policy_hash": baseline.EXPECTED_SPLIT_HASH,
        "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "synthetic_portfolio_config_hash": None, "data_snapshot_id": "wrong",
    })
    with pytest.raises(ValueError, match="sector snapshot changed"):
        baseline.pre_run_gate(tmp_path, tmp_path, baseline.EXPECTED_IMAGE_ID)


def test_writer_rejects_validation_rows_before_creating_directory(tmp_path):
    output = baseline.DevelopmentOutput(
        predictions=pd.DataFrame([{"ordinal": 221}]),
        per_date_metrics=pd.DataFrame([{"ordinal": 1, "metric": "IC_10"}]),
        aggregate_metrics={}, training_diagnostics=pd.DataFrame([{"ordinal": 1}]),
        data_quality_diagnostics={}, metadata={
            "phase": "DEVELOPMENT", "executable": False,
            "synthetic_portfolio_enabled": False,
        },
    )
    with pytest.raises(PermissionError, match="SEALED_PHASE_ACCESS_ERROR"):
        baseline.write_artifacts(output, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_no_network_or_etf_path_in_gate(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(baseline, "_git", lambda repo, *args: (
        baseline.EXPECTED_BRANCH if args[0] == "branch" else
        "commit" if args[0] == "rev-parse" else ""))
    gate = baseline.pre_run_gate(
        Path("data/processed/shenwan"), Path.cwd(), baseline.EXPECTED_IMAGE_ID)
    assert gate["gate"] == "PASS"
    assert gate["sector_count"] == 124
    assert gate["validation_access"] == gate["final_oos_access"] == "SEALED"
    source = Path(baseline.__file__).read_text(encoding="utf-8")
    assert "build_etf_candidates(" not in source
    assert "sector_scores_to_weights(" not in source

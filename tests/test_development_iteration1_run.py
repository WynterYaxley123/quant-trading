"""Synthetic-only gates for the authorized Development Iteration-1 runner."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from research import development_iteration1_protocol as protocol
from research import development_iteration1_run as runner
from research.sector_development_baseline import evaluate_date
from research.sector_universe_feasibility import prediction_metric_contract
from strategies.sw_sector_rotation.src.model.model import RankingResult
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore


def test_four_candidate_transformations_are_exactly_frozen_and_train_only():
    origin = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-01", "2025-01-02"])
    train = np.array([[1., 7.], [3., 7.], [5., 7.], [7., 7.]])
    predict = np.array([[9., 700.]])
    raw = np.array([1., 10., 3., 20.])
    for cid in protocol.FROZEN_CANDIDATE_IDS:
        x, xp, y, diagnostic = runner.transform_candidate(cid, train, predict, raw, origin, 40)
        if cid in {"D0", "D2"}:
            np.testing.assert_array_equal(x, train)
            np.testing.assert_array_equal(xp, predict)
            assert diagnostic["scaler"] is None
        else:
            np.testing.assert_allclose(x[:, 0], [-1.3416407864998738, -0.4472135954999579,
                                                  0.4472135954999579, 1.3416407864998738])
            np.testing.assert_allclose(xp, [[2.23606797749979, 0.]])
            np.testing.assert_array_equal(x[:, 1], np.zeros(4))
            assert diagnostic["scaler"]["scaler_training_rows"] == 4
            assert diagnostic["scaler"]["zero_std_features"] == [1]
        if cid in {"D0", "D1"}:
            np.testing.assert_array_equal(y, raw)
            assert diagnostic["demean_residual_max_abs_mean"] is None
        else:
            np.testing.assert_allclose(y, [-1., -5., 1., 5.])
            assert diagnostic["demean_residual_max_abs_mean"] < 1e-12
            assert not np.allclose(y, raw - raw.mean())
    x2, xp2, _, _ = runner.transform_candidate(
        "D1", train, np.array([[900., -700.]]), raw, origin, 40,
    )
    np.testing.assert_allclose(x2, runner.transform_candidate("D1", train, predict, raw, origin, 40)[0])
    assert xp2[0, 0] > 100  # Prediction cannot refit the training scaler.
    with pytest.raises(ValueError, match="CANDIDATE_BUDGET"):
        runner.transform_candidate("D4", train, predict, raw, origin, 40)


def test_one_fused_top5_is_reused_for_all_horizon_labels():
    codes = [f"C{i:03d}" for i in range(124)]
    signal = pd.Timestamp("2025-04-02")
    core = SWSectorRotationCore(SWSectorRotationConfig())
    # Horizon preferences conflict deliberately. Selection must use fused scores.
    raw = {"short": {c: float(i) for i, c in enumerate(codes)},
           "medium": {c: float(np.sin(i / 10)) for i, c in enumerate(codes)},
           "long": {c: float(i) for i, c in enumerate(codes)}}
    results = {p: RankingResult(period=p, forward_days=h, predict_date=signal,
                                train_start=signal, train_end=signal,
                                n_train_dates=30, n_train_samples=3720, scores=raw[p])
               for p, h in [("short", 10), ("medium", 40), ("long", 120)]}
    fused = core.model.fuse_periods(results)
    assert len(fused) == 124
    assert len({code for code, _ in fused[:5]}) == 5
    assert [code for code, _ in fused[:5]] != [code for code, _ in
                                               sorted(raw["short"].items(), key=lambda kv: -kv[1])[:5]]
    labels = {h: {c: float(i * h) for i, c in enumerate(codes)} for h in (10, 40, 120)}
    metrics = evaluate_date(1, str(signal.date()), codes,
                            {h: raw[p] for p, h in [("short", 10), ("medium", 40), ("long", 120)]},
                            fused, labels)
    assert set(row["metric"] for row in metrics) == set(prediction_metric_contract()["metric_names"])
    for h in (10, 40, 120):
        top_return = next(row["value"] for row in metrics
                          if row["metric"] == f"Top5_forward_return_{h}")
        assert top_return == pytest.approx(np.mean([labels[h][c] for c, _ in fused[:5]]))


def test_wide_output_rejects_horizon_specific_top5_and_keeps_full_grid():
    records = []
    for ordinal in range(1, 101):
        for i in range(124):
            code = f"C{i:03d}"
            for h in (10, 40, 120):
                records.append({
                    "ordinal": ordinal, "signal_date": "2025-04-02",
                    "sector_code": code, "horizon": h,
                    "prediction_score": float(i), "fused_score": float(i),
                    "fused_rank": 124 - i, "top5": i >= 119,
                    "realized_forward_return": float(i) / 1000,
                    "label_end": "2025-04-20", "training_observations": 3720,
                    "training_valid_days": 30,
                })
    long = pd.DataFrame(records)
    wide = runner.long_to_wide(long)
    assert len(wide) == 12_400
    assert tuple(wide.columns) == runner.WIDE_COLUMNS
    assert wide.groupby("ordinal")["top5"].sum().eq(5).all()
    assert wide.loc[0, "pred_10"] == wide.loc[0, "pred_120"]
    changed = long.copy()
    changed.loc[changed["horizon"].eq(120) & changed["sector_code"].eq("C123"), "top5"] = False
    with pytest.raises(ValueError, match="Top5 differs by horizon"):
        runner.long_to_wide(changed)


def test_comparison_is_exact_registered_two_weights_and_joint_threshold():
    names = prediction_metric_contract()["metric_names"]
    def metrics(rankic, spread):
        values = {name: {"mean": 0.0} for name in names}
        for h in (10, 40, 120):
            values[f"RankIC_{h}"]["mean"] = rankic[h]
            values[f"Top5_minus_universe_{h}"]["mean"] = spread[h]
        return values
    inputs = {
        "D0": metrics({10: -.1, 40: -.1, 120: -.1}, {10: .1, 40: .1, 120: .1}),
        "D1": metrics({10: .1, 40: .2, 120: -.1}, {10: .04, 40: .02, 120: -.04}),
        "D2": metrics({10: .2, 40: .1, 120: .2}, {10: -.2, 40: -.1, 120: -.2}),
        "D3": metrics({10: .02, 40: .02, 120: .02}, {10: .01, 40: .01, 120: .01}),
    }
    output = runner.comparison(inputs)
    assert output["review_priority"] == ["D1", "D3"]
    assert output["comparison"][0]["candidate"] == "D2"  # Higher primary, failed spread.
    d1 = next(row for row in output["comparison"] if row["candidate"] == "D1")
    assert d1["Weighted_RankIC"] == pytest.approx(.25*.1 + .5*.2 + .25*-.1)
    assert d1["Weighted_Spread"] == pytest.approx(.25*.04 + .5*.02 + .25*-.04)
    assert d1["promotion_status"] == "DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW"
    with pytest.raises(ValueError, match="CANDIDATE_BUDGET"):
        runner.comparison({**inputs, "D4": inputs["D0"]})


def test_d0_artifact_hash_guard_and_preregistered_phase_seal(tmp_path):
    source = tmp_path / "baseline"
    source.mkdir()
    hashes = {}
    for name in runner.ARTIFACT_NAMES:
        content = b"control\n"
        (source / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    hashes["aggregate_metrics.json"] = runner.BASELINE_AGGREGATE_SHA256
    (source / "metadata.json").write_text(json.dumps({
        "artifact_sha256": hashes, "sector_snapshot_id": runner.baseline.EXPECTED_SNAPSHOT,
        "phase": "DEVELOPMENT", "strict_pit": False,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="D0_CONTROL_REPRODUCTION_BLOCKER"):
        runner.verify_d0_control(source)
    for ordinal in (101, 220, 221, 280, 281, 400, 401, 460):
        with pytest.raises(PermissionError):
            protocol.guard_iteration1_scope(
                "D1", "development", [ordinal],
                supplied_hash=protocol.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH,
            )
    with pytest.raises(PermissionError):
        protocol.guard_iteration1_scope(
            "D1", "final_oos", [401],
            supplied_hash=protocol.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH,
        )
    assert protocol.development_iteration1_protocol_hash() == (
        protocol.FROZEN_DEVELOPMENT_ITERATION1_PROTOCOL_HASH
    )

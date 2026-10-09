"""Synthetic scientific contracts; no historical numeric data or formal runners."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.swl1_failure_forensics.boundary import npy_prefix, sha
from research.swl1_failure_forensics.report import public_safe
from research.swl1_ridge_v1.evaluation import rank_ic
from research.swl1_ridge_v1.protocol import exact_targets
from research.swl1_ridge_v2.evaluation import calendar_blocks, extremes
from research.swl1_short_horizon_exploration import boundary
from research.swl1_short_horizon_exploration.design import DESIGN, DESIGN_SHA, load_design
from research.swl1_short_horizon_exploration.diagnostics import (
    autocorrelation,
    block_interval,
    evaluate,
    market_states,
    paired,
    rank_rows,
)
from research.swl1_short_horizon_exploration.signals import (
    equal_reversal,
    fit_ridge,
    relative_features,
    reversal_features,
)
from research.swl1_short_horizon_exploration.study import decision
from research.swl1_short_horizon_exploration.verify import REPORTS, verify_reports

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    generator = np.random.default_rng(3)
    returns = generator.normal(0, 0.01, (170, 30))
    dates = pd.bdate_range("2023-01-02", periods=170).strftime("%Y-%m-%d").tolist()
    codes = [f"{i:06d}" for i in range(30)]
    return returns, dates, codes


@pytest.mark.parametrize("h", [5, 10])
def test_exact_sessions_centering_and_missingness(h):
    returns, _, _ = fixture()
    targets = exact_targets(returns, h)
    np.testing.assert_allclose(targets[15], np.prod(1 + returns[16 : 16 + h], axis=0) - 1)
    assert np.isnan(targets[-h:]).all()
    centered = targets[15] - targets[15].mean()
    assert abs(centered.sum()) < 1e-14
    returns[18, 2] = np.nan
    assert np.isnan(exact_targets(returns, h)[15]).all()


def test_existing_reversal_definition_lag_and_alignment():
    returns, _, _ = fixture()
    features = reversal_features(returns)
    np.testing.assert_allclose(features[12, :, 0], -returns[8:13].mean(axis=0))
    np.testing.assert_allclose(features[12, :, 1], -returns[3:13].mean(axis=0))
    returns[13:] = 1000
    np.testing.assert_allclose(features[:13], reversal_features(returns)[:13])
    assert np.isnan(features[:4, :, 0]).all()


def test_relative_rank_equivalence_and_equal_weight_scale():
    returns, _, _ = fixture()
    raw = reversal_features(returns)
    relative = relative_features(raw)
    assert np.max(np.abs(relative[10:].mean(axis=1))) < 1e-16
    assert np.all(rank_rows(raw[10:, :, 0], relative[10:, :, 0]) == pytest.approx(1))
    manual = ((raw[10] - raw[10].mean(axis=0)) / raw[10].std(axis=0)).mean(axis=1)
    np.testing.assert_allclose(equal_reversal(raw)[10], manual)


def test_frozen_recursive_price_seed_warmup():
    returns, _, _ = fixture()
    returns[0] = np.nan
    features = reversal_features(returns)
    assert np.flatnonzero(np.isfinite(features[:, :, 0]).all(axis=1))[0] == 6
    assert np.flatnonzero(np.isfinite(features[:, :, 1]).all(axis=1))[0] == 11


@pytest.mark.parametrize("h", [5, 10])
def test_mature_labels_train_only_scaling_and_future_poisoning(h):
    returns, dates, _ = fixture()
    features = relative_features(reversal_features(returns))
    targets = exact_targets(returns, h)
    prediction, trace = fit_ridge(features, targets, dates, 100, h)
    valid = trace["training_indices"]
    assert max(valid) + h == 100
    assert trace["all_training_labels_mature"] and trace["training_date_lt_signal"]
    np.testing.assert_allclose(trace["training_mean"], features[valid].reshape(-1, 2).mean(axis=0))
    np.testing.assert_allclose(trace["training_scale"], features[valid].reshape(-1, 2).std(axis=0))
    assert trace["alpha"] == 10 * len(valid) * 30
    returns[101:] = 1e5
    changed_features = relative_features(reversal_features(returns))
    changed_targets = exact_targets(returns, h)
    actual, poisoned = fit_ridge(changed_features, changed_targets, dates, 100, h)
    np.testing.assert_array_equal(prediction, actual)
    assert trace == poisoned
    # Independent normal equations verify the reused augmented solver objective.
    x = (features[valid].reshape(-1, 2) - np.asarray(trace["training_mean"])) / trace[
        "training_scale"
    ]
    y0 = targets[valid]
    y = (y0 - y0.mean(axis=1, keepdims=True)).reshape(-1)
    expected = np.linalg.solve(x.T @ x + trace["alpha"] * np.eye(2), x.T @ (y - y.mean()))
    np.testing.assert_allclose(trace["coefficients"], expected, atol=1e-15)


@pytest.mark.parametrize("h", [5, 10, 40])
def test_no_unregistered_horizon_or_insufficient_training(h):
    returns, dates, _ = fixture()
    with pytest.raises(ValueError):
        fit_ridge(reversal_features(returns), exact_targets(returns, 5), dates, 15, h)


def test_spearman_average_ties_and_constants():
    a = np.array([[1, 2, 2, 4], [0, 0, 0, 0], [4, 3, 2, 1]], dtype=float)
    b = np.array([[4, 2, 2, 1], [1, 2, 3, 4], [1, 2, 3, 4]], dtype=float)
    values = rank_rows(a, b)
    for i in (0, 2):
        assert values[i] == pytest.approx(rank_ic(a[i], b[i]))
    assert np.isnan(values[1]) and rank_ic(a[1], b[1]) is None


def test_zero_baseline_groups_undefined_and_all_leave_one_out():
    returns, dates, codes = fixture()
    indices = list(range(40, 70))
    result, _ = evaluate(np.zeros((30, 30)), returns[indices], indices, dates, codes, dates[-1])
    assert result["rank_ic"]["mean"] is None
    assert result["raw_top5_minus_bottom5_spread"]["mean"] is None
    assert result["undefined_constant_rankings"] == 30
    assert len(result["leave_one_industry_out"]) == 30
    assert result["selection_concentration"]["top5"]["hhi"] is None


def test_top_bottom_ties_code_order_turnover_and_nonadjacent_gap():
    returns, dates, codes = fixture()
    scores = np.tile(np.arange(30, dtype=float), (3, 1))
    indices = [40, 41, 50]
    result, trace = evaluate(scores, returns[indices], indices, dates, codes, dates[-1])
    top, bottom = extremes(scores[0], codes)
    assert top.tolist() == [29, 28, 27, 26, 25] and bottom.tolist() == [0, 1, 2, 3, 4]
    assert trace["spread"][0] == pytest.approx(returns[40, top].mean() - returns[40, bottom].mean())
    assert result["turnover"]["top5"]["count"] == 1
    assert result["turnover"]["top5"]["mean"] == 0
    assert extremes(np.zeros(30), codes)[0].tolist() == list(range(5))
    tied_scores = np.zeros((1, 30))
    tied_scores[0, -1] = 1
    tied, _ = evaluate(tied_scores, returns[40:41], [40], dates, codes, dates[-1])
    assert (
        tied["overlapping_tie_groups"] == 1
        and tied["raw_top5_minus_bottom5_spread"]["mean"] is None
    )


def test_block_assignment_precedes_filtering_and_paired_dates():
    dates = ["2023-08-02", "2024-08-02", "2025-08-02", "2026-09-21"]
    assigned = calendar_blocks(dates, dates[0], dates[-1])
    assert assigned == [0, 1, 2, 3]
    assert calendar_blocks(dates[1:3], dates[0], dates[-1]) == assigned[1:3]
    first = {"indices": [1, 2, 3], "rank_ic": np.array([10, 20, 30]), "spread": np.zeros(3)}
    second = {"indices": [3, 5], "rank_ic": np.array([25, 50]), "spread": np.zeros(2)}
    result = paired(first, second)
    assert result["matched_signal_count"] == 1 and result["delta_rank_ic"]["mean"] == 5


def test_gap_aware_dependence_and_reproducible_block_bootstrap():
    values = np.linspace(-1, 1, 60)
    indices = list(range(30)) + list(range(60, 90))
    assert autocorrelation(values, indices, 1) == pytest.approx(1)
    a = block_interval(values, indices)
    assert a == block_interval(values, indices)
    assert a["contiguous_runs"] == 2 and a["independent_confidence"] is False


def test_regime_definition_uses_only_past_values():
    returns, _, _ = fixture()
    a, dimensions = market_states(returns)
    returns[101:] = 100
    b, changed = market_states(returns)
    assert a[:101] == b[:101]
    np.testing.assert_array_equal(dimensions[:101], changed[:101])


@pytest.mark.parametrize("order", ["C", "F"])
@pytest.mark.parametrize("compressed", [True, False])
def test_reused_reader_decodes_no_future_numeric_tail(tmp_path, order, compressed):
    a = np.array(np.arange(90).reshape(3, 30), dtype=float, order=order)
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    save = np.savez_compressed if compressed else np.savez
    save(first, returns=a)
    a[2] = np.inf
    save(second, returns=a)
    x, receipt = npy_prefix(first, "returns.npy", 2, 2)
    y, poisoned = npy_prefix(second, "returns.npy", 2, 2)
    np.testing.assert_array_equal(x, y)
    assert receipt == poisoned and receipt["rows_decoded"] == 2
    assert receipt["decompressed_read_ahead"] == 0 and receipt["tail_rows_not_decoded"] == 1


def test_owner_authorization_denied_before_numeric_decode(tmp_path, monkeypatch):
    task = tmp_path / "owner.txt"
    task.write_text("not authorized")

    def forbidden(*args, **kwargs):
        pytest.fail("numeric decoder called before owner authorization")

    monkeypatch.setattr(boundary, "npy_prefix", forbidden)
    with pytest.raises(ValueError, match="SOURCE_BYTES_NOT_PINNED"):
        boundary.prepare(ROOT, tmp_path, task, tmp_path / "view")


@pytest.mark.parametrize("rows", [1252, 1253])
def test_physical_view_size_gate_precedes_payload_decode(tmp_path, monkeypatch, rows):
    design = load_design(ROOT)
    codes = json.loads((ROOT / design["universe_file"]).read_text())["industries"]
    dates = pd.bdate_range(end="2026-09-29", periods=1252).strftime("%Y-%m-%d").tolist()
    np.save(tmp_path / "returns.npy", np.zeros((rows, 30)), allow_pickle=False)
    (tmp_path / "metadata.json").write_text(json.dumps({"dates": dates, "codes": codes}))
    (tmp_path / "reference.json").write_text("{}")
    receipt = {
        "design_sha256": DESIGN_SHA,
        "owner_task_sha256": design["owner_task_sha256"],
        "panel_sha256": design["panel_sha256"],
        "return_rows": 1252,
        "last_outcome": "2026-09-29",
        "view_sha256": {
            name: sha(tmp_path / name)
            for name in ("returns.npy", "metadata.json", "reference.json")
        },
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(boundary, "isolated_inputs", lambda paths: {"synthetic": True})
    if rows == 1253:
        monkeypatch.setattr(np, "load", lambda *args, **kwargs: pytest.fail("future row decoded"))
        with pytest.raises(ValueError, match="PHYSICAL_VIEW_BOUNDARY_MISMATCH"):
            boundary.load_view(ROOT, tmp_path)
    else:
        value, _, _, _, _ = boundary.load_view(ROOT, tmp_path)
        assert value.shape == (1252, 30)


def test_internal_lock_and_budget_are_immutable(tmp_path):
    design = load_design(ROOT)
    assert sha(ROOT / DESIGN) == DESIGN_SHA
    assert len(design["specifications"]) == 6
    assert design["horizons"] == [5, 10]
    assert not design["design_lock_is_independent_preregistration"]
    assert not design["budget"]["penalty_search"]
    assert set(inspect.signature(fit_ridge).parameters) == {
        "features",
        "targets",
        "dates",
        "signal",
        "horizon",
    }
    target = tmp_path / DESIGN
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({**design, "horizons": [5, 10, 20]}))
    with pytest.raises(ValueError, match="EXPLORATORY_DESIGN_LOCK_CHANGED"):
        load_design(tmp_path)


@pytest.mark.parametrize(
    "key", ["signal_date", "prediction", "raw_returns", "fit_records", "coefficients", "membership"]
)
def test_private_publication_denied(key):
    with pytest.raises(ValueError):
        public_safe({key: [1, 2]})


def test_default_cli_is_metadata_only_and_no_formal_entrypoints():
    result = subprocess.run(
        [sys.executable, "-m", "research.swl1_short_horizon_exploration"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["status"] == "DESIGN_VERIFIED_NO_NUMERIC_ACCESS"
    directory = ROOT / "research/swl1_short_horizon_exploration"
    source = "\n".join(p.read_text() for p in directory.glob("*.py"))
    for prohibited in (
        "lifecycle import",
        "preregister import",
        "SourceRegistry(",
        "subprocess",
        "requests.",
        "broker",
        "validation_pass(",
    ):
        assert prohibited not in source


@pytest.mark.parametrize("value,expected", [(-0.1, "C"), (0.01, "A")])
def test_decision_is_fixed_direction_not_ridge_optimization(value, expected):
    m = {
        "rank_ic": {"mean": value, "median": value},
        "raw_top5_minus_bottom5_spread": {"mean": value},
        "positive_blocks": 4,
        "leave_one_industry_out": [{"rank_ic": {"mean": value}}] * 30,
    }
    models = {s: {h: m for h in ("5", "10")} for s in ("S1", "S2")}
    assert decision(models) == expected


def test_reviewed_aggregate_reports_and_frozen_hashes_without_numeric_sources():
    result = verify_reports(ROOT)
    assert result["reports"] == 8 and result["charts"] == 6
    assert not result["numeric_source_access"] and not result["independent_validation"]


def test_public_source_payload_and_false_validation_claim_rejected(tmp_path):
    from shutil import copytree

    from research.swl1_short_horizon_exploration.design import REPORT_DIR

    copytree(ROOT / "config", tmp_path / "config")
    copytree(ROOT / REPORT_DIR, tmp_path / REPORT_DIR)
    target = tmp_path / REPORT_DIR / REPORTS[-1]
    value = json.loads(target.read_text())
    value["independent_validation_created"] = True
    target.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="EXPLORATORY_DECISION_OR_LIFECYCLE_MISMATCH"):
        verify_reports(tmp_path)

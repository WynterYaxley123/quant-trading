"""Synthetic authorization and unchanged target-equation checks."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from research.etf_quant_v2.experiment import ExperimentSplit, targets
from research.etf_quant_v2.finalization import (
    STRONG_EVIDENCE,
    classify,
    exclusive_json,
    final_targets,
)


def test_published_result_is_bound_to_the_preaccess_frozen_gate_and_unchanged_model():
    root = Path(__file__).resolve().parents[2]
    freeze = json.loads((root / "config/research/etf-quant-v2-final-oos-freeze.json").read_bytes())
    result = json.loads((root / "reports/engineering/etf-quant-v2-final-oos.json").read_bytes())
    candidate_path = root / "strategies/etf_quant_v2/config/candidate.json"
    candidate = json.loads(candidate_path.read_bytes())
    assert result["open_count"] == freeze["open_count_maximum"] == 1
    assert result["model_retuned"] is freeze["retuning_allowed"] is False
    assert (
        freeze["candidate_file_sha256"] == hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    )
    assert result["candidate_sha256"] == freeze["candidate_sha256"] == candidate["candidate_sha256"]
    assert result["freeze_sha256"] == freeze["freeze_sha256"]
    assert result["gate_sha256"] == freeze["gate_sha256"]
    assert (
        freeze["evaluation_code_sha256"]
        == json.loads(
            (root / "reports/engineering/shadow-task-installation-integrity.json").read_bytes()
        )["implementation_integrity"]["files"]["research/etf_quant_v2/finalization.py"]
    )
    assert datetime.fromisoformat(freeze["frozen_at"]) < datetime.fromisoformat(
        result["completed_at"]
    )
    assert result["decision"] == classify(
        result["metrics"], freeze["gate"], freeze["development_rank_ic"]
    )


@pytest.mark.parametrize("development_ic", [0.0, -0.1, float("nan"), float("inf")])
def test_missing_positive_development_direction_has_null_ratio(development_ic):
    result = classify(
        metrics(), {"minimum_block_observations": 10, "minimum_observations": 40}, development_ic
    )
    assert result["development_to_oos_rank_ic_ratio"] is None
    assert result["secondary"]["development_direction_retention"] is False
    assert result["classification"] != "PASS_STRONG"


def test_target_equation_matches_frozen_research():
    rng = np.random.default_rng(710)
    x = rng.normal(size=(100, 16, 19))
    close = np.exp(rng.normal(0, 0.02, (100, 16)).cumsum(axis=0))
    segments = np.ones((100, 16), dtype=np.int64)
    segments[50:, 0] = 2
    x[30, 3, 0] = np.nan
    split = ExperimentSplit(0, 40, 41, 70, 71, 80, 81)
    for horizon in (10, 40):
        np.testing.assert_allclose(
            final_targets(x, close, segments, horizon, 70),
            targets(x, close, segments, horizon, split, "VALIDATION"),
            equal_nan=True,
        )


def test_single_exclusive_access_record(tmp_path):
    path = tmp_path / "access.json"
    exclusive_json(path, {"open_count": 1})
    with pytest.raises(FileExistsError):
        exclusive_json(path, {"open_count": 2})
    assert json.loads(path.read_bytes()) == {"open_count": 1}


def metrics():
    return {
        "folds": [{"signals": 15, "mean_rank_ic": 0.1, "mean_spread": 0.01} for _ in range(4)],
        "mean_rank_ic": 0.1,
        "mean_spread": 0.01,
        "signals": 60,
        "minimum_component_fit_fraction": 1.0,
        "component_norm_cv": {"10": 0.1, "40": 0.1, "120": 0.1},
        "all_fitted_coefficients_finite": True,
    }


@pytest.mark.parametrize(
    "case,expected",
    [
        ("strong", "PASS_STRONG"),
        ("degradation", "PASS_WEAK"),
        ("negative", "FAIL"),
        ("chronology", "FAIL"),
        ("degenerate", "FAIL"),
    ],
)
def test_predeclared_scientific_classification(case, expected):
    values = metrics()
    if case == "degradation":
        values["mean_rank_ic"] = 0.001
    if case == "negative":
        values["mean_spread"] = -0.001
    if case == "chronology":
        for block in values["folds"][:3]:
            block["mean_rank_ic"] = -0.1
    if case == "degenerate":
        values["minimum_component_fit_fraction"] = 0.5
    result = classify(values, {"minimum_block_observations": 10, "minimum_observations": 40}, 0.14)
    assert result["classification"] == expected
    if expected == "FAIL":
        assert result["product_status"] == "EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW"


@pytest.mark.parametrize(
    "ess,tier_a,expected",
    [
        (None, 0, "PASS_WEAK"),
        (None, 5, "PASS_WEAK"),
        (24.0, 0, "PASS_WEAK"),
        (24.0, 5, "PASS_STRONG"),
    ],
)
def test_new_gates_require_dependence_aware_and_independent_evidence_for_strong(
    ess, tier_a, expected
):
    values = metrics() | {"uncertainty": {"bootstrap_ess": ess}}
    gate = {
        "minimum_block_observations": 10,
        "minimum_observations": 40,
        "strong_evidence": STRONG_EVIDENCE,
        "independent_membership_rows": tier_a,
    }
    result = classify(values, gate, 0.14)
    assert result["classification"] == expected
    assert result["strong_evidence"] == {
        "dependence_aware_uncertainty": ess is not None,
        "independent_membership_evidence": tier_a > 0,
    }


def test_consumed_gate_predates_strong_evidence_rule():
    root = Path(__file__).resolve().parents[2]
    freeze = json.loads((root / "config/research/etf-quant-v2-final-oos-freeze.json").read_bytes())
    assert "strong_evidence" not in freeze["gate"]

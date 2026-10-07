"""Synthetic-only SWL1-Ridge-V2 draft contracts; no factual panel is read."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.swl1_ridge_v1.protocol import body, digest, immutable
from research.swl1_ridge_v2 import execute as execute_module
from research.swl1_ridge_v2.anchor import PROTOCOL, public_anchor
from research.swl1_ridge_v2.evaluation import (
    calendar_blocks,
    development_admitted,
    evaluate,
    extremes,
)
from research.swl1_ridge_v2.lifecycle import Lifecycle
from research.swl1_ridge_v2.preregister import preregister
from research.swl1_ridge_v2.protocol import Spec, fit_predict, split_sessions
from strategies.etf_quant.config import FACTORS_19

ROOT = Path(__file__).resolve().parents[1]


def days(count, start="2020-01-01"):
    return pd.bdate_range(start, periods=count).strftime("%Y-%m-%d").tolist()


def test_penalty_scales_with_training_rows_and_keeps_v1_maturity():
    rng = np.random.default_rng(5)
    features = rng.normal(size=(700, 11, len(FACTORS_19)))
    targets = rng.normal(size=(700, 11))
    dates = days(700)
    light, meta = fit_predict(features, targets, dates, 600, 120, Spec(0.01, 12, "B"))
    heavy, _ = fit_predict(features, targets, dates, 600, 120, Spec(10.0, 12, "B"))
    assert meta["ridge_alpha"] == pytest.approx(0.01 * meta["industry_rows"])
    assert meta["mature_label_cutoff"] == dates[480] and meta["training_end"] <= dates[480]
    # A per-row penalty of 10 shrinks the centered prediction by roughly 11x.
    assert np.std(heavy) < np.std(light) / 5
    changed = targets.copy()
    changed[481:] = 1000
    np.testing.assert_array_equal(
        fit_predict(features, changed, dates, 600, 120, Spec(0.01, 12, "B"))[0], light
    )
    with pytest.raises(ValueError, match="BUDGET"):
        Spec(100.0, 12, "B")


def test_validation_starts_after_every_seen_v1_label():
    dates = days(1100)
    split = split_sessions(dates, list(range(520, 980)), dates[700])
    assert split is not None
    phases = split["indices"]
    assert phases["validation"][0] == 700 + 120
    assert len(phases["validation"]) == 126
    assert phases["development"][-1] + 120 < phases["validation"][0]
    assert split["final_oos"] == "PROSPECTIVE_FORWARD_ONLY"
    assert split_sessions(dates, list(range(520, 980)), dates[760]) is None


def test_calendar_blocks_follow_dates_not_row_counts():
    assert calendar_blocks(
        ["2024-01-01", "2024-01-02", "2024-03-01", "2024-12-31"], "2024-01-01", "2024-12-31"
    ) == [0, 0, 0, 3]


def test_bottom_ties_break_by_code_like_top():
    prediction = np.zeros(8)
    top, bottom = extremes(prediction, [f"{i}" for i in range(8)])
    assert top.tolist() == bottom.tolist() == [0, 1, 2, 3, 4]


def test_dropped_signals_are_recorded_with_reasons():
    rng = np.random.default_rng(11)
    features = rng.normal(size=(800, 10, len(FACTORS_19)))
    returns = rng.normal(0, 0.01, size=(800, 10))
    features[600, 3, 0] = np.nan
    metrics = evaluate(
        features,
        returns,
        days(800),
        [str(i) for i in range(10)],
        list(range(595, 605)),
        Spec(1.0, 12, "B"),
    )
    assert metrics["signal_count"] == 9
    assert metrics["dropped_signals"] == [
        {"date": days(800)[600], "reason": "INSUFFICIENT_COMPLETE_MATURE_TRAINING_DATES"}
    ]


def test_development_admission_requires_block_stability():
    metrics = {
        "sufficient_dates": True,
        "horizons": {str(h): {"mean_rank_ic": 0.1} for h in (10, 40, 120)},
        "positive_blocks": 2,
    }
    assert not development_admitted(metrics)
    assert development_admitted(metrics | {"positive_blocks": 3})


@pytest.fixture
def lifecycle(tmp_path):
    protocol = tmp_path / "protocol.json"
    return Lifecycle(tmp_path / "run", protocol, immutable(protocol, {"split": {}}))


def test_development_requires_anchor_and_final_oos_is_never_historical(lifecycle):
    with pytest.raises(ValueError, match="ANCHOR_REQUIRED"):
        lifecycle.claim("development")
    lifecycle.record_anchor({"protocol_commit": "0" * 40})
    assert lifecycle.claim("development")["phase"] == "development"
    with pytest.raises(ValueError, match="PROSPECTIVE_FINAL_OOS_ONLY"):
        lifecycle.claim("final_oos")


def git(repository, *args):
    subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True)


def commit(repository, message):
    git(repository, "add", "-A")
    git(repository, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "repo"
    (path / PROTOCOL).parent.mkdir(parents=True)
    git(path, "init", "-q")
    return path


def test_anchor_requires_protocol_alone_on_a_remote_tracking_ref(repository):
    (repository / PROTOCOL).write_bytes(body({"draft": 1}))
    commit(repository, "protocol")
    with pytest.raises(ValueError, match="REMOTE_TRACKING_REF_REQUIRED"):
        public_anchor(repository, "HEAD")
    with pytest.raises(ValueError, match="NOT_FETCHED"):
        public_anchor(repository, "refs/remotes/origin/main")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert len(public_anchor(repository, "refs/remotes/origin/main")["protocol_commit"]) == 40
    (repository / PROTOCOL).write_bytes(body({"draft": 2}))
    with pytest.raises(ValueError, match="CHANGED_AFTER_PUBLICATION"):
        public_anchor(repository, "refs/remotes/origin/main")


def test_anchor_rejects_results_published_with_protocol(repository):
    (repository / PROTOCOL).write_bytes(body({"draft": 1}))
    result = repository / "reports/research/swl1_ridge_v2/development.json"
    result.parent.mkdir(parents=True)
    result.write_text("{}")
    commit(repository, "protocol and results")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    with pytest.raises(ValueError, match="RESULTS_PUBLISHED_WITH_PROTOCOL"):
        public_anchor(repository, "refs/remotes/origin/main")


def synthetic_rows(composite, required, start, end, blocks=4):
    return {
        "signal_count": required,
        "sufficient_dates": True,
        "dropped_signals": [],
        "horizons": {
            str(h): {"mean_rank_ic": composite, "spread": composite} for h in (10, 40, 120)
        },
        "composite_rank_ic": composite,
        "median_composite_rank_ic": composite,
        "weighted_positive_fraction": 0.6 if composite > 0 else 0.4,
        "weighted_spread": composite,
        "positive_blocks": blocks if composite > 0 else 0,
    }


def test_preregister_and_execute_end_to_end_without_historical_final_oos(
    repository, tmp_path, monkeypatch
):
    rng = np.random.default_rng(3)
    dates, codes = days(1100), [f"{i:06d}" for i in range(12)]
    research = tmp_path / "research"
    research.mkdir()
    np.savez(
        research / "factual_panel.npz",
        dates=np.array(dates),
        codes=np.array(codes),
        features=rng.normal(size=(1100, 12, len(FACTORS_19))),
        returns=rng.normal(0, 0.01, size=(1100, 12)),
    )
    panel_hash = digest((research / "factual_panel.npz").read_bytes())
    v1 = json.loads((ROOT / "config/research/swl1-ridge-v1-protocol.json").read_bytes())
    v1 |= {"data_panel_sha256": panel_hash, "model_universe": codes}
    v1["split"]["ranges"]["validation"]["end"] = dates[700]
    immutable(repository / "config/research/swl1-ridge-v1-protocol.json", v1)
    for package in ("research/swl1_ridge_v1", "research/swl1_ridge_v2"):
        shutil.copytree(
            ROOT / package, repository / package, ignore=shutil.ignore_patterns("__pycache__")
        )
    registered = preregister(research, repository, "a" * 40)
    assert registered["search_specs"] == 16
    commit(repository, "preregister V2")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")

    def fake(features, returns, dates_, codes_, signals, spec):
        score = 0.05 if spec.months == 12 else -0.01
        return synthetic_rows(score + spec.penalty * 1e-4, len(signals), "", "")

    monkeypatch.setattr(execute_module, "evaluate", fake)
    status = execute_module.execute(research, repository, "refs/remotes/origin/main")
    candidate = json.loads(
        (repository / "config/research/swl1-ridge-v2-candidate.json").read_bytes()
    )
    assert candidate["spec"] == {"penalty": 10.0, "months": 12, "policy": "A"}
    assert status["validation_passed"] is True
    assert status["scientific_status"] == "AWAITING_PROSPECTIVE_FINAL_OOS"
    assert status["final_oos_opened"] is False and status["forward_eligible"] is False
    assert not (research / "lifecycle/final_oos.claim.json").exists()
    with pytest.raises(ValueError, match="REJECT_ALREADY_CONSUMED"):
        execute_module.execute(research, repository, "refs/remotes/origin/main")

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
from research.swl1_ridge_v2 import preregister as preregister_module
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
from research.swl1_ridge_v2.seen import V1_ARTIFACTS, chronology_proof, v1_lineage
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


def test_unseen_target_convention_allows_endpoint_but_rejects_one_session_overlap():
    dates = days(1100)
    v1 = {
        "split": {
            "indices": {"development": list(range(500, 575)), "validation": list(range(575, 701))},
            "ranges": {"validation": {"end": dates[700]}},
        }
    }
    lineage = {"passed": True, "reason_codes": [], "artifact_hashes": {}}
    split = split_sessions(dates, list(range(520, 980)), dates[700])
    assert split is not None
    proof = chronology_proof(v1, dates, split, lineage)
    assert proof["passed"] and proof["outcome_intervals_checked"] == 126 * 3
    assert proof["v1_last_consumed_label_maturity_session"] == dates[820]
    assert proof["v2_validation_first_signal"] == dates[820]
    assert proof["v2_validation_first_outcome_session"] == dates[821]
    split["indices"]["validation"][0] -= 1
    assert not chronology_proof(v1, dates, split, lineage)["passed"]


def test_calendar_boundaries_do_not_move_when_a_signal_is_dropped():
    all_dates = ["2024-01-01", "2024-02-01", "2024-04-01", "2024-08-01", "2024-12-31"]
    original = calendar_blocks(all_dates, all_dates[0], all_dates[-1])
    kept = calendar_blocks(all_dates[1:], all_dates[0], all_dates[-1])
    assert original[1:] == kept


def test_closed_v1_lineage_requires_matching_private_witness_and_no_oos(tmp_path):
    repository = tmp_path / "repository"
    for name in V1_ARTIFACTS:
        target = repository / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    shutil.copytree(
        ROOT / "research/swl1_ridge_v1",
        repository / "research/swl1_ridge_v1",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    evidence = tmp_path / "evidence"
    assert not v1_lineage(repository, evidence)["passed"]
    protocol_hash = digest((repository / V1_ARTIFACTS[0]).read_bytes())
    development_lineage = {"phase": "development", "protocol_hash": protocol_hash}
    immutable(
        evidence / "lifecycle/development.claim.json", {**development_lineage, "consumed": True}
    )
    immutable(evidence / "lifecycle/development.result.json", {"lineage": development_lineage})
    validation = json.loads((repository / V1_ARTIFACTS[4]).read_bytes())
    immutable(
        evidence / "lifecycle/validation.claim.json", {**validation["lineage"], "consumed": True}
    )
    target = evidence / "lifecycle/validation.result.json"
    target.write_bytes((repository / V1_ARTIFACTS[4]).read_bytes())
    assert v1_lineage(repository, evidence)["passed"]
    (evidence / "lifecycle/final_oos.claim.json").write_bytes(b"must not be read")
    proof = v1_lineage(repository, evidence)
    assert "V1_FINAL_OOS_CONSUMPTION_DETECTED" in proof["reason_codes"]


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
        {
            "signal_date": days(800)[600],
            "phase": "synthetic",
            "spec": "B-m12-l1",
            "horizon": "10",
            "reason_code": "INSUFFICIENT_COMPLETE_MATURE_TRAINING_DATES",
        }
    ]
    assert metrics["fit_count"] == 27
    assert len(metrics["fit_records"]) == 27
    assert all(f["ridge_alpha"] == f["industry_rows"] for f in metrics["fit_records"])


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


def test_candidate_freeze_and_single_validation_in_v2(lifecycle):
    with pytest.raises(ValueError, match="COMPLETED_DEVELOPMENT"):
        lifecycle.freeze_candidate({"spec": "synthetic"})
    lifecycle.record_anchor({"protocol_commit": "0" * 40})
    claim = lifecycle.claim("development")
    lifecycle.complete("development", claim, {"leaderboard": []})
    lifecycle.freeze_candidate({"spec": "synthetic"})
    validation = lifecycle.claim("validation")
    lifecycle.complete("validation", validation, {"passed": False})
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        lifecycle.claim("validation")
    with pytest.raises(ValueError, match="REVISION_FORBIDDEN"):
        lifecycle.freeze_candidate({"spec": "changed"})


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


def test_anchor_rejects_protocol_changed_in_later_commit(repository):
    (repository / PROTOCOL).write_bytes(body({"draft": 1}))
    commit(repository, "first protocol")
    (repository / PROTOCOL).write_bytes(body({"draft": 2}))
    commit(repository, "mutated protocol")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    with pytest.raises(ValueError, match="CHANGED_AFTER_PUBLICATION"):
        public_anchor(repository, "refs/remotes/origin/main")


def test_anchor_rejects_result_created_then_removed_before_protocol(repository):
    result = repository / "reports/research/swl1_ridge_v2/development.json"
    result.parent.mkdir(parents=True)
    result.write_text("{}")
    commit(repository, "premature results")
    result.unlink()
    commit(repository, "remove results")
    (repository / PROTOCOL).write_bytes(body({"draft": 1}))
    commit(repository, "protocol too late")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    with pytest.raises(ValueError, match="RESULTS_EXISTED_BEFORE_PROTOCOL"):
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


@pytest.mark.parametrize("outcome", ["pass", "fail", "no_candidate", "unseen"])
def test_preregister_and_execute_end_to_end_without_historical_final_oos(
    repository, tmp_path, monkeypatch, outcome
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
    v1["split"]["indices"]["development"] = list(range(500, 575))
    v1["split"]["indices"]["validation"] = list(range(575, 701))
    immutable(repository / "config/research/swl1-ridge-v1-protocol.json", v1)
    for package in ("research/swl1_ridge_v1", "research/swl1_ridge_v2"):
        shutil.copytree(
            ROOT / package, repository / package, ignore=shutil.ignore_patterns("__pycache__")
        )
    monkeypatch.setattr(
        preregister_module,
        "v1_lineage",
        lambda *args: {
            "passed": outcome != "unseen",
            "reason_codes": ["SYNTHETIC_WITNESS_FAILURE"] if outcome == "unseen" else [],
            "artifact_hashes": {},
        },
    )
    registered = preregister(research, repository, "a" * 40)
    assert registered["search_specs"] == 16
    commit(repository, "preregister V2")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository).decode().strip()
    immutable(
        research / "evidence/public-anchor.json",
        {
            "merged": True,
            "merged_at": "2028-01-01T00:00:00Z",
            "pr_number": 1,
            "protocol_commit": sha,
            "protocol_hash": registered["protocol_hash"],
            "head_sha": sha,
            "merge_sha": sha,
        },
    )

    def fake(features, returns, dates_, codes_, signals, spec, phase="synthetic"):
        score = 0.05 if spec.months == 12 else -0.01
        if outcome == "no_candidate" or (phase == "validation" and outcome == "fail"):
            score = -0.2
        return synthetic_rows(score + spec.penalty * 1e-4, len(signals), "", "")

    monkeypatch.setattr(execute_module, "evaluate", fake)
    status = execute_module.execute(research, repository, "refs/remotes/origin/main")
    assert status["final_oos_opened"] is False and status["forward_eligible"] is False
    assert not (research / "lifecycle/final_oos.claim.json").exists()
    if outcome in ("no_candidate", "unseen"):
        assert (
            status["scientific_status"]
            == {
                "no_candidate": "NO_DEVELOPMENT_CANDIDATE",
                "unseen": "VALIDATION_INTERVAL_NOT_UNSEEN",
            }[outcome]
        )
        assert not status["validation_opened"]
        assert not (repository / "config/research/swl1-ridge-v2-candidate.json").exists()
        assert not (repository / "reports/research/swl1_ridge_v2/validation.json").exists()
        return
    candidate = json.loads(
        (repository / "config/research/swl1-ridge-v2-candidate.json").read_bytes()
    )
    assert candidate["spec"] == {"penalty": 10.0, "months": 12, "policy": "A"}
    assert status["validation_passed"] is (outcome == "pass")
    assert status["scientific_status"] == (
        "AWAITING_PROSPECTIVE_FINAL_OOS" if outcome == "pass" else "FAILED_VALIDATION"
    )
    with pytest.raises(ValueError, match="REJECT_ALREADY_CONSUMED"):
        execute_module.execute(research, repository, "refs/remotes/origin/main")

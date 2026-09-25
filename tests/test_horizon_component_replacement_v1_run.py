"""Synthetic runner/integrity tests; never writes a formal research result."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import horizon_component_replacement_v1_run as runner
from research import horizon_component_replacement_v1_verify as verifier
from research import horizon_component_replacement_v1_protocol as protocol


def _synthetic_components() -> dict[str, pd.DataFrame]:
    factors = {"C0_H10": (10, 0.01, 0.0), "C0_H40": (40, 0.02, 0.0),
               "C0_H120": (120, 0.03, 0.0), "H10_C": (10, 0.04, 0.2),
               "H40_S": (40, 0.05, -0.1)}
    codes = [f"C{i:03d}" for i in range(124)]
    outputs = {}
    for name, (horizon, scale, offset) in factors.items():
        rows = []
        for ordinal in range(1, 101):
            signal = str(date(2025, 1, 1) + timedelta(days=ordinal - 1))
            for i, code in enumerate(codes):
                rows.append({"candidate": name, "horizon": horizon,
                             "ordinal": ordinal, "signal_date": signal,
                             "sector_code": code, "sector_name": code,
                             "prediction_score": offset + scale * i,
                             "cross_sectional_rank": 124 - i,
                             "realized_forward_return": (i - 60) * 0.0001 * horizon,
                             "label_end": "2026-01-01", "exclusion_reason": None,
                             "training_observations": 12400,
                             "training_valid_days": 100,
                             "training_label_cutoff": "2024-12-31"})
        outputs[name] = pd.DataFrame(rows)
    return outputs


@pytest.fixture(scope="module")
def synthetic_f0():
    components = _synthetic_components()
    return components, runner.compose_scheme("F0_CONTROL", components)


def test_source_loader_current_artifact_hashes_and_grid():
    repo = Path(__file__).resolve().parents[1]
    source = repo / protocol.load_sources()["sourceRunPath"]
    if not source.exists():
        pytest.skip("ignored formal source artifacts unavailable outside original workspace")
    components, integrity = runner.load_sources(repo)
    assert integrity["status"] == "PASS"
    assert integrity["firstRerunIdentical"] is True
    assert set(components) == set(protocol.EXACT_FACTOR_LISTS)
    assert all(len(frame) == 12400 for frame in components.values())
    assert all(len(components[name]["sector_code"].unique()) == 124
               for name in components)


def test_synthetic_f0_calls_existing_fusion_and_evaluation(synthetic_f0):
    _, output = synthetic_f0
    assert len(output["predictions"]) == 37200
    assert len(output["wide"]) == 12400
    assert len(output["perDateMetrics"]) == 1500
    assert len(output["aggregateMetrics"]) == 15
    assert output["wide"].groupby("ordinal")["top5"].sum().eq(5).all()
    assert all(len(output["blocks"]) == 16 for _ in (0,))
    assert output["weighted"]["weightedRankIc"] > 0
    assert output["weighted"]["weightedSpread"] > 0
    for block in ("B1", "B2", "B3", "B4"):
        assert output["blockWeighted"][block]["weightedRankIc"] > 0


def test_f0_identity_gate_exact_rank_top5_and_numeric(synthetic_f0):
    _, output = synthetic_f0
    d2 = {"wide": output["wide"].copy(),
          "metrics": output["perDateMetrics"].drop(columns=["candidate"]).copy(),
          "aggregate": output["aggregateMetrics"], "sha256": {}}
    assert runner.verify_f0(output, d2)["status"] == "PASS"
    tampered_rank = {**d2, "wide": d2["wide"].copy()}
    tampered_rank["wide"].loc[0, "fused_rank"] += 1
    with pytest.raises(ValueError, match="FUSION_CONTROL_REPRODUCTION_BLOCKER"):
        runner.verify_f0(output, tampered_rank)
    tampered_score = {**d2, "wide": d2["wide"].copy()}
    tampered_score["wide"].loc[0, "fused_score"] += 1e-4
    with pytest.raises(ValueError, match="FUSION_CONTROL_REPRODUCTION_BLOCKER"):
        runner.verify_f0(output, tampered_score)


def test_fusion_independent_arithmetic_and_top5_samples(synthetic_f0):
    components, output = synthetic_f0
    outputs = {cid: output for cid in protocol.CANDIDATE_IDS}
    result = runner.verify_fusion_samples(outputs, components)
    assert result["status"] == "PASS"
    assert result["schemeDateCases"] == 15
    assert result["sectorComparisons"] == 15 * 124
    assert result["maxAbsDiff"] <= 1e-12


def test_read_only_independent_daily_metric_recompute(synthetic_f0):
    _, output = synthetic_f0
    long = output["predictions"]
    assert verifier._wide_long_identity(long, output["wide"]) == 0
    damaged = output["wide"].copy()
    damaged.loc[0, "top5"] = not bool(damaged.loc[0, "top5"])
    with pytest.raises(ValueError, match="TOP5_IDENTITY_BLOCKER"):
        verifier._wide_long_identity(long, damaged)
    fresh = verifier._daily_recompute(long)
    assert len(fresh) == 1500
    stored = output["perDateMetrics"]
    merged = fresh.merge(stored, on=["ordinal", "metric"], validate="one_to_one")
    assert np.max(np.abs(merged["value_x"] - merged["value_y"])) < 1e-12
    aggregate = verifier._aggregate(fresh)
    assert len(aggregate) == 15
    for name, metrics in aggregate.items():
        assert metrics["mean"] == pytest.approx(output["aggregateMetrics"][name]["mean"], abs=1e-12)


def test_frozen_advancement_summary_never_adds_candidate():
    def item(rankic, spread, by_h, block):
        aggregate = {f"RankIC_{h}": {"mean": by_h[str(h)]} for h in (10, 40, 120)}
        aggregate.update({f"Top5_minus_universe_{h}": {"mean": spread}
                          for h in (10, 40, 120)})
        return {"weighted": {"weightedRankIc": rankic, "weightedSpread": spread},
                "aggregateMetrics": aggregate,
                "blockWeighted": {b: {"weightedRankIc": v, "weightedSpread": spread}
                                  for b, v in block.items()}}
    blocks = {"B1": 0.1, "B2": 0.1, "B3": 0.1, "B4": -0.01}
    by_h = {"10": 0.1, "40": 0.1, "120": 0.1}
    outputs = {
        "F0_CONTROL": item(0.1, 0.02, by_h, blocks),
        "F1_H10_REPLACEMENT": item(0.11, 0.021, by_h, blocks),
        "F2_H10_H40_REPLACEMENT": item(0.115, 0.025, by_h, blocks),
    }
    summary, decisions = runner.summarize(outputs)
    assert [r["candidateId"] for r in summary["comparison"]] == list(protocol.CANDIDATE_IDS)
    assert decisions["decisions"]["F0_CONTROL"]["advancementStatus"] == protocol.STATUS_CONTROL
    assert decisions["decisions"]["F1_H10_REPLACEMENT"]["advancementStatus"] == protocol.STATUS_ADVANCED
    assert decisions["decisions"]["F2_H10_H40_REPLACEMENT"]["advancementStatus"] == protocol.STATUS_ADVANCED
    assert summary["minimalReplacementPreference"] is True
    assert summary["nextResearchGate"] == "H10_REPLACEMENT_ONLY_SUPPORTED"
    independent, gate, near = verifier._independent_decisions(summary)
    assert independent["F1_H10_REPLACEMENT"]["advancementStatus"] == protocol.STATUS_ADVANCED
    assert gate == summary["nextResearchGate"] and near


def test_runner_contains_no_training_or_parameter_search_entrypoint():
    assert not hasattr(runner, "fit_model")
    assert not hasattr(runner, "search_weights")
    assert runner.SCHEME_IDS == protocol.CANDIDATE_IDS
    assert runner.HORIZON_PERIOD == {10: "short", 40: "medium", 120: "long"}


def test_synthetic_artifact_serialization_and_hash_contract(tmp_path, synthetic_f0):
    """Exercise the writer outside reports/research, without a formal run."""
    _, f0 = synthetic_f0
    outputs = {cid: f0 for cid in protocol.CANDIDATE_IDS}
    summary, decisions = runner.summarize(outputs)
    source = {"components": {name: {stem: {"sha256": "a" * 64}
                                   for stem in ("predictions", "metrics")}
                             for name in protocol.EXACT_FACTOR_LISTS}}
    gate = {"branch": runner.EXPECTED_BRANCH, "executionGitCommit": "b" * 40,
            "dockerImageId": "sha256:" + "c" * 64,
            "splitPolicyHash": "d" * 64, "sectorSnapshotId": "synthetic",
            "startDate": "2025-01-01", "endDate": "2025-04-10"}
    run = runner.write_run(tmp_path, gate, outputs, summary, decisions, source,
                           {"status": "PASS"}, {"status": "PASS"})
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["executionImplementationCommit"] == gate["executionGitCommit"]
    assert metadata["sourceHashes"]["H10_C"]["predictions"] == "a" * 64
    assert metadata["validation"] == metadata["finalOos"] == "SEALED"
    actual = {str(path.relative_to(run)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in run.rglob("*") if path.is_file() and path.name != "metadata.json"}
    assert actual == metadata["contentSha256"]
    assert len(actual) == 21

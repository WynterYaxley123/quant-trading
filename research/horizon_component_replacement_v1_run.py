"""Formal Development execution of frozen Horizon Component Replacement V1.

Reuses byte-verified horizon prediction artifacts; never retrains a model,
changes a factor, opens a sealed phase, or searches fusion weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import development_iteration1_protocol as d1
from research import horizon_component_replacement_v1_protocol as protocol
from research import sector_development_baseline as baseline
from research.development_iteration1_run import long_to_wide
from research.factor_set_v2_run import block_stability_rows
from research.sector_development_protocol import audit_local_policy
from strategies.sw_sector_rotation.src.model.model import (
    CrossSectionalRidgeModel, RankingResult,
)

PREREGISTRATION_COMMIT = "95e54ee6461b315b51f5ca7cc17cd985caa96a1d"
PREREG_HANDOFF_COMMIT = "d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd"
EXPECTED_BRANCH = "experiment/sw-sector-index-research-baseline"
FROZEN_PATHS = (
    protocol.CONFIG_RELPATH, protocol.SOURCES_RELPATH,
    protocol.PROTOCOL_RELPATH, protocol.TRACE_RELPATH,
    "research/horizon_component_replacement_v1_protocol.py",
    "docs/research/shenwan_horizon_component_replacement_v1_preregistration_report.md",
)
OUTPUT_COLUMNS = (
    "candidate", "ordinal", "signal_date", "sector_code", "sector_name",
    "horizon", "prediction_score", "cross_sectional_rank", "fused_score",
    "fused_rank", "top5", "realized_forward_return", "label_end",
    "exclusion_reason", "training_observations", "training_valid_days",
    "training_label_cutoff",
)
PER_DATE_COLUMNS = (
    "candidate", "ordinal", "signal_date", "horizon", "metric", "value",
    "null_reason", "valid_sector_count",
)
SCHEME_IDS = protocol.CANDIDATE_IDS
HORIZON_PERIOD = {10: "short", 40: "medium", 120: "long"}
TOLERANCE = 1e-12
SAMPLED_ORDINALS = (1, 25, 50, 75, 100)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_file(repo: Path, relative: str, expected: str, blocker: str) -> Path:
    path = repo / relative
    if not path.is_file():
        raise ValueError(f"{blocker}: missing {relative}")
    if _sha(path) != expected:
        raise ValueError(f"{blocker}: SHA-256 mismatch {relative}")
    return path


def pre_run_gate(repo: Path, processed: Path, image_id: str,
                 *, repeat_of: Path | None = None) -> dict:
    protocol.verify_protocol(repo)
    if image_id != baseline.EXPECTED_IMAGE_ID:
        raise ValueError("ENVIRONMENT_STABILITY_BLOCKER")
    branch = baseline._git(repo, "branch", "--show-current")
    head = baseline._git(repo, "rev-parse", "HEAD")
    status = baseline._git(repo, "status", "--porcelain")
    if branch != EXPECTED_BRANCH or status:
        raise ValueError("RESEARCH_WORKTREE_DIRTY_BLOCKER")
    for ancestor in (PREREGISTRATION_COMMIT, PREREG_HANDOFF_COMMIT,
                     protocol.SOURCE_RESULT_COMMIT):
        baseline._git(repo, "merge-base", "--is-ancestor", ancestor, head)
    changed = baseline._git(repo, "diff", "--name-only", PREREGISTRATION_COMMIT,
                            "HEAD", "--", *FROZEN_PATHS).splitlines()
    if changed:
        raise ValueError("PREREGISTRATION_IMMUTABILITY_BLOCKER: " + ",".join(changed))
    audit = audit_local_policy(processed)
    dev = audit["availability"]["development"]
    if (audit["split_policy_hash"] != baseline.EXPECTED_SPLIT_HASH
            or audit["data_snapshot_id"] != baseline.EXPECTED_SNAPSHOT
            or dev["available_count"] != 100
            or (dev["available_start"], dev["available_end"])
            != baseline.EXPECTED_DEVELOPMENT_DATES
            or audit["validation_status"] != "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
            or audit["oos_performance_status"] != "UNOPENED"):
        raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")
    if repeat_of is not None and not (repeat_of / "metadata.json").is_file():
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_DETERMINISM_BLOCKER: repeat source")
    return {
        "status": "PASS", "branch": branch, "executionGitCommit": head,
        "dockerImageId": image_id, "environmentChanged": False,
        "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
        "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
        "developmentIds": "E001-E100",
        "startDate": dev["available_start"], "endDate": dev["available_end"],
        "validation": "SEALED", "finalOos": "SEALED",
    }


def load_sources(repo: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    """Verify first/rerun bytes, identity, and the complete source grid."""
    manifest = protocol.load_sources(repo)
    source_meta = json.loads((repo / manifest["sourceRunPath"] / "metadata.json")
                             .read_text(encoding="utf-8"))
    if (source_meta["phase"] != "DEVELOPMENT"
            or source_meta["protocolHash"] != protocol.SOURCE_PROTOCOL_HASH
            or source_meta["sectorSnapshotId"] != baseline.EXPECTED_SNAPSHOT
            or source_meta["splitPolicyHash"] != baseline.EXPECTED_SPLIT_HASH
            or source_meta["developmentIds"] != "E001-E100"
            or source_meta["validation"] != "SEALED"
            or source_meta["finalOos"] != "SEALED"):
        raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: source metadata")
    outputs = {}
    checks = {}
    first_root = Path(manifest["sourceRunPath"])
    rerun_root = Path(manifest["sourceRerunPath"])
    for name, entry in manifest["components"].items():
        checks[name] = {}
        for stem in ("predictions", "metrics"):
            relative = entry[f"{stem}Artifact"]
            expected = entry[f"{stem}Sha256"]
            first = _verified_file(repo, relative, expected, "SOURCE_ARTIFACT_HASH_MISMATCH_BLOCKER")
            try:
                suffix = Path(relative).relative_to(first_root)
            except ValueError as exc:
                raise ValueError("COMPONENT_SOURCE_MISSING_BLOCKER: path outside run") from exc
            rerun = _verified_file(repo, str(rerun_root / suffix), expected,
                                   "COMPONENT_SOURCE_DETERMINISM_BLOCKER")
            checks[name][stem] = {"firstPath": relative, "rerunPath": str(rerun_root / suffix),
                                  "sha256": expected, "identical": _sha(first) == _sha(rerun)}
        frame = pd.read_csv(repo / entry["predictionsArtifact"],
                            dtype={"sector_code": str}, float_precision="round_trip")
        required = {"candidate", "horizon", "ordinal", "signal_date", "sector_code",
                    "sector_name", "prediction_score", "realized_forward_return", "label_end",
                    "cross_sectional_rank", "training_observations", "training_valid_days",
                    "training_label_cutoff"}
        if (not required <= set(frame.columns) or len(frame) != 100 * 124
                or frame.duplicated(["ordinal", "signal_date", "sector_code"]).any()
                or set(frame["ordinal"]) != set(range(1, 101))
                or set(frame["candidate"]) != {name}
                or set(frame["horizon"]) != {entry["horizon"]}
                or frame["prediction_score"].isna().any()
                or frame["realized_forward_return"].isna().any()
                or not np.isfinite(frame[["prediction_score", "realized_forward_return"]]
                                   .to_numpy(dtype=float)).all()):
            raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: incomplete source grid")
        frame = frame.sort_values(["ordinal", "sector_code"]).reset_index(drop=True)
        if (not frame.groupby("ordinal").size().eq(124).all()
                or frame.groupby("ordinal")["signal_date"].nunique().ne(1).any()
                or frame.groupby("ordinal")["sector_code"].nunique().ne(124).any()):
            raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: date/universe")
        outputs[name] = frame
    reference = outputs["C0_H10"][["ordinal", "signal_date", "sector_code", "sector_name"]]
    for name, frame in outputs.items():
        if not frame[["ordinal", "signal_date", "sector_code", "sector_name"]].equals(reference):
            raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: cross-component keys")
        h = int(manifest["components"][name]["horizon"])
        c0 = outputs[f"C0_H{h}"]
        if (not frame["label_end"].equals(c0["label_end"])
                or not np.array_equal(frame["realized_forward_return"].to_numpy(dtype=float),
                                      c0["realized_forward_return"].to_numpy(dtype=float))):
            raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: evaluation label identity")
    return outputs, {"status": "PASS", "components": checks,
                     "sourceResultCommit": manifest["sourceResultCommit"],
                     "sourceProtocolHash": manifest["sourceProtocolHash"],
                     "sourceSnapshotId": source_meta["sectorSnapshotId"],
                     "sourceSplitPolicyHash": source_meta["splitPolicyHash"],
                     "rowCountPerComponent": 12400, "firstRerunIdentical": True}


def load_d2(repo: Path) -> dict:
    manifest = protocol.load_sources(repo)["f0ReferenceArtifacts"]
    paths = {}
    for key in ("perDatePredictions", "predictions", "aggregateMetrics", "perDateMetrics"):
        entry = manifest[key]
        paths[key] = _verified_file(repo, entry["path"], entry["sha256"],
                                    "FUSION_CONTROL_REPRODUCTION_BLOCKER")
    return {
        "wide": pd.read_csv(paths["perDatePredictions"],
                            dtype={"sector_code": str}, float_precision="round_trip"),
        "metrics": pd.read_csv(paths["perDateMetrics"], float_precision="round_trip"),
        "aggregate": json.loads(paths["aggregateMetrics"].read_text(encoding="utf-8")),
        "sha256": {key: _sha(path) for key, path in paths.items()},
    }


def _ranking_result(period: str, signal: str, scores: dict[str, float],
                    source_day: pd.DataFrame) -> RankingResult:
    return RankingResult(period=period, forward_days={"short": 10, "medium": 40,
                                                      "long": 120}[period],
                         predict_date=pd.Timestamp(signal),
                         train_start=pd.NaT,
                         train_end=pd.Timestamp(source_day["training_label_cutoff"].iloc[0]),
                         n_train_dates=int(source_day["training_valid_days"].iloc[0]),
                         n_train_samples=int(source_day["training_observations"].iloc[0]),
                         scores=scores)


def compose_scheme(candidate_id: str, components: dict[str, pd.DataFrame]) -> dict:
    """Call the original fusion/evaluation helpers, without retraining."""
    protocol.guard_scope("development", list(range(1, 101)))
    mapping = protocol.COMPONENT_MAPPINGS[candidate_id]
    model = CrossSectionalRidgeModel(fusion_weights={
        "short": protocol.FUSION_WEIGHTS["h10"],
        "medium": protocol.FUSION_WEIGHTS["h40"],
        "long": protocol.FUSION_WEIGHTS["h120"],
    })
    predictions, metrics = [], []
    for ordinal in range(1, 101):
        protocol.guard_scope("development", [ordinal])
        day = {h: components[mapping[f"h{h}"]]
               .loc[lambda df: df["ordinal"].eq(ordinal)] for h in protocol.HORIZONS}
        codes = day[10]["sector_code"].tolist()
        signal = str(day[10]["signal_date"].iloc[0])
        scores = {h: dict(zip(day[h]["sector_code"],
                              day[h]["prediction_score"].astype(float)))
                  for h in protocol.HORIZONS}
        labels = {h: dict(zip(day[h]["sector_code"],
                              day[h]["realized_forward_return"].astype(float)))
                  for h in protocol.HORIZONS}
        results = {_period: _ranking_result(_period, signal, scores[h], day[h])
                   for h, _period in HORIZON_PERIOD.items()}
        fused = model.fuse_periods(results)
        if len(fused) != 124:
            raise ValueError("COMPONENT_ALIGNMENT_BLOCKER: fusion did not retain U0")
        fused_rank = {code: i for i, (code, _) in enumerate(fused, 1)}
        fused_score = dict(fused)
        top = {code for code, _ in fused[:5]}
        for h in protocol.HORIZONS:
            for row in day[h].itertuples(index=False):
                predictions.append({
                    "candidate": candidate_id, "ordinal": ordinal,
                    "signal_date": signal, "sector_code": row.sector_code,
                    "sector_name": row.sector_name, "horizon": h,
                    "prediction_score": float(row.prediction_score),
                    "cross_sectional_rank": int(row.cross_sectional_rank),
                    "fused_score": fused_score[row.sector_code],
                    "fused_rank": fused_rank[row.sector_code],
                    "top5": row.sector_code in top,
                    "realized_forward_return": float(row.realized_forward_return),
                    "label_end": row.label_end,
                    "exclusion_reason": None,
                    "training_observations": int(row.training_observations),
                    "training_valid_days": int(row.training_valid_days),
                    "training_label_cutoff": row.training_label_cutoff,
                })
        for item in baseline.evaluate_date(ordinal, signal, codes, scores, fused, labels):
            metrics.append({"candidate": candidate_id, **item})
    long = pd.DataFrame(predictions, columns=OUTPUT_COLUMNS)
    per_date = pd.DataFrame(metrics, columns=PER_DATE_COLUMNS)
    if (len(long) != 100 * 124 * 3 or len(per_date) != 1500
            or long.duplicated(["ordinal", "horizon", "sector_code"]).any()
            or per_date.duplicated(["ordinal", "metric"]).any()):
        raise ValueError("FORMAL_RUN_IMPLEMENTATION_BLOCKER: output grid")
    aggregate = baseline.aggregate_metrics(per_date)
    means = {name: item["mean"] for name, item in aggregate.items()}
    weighted = {"weightedRankIc": d1.weighted_rankic(means),
                "weightedSpread": d1.weighted_spread(means)}
    if any(value is None for value in weighted.values()):
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
    blocks = block_stability_rows(candidate_id, per_date)
    for row in blocks:
        row["block"] = f"B{row['block']}"  # V2 helper uses integer 1..4; V1 config names B1..B4.
    by_block = {}
    for block, _, _ in protocol.BLOCKS:
        rows = [row for row in blocks if row["block"] == block]
        if len(rows) != 3 or any(row["valid_dates"] != 25 for row in rows):
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: block")
        rankic_means = {f"RankIC_{r['horizon']}": r["rankic_mean"] for r in rows}
        spread_means = {f"Top5_minus_universe_{r['horizon']}": r["spread_mean"]
                        for r in rows}
        by_block[block] = {"weightedRankIc": d1.weighted_rankic(rankic_means),
                           "weightedSpread": d1.weighted_spread(spread_means)}
        blocks.append({"candidate": candidate_id, "horizon": "WEIGHTED", "block": block,
                       "block_ordinal_start": next(f for b, f, _ in protocol.BLOCKS if b == block),
                       "block_ordinal_end": next(e for b, _, e in protocol.BLOCKS if b == block),
                       "valid_dates": 25, "rankic_mean": by_block[block]["weightedRankIc"],
                       "rankic_median": None, "spread_mean": by_block[block]["weightedSpread"]})
    return {"predictions": long, "wide": long_to_wide(long),
            "perDateMetrics": per_date, "aggregateMetrics": aggregate,
            "weighted": weighted, "blocks": blocks, "blockWeighted": by_block}


def verify_f0(output: dict, d2: dict) -> dict:
    """Independent artifact-level F0 control identity before F1/F2."""
    wide = output["wide"].sort_values(["ordinal", "sector_code"]).reset_index(drop=True)
    reference = d2["wide"].sort_values(["ordinal", "sector_code"]).reset_index(drop=True)
    if (len(wide) != len(reference) or len(wide) != 12400
            or not wide[["ordinal", "signal_date", "sector_code"]].equals(
                reference[["ordinal", "signal_date", "sector_code"]])
            or not np.array_equal(wide["fused_rank"], reference["fused_rank"])
            or not np.array_equal(wide["top5"], reference["top5"])):
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: date/rank/Top5")
    score_diff = float(np.max(np.abs(wide["fused_score"].to_numpy(dtype=float)
                                     - reference["fused_score"].to_numpy(dtype=float))))
    ref_metrics = d2["metrics"].sort_values(["ordinal", "metric"]).reset_index(drop=True)
    my_metrics = output["perDateMetrics"].sort_values(["ordinal", "metric"]).reset_index(drop=True)
    if (not my_metrics[["ordinal", "signal_date", "metric"]].equals(
            ref_metrics[["ordinal", "signal_date", "metric"]])
            or not np.array_equal(my_metrics["valid_sector_count"],
                                  ref_metrics["valid_sector_count"])):
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: metric grid")
    metric_diff = float(np.max(np.abs(my_metrics["value"].to_numpy(dtype=float)
                                      - ref_metrics["value"].to_numpy(dtype=float))))
    aggregate_diff = max(abs(output["aggregateMetrics"][name]["mean"] - value["mean"])
                         for name, value in d2["aggregate"].items())
    wr_ref = d1.weighted_rankic({k: v["mean"] for k, v in d2["aggregate"].items()})
    ws_ref = d1.weighted_spread({k: v["mean"] for k, v in d2["aggregate"].items()})
    primary_diff = max(abs(output["weighted"]["weightedRankIc"] - wr_ref),
                       abs(output["weighted"]["weightedSpread"] - ws_ref))
    worst = max(score_diff, metric_diff, aggregate_diff, primary_diff)
    if worst > TOLERANCE:
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: numeric identity")
    return {"status": "PASS", "dates": 100, "sectors": 124, "scoreMaxAbsDiff": score_diff,
            "rankMismatches": 0, "top5Mismatches": 0,
            "dailyMetricMaxAbsDiff": metric_diff,
            "aggregateMeanMaxAbsDiff": aggregate_diff,
            "primaryMaxAbsDiff": primary_diff, "toleranceAbs": TOLERANCE,
            "referenceSha256": d2["sha256"]}


def summarize(outputs: dict[str, dict]) -> tuple[dict, dict]:
    f0, f1, f2 = (outputs[cid] for cid in SCHEME_IDS)
    decisions = {}
    for cid, output in outputs.items():
        weighted = output["weighted"]
        by_h = {str(h): output["aggregateMetrics"][f"RankIC_{h}"]["mean"]
                for h in protocol.HORIZONS}
        blocks = {b: item["weightedRankIc"] for b, item in output["blockWeighted"].items()}
        decisions[cid] = protocol.advancement_decision(
            candidate_id=cid, weighted_rankic=weighted["weightedRankIc"],
            weighted_spread=weighted["weightedSpread"],
            f0_rankic=f0["weighted"]["weightedRankIc"],
            f0_spread=f0["weighted"]["weightedSpread"],
            f1_rankic=f1["weighted"]["weightedRankIc"],
            f1_spread=f1["weighted"]["weightedSpread"],
            rankic_by_horizon=by_h, block_weighted_rankic=blocks)
    f1_status = decisions["F1_H10_REPLACEMENT"]["advancementStatus"]
    f2_status = decisions["F2_H10_H40_REPLACEMENT"]["advancementStatus"]
    prefer_f1 = protocol.prefer_minimal_replacement(
        f1_status=f1_status, f2_status=f2_status,
        f1_rankic=f1["weighted"]["weightedRankIc"],
        f2_rankic=f2["weighted"]["weightedRankIc"],
        f1_spread=f1["weighted"]["weightedSpread"],
        f2_spread=f2["weighted"]["weightedSpread"])
    if prefer_f1:
        next_gate = "H10_REPLACEMENT_ONLY_SUPPORTED"
        decisions["F1_H10_REPLACEMENT"]["minimalReplacementPreference"] = "MINIMAL_REPLACEMENT_PREFERENCE"
    elif f1_status == protocol.STATUS_ADVANCED and f2_status == protocol.STATUS_ADVANCED:
        next_gate = "H10_H40_REPLACEMENT_SUPPORTED"
    elif f1_status == protocol.STATUS_ADVANCED:
        next_gate = "H10_REPLACEMENT_ONLY_SUPPORTED"
    elif f2_status == protocol.STATUS_ADVANCED:
        next_gate = "MIXED_COMPONENT_REPLACEMENT_EVIDENCE"
    else:
        next_gate = "COMPONENT_REPLACEMENT_NOT_SUPPORTED"
    if next_gate not in protocol.NEXT_RESEARCH_GATE_VALUES:
        raise ValueError("ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER")
    comparison = []
    for cid in SCHEME_IDS:
        output = outputs[cid]
        row = {"candidateId": cid, "componentMapping": protocol.COMPONENT_MAPPINGS[cid],
               **output["weighted"],
               "rankIcByHorizon": {str(h): output["aggregateMetrics"][f"RankIC_{h}"]["mean"]
                                     for h in protocol.HORIZONS},
               "spreadByHorizon": {str(h): output["aggregateMetrics"][f"Top5_minus_universe_{h}"]["mean"]
                                   for h in protocol.HORIZONS},
               "blocks": output["blockWeighted"],
               "advancementStatus": decisions[cid]["advancementStatus"]}
        comparison.append(row)
    summary = {"researchType": protocol.RESEARCH_TYPE, "phase": "DEVELOPMENT",
               "comparison": comparison, "candidateCount": 3,
               "deltas": {
                   "F1_minus_F0": {key: f1["weighted"][key] - f0["weighted"][key]
                                   for key in ("weightedRankIc", "weightedSpread")},
                   "F2_minus_F0": {key: f2["weighted"][key] - f0["weighted"][key]
                                   for key in ("weightedRankIc", "weightedSpread")},
                   "F2_minus_F1": {key: f2["weighted"][key] - f1["weighted"][key]
                                   for key in ("weightedRankIc", "weightedSpread")},
               }, "nextResearchGate": next_gate,
               "minimalReplacementPreference": prefer_f1,
               "H40_NO_STRONG_STABILITY_EVIDENCE": True,
               "NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT": True,
               "DEVELOPMENT_REUSE_WARNING": True,
               "INDEPENDENT_VALIDATION": False, "OOS": False}
    return summary, {"decisions": decisions, "nextResearchGate": next_gate,
                     "minimalReplacementPreference": prefer_f1}


def verify_fusion_samples(outputs: dict[str, dict], components: dict[str, pd.DataFrame]) -> dict:
    """Independent arithmetic check of all sectors on five frozen dates."""
    worst = 0.0
    checked = 0
    top5_checked = 0
    for cid in SCHEME_IDS:
        mapping = protocol.COMPONENT_MAPPINGS[cid]
        wide = outputs[cid]["wide"]
        for ordinal in SAMPLED_ORDINALS:
            subset = wide[wide["ordinal"] == ordinal].sort_values("sector_code")
            codes = subset["sector_code"].tolist()
            combined = np.zeros(124, dtype=float)
            for h in protocol.HORIZONS:
                comp = components[mapping[f"h{h}"]]
                day = comp[comp["ordinal"] == ordinal].sort_values("sector_code")
                if day["sector_code"].tolist() != codes:
                    raise ValueError("FUSION_IDENTITY_BLOCKER: code alignment")
                values = day["prediction_score"].to_numpy(dtype=float)
                magnitude = max(float(np.max(np.abs(values))), 1.0)
                scaled = values / magnitude
                std = float(np.std(scaled, ddof=0))
                z = ((scaled - np.mean(scaled)) / std if std > 1e-12 / magnitude
                     else np.zeros_like(scaled))
                combined += protocol.FUSION_WEIGHTS[f"h{h}"] * z
            combined /= sum(protocol.FUSION_WEIGHTS.values())
            diff = float(np.max(np.abs(combined - subset["fused_score"].to_numpy(dtype=float))))
            worst = max(worst, diff)
            if diff > TOLERANCE:
                raise ValueError("FUSION_IDENTITY_BLOCKER")
            ranked = sorted(zip(codes, combined), key=lambda pair: (-pair[1], pair[0]))
            expected_top = [code for code, _ in ranked[:5]]
            actual_top = subset.loc[subset["top5"]].sort_values("fused_rank")["sector_code"].tolist()
            if expected_top != actual_top:
                raise ValueError("TOP5_IDENTITY_BLOCKER")
            checked += 124
            top5_checked += 1
    return {"status": "PASS", "sampledOrdinals": list(SAMPLED_ORDINALS),
            "schemeDateCases": top5_checked, "sectorComparisons": checked,
            "maxAbsDiff": worst, "toleranceAbs": TOLERANCE,
            "top5Exact": True}


def write_run(root: Path, gate: dict, outputs: dict[str, dict], summary: dict,
              decisions: dict, source_integrity: dict, f0_reproduction: dict,
              fusion_integrity: dict, *, repeat_of: Path | None = None) -> Path:
    """Write only after in-memory F0 and identity gates have passed."""
    if tuple(outputs) != SCHEME_IDS or f0_reproduction["status"] != "PASS":
        raise ValueError("FORMAL_RUN_IMPLEMENTATION_BLOCKER: output identity")
    run_id = datetime.now(timezone.utc).strftime(
        "horizon_component_replacement_v1_%Y%m%d_%H%M%S_%f_utc")
    payloads = {}
    for cid in SCHEME_IDS:
        output = outputs[cid]
        payloads[f"{cid}/per_date_predictions.csv"] = baseline._csv_bytes(output["wide"])
        payloads[f"{cid}/predictions.csv"] = baseline._csv_bytes(output["predictions"])
        payloads[f"{cid}/per_date_metrics.csv"] = baseline._csv_bytes(output["perDateMetrics"])
        payloads[f"{cid}/aggregate_metrics.json"] = baseline._json_bytes(output["aggregateMetrics"])
    payloads["candidate_summary.json"] = baseline._json_bytes(summary)
    payloads["aggregate_metrics.json"] = baseline._json_bytes({
        cid: outputs[cid]["aggregateMetrics"] for cid in SCHEME_IDS})
    payloads["per_date_metrics.csv"] = baseline._csv_bytes(pd.concat(
        [outputs[cid]["perDateMetrics"] for cid in SCHEME_IDS], ignore_index=True))
    payloads["per_date_predictions.csv"] = baseline._csv_bytes(pd.concat(
        [outputs[cid]["wide"].assign(candidate=cid) for cid in SCHEME_IDS],
        ignore_index=True))
    payloads["block_stability.csv"] = baseline._csv_bytes(pd.DataFrame(
        [row for cid in SCHEME_IDS for row in outputs[cid]["blocks"]]))
    payloads["component_source_integrity.json"] = baseline._json_bytes(source_integrity)
    payloads["fusion_integrity.json"] = baseline._json_bytes(fusion_integrity)
    payloads["advancement_decision.json"] = baseline._json_bytes(decisions)
    payloads["integrity.json"] = baseline._json_bytes({
        "f0Reproduction": f0_reproduction, "sourceIntegrity": "PASS",
        "fusionIdentity": fusion_integrity["status"], "top5Identity": "PASS",
        "inMemoryMetricGrid": "PASS", "validation": "SEALED", "finalOos": "SEALED"})
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
    if repeat_of is not None:
        previous = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if (previous["contentSha256"] != hashes
                or previous["protocolHash"] != protocol.FROZEN_PROTOCOL_HASH):
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_DETERMINISM_BLOCKER")
    metadata = {
        "researchType": protocol.RESEARCH_TYPE, "phase": "DEVELOPMENT",
        "runId": run_id, "branch": gate["branch"], "executionGitCommit": gate["executionGitCommit"],
        "executionImplementationCommit": gate["executionGitCommit"],
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "preregistrationHandoffCommit": PREREG_HANDOFF_COMMIT,
        "protocolHash": protocol.FROZEN_PROTOCOL_HASH,
        "configHash": protocol.FROZEN_CONFIG_HASH,
        "sourceManifestHash": protocol.FROZEN_SOURCES_HASH,
        "sourceResultCommit": protocol.SOURCE_RESULT_COMMIT,
        "sourceHandoffCommit": protocol.SOURCE_HANDOFF_COMMIT,
        "sourceProtocolHash": protocol.SOURCE_PROTOCOL_HASH,
        "sourceHashes": {name: {stem: entry[stem]["sha256"]
                                for stem in ("predictions", "metrics")}
                         for name, entry in source_integrity["components"].items()},
        "dockerImageId": gate["dockerImageId"], "environmentChanged": False,
        "splitPolicyHash": gate["splitPolicyHash"], "sectorSnapshotId": gate["sectorSnapshotId"],
        "developmentIds": "E001-E100", "startDate": gate["startDate"],
        "endDate": gate["endDate"], "universe": "U0_FIXED_124", "sectorCount": 124,
        "candidateIds": list(SCHEME_IDS), "componentMappings": protocol.COMPONENT_MAPPINGS,
        "fusionWeights": protocol.FUSION_WEIGHTS,
        "fusionSemantics": "PER_DATE_CROSS_SECTIONAL_Z_SCORE_THEN_FIXED_WEIGHTED_AVERAGE",
        "top5": "FUSED_RANKING_FIRST_FIVE_SECTOR_CODE_ASCENDING_TIE_BREAK",
        "blocks": [{"id": b, "first": f, "last": e} for b, f, e in protocol.BLOCKS],
        "advancementRules": (
            "LEVEL1_POSITIVE_BOTH; PARETO_VS_F0; F2_PARETO_VS_F1; "
            "HORIZON_RANKIC_RED_FLAG_LT_MINUS_0.02; "
            "TEMPORAL_AT_LEAST_3_POSITIVE_BLOCKS_AND_AT_MOST_1_RED_BLOCK; "
            "MINIMAL_F1_PREFERENCE_IF_BOTH_ADVANCE_AND_BOTH_PRIMARY_DELTAS_LT_0.01"),
        "nextResearchGate": summary["nextResearchGate"],
        "DEVELOPMENT_REUSE_WARNING": True,
        "H40_NO_STRONG_STABILITY_EVIDENCE": True,
        "NEUTRALITY_INDUCED_LOW_FLIP_CAVEAT": True,
        "validation": "SEALED", "finalOos": "SEALED",
        "strictPit": False, "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "researchLabel": "SECTOR_INDEX_RESEARCH_ONLY", "executable": False,
        "tradable": False, "INDEPENDENT_VALIDATION": False, "OOS": False,
        "noWeightSearch": True, "noRetraining": True,
        "contentSha256": hashes,
        "determinismRepeatOf": None if repeat_of is None else previous["runId"],
    }
    target = root / run_id
    root.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    for name, content in payloads.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index"))
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(repo, args.processed_dir, args.docker_image_id,
                        repeat_of=args.repeat_of)
    if args.repeat_of is None:
        protocol.guard_no_formal_results(args.output_root)
    print("HORIZON COMPONENT REPLACEMENT V1 PRE-RUN GATE", flush=True)
    print(json.dumps(gate, indent=2, sort_keys=True), flush=True)
    if not args.execute:
        return 0
    components, source_integrity = load_sources(repo)
    d2 = load_d2(repo)
    outputs = {"F0_CONTROL": compose_scheme("F0_CONTROL", components)}
    f0_reproduction = verify_f0(outputs["F0_CONTROL"], d2)
    print("F0_CONTROL REPRODUCTION PASS", flush=True)
    # Execute both frozen hypotheses unconditionally after the control gate.
    for cid in SCHEME_IDS[1:]:
        outputs[cid] = compose_scheme(cid, components)
    summary, decisions = summarize(outputs)
    fusion_integrity = verify_fusion_samples(outputs, components)
    target = write_run(args.output_root, gate, outputs, summary, decisions,
                       source_integrity, f0_reproduction, fusion_integrity,
                       repeat_of=args.repeat_of)
    print("HORIZON COMPONENT REPLACEMENT V1 RUN COMPLETE:", target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

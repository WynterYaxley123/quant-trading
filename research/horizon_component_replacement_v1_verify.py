"""Read-only independent integrity audit of a formal component-replacement run.

Uses stored CSVs and direct arithmetic, not the generation helpers for
fusion, daily metrics, aggregation, or advancement decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research import horizon_component_replacement_v1_protocol as protocol
from research import sector_development_baseline as baseline

TOLERANCE = 1e-12
SAMPLED_ORDINALS = (1, 25, 50, 75, 100)
METRIC_STEMS = ("IC", "RankIC", "Top5_forward_return",
                "Universe_forward_return", "Top5_minus_universe")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(a: float, b: float, code: str) -> float:
    if not (np.isfinite(a) and np.isfinite(b)):
        raise ValueError(code + ": nonfinite")
    diff = abs(float(a) - float(b))
    if diff > TOLERANCE:
        raise ValueError(code + f": abs diff {diff}")
    return diff


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) != 124 or len(y) != 124 or np.std(x) == 0 or np.std(y) == 0:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: complete case")
    return float(np.corrcoef(x, y)[0, 1])


def _daily_recompute(long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ordinal in range(1, 101):
        each = long[long["ordinal"] == ordinal]
        for horizon in protocol.HORIZONS:
            day = each[each["horizon"] == horizon].sort_values("sector_code")
            if len(day) != 124 or day["sector_code"].nunique() != 124:
                raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: daily grid")
            x = day["prediction_score"].to_numpy(dtype=float)
            y = day["realized_forward_return"].to_numpy(dtype=float)
            top = day.loc[day["top5"]]
            if len(top) != 5:
                raise ValueError("TOP5_IDENTITY_BLOCKER: five flags")
            rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
            ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
            top_mean = float(top["realized_forward_return"].mean())
            universe_mean = float(np.mean(y))
            values = (_corr(x, y), _corr(rx, ry), top_mean, universe_mean,
                      top_mean - universe_mean)
            for stem, value in zip(METRIC_STEMS, values):
                rows.append({"ordinal": ordinal, "metric": f"{stem}_{horizon}",
                             "value": value})
    return pd.DataFrame(rows)


def _aggregate(daily: pd.DataFrame) -> dict:
    result = {}
    for horizon in protocol.HORIZONS:
        for stem in METRIC_STEMS:
            name = f"{stem}_{horizon}"
            values = daily.loc[daily["metric"] == name, "value"].to_numpy(dtype=float)
            if len(values) != 100 or not np.isfinite(values).all():
                raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: aggregate grid")
            result[name] = {"mean": float(np.mean(values)),
                            "median": float(np.median(values)),
                            "std": float(np.std(values, ddof=0)),
                            "min": float(np.min(values)), "max": float(np.max(values)),
                            "valid_dates": 100, "null_dates": 0}
    return result


def _weighted(means: dict, rankic: bool) -> float:
    stem = "RankIC" if rankic else "Top5_minus_universe"
    return float(sum(protocol.FUSION_WEIGHTS[f"h{h}"] * means[f"{stem}_{h}"]
                     for h in protocol.HORIZONS))


def _blocks(daily: pd.DataFrame) -> dict:
    result = {}
    for block, first, last in protocol.BLOCKS:
        subset = daily[daily["ordinal"].between(first, last)]
        means = {name: float(values["value"].mean())
                 for name, values in subset.groupby("metric")}
        result[block] = {"weightedRankIc": _weighted(means, True),
                         "weightedSpread": _weighted(means, False)}
    return result


def _wide_long_identity(long: pd.DataFrame, wide: pd.DataFrame) -> float:
    """Require all three long rows and the wide row to describe one fusion."""
    if (len(wide) != 12400 or wide.duplicated(["ordinal", "sector_code"]).any()
            or not wide.groupby("ordinal")["top5"].sum().eq(5).all()):
        raise ValueError("TOP5_IDENTITY_BLOCKER: wide grid")
    reference = wide.sort_values(["ordinal", "sector_code"]).reset_index(drop=True)
    worst = 0.0
    for horizon in protocol.HORIZONS:
        part = (long[long["horizon"] == horizon]
                .sort_values(["ordinal", "sector_code"]).reset_index(drop=True))
        if (len(part) != 12400
                or not part[["ordinal", "signal_date", "sector_code"]].equals(
                    reference[["ordinal", "signal_date", "sector_code"]])
                or not np.array_equal(part["fused_rank"], reference["fused_rank"])
                or not np.array_equal(part["top5"], reference["top5"])):
            raise ValueError("TOP5_IDENTITY_BLOCKER: long/wide mismatch")
        diff = float(np.max(np.abs(part["fused_score"].to_numpy(dtype=float)
                                   - reference["fused_score"].to_numpy(dtype=float))))
        if not np.isfinite(diff) or diff > TOLERANCE:
            raise ValueError("FUSION_IDENTITY_BLOCKER: long/wide scores")
        worst = max(worst, diff)
    return worst


def _pareto(c: dict, r: dict) -> bool:
    return ((c["weightedRankIc"] > r["weightedRankIc"]
             and c["weightedSpread"] >= r["weightedSpread"])
            or (c["weightedSpread"] > r["weightedSpread"]
                and c["weightedRankIc"] >= r["weightedRankIc"]))


def _independent_decisions(summary: dict) -> tuple[dict, str, bool]:
    by_id = {row["candidateId"]: row for row in summary["comparison"]}
    f0, f1, f2 = (by_id[cid] for cid in protocol.CANDIDATE_IDS)
    decisions = {}
    for cid, row in by_id.items():
        if cid == "F0_CONTROL":
            decisions[cid] = {"advancementStatus": protocol.STATUS_CONTROL,
                              "level1": "NOT_APPLICABLE", "vsF0": "NOT_APPLICABLE",
                              "vsF1": "NOT_APPLICABLE", "temporalStability": "NOT_APPLICABLE",
                              "horizonRedFlag": False, "redFlagHorizons": [],
                              "frozenGateResult": protocol.STATUS_CONTROL}
            continue
        level1 = row["weightedRankIc"] > 0 and row["weightedSpread"] > 0
        vs_f0 = _pareto(row, f0)
        vs_f1 = _pareto(row, f1) if cid == "F2_H10_H40_REPLACEMENT" else None
        red_horizons = [str(h) for h in protocol.HORIZONS
                        if row["rankIcByHorizon"][str(h)] < -0.02]
        block_r = [row["blocks"][b]["weightedRankIc"] for b, _, _ in protocol.BLOCKS]
        temporal = sum(v > 0 for v in block_r) >= 3 and sum(v < -0.02 for v in block_r) <= 1
        if not level1:
            gate_result = "LEVEL1_FAIL"
        elif not vs_f0:
            gate_result = "F1_RELATIVE_GATE_FAIL" if cid == "F1_H10_REPLACEMENT" else "F2_VS_F0_GATE_FAIL"
        elif vs_f1 is False:
            gate_result = "H40_INCREMENTAL_REPLACEMENT_NOT_SUPPORTED"
        elif red_horizons:
            gate_result = "HORIZON_RED_FLAG"
        elif not temporal:
            gate_result = "FUSION_TEMPORAL_STABILITY_GATE_FAIL"
        else:
            gate_result = protocol.STATUS_ADVANCED
        decisions[cid] = {
            "advancementStatus": (protocol.STATUS_ADVANCED if gate_result == protocol.STATUS_ADVANCED
                                  else protocol.STATUS_NOT_ADVANCED),
            "level1": "LEVEL1_PASS" if level1 else "LEVEL1_FAIL",
            "vsF0": "VS_F0_PASS" if vs_f0 else "VS_F0_FAIL",
            "vsF1": "NOT_APPLICABLE" if vs_f1 is None else ("VS_F1_PASS" if vs_f1 else "VS_F1_FAIL"),
            "temporalStability": "TEMPORAL_PASS" if temporal else "TEMPORAL_FAIL",
            "horizonRedFlag": bool(red_horizons), "redFlagHorizons": red_horizons,
            "frozenGateResult": gate_result,
        }
    f1_advanced = decisions["F1_H10_REPLACEMENT"]["advancementStatus"] == protocol.STATUS_ADVANCED
    f2_advanced = decisions["F2_H10_H40_REPLACEMENT"]["advancementStatus"] == protocol.STATUS_ADVANCED
    near = (f1_advanced and f2_advanced
            and abs(f2["weightedRankIc"] - f1["weightedRankIc"]) < 0.01
            and abs(f2["weightedSpread"] - f1["weightedSpread"]) < 0.01)
    if near or (f1_advanced and not f2_advanced):
        next_gate = "H10_REPLACEMENT_ONLY_SUPPORTED"
    elif f1_advanced and f2_advanced:
        next_gate = "H10_H40_REPLACEMENT_SUPPORTED"
    elif f2_advanced:
        next_gate = "MIXED_COMPONENT_REPLACEMENT_EVIDENCE"
    else:
        next_gate = "COMPONENT_REPLACEMENT_NOT_SUPPORTED"
    return decisions, next_gate, near


def _fusion_samples(repo: Path, run: Path, summary: dict) -> tuple[int, float]:
    manifest = protocol.load_sources(repo)
    sources = {}
    for name, item in manifest["components"].items():
        path = repo / item["predictionsArtifact"]
        if _sha(path) != item["predictionsSha256"]:
            raise ValueError("SOURCE_ARTIFACT_HASH_MISMATCH_BLOCKER")
        sources[name] = pd.read_csv(path, dtype={"sector_code": str},
                                    float_precision="round_trip")
    worst, cases = 0.0, 0
    for cid in protocol.CANDIDATE_IDS:
        wide = pd.read_csv(run / cid / "per_date_predictions.csv",
                           dtype={"sector_code": str}, float_precision="round_trip")
        mapping = protocol.COMPONENT_MAPPINGS[cid]
        for ordinal in SAMPLED_ORDINALS:
            day = wide[wide["ordinal"] == ordinal].sort_values("sector_code")
            codes = day["sector_code"].tolist()
            if len(codes) != 124:
                raise ValueError("FUSION_IDENTITY_BLOCKER: sample grid")
            combined = np.zeros(124, dtype=float)
            for h in protocol.HORIZONS:
                source = sources[mapping[f"h{h}"]]
                component = source[source["ordinal"] == ordinal].sort_values("sector_code")
                if component["sector_code"].tolist() != codes:
                    raise ValueError("COMPONENT_ALIGNMENT_BLOCKER")
                vals = component["prediction_score"].to_numpy(dtype=float)
                magnitude = max(float(np.max(np.abs(vals))), 1.0)
                scaled = vals / magnitude
                std = float(np.std(scaled, ddof=0))
                z = ((scaled - float(np.mean(scaled))) / std
                     if std > 1e-12 / magnitude else np.zeros_like(scaled))
                combined += protocol.FUSION_WEIGHTS[f"h{h}"] * z
            combined /= sum(protocol.FUSION_WEIGHTS.values())
            worst = max(worst, float(np.max(np.abs(combined - day["fused_score"].to_numpy(dtype=float)))))
            if worst > TOLERANCE:
                raise ValueError("FUSION_IDENTITY_BLOCKER")
            expected_top = [code for code, _ in
                            sorted(zip(codes, combined), key=lambda pair: (-pair[1], pair[0]))[:5]]
            actual_top = day.loc[day["top5"]].sort_values("fused_rank")["sector_code"].tolist()
            if expected_top != actual_top:
                raise ValueError("TOP5_IDENTITY_BLOCKER")
            cases += 1
    return cases, worst


def verify_result(repo: Path, run: Path) -> dict:
    protocol.verify_protocol(repo)
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    if (metadata["researchType"] != protocol.RESEARCH_TYPE
            or metadata["phase"] != "DEVELOPMENT"
            or metadata["protocolHash"] != protocol.FROZEN_PROTOCOL_HASH
            or metadata["candidateIds"] != list(protocol.CANDIDATE_IDS)
            or metadata["validation"] != "SEALED" or metadata["finalOos"] != "SEALED"
            or metadata["environmentChanged"] is not False):
        raise ValueError("FORMAL_RUN_IMPLEMENTATION_BLOCKER: metadata")
    files = {str(path.relative_to(run)): _sha(path) for path in run.rglob("*")
             if path.is_file() and path.name != "metadata.json"}
    if files != metadata["contentSha256"]:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_DETERMINISM_BLOCKER: content hashes")
    manifest = protocol.load_sources(repo)
    source_integrity = json.loads((run / "component_source_integrity.json")
                                  .read_text(encoding="utf-8"))
    if (source_integrity["status"] != "PASS"
            or source_integrity["firstRerunIdentical"] is not True
            or set(source_integrity["components"]) != set(manifest["components"])):
        raise ValueError("SOURCE_ARTIFACT_HASH_MISMATCH_BLOCKER: source manifest")
    first_root = Path(manifest["sourceRunPath"])
    rerun_root = Path(manifest["sourceRerunPath"])
    for name, entry in manifest["components"].items():
        for stem in ("predictions", "metrics"):
            expected = entry[f"{stem}Sha256"]
            relative = Path(entry[f"{stem}Artifact"])
            rerun = rerun_root / relative.relative_to(first_root)
            if (source_integrity["components"][name][stem]["sha256"] != expected
                    or metadata["sourceHashes"][name][stem] != expected
                    or _sha(repo / relative) != expected
                    or _sha(repo / rerun) != expected):
                raise ValueError("SOURCE_ARTIFACT_HASH_MISMATCH_BLOCKER: " + name)
    summary = json.loads((run / "candidate_summary.json").read_text(encoding="utf-8"))
    stored_decisions = json.loads((run / "advancement_decision.json").read_text(encoding="utf-8"))
    comparison = {row["candidateId"]: row for row in summary["comparison"]}
    if set(comparison) != set(protocol.CANDIDATE_IDS):
        raise ValueError("FORMAL_RUN_IMPLEMENTATION_BLOCKER: candidate budget")
    worst_metric, worst_aggregate, worst_wide_long = 0.0, 0.0, 0.0
    independent = {}
    for cid in protocol.CANDIDATE_IDS:
        long = pd.read_csv(run / cid / "predictions.csv",
                           dtype={"sector_code": str}, float_precision="round_trip")
        stored_daily = pd.read_csv(run / cid / "per_date_metrics.csv",
                                   float_precision="round_trip")
        stored_aggregate = json.loads((run / cid / "aggregate_metrics.json").read_text(encoding="utf-8"))
        if (len(long) != 37200 or len(stored_daily) != 1500
                or long.duplicated(["ordinal", "horizon", "sector_code"]).any()
                or set(long["ordinal"]) != set(range(1, 101))):
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: grid")
        wide = pd.read_csv(run / cid / "per_date_predictions.csv",
                           dtype={"sector_code": str}, float_precision="round_trip")
        worst_wide_long = max(worst_wide_long, _wide_long_identity(long, wide))
        fresh_daily = _daily_recompute(long)
        merged = fresh_daily.merge(stored_daily, on=["ordinal", "metric"],
                                   how="outer", validate="one_to_one", indicator=True)
        if len(merged) != 1500 or not merged["_merge"].eq("both").all():
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: daily keys")
        for row in merged.itertuples(index=False):
            worst_metric = max(worst_metric, _close(row.value_x, row.value_y,
                "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER"))
        fresh_agg = _aggregate(fresh_daily)
        for name, values in fresh_agg.items():
            for field, fresh in values.items():
                stored = stored_aggregate[name][field]
                if field in ("valid_dates", "null_dates"):
                    if fresh != stored:
                        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER: date count")
                else:
                    worst_aggregate = max(worst_aggregate, _close(fresh, stored,
                        "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER"))
        means = {name: item["mean"] for name, item in fresh_agg.items()}
        wr, ws = _weighted(means, True), _weighted(means, False)
        _close(wr, comparison[cid]["weightedRankIc"],
               "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
        _close(ws, comparison[cid]["weightedSpread"],
               "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
        by_h = {str(h): fresh_agg[f"RankIC_{h}"]["mean"] for h in protocol.HORIZONS}
        spreads = {str(h): fresh_agg[f"Top5_minus_universe_{h}"]["mean"]
                   for h in protocol.HORIZONS}
        for h in by_h:
            _close(by_h[h], comparison[cid]["rankIcByHorizon"][h],
                   "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
            _close(spreads[h], comparison[cid]["spreadByHorizon"][h],
                   "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
        fresh_blocks = _blocks(fresh_daily)
        for block, item in fresh_blocks.items():
            for field in item:
                _close(item[field], comparison[cid]["blocks"][block][field],
                       "HORIZON_COMPONENT_REPLACEMENT_METRIC_INTEGRITY_BLOCKER")
        independent[cid] = {"weightedRankIc": wr, "weightedSpread": ws,
                            "rankIcByHorizon": by_h, "spreadByHorizon": spreads,
                            "blocks": fresh_blocks}
    f0 = pd.read_csv(run / "F0_CONTROL" / "per_date_predictions.csv",
                     dtype={"sector_code": str}, float_precision="round_trip")
    d2_entry = protocol.load_sources(repo)["f0ReferenceArtifacts"]["perDatePredictions"]
    d2_path = repo / d2_entry["path"]
    if _sha(d2_path) != d2_entry["sha256"]:
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: reference hash")
    d2 = pd.read_csv(d2_path, dtype={"sector_code": str}, float_precision="round_trip")
    f0, d2 = (frame.sort_values(["ordinal", "sector_code"]).reset_index(drop=True)
              for frame in (f0, d2))
    if (not f0[["ordinal", "signal_date", "sector_code"]].equals(
            d2[["ordinal", "signal_date", "sector_code"]])
            or not np.array_equal(f0["fused_rank"], d2["fused_rank"])
            or not np.array_equal(f0["top5"], d2["top5"])):
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: rank/Top5")
    f0_diff = float(np.max(np.abs(f0["fused_score"].to_numpy(dtype=float)
                                   - d2["fused_score"].to_numpy(dtype=float))))
    if f0_diff > TOLERANCE:
        raise ValueError("FUSION_CONTROL_REPRODUCTION_BLOCKER: fused score")
    cases, fusion_diff = _fusion_samples(repo, run, summary)
    independent_summary = {"comparison": [dict(candidateId=cid, **independent[cid])
                                          for cid in protocol.CANDIDATE_IDS]}
    independent_decisions, next_gate, near = _independent_decisions(independent_summary)
    for cid in protocol.CANDIDATE_IDS:
        actual = stored_decisions["decisions"][cid]
        for key, value in independent_decisions[cid].items():
            if actual[key] != value:
                raise ValueError("ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER: " + cid + "." + key)
    if (stored_decisions["nextResearchGate"] != next_gate
            or summary["nextResearchGate"] != next_gate
            or stored_decisions["minimalReplacementPreference"] != near):
        raise ValueError("ADVANCEMENT_LOGIC_INTEGRITY_BLOCKER: next gate")
    return {"status": "PASS", "runId": metadata["runId"],
            "fileCountNonMetadata": len(files), "f0Reproduction": "PASS",
            "f0FusedScoreMaxAbsDiff": f0_diff,
            "dailyMetricMaxAbsDiff": worst_metric,
            "aggregateMaxAbsDiff": worst_aggregate,
            "fusionIdentity": "PASS", "fusionSampleCases": cases,
            "fusionMaxAbsDiff": fusion_diff, "top5Identity": "PASS",
            "wideLongMaxAbsDiff": worst_wide_long,
            "advancementIntegrity": "PASS", "nextResearchGate": next_gate,
            "metricIntegrity": "PASS", "sourceIntegrity": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    print(json.dumps(verify_result(repo, args.run_dir), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

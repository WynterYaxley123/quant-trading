"""Execute the frozen Factor Set V2 formal Development run.

Runs the D2 reproduction control (C0) and the three admitted V2 candidates
(V2_A, V2_B, V2_D) on Development E001-E100 under the preregistered Factor
Set V2 protocol. Every setting except the candidate factor list is frozen;
V2_C is forbidden. No parameter search, no factor adaptation, no sign flip,
no Validation / Final OOS access. Outputs are POST-AUDIT DEVELOPMENT
RESEARCH: never validated alpha, never OOS evidence, never tradable.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research import development_iteration1_protocol as iteration1_protocol
from research import factor_set_v2_protocol as protocol
from research import sector_development_baseline as baseline
from research.sector_development_protocol import (
    audit_local_policy, guard_evaluation_dates, verify_frozen_prefix,
)
from research.sector_index_baseline import FEATURE_WARMUP
from research.development_iteration1_run import long_to_wide
from strategies.sw_sector_rotation.src.factors.sector_rotation import compute_all_price_features
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA, DEFAULT_TOP_N, FORWARD_WINDOWS, MIN_TRAIN_DATES,
    NumPyRidge, RankingResult,
)
from strategies.sw_sector_rotation.src.common.temporal_integrity import make_forward_label
from strategies.sw_sector_rotation.src.model.ranking import rank_sectors
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationConfig, SWSectorRotationCore

EXPERIMENT = "FACTOR_SET_V2"
PREREGISTRATION_COMMIT = "b836f27e33987ea3d987b8683a38acc442cb2cdd"
EXPECTED_BRANCH = "experiment/sw-sector-index-research-baseline"
ITERATION1_RUN_ID = "iteration1_20260924_163607_787266_utc"
D2_PREDICTIONS_SHA256 = "b2191cdcf907d3217a14b494eac36325f473f285392784e118e17cadd13dbb17"
D2_AGGREGATE_SHA256 = "cc7f9b5712c0f072ea74d1d9634bb990e3f29e2819e6e6cddff27933b17c86b4"
FACTOR_IDENTITY_TOLERANCE = 1e-9
TARGET_IDENTITY_TOLERANCE = 1e-12
C0_REPRODUCTION_TOLERANCE = 1e-12
ALLOWED_UNTRACKED = ("research/factor_set_v2_run.py", "tests/test_factor_set_v2_run.py")
FROZEN_PATHS = (
    "docs/research/shenwan_factor_set_v2_preregistration.md",
    "research/configs/factor_set_v2_candidates.json",
    "research/factor_set_v2_protocol.py",
    "tests/test_factor_set_v2_protocol.py",
)
STATUS_CONTROL = "CONTROL_NOT_A_CANDIDATE"
STATUS_ADVANCED = "V2_ADVANCED_FOR_FURTHER_REVIEW"
STATUS_NOT_ADVANCED = "V2_NOT_ADVANCED"
FORBIDDEN_RESULT_LABELS = ("WINNER", "BEST", "PRODUCTION", "VALIDATED", "TRADABLE")
CANDIDATE_ARTIFACT_NAMES = (
    "predictions.csv", "per_date_metrics.csv", "per_date_predictions.csv",
    "aggregate_metrics.json", "training_diagnostics.csv",
    "data_quality_diagnostics.json", "transformation_diagnostics.json",
)
RUN_ARTIFACT_NAMES = ("candidate_summary.json", "block_stability.csv", "integrity.json")
IDENTITY_SAMPLE_ORDINALS = (1, 50, 100)
IDENTITY_SAMPLE_SECTOR_COUNT = 10


@dataclass(frozen=True)
class SchemeOutput:
    predictions: pd.DataFrame
    per_date_metrics: pd.DataFrame
    aggregate_metrics: dict
    training_diagnostics: pd.DataFrame
    data_quality_diagnostics: dict
    transformation_diagnostics: dict


def scheme_specs() -> list[dict]:
    """Frozen scheme order: C0 control first, then admitted candidates."""
    config = protocol.load_candidate_config()
    control = config["control"]
    specs = [{
        "schemeId": control["candidateId"], "isControl": True,
        "factorList": list(control["factorList"]),
    }]
    for row in config["candidates"]:
        specs.append({"schemeId": row["candidateId"], "isControl": False,
                      "factorList": list(row["factorList"])})
    for spec in specs:
        if spec["schemeId"] in protocol.EXCLUDED_CANDIDATE_IDS:
            raise ValueError("FACTOR_SET_V2_C_FORBIDDEN")
        if spec["schemeId"] not in {protocol.CONTROL_ID, *protocol.CANDIDATE_IDS}:
            raise ValueError("FACTOR_SET_V2_CANDIDATE_BUDGET_VIOLATION")
        protocol.factor_indices(spec["factorList"])
    return specs


def weighted_metrics(means: dict) -> dict:
    return {
        "weightedRankIc": iteration1_protocol.weighted_rankic(means),
        "weightedSpread": iteration1_protocol.weighted_spread(means),
        "rankIcByHorizon": {str(h): means[f"RankIC_{h}"] for h in protocol.FROZEN_SETTINGS["horizons"]},
        "spreadByHorizon": {str(h): means[f"Top5_minus_universe_{h}"]
                            for h in protocol.FROZEN_SETTINGS["horizons"]},
    }


def evaluate_advancement(means: dict, c0_frozen: dict,
                         *, red_flag_threshold: float = -0.02) -> dict:
    """Apply the frozen LEVEL 1 / LEVEL 2 / red-flag rules verbatim."""
    metrics = weighted_metrics(means)
    wic, wsp = metrics["weightedRankIc"], metrics["weightedSpread"]
    if wic is None or wsp is None:
        return {"level1": False, "level2": False, "level2Option": None,
                "horizonRedFlag": True, "redFlagHorizons": ["missing_metrics"],
                "advancementStatus": STATUS_NOT_ADVANCED, **metrics}
    level1 = bool(wic > 0 and wsp > 0)
    option_a = bool(wic > c0_frozen["weightedRankIc"] and wsp >= c0_frozen["weightedSpread"])
    option_b = bool(wsp > c0_frozen["weightedSpread"] and wic >= c0_frozen["weightedRankIc"])
    level2 = option_a or option_b
    red_horizons = [h for h in protocol.FROZEN_SETTINGS["horizons"]
                    if means[f"RankIC_{h}"] is not None and means[f"RankIC_{h}"] < red_flag_threshold]
    red_flag = bool(red_horizons)
    status = STATUS_ADVANCED if (level1 and level2 and not red_flag) else STATUS_NOT_ADVANCED
    return {"level1": level1, "level2": level2,
            "level2Option": "A" if option_a else ("B" if option_b else None),
            "horizonRedFlag": red_flag, "redFlagHorizons": red_horizons,
            "advancementStatus": status, **metrics}


def simplicity_preference(advanced: list[dict]) -> dict:
    """Frozen tie-break discipline: fewer factors inside the 0.01/0.01 band."""
    band_r = protocol.ADVANCEMENT["simplicityRankIcTieBand"]
    band_s = protocol.ADVANCEMENT["simplicitySpreadTieBand"]
    order = {spec["schemeId"]: i for i, spec in enumerate(scheme_specs())}
    ties, winners = [], []
    for a, b in itertools.combinations(advanced, 2):
        d_r = abs(a["weightedRankIc"] - b["weightedRankIc"])
        d_s = abs(a["weightedSpread"] - b["weightedSpread"])
        if d_r < band_r and d_s < band_s:
            ties.append({"pair": [a["candidateId"], b["candidateId"]],
                         "absDeltaWeightedRankIc": d_r, "absDeltaWeightedSpread": d_s})
            if a["factorCount"] != b["factorCount"]:
                winner = a if a["factorCount"] < b["factorCount"] else b
            else:
                winner = a if order[a["candidateId"]] < order[b["candidateId"]] else b
            winners.append(winner["candidateId"])
    preferred = None
    if ties:
        contenders = {cid for tie in ties for cid in tie["pair"]}
        total_wins = {cid: sum(1 for w in winners if w == cid) for cid in contenders}
        tied_appearances = {cid: sum(1 for tie in ties if cid in tie["pair"]) for cid in contenders}
        undefeated = [cid for cid in contenders if total_wins[cid] == tied_appearances[cid]]
        if len(undefeated) == 1:
            preferred = undefeated[0]
    return {
        "SIMPLICITY_PREFERENCE": True,
        "triggered": bool(ties),
        "tieBand": {"weightedRankIc": band_r, "weightedSpread": band_s},
        "tiedPairs": ties,
        "pairWinners": winners,
        "preferred": preferred,
        "rule": "fewer factors inside tie band; equal factor count -> lower candidate ID order",
        "note": "tie-break discipline only, not statistical significance",
    }


def block_stability_rows(scheme_id: str, per_date: pd.DataFrame) -> list[dict]:
    """Frozen B1..B4 slices of daily RankIC and spread; descriptive only."""
    rows = []
    for horizon in protocol.FROZEN_SETTINGS["horizons"]:
        for block, start, end in protocol.STABILITY_BLOCKS:
            mask = (per_date["ordinal"].between(start, end)
                    & per_date["metric"].eq(f"RankIC_{horizon}"))
            rankic = pd.to_numeric(per_date.loc[mask, "value"], errors="coerce").dropna()
            mask_s = (per_date["ordinal"].between(start, end)
                      & per_date["metric"].eq(f"Top5_minus_universe_{horizon}"))
            spread = pd.to_numeric(per_date.loc[mask_s, "value"], errors="coerce").dropna()
            rows.append({
                "candidate": scheme_id, "horizon": horizon, "block": block,
                "block_ordinal_start": start, "block_ordinal_end": end,
                "valid_dates": int(len(rankic)),
                "rankic_mean": float(np.mean(rankic)) if len(rankic) else None,
                "rankic_median": float(np.median(rankic)) if len(rankic) else None,
                "spread_mean": float(np.mean(spread)) if len(spread) else None,
            })
    return rows


def _means_over(per_date: pd.DataFrame, ordinals: set[int]) -> dict:
    means = {}
    for name in sorted(set(per_date["metric"])):
        values = pd.to_numeric(
            per_date.loc[per_date["metric"].eq(name) & per_date["ordinal"].isin(ordinals),
                         "value"], errors="coerce").dropna().to_numpy(dtype=float)
        means[name] = float(np.mean(values)) if len(values) else None
    return means


def extreme_date_sensitivity(per_date: pd.DataFrame,
                             universe_mean_120: dict[int, float]) -> dict:
    """Frozen protocol method: drop 5 lowest + 5 highest U0-mean-120d dates."""
    tail = protocol.EXTREME_DATE_TAIL_COUNT
    ordered = sorted(universe_mean_120, key=lambda o: (universe_mean_120[o], o))
    dropped = sorted(ordered[:tail] + ordered[-tail:])
    remaining = set(universe_mean_120) - set(dropped)
    full = weighted_metrics(_means_over(per_date, set(universe_mean_120)))
    trimmed = weighted_metrics(_means_over(per_date, remaining))
    return {
        "method": "exclude_5_lowest_and_5_highest_development_dates_by_u0_mean_realized_120d_return",
        "excludedOrdinals": dropped, "remainingDates": len(remaining),
        "full": full, "extremeExcluded": trimmed,
        "sensitivityWeightedRankIc": (None if full["weightedRankIc"] is None
                                      or trimmed["weightedRankIc"] is None
                                      else full["weightedRankIc"] - trimmed["weightedRankIc"]),
        "sensitivityWeightedSpread": (None if full["weightedSpread"] is None
                                      or trimmed["weightedSpread"] is None
                                      else full["weightedSpread"] - trimmed["weightedSpread"]),
        "descriptiveOnly": True,
    }


def factor_identity_gate(stashed: dict, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str]) -> dict:
    """Sampled Ridge-input factor values vs independent recomputation."""
    factors = tuple(dict.fromkeys(
        f for spec in scheme_specs() for f in spec["factorList"]))
    protocol.factor_indices(factors)
    max_diff, comparisons = 0.0, 0
    for ordinal in IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
            independent = compute_all_price_features(
                baseline._source_frame(frames[code], frames[code].index[0], signal),
                include_rsrs=False,
            ).loc[signal, list(factors)].to_numpy(dtype=float)
            recorded = np.array([stashed[(ordinal, code)][f] for f in factors], dtype=float)
            if not np.isfinite(independent).all():
                raise ValueError("FACTOR_IDENTITY_BLOCKER: independent recomputation invalid")
            diff = float(np.max(np.abs(independent - recorded)))
            max_diff = max(max_diff, diff)
            comparisons += len(factors)
            if diff > FACTOR_IDENTITY_TOLERANCE:
                raise ValueError("FACTOR_IDENTITY_BLOCKER")
    return {"status": "PASS", "sampledOrdinals": list(IDENTITY_SAMPLE_ORDINALS),
            "sampledFactors": list(factors), "sampledSectorCount": IDENTITY_SAMPLE_SECTOR_COUNT,
            "comparisons": comparisons, "maxAbsDiff": max_diff,
            "toleranceAbs": FACTOR_IDENTITY_TOLERANCE, "onMismatch": "FACTOR_IDENTITY_BLOCKER"}


def target_identity_gate(labels_by_h: dict, frames: dict, calendar: pd.DatetimeIndex,
                         development_dates: pd.DatetimeIndex, codes: list[str],
                         d2_predictions: pd.DataFrame) -> dict:
    """Sampled labels vs direct calendar arithmetic and the frozen D2 artifact."""
    lookup = {(int(row.ordinal), int(row.horizon), str(row.sector_code)): row
              for row in d2_predictions.itertuples(index=False)}
    max_direct, max_artifact, comparisons = 0.0, 0.0, 0
    for ordinal in IDENTITY_SAMPLE_ORDINALS:
        signal = development_dates[ordinal - 1]
        signal_i = int(calendar.get_loc(signal))
        for horizon in protocol.FROZEN_SETTINGS["horizons"]:
            endpoint = calendar[signal_i + horizon]
            for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
                recorded = float(labels_by_h[horizon][code].loc[signal])
                close = frames[code]["close"]
                direct = float(close.loc[endpoint]) / float(close.loc[signal]) - 1.0
                row = lookup[(ordinal, horizon, code)]
                artifact = float(row.realized_forward_return)
                if str(row.label_end) != str(endpoint.date()):
                    raise ValueError("TARGET_IDENTITY_BLOCKER: endpoint semantics drift")
                max_direct = max(max_direct, abs(recorded - direct))
                max_artifact = max(max_artifact, abs(recorded - artifact))
                comparisons += 1
                if (abs(recorded - direct) > TARGET_IDENTITY_TOLERANCE
                        or abs(recorded - artifact) > TARGET_IDENTITY_TOLERANCE):
                    raise ValueError("TARGET_IDENTITY_BLOCKER")
    return {"status": "PASS", "sampledOrdinals": list(IDENTITY_SAMPLE_ORDINALS),
            "sampledHorizons": protocol.FROZEN_SETTINGS["horizons"],
            "sampledSectorCount": IDENTITY_SAMPLE_SECTOR_COUNT,
            "comparisons": comparisons, "maxAbsDiffDirectArithmetic": max_direct,
            "maxAbsDiffD2ControlArtifact": max_artifact,
            "toleranceAbs": TARGET_IDENTITY_TOLERANCE,
            "endpointSemantics": "common_trading_calendar_t_plus_h_confirmed",
            "onMismatch": "TARGET_IDENTITY_BLOCKER"}


def verify_metric_integrity(predictions: dict, summary_rows: list[dict]) -> dict:
    """Independent recompute of IC/RankIC/spread from predictions, then compare."""
    worst = 0.0
    details = []
    for row in summary_rows:
        scheme = row["candidateId"]
        pred = predictions[scheme]
        recomputed = {}
        for horizon in protocol.FROZEN_SETTINGS["horizons"]:
            ics, rankics, spreads = [], [], []
            for ordinal in range(1, 101):
                day = pred[(pred["ordinal"] == ordinal) & (pred["horizon"] == horizon)]
                valid = day[day["prediction_score"].notna() & day["realized_forward_return"].notna()]
                x = valid["prediction_score"].to_numpy(dtype=float)
                y = valid["realized_forward_return"].to_numpy(dtype=float)
                if len(x) >= 2 and np.std(x) > 0 and np.std(y) > 0:
                    ics.append(float(np.corrcoef(x, y)[0, 1]))
                    rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
                    ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
                    rankics.append(float(np.corrcoef(rx, ry)[0, 1]))
                top = valid[valid["top5"] == True]  # noqa: E712
                if len(top):
                    spreads.append(float(top["realized_forward_return"].mean()
                                         - valid["realized_forward_return"].mean()))
            recomputed[f"IC_{horizon}"] = float(np.mean(ics)) if ics else None
            recomputed[f"RankIC_{horizon}"] = float(np.mean(rankics)) if rankics else None
            recomputed[f"Top5_minus_universe_{horizon}"] = float(np.mean(spreads)) if spreads else None
        recomputed_weighted = weighted_metrics(recomputed)
        diffs = {}
        for key in ("weightedRankIc", "weightedSpread"):
            diff = abs(recomputed_weighted[key] - row[key])
            diffs[key] = diff
            worst = max(worst, diff)
        for horizon in protocol.FROZEN_SETTINGS["horizons"]:
            for stem, target in (("RankIC", "rankIcByHorizon"),
                                 ("Top5_minus_universe", "spreadByHorizon")):
                diff = abs(recomputed[f"{stem}_{horizon}"] - row[target][str(horizon)])
                diffs[f"{stem}_{horizon}"] = diff
                worst = max(worst, diff)
        details.append({"candidateId": scheme, "maxAbsDiff": max(diffs.values()),
                        "perMetricAbsDiff": diffs})
    if worst > TARGET_IDENTITY_TOLERANCE:
        raise ValueError("FACTOR_SET_V2_METRIC_INTEGRITY_BLOCKER")
    return {"status": "PASS", "method": "independent_recompute_from_predictions",
            "toleranceAbs": TARGET_IDENTITY_TOLERANCE,
            "maxAbsDiff": worst, "perCandidate": details}


def load_frozen_d2_reference(d2_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Read-only, hash-verified Iteration-1 D2 reference (never recomputed here)."""
    pred_digest = hashlib.sha256((d2_dir / "predictions.csv").read_bytes()).hexdigest()
    agg_digest = hashlib.sha256((d2_dir / "aggregate_metrics.json").read_bytes()).hexdigest()
    if pred_digest != D2_PREDICTIONS_SHA256 or agg_digest != D2_AGGREGATE_SHA256:
        raise ValueError("C0_REPRODUCTION_BLOCKER: frozen D2 artifact hash changed")
    predictions = pd.read_csv(d2_dir / "predictions.csv", dtype={"sector_code": str})
    aggregate = json.loads((d2_dir / "aggregate_metrics.json").read_text(encoding="utf-8"))
    return predictions, aggregate


def pre_run_gate(processed_dir: Path, repo_dir: Path, docker_image_id: str) -> dict:
    """Fail closed: frozen protocol, frozen files, preregistration ancestry."""
    protocol.verify_frozen_factor_set_v2_protocol()
    config = protocol.load_candidate_config()
    if docker_image_id != baseline.EXPECTED_IMAGE_ID:
        raise ValueError("ENVIRONMENT_STABILITY_BLOCKER: Docker image ID changed")
    branch = baseline._git(repo_dir, "branch", "--show-current")
    head = baseline._git(repo_dir, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise ValueError("RESEARCH_BASELINE_STATE_MISMATCH: branch changed")
    status = baseline._git(repo_dir, "status", "--porcelain")
    for line in status.splitlines():
        if not line.startswith("?? ") or line[3:] not in ALLOWED_UNTRACKED:
            raise ValueError("RESEARCH_WORKTREE_DIRTY_BLOCKER: " + line)
    baseline._git(repo_dir, "merge-base", "--is-ancestor", PREREGISTRATION_COMMIT, head)
    changed = baseline._git(
        repo_dir, "diff", "--name-only", PREREGISTRATION_COMMIT, "HEAD",
        "--", *FROZEN_PATHS).splitlines()
    changed += baseline._git(repo_dir, "diff", "--name-only", "HEAD", "--", *FROZEN_PATHS).splitlines()
    if changed:
        raise ValueError("FACTOR_SET_V2_FROZEN_FILE_CHANGED")
    audit = audit_local_policy(processed_dir)
    if (audit["split_policy_hash"] != baseline.EXPECTED_SPLIT_HASH
            or audit["prediction_config_hash"] != baseline.EXPECTED_PREDICTION_HASH
            or audit["data_snapshot_id"] != baseline.EXPECTED_SNAPSHOT
            or audit["synthetic_portfolio_config_hash"] is not None):
        raise ValueError("RESEARCH_PROTOCOL_HASH_MISMATCH")
    dev = audit["availability"]["development"]
    if (audit["split_policy"]["formal_universe_sector_count"] != 124
            or dev["available_count"] != 100
            or (dev["available_start"], dev["available_end"]) != baseline.EXPECTED_DEVELOPMENT_DATES
            or audit["validation_status"] != "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
            or audit["oos_performance_status"] != "UNOPENED"):
        raise ValueError("REPO_PROTOCOL_CONFLICT: frozen Development identity changed")
    return {
        "gate": "PASS", "branch": branch, "git_head": head, "git_status": "clean",
        "docker_image_id": docker_image_id, "environment_changed": False,
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH,
        "split_policy_hash": baseline.EXPECTED_SPLIT_HASH,
        "prediction_config_hash": baseline.EXPECTED_PREDICTION_HASH,
        "sector_snapshot_id": baseline.EXPECTED_SNAPSHOT,
        "universe": "U0_FIXED_124", "sector_count": 124,
        "development_ordinals": [1, 100],
        "development_first_date": dev["available_start"],
        "development_last_date": dev["available_end"],
        "validation_access": "SEALED", "final_oos_access": "SEALED",
        "schemes": [spec["schemeId"] for spec in scheme_specs()],
        "admittedCandidates": list(protocol.CANDIDATE_IDS),
        "forbiddenCandidates": list(protocol.EXCLUDED_CANDIDATE_IDS),
    }


def compute_schemes(processed_dir: Path, gate: dict) -> tuple[dict, dict, dict, dict]:
    """One deterministic pass: shared panel per date, frozen transforms per scheme."""
    if gate.get("gate") != "PASS":
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: pre-run gate not passed")
    protocol.verify_frozen_factor_set_v2_protocol()
    specs = scheme_specs()
    audit = audit_local_policy(processed_dir)
    codes, names, calendar, frames, invalid_in_window, invalid_total = baseline._verified_market(
        processed_dir, audit["development_last_120_label_endpoint"],
    )
    if invalid_in_window or len(codes) != 124:
        raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: invalid fixed universe")
    eligible = calendar[
        (calendar >= pd.Timestamp(audit["availability"]["development"]["available_start"]))
        & (calendar <= pd.Timestamp("2026-03-27"))
    ]
    verify_frozen_prefix(eligible, codes)
    dates = eligible[:100]
    ordinals = guard_evaluation_dates("development", dates, eligible)
    if (ordinals != list(range(1, 101))
            or (str(dates[0].date()), str(dates[-1].date())) != baseline.EXPECTED_DEVELOPMENT_DATES):
        raise ValueError("RESEARCH_PROTOCOL_VIOLATION: Development ordinal drift")
    label_calendar = calendar[calendar <= pd.Timestamp(audit["development_last_120_label_endpoint"])]
    labels_expost = {
        horizon: {code: make_forward_label(frames[code]["close"], horizon, calendar=label_calendar)
                  for code in codes}
        for horizon in FORWARD_WINDOWS.values()
    }
    core = SWSectorRotationCore(SWSectorRotationConfig())
    if core.feature_names != list(baseline.EXPECTED_FEATURES):
        raise ValueError("REPO_PROTOCOL_CONFLICT: feature order")
    state = {spec["schemeId"]: {"predictions": [], "per_date": [], "training": [],
                                "targets": [], "leakage_checks": 0}
             for spec in specs}
    stashed: dict = {}
    universe_mean_120: dict[int, float] = {}
    for ordinal, signal in zip(ordinals, dates):
        protocol.guard_factor_set_v2_scope("development", [ordinal])
        signal_s = str(signal.date())
        signal_i = int(calendar.get_loc(signal))
        boundaries = {p: core.boundaries(calendar[:signal_i + 1], signal, p)
                      for p in FORWARD_WINDOWS}
        if any(b is None for b in boundaries.values()):
            raise ValueError("RESEARCH_LEAKAGE_BLOCKER: temporal boundary")
        first_train_i = int(calendar.searchsorted(
            min(b.train_start for b in boundaries.values())))
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: warmup")
        visible_calendar = calendar[warmup_i:signal_i + 1]
        visible_frames = {code: baseline._source_frame(frames[code], calendar[warmup_i], signal)
                          for code in codes}
        if any(not frame.index.equals(visible_calendar) for frame in visible_frames.values()):
            raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: U0 history incomplete")
        panel = core.build_panel(visible_frames, include_rsrs=False, calendar=visible_calendar)
        if ordinal in IDENTITY_SAMPLE_ORDINALS:
            for code in codes[:IDENTITY_SAMPLE_SECTOR_COUNT]:
                row = panel[code].loc[signal]
                stashed[(ordinal, code)] = {
                    f: float(row[f]) for spec in specs for f in spec["factorList"]}
        universe_mean_120[ordinal] = float(np.mean([
            labels_expost[120][code].loc[signal] for code in codes]))
        per_scheme_results = {spec["schemeId"]: {} for spec in specs}
        for period, h in FORWARD_WINDOWS.items():
            boundary = boundaries[period]
            candidate_dates = visible_calendar[
                (visible_calendar >= boundary.train_start)
                & (visible_calendar <= boundary.label_cutoff)
            ]
            labelled_sets = [set(frame.dropna(subset=[f"fwd{h}"]).index)
                             for frame in panel.values()]
            labelled = sorted(set.intersection(*labelled_sets)) if labelled_sets else []
            train_dates = [d for d in labelled if boundary.train_start <= d <= boundary.label_cutoff]
            if len(train_dates) < MIN_TRAIN_DATES:
                raise ValueError("RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: insufficient training")
            checks = baseline.assert_training_labels_realized(
                calendar, candidate_dates, signal, h, len(codes))
            origins = pd.DatetimeIndex(np.tile(train_dates, len(codes)))
            positions = calendar.get_indexer(origins)
            iteration1_protocol.assert_training_chronology(origins, calendar[positions + h], signal)
            endpoint = calendar[signal_i + h]
            if endpoint > label_calendar[-1]:
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: label endpoint beyond Purge 1")
            for spec in specs:
                scheme = spec["schemeId"]
                factor_names = spec["factorList"]
                arrays = [panel[code].loc[train_dates, factor_names + [f"fwd{h}"]]
                          .to_numpy(dtype=float) for code in codes]
                stacked = np.vstack(arrays)
                x_train, raw_y = stacked[:, :-1], stacked[:, -1]
                x_predict = np.vstack([
                    panel[code].loc[signal, factor_names].to_numpy(dtype=float) for code in codes])
                if (not np.isfinite(stacked).all() or not np.isfinite(x_predict).all()
                        or len(train_dates) != len(candidate_dates)
                        or len(stacked) != len(codes) * len(train_dates)):
                    raise ValueError(
                        "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: silent sector/date exclusion")
                target = iteration1_protocol.cross_sectional_excess_training_target(
                    raw_y, origins, horizon=h)
                residual = max(abs(float(target[origins == d].mean())) for d in origins.unique())
                if residual > 1e-12:
                    raise ValueError("RESEARCH_LEAKAGE_BLOCKER: target demean residual")
                model = NumPyRidge(alpha=DEFAULT_ALPHA).fit(x_train, target)
                scores = {code: float(value) for code, value in
                          zip(codes, model.predict(x_predict))}
                ranking = rank_sectors(scores)
                result = RankingResult(
                    period=period, forward_days=h, predict_date=signal,
                    train_start=boundary.train_start, train_end=boundary.label_cutoff,
                    n_train_dates=len(train_dates), n_train_samples=len(stacked),
                    scores=scores)
                per_scheme_results[scheme][period] = {"result": result, "scores": scores,
                                                      "ranking": ranking}
                item = state[scheme]
                item["leakage_checks"] += checks
                item["targets"].append({"ordinal": ordinal, "horizon": h,
                                        "training_dates": len(train_dates),
                                        "max_abs_mean": residual})
                item["training"].append({
                    "ordinal": ordinal, "signal_date": signal_s, "horizon": h,
                    "status": "success", "reason": None,
                    "train_start": str(boundary.train_start.date()),
                    "label_cutoff": str(boundary.label_cutoff.date()),
                    "first_train_origin": str(train_dates[0].date()),
                    "last_train_origin": str(train_dates[-1].date()),
                    "last_train_label_end": str(calendar[
                        int(calendar.get_loc(train_dates[-1])) + h].date()),
                    "training_candidate_days": len(candidate_dates),
                    "training_valid_days": len(train_dates),
                    "training_observations": len(stacked), "valid_sector_count": len(scores),
                    "missing_factor_exclusions": 0, "missing_label_exclusions": 0,
                    "numerical_failures": 0, "leakage_checks": checks,
                })
        for spec in specs:
            scheme = spec["schemeId"]
            item = state[scheme]
            results = per_scheme_results[scheme]
            fused = core.model.fuse_periods({p: r["result"] for p, r in results.items()})
            if len(fused) != len(codes):
                raise ValueError("RESEARCH_PROTOCOL_VIOLATION: incomplete fused U0")
            top = {code for code, _ in fused[:DEFAULT_TOP_N]}
            fused_lookup = dict(fused)
            fused_rank = {code: i for i, (code, _) in enumerate(fused, 1)}
            horizon_scores, horizon_labels = {}, {}
            for period, h in FORWARD_WINDOWS.items():
                result = results[period]
                horizon_scores[h] = result["scores"]
                rank = {code: i for i, (code, _) in enumerate(result["ranking"], 1)}
                diagnostic = item["training"][-len(FORWARD_WINDOWS) + list(FORWARD_WINDOWS).index(period)]
                realized = {}
                for code in codes:
                    value = labels_expost[h][code].get(signal, np.nan)
                    if pd.isna(value) or not np.isfinite(value):
                        raise ValueError(
                            "RESEARCH_BASELINE_IMPLEMENTATION_BLOCKER: missing realized label")
                    realized[code] = float(value)
                    item["predictions"].append({
                        "ordinal": ordinal, "signal_date": signal_s,
                        "sector_code": code, "sector_name": names[code], "horizon": h,
                        "prediction_score": result["scores"][code],
                        "cross_sectional_rank": rank[code],
                        "fused_score": fused_lookup[code], "fused_rank": fused_rank[code],
                        "top5": code in top, "realized_forward_return": realized[code],
                        "label_end": str(calendar[signal_i + h].date()),
                        "exclusion_reason": None,
                        "training_observations": diagnostic["training_observations"],
                        "training_valid_days": diagnostic["training_valid_days"],
                        "training_label_cutoff": diagnostic["label_cutoff"],
                    })
                horizon_labels[h] = realized
            item["per_date"].extend(baseline.evaluate_date(
                ordinal, signal_s, codes, horizon_scores, fused, horizon_labels))
    outputs = {}
    for spec in specs:
        scheme = spec["schemeId"]
        item = state[scheme]
        predictions = pd.DataFrame(item["predictions"], columns=baseline.PREDICTION_COLUMNS)
        per_date = pd.DataFrame(item["per_date"], columns=baseline.PER_DATE_COLUMNS)
        training = pd.DataFrame(item["training"], columns=baseline.TRAINING_COLUMNS)
        if (len(predictions) != 100 * 124 * 3 or len(per_date) != 1500 or len(training) != 300):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: scheme grid incomplete")
        outputs[scheme] = SchemeOutput(
            predictions=predictions, per_date_metrics=per_date,
            aggregate_metrics=baseline.aggregate_metrics(per_date),
            training_diagnostics=training,
            data_quality_diagnostics={
                "attempted_development_dates": 100, "successful_dates": 100,
                "skipped_dates": [], "excluded_sector_date_horizon_rows": [],
                "training_excluded_sector_date_horizon_rows": [],
                "missing_factor_exclusions": 0, "missing_label_exclusions": 0,
                "numerical_failures": 0, "insufficient_training_cases": 0,
                "source_invalid_total_in_snapshot": invalid_total,
                "source_invalid_interactions_with_development": invalid_in_window,
                "training_observation_leakage_checks": item["leakage_checks"],
                "training_label_end_after_signal_count": 0,
            },
            transformation_diagnostics={
                "x_preprocessing": "NONE_RAW",
                "training_target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
                "demean_residual_max_abs_mean": max(
                    (row["max_abs_mean"] for row in item["targets"]), default=None),
                "target_diagnostics": item["targets"],
            },
        )
    return outputs, stashed, universe_mean_120, {
        "codes": codes, "frames": frames, "calendar": calendar, "dates": dates,
        "labels_expost": labels_expost,
    }


def evaluate_outputs(outputs: dict, stashed: dict, universe_mean_120: dict,
                     context: dict, d2_predictions: pd.DataFrame,
                     d2_aggregate: dict) -> tuple[dict, pd.DataFrame, dict]:
    """Frozen advancement judgments, block stability, and all integrity gates."""
    factor_identity = factor_identity_gate(
        stashed, context["frames"], context["calendar"], context["dates"], context["codes"])
    target_identity = target_identity_gate(
        context["labels_expost"], context["frames"], context["calendar"], context["dates"],
        context["codes"], d2_predictions)
    d2_means = {name: stats["mean"] for name, stats in d2_aggregate.items()}
    c0_frozen = protocol.FROZEN_C0_METRICS
    if iteration1_protocol.weighted_rankic(d2_means) != c0_frozen["weightedRankIc"] \
            or iteration1_protocol.weighted_spread(d2_means) != c0_frozen["weightedSpread"]:
        raise ValueError("C0_REPRODUCTION_BLOCKER: frozen constants disagree with artifact")
    c0_rerun = {name: stats["mean"] for name, stats in outputs["C0"].aggregate_metrics.items()}
    c0_diffs = {name: abs(c0_rerun[name] - d2_means[name]) for name in d2_means}
    c0_max_diff = max(c0_diffs.values())
    if c0_max_diff > C0_REPRODUCTION_TOLERANCE:
        raise ValueError("C0_REPRODUCTION_BLOCKER")
    rows, block_rows = [], []
    for spec in scheme_specs():
        scheme = spec["schemeId"]
        output = outputs[scheme]
        means = {name: stats["mean"] for name, stats in output.aggregate_metrics.items()}
        block_rows.extend(block_stability_rows(scheme, output.per_date_metrics))
        if spec["isControl"]:
            rows.append({
                "candidateId": scheme, "factorList": spec["factorList"],
                "factorCount": len(spec["factorList"]), "isControl": True,
                "advancementStatus": STATUS_CONTROL,
                "level1": None, "level2": None, "level2Option": None,
                "horizonRedFlag": None, "redFlagHorizons": [],
                **weighted_metrics(means),
                "medianRankIcByHorizon": {
                    str(h): output.aggregate_metrics[f"RankIC_{h}"]["median"]
                    for h in protocol.FROZEN_SETTINGS["horizons"]},
                "extremeDateSensitivity": extreme_date_sensitivity(
                    output.per_date_metrics, universe_mean_120),
            })
            continue
        judgment = evaluate_advancement(means, c0_frozen)
        if judgment["advancementStatus"] not in (STATUS_ADVANCED, STATUS_NOT_ADVANCED):
            raise ValueError("FACTOR_SET_V2_RESULT_LABEL_VIOLATION")
        frozen_facts = protocol.load_candidate_config()
        declared = next(r for r in frozen_facts["candidates"] if r["candidateId"] == scheme)
        if declared["factorList"] != spec["factorList"]:
            raise ValueError("FACTOR_SET_V2_CANDIDATE_LIST_MISMATCH")
        deltas = {
            "weightedRankIc": judgment["weightedRankIc"] - c0_frozen["weightedRankIc"],
            "weightedSpread": judgment["weightedSpread"] - c0_frozen["weightedSpread"],
            "rankIcByHorizon": {str(h): judgment["rankIcByHorizon"][str(h)]
                                - c0_frozen["rankIcByHorizon"][str(h)]
                                for h in protocol.FROZEN_SETTINGS["horizons"]},
            "spreadByHorizon": {str(h): judgment["spreadByHorizon"][str(h)]
                                - c0_frozen["spreadByHorizon"][str(h)]
                                for h in protocol.FROZEN_SETTINGS["horizons"]},
        }
        rows.append({
            "candidateId": scheme, "factorList": spec["factorList"],
            "factorCount": len(spec["factorList"]), "isControl": False,
            **judgment, "deltaVsC0": deltas,
            "medianRankIcByHorizon": {
                str(h): output.aggregate_metrics[f"RankIC_{h}"]["median"]
                for h in protocol.FROZEN_SETTINGS["horizons"]},
            "extremeDateSensitivity": extreme_date_sensitivity(
                output.per_date_metrics, universe_mean_120),
        })
    advanced = [{"candidateId": row["candidateId"], "factorCount": row["factorCount"],
                 "weightedRankIc": row["weightedRankIc"],
                 "weightedSpread": row["weightedSpread"]}
                for row in rows if row["advancementStatus"] == STATUS_ADVANCED]
    simplicity = simplicity_preference(advanced)
    metric_integrity = verify_metric_integrity(
        {scheme: outputs[scheme].predictions for scheme in outputs}, rows)
    summary = {
        "experiment": EXPERIMENT,
        "protocolHash": protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH,
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "selectionBias": {
            "POST_AUDIT_DEVELOPMENT_RESEARCH": True,
            "NOT_INDEPENDENT_VALIDATION": True, "NOT_OOS_EVIDENCE": True,
        },
        "control": next(row for row in rows if row["isControl"]),
        "candidates": [row for row in rows if not row["isControl"]],
        "simplicityPreference": simplicity,
        "c0Reproduction": {
            "status": "PASS", "sourceRunId": ITERATION1_RUN_ID,
            "maxAbsDiff": c0_max_diff, "toleranceAbs": C0_REPRODUCTION_TOLERANCE,
            "perMetricAbsDiff": c0_diffs,
        },
        "notices": [
            "POST-AUDIT DEVELOPMENT RESEARCH", "NOT INDEPENDENT VALIDATION",
            "NOT OOS EVIDENCE", "NOT VALIDATED ALPHA", "NOT TRADABLE",
            "DEVELOPMENT ONLY", "NO PARAMETER SEARCH", "NO FACTOR ADAPTATION",
        ],
    }
    blocks = pd.DataFrame(block_rows, columns=(
        "candidate", "horizon", "block", "block_ordinal_start", "block_ordinal_end",
        "valid_dates", "rankic_mean", "rankic_median", "spread_mean"))
    integrity = {
        "factorIdentity": factor_identity, "targetIdentity": target_identity,
        "c0Reproduction": summary["c0Reproduction"], "metricRecompute": metric_integrity,
    }
    return summary, blocks, integrity


def build_metadata(gate: dict, summary: dict, run_id: str,
                   content_hashes: dict, repeat_of: Path | None) -> dict:
    config = protocol.load_candidate_config()
    metadata = {
        "researchLabel": "SECTOR_INDEX_RESEARCH_ONLY",
        "phase": "DEVELOPMENT",
        "experiment": EXPERIMENT,
        "preregistrationCommit": PREREGISTRATION_COMMIT,
        "protocolHash": protocol.FROZEN_FACTOR_SET_V2_PROTOCOL_HASH,
        "executionGitCommit": gate["git_head"],
        "sectorSnapshotId": baseline.EXPECTED_SNAPSHOT,
        "splitPolicyHash": baseline.EXPECTED_SPLIT_HASH,
        "predictionConfigHash": baseline.EXPECTED_PREDICTION_HASH,
        "candidateIds": [spec["schemeId"] for spec in scheme_specs()],
        "candidateFactorLists": {spec["schemeId"]: spec["factorList"] for spec in scheme_specs()},
        "factorOrder": list(protocol.FROZEN_FACTOR_ORDER),
        "target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
        "preprocessing": "NONE_RAW",
        "alpha": DEFAULT_ALPHA,
        "trainWindow": "6 calendar months",
        "horizons": protocol.FROZEN_SETTINGS["horizons"],
        "fusion": protocol.FROZEN_SETTINGS["fusion"],
        "topKSemantics": "highest_five_fused_scores_sector_code_ascending_tie_break",
        "validation": "SEALED",
        "finalOos": "SEALED",
        "strictPit": False,
        "classification": "FIXED_CLASSIFICATION_RESEARCH",
        "executable": False,
        "tradable": False,
        "POST_AUDIT_DEVELOPMENT_RESEARCH": True,
        "NO_INDEPENDENT_VALIDATION": True,
        "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
        "universe": "U0_FIXED_124", "sector_count": 124,
        "development_ordinals": [1, 100],
        "development_first_date": gate["development_first_date"],
        "development_last_date": gate["development_last_date"],
        "branch": gate["branch"], "docker_image_id": gate["docker_image_id"],
        "environment_changed": False,
        "run_id": run_id,
        "content_sha256": content_hashes,
        "c0ReproductionStatus": summary["c0Reproduction"]["status"],
        "advancementStatuses": {row["candidateId"]: row["advancementStatus"]
                                for row in summary["candidates"]},
        "notices": summary["notices"],
    }
    if repeat_of is not None:
        previous = json.loads((repeat_of / "metadata.json").read_text(encoding="utf-8"))
        if (previous["content_sha256"] != content_hashes
                or previous["protocolHash"] != metadata["protocolHash"]):
            raise ValueError("FACTOR_SET_V2_DETERMINISM_BLOCKER")
        metadata["determinism_repeat_of"] = previous["run_id"]
        metadata["determinism"] = "PASS_CONTENT_SHA256_IDENTICAL"
    for status in metadata["advancementStatuses"].values():
        if any(bad in status for bad in FORBIDDEN_RESULT_LABELS):
            raise ValueError("FACTOR_SET_V2_RESULT_LABEL_VIOLATION")
    return metadata


def write_run(output_root: Path, outputs: dict, summary: dict,
              blocks: pd.DataFrame, integrity: dict, gate: dict,
              repeat_of: Path | None = None) -> Path:
    for scheme, output in outputs.items():
        if (len(output.predictions) != 100 * 124 * 3 or len(output.per_date_metrics) != 1500
                or output.predictions.duplicated(["ordinal", "horizon", "sector_code"]).any()
                or set(output.predictions["ordinal"]) != set(range(1, 101))):
            raise ValueError("RESEARCH_PROTOCOL_VIOLATION: incomplete scheme output grid")
        guard = sorted(set(output.per_date_metrics["ordinal"].astype(int)))
        protocol.guard_factor_set_v2_scope("development", guard)
    run_id = datetime.now(timezone.utc).strftime("factor_set_v2_%Y%m%d_%H%M%S_%f_utc")
    if not run_id.replace("_", "").isalnum():
        raise ValueError("run_id contains unsafe characters")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / run_id
    target.mkdir(exist_ok=False)
    hashes = {}
    for spec in scheme_specs():
        scheme = spec["schemeId"]
        folder = target / scheme
        folder.mkdir()
        output = outputs[scheme]
        payloads = {
            "predictions.csv": baseline._csv_bytes(output.predictions),
            "per_date_metrics.csv": baseline._csv_bytes(output.per_date_metrics),
            "per_date_predictions.csv": baseline._csv_bytes(long_to_wide(output.predictions)),
            "aggregate_metrics.json": baseline._json_bytes(output.aggregate_metrics),
            "training_diagnostics.csv": baseline._csv_bytes(output.training_diagnostics),
            "data_quality_diagnostics.json": baseline._json_bytes(output.data_quality_diagnostics),
            "transformation_diagnostics.json": baseline._json_bytes(output.transformation_diagnostics),
        }
        for name, content in payloads.items():
            (folder / name).write_bytes(content)
            hashes[f"{scheme}/{name}"] = hashlib.sha256(content).hexdigest()
    run_payloads = {
        "candidate_summary.json": baseline._json_bytes(summary),
        "block_stability.csv": baseline._csv_bytes(blocks),
        "integrity.json": baseline._json_bytes(integrity),
    }
    for name, content in run_payloads.items():
        (target / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    metadata = build_metadata(gate, summary, run_id, hashes, repeat_of)
    (target / "metadata.json").write_bytes(baseline._json_bytes(metadata))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-image-id", required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/shenwan"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("reports/research/shenwan_sector_index"))
    parser.add_argument("--d2-source-dir", type=Path,
                        default=Path("reports/research/shenwan_sector_index")
                        / ITERATION1_RUN_ID / "D2")
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo_dir = Path(__file__).resolve().parents[1]
    gate = pre_run_gate(args.processed_dir, repo_dir, args.docker_image_id)
    load_frozen_d2_reference(args.d2_source_dir)
    print("FACTOR SET V2 PRE-RUN GATE", flush=True)
    print(json.dumps(gate, sort_keys=True, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    outputs, stashed, universe_mean_120, context = compute_schemes(args.processed_dir, gate)
    d2_predictions, d2_aggregate = load_frozen_d2_reference(args.d2_source_dir)
    summary, blocks, integrity = evaluate_outputs(
        outputs, stashed, universe_mean_120, context, d2_predictions, d2_aggregate)
    target = write_run(args.output_root, outputs, summary, blocks, integrity, gate,
                       args.repeat_of)
    print(f"FACTOR SET V2 RUN COMPLETE: {target}", flush=True)
    print(json.dumps({"run_dir": str(target),
                      "content_sha256": json.loads(
                          (target / "metadata.json").read_text(encoding="utf-8"))["content_sha256"]},
                     sort_keys=True, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

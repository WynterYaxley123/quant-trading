"""Read-only Shenwan sample-budget and universe-continuity diagnostics.

U1 and U2 are counterfactuals, not admitted universes. This module never
fits a model, computes a return, chooses an OOS period, or changes data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.sector_index_baseline import (
    ADMISSION,
    FEATURE_WARMUP,
    MAX_HORIZON,
    audit_signal_range,
    load_and_audit,
)
from research.sector_research_split import UNLOCKED, strict_budget
from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_TOP_N,
    DEFAULT_TRAIN_MONTHS,
    FORWARD_WINDOWS,
    MIN_TRAIN_DATES,
)

EXCLUDED_DIAGNOSTIC_CODE = "801193"
MIN_METRIC_SECTORS = DEFAULT_TOP_N + 1  # non-degenerate Top5-versus-universe
POLICY_SIGNAL_COUNTS = {
    "A": (60, 40, 40),
    "B": (80, 40, 40),
    "C": (100, 60, 60),
    "D": (120, 60, 60),
}


def sample_budget_policy(
    name: str, phase_counts: tuple[int, int, int], eligible_sessions: int, *, cadence: int = 10
) -> dict:
    """Session arithmetic only; counts are proposals, not adequacy claims."""
    if len(phase_counts) != 3 or any(
        isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in phase_counts
    ):
        raise ValueError("three positive phase signal counts are required")
    if isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < 1:
        raise ValueError("cadence must be a positive session count")
    purge = 2 * MAX_HORIZON
    required = sum(phase_counts) + purge
    return {
        "policy": name,
        "development_signals": phase_counts[0],
        "validation_signals": phase_counts[1],
        "final_oos_signals": phase_counts[2],
        "purge_1_sessions": MAX_HORIZON,
        "purge_2_sessions": MAX_HORIZON,
        "required_eligible_sessions": required,
        "available_eligible_sessions": eligible_sessions,
        "additional_eligible_sessions_needed": max(0, required - eligible_sessions),
        "mathematically_feasible": eligible_sessions >= required,
        "research_adequacy_approved": False,
        "nominal_10_session_decision_counts": {
            "development": (phase_counts[0] + cadence - 1) // cadence,
            "validation": (phase_counts[1] + cadence - 1) // cadence,
            "final_oos": (phase_counts[2] + cadence - 1) // cadence,
        },
        "decision_count_status": "ARITHMETIC_ONLY_ANCHOR_NOT_FROZEN",
    }


def prediction_metric_contract() -> dict:
    """Versioned definitions only; not a performance computation."""
    horizons = tuple(FORWARD_WINDOWS.values())
    return {
        "version": "sector-index-prediction-metrics-v1",
        "status": "FROZEN_DEFINITIONS_ONLY",
        "prediction_horizons_sessions": dict(FORWARD_WINDOWS),
        "metric_names": [
            f"{prefix}_{horizon}"
            for prefix in (
                "IC",
                "RankIC",
                "Top5_forward_return",
                "Universe_forward_return",
                "Top5_minus_universe",
            )
            for horizon in horizons
        ],
        "label": "sector_close[t+h]/sector_close[t]-1",
        "signal_time": "t_after_close",
        "minimum_sectors_per_date_horizon": MIN_METRIC_SECTORS,
        "minimum_sector_count_reason": "Top5 must be a strict subset of the comparison universe; not a statistical adequacy claim",
        "ranking_score": "fused_10_40_120_score",
        "ic_score": "corresponding_horizon_model_score",
        "cross_section": "approved_asof_universe_at_signal_date",
        "missing_rule": (
            "No future-aware replacement or universe shrinking. If any as-of universe member "
            "lacks its horizon label or score, that date/horizon metric is null with a reason. "
            "A missing selected Top5 label also invalidates Top5 and spread."
        ),
        "top5_tie_break": "fused_score_descending_then_sector_code_ascending",
        "correlation_ties": "average_ranks_for_spearman_ties",
        "zero_variance_correlation": None,
        "ic_by_horizon": "Pearson across sectors: horizon-model score versus same-horizon absolute forward return",
        "rankic_by_horizon": "Spearman across sectors: horizon-model score versus same-horizon absolute forward return",
        "top5_forward_return_by_horizon": "arithmetic_mean_of_exactly_five_fused_Top5_sector_labels",
        "universe_forward_return_by_horizon": "equal_weight_arithmetic_mean_of_all_asof_universe_labels",
        "top5_minus_universe_by_horizon": "Top5_forward_return_h minus Universe_forward_return_h",
        "date_aggregation": "equal_weight_arithmetic_mean_of_valid_date_metrics; report_valid_and_null_date_counts",
        "overlap_policy": "forward_labels_overlap; no naive_independent_sample_t_stat_or_significance_claim",
        "execution": False,
        "etf_costs": None,
    }


def missing_blocks(calendar: pd.DatetimeIndex, valid: np.ndarray) -> list[dict]:
    """Calendar-position intervals, not natural-day estimates."""
    if len(calendar) != len(valid):
        raise ValueError("calendar and availability length mismatch")
    missing = np.flatnonzero(~np.asarray(valid, dtype=bool))
    if not len(missing):
        return []
    starts = np.r_[0, np.flatnonzero(np.diff(missing) > 1) + 1]
    ends = np.r_[starts[1:] - 1, len(missing) - 1]
    return [
        {
            "start": str(calendar[missing[a]].date()),
            "end": str(calendar[missing[b]].date()),
            "sessions": int(b - a + 1),
        }
        for a, b in zip(starts, ends)
    ]


def _first_last_count(calendar: pd.DatetimeIndex, mask: np.ndarray) -> dict:
    positions = np.flatnonzero(mask)
    return {
        "start": str(calendar[positions[0]].date()) if len(positions) else None,
        "end": str(calendar[positions[-1]].date()) if len(positions) else None,
        "session_count": int(len(positions)),
    }


def _terminal_continuous_start(calendar: pd.DatetimeIndex, good: np.ndarray) -> str | None:
    if not good[-1]:
        return None
    bad = np.flatnonzero(~good)
    return str(calendar[(int(bad[-1]) + 1) if len(bad) else 0].date())


def _history_masks(
    calendar: pd.DatetimeIndex, availability: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """As-of sector readiness; excludes all future prices and labels."""
    n_dates, n_sectors = availability.shape
    bad_prefix = np.vstack(
        (np.zeros(n_sectors, dtype=int), np.cumsum(~availability, axis=0, dtype=int))
    )
    factor = np.zeros((n_dates, n_sectors), dtype=bool)
    training = np.zeros((n_dates, n_sectors), dtype=bool)
    for i in range(n_dates):
        if i >= FEATURE_WARMUP:
            factor[i] = bad_prefix[i + 1] == bad_prefix[i - FEATURE_WARMUP]
        starts = []
        for horizon in FORWARD_WINDOWS.values():
            cutoff = i - horizon
            if cutoff < 0:
                break
            train_start_date = calendar[cutoff] - pd.DateOffset(months=DEFAULT_TRAIN_MONTHS)
            train_start = int(calendar.searchsorted(train_start_date))
            if cutoff - train_start + 1 < MIN_TRAIN_DATES:
                break
            starts.append(train_start)
        if len(starts) != len(FORWARD_WINDOWS):
            continue
        warmup_start = min(starts) - FEATURE_WARMUP
        if warmup_start < 0:
            continue
        training[i] = bad_prefix[i + 1] == bad_prefix[warmup_start]
    return factor, training


def _scenario_stage_summary(
    calendar: pd.DatetimeIndex,
    availability: np.ndarray,
    factor: np.ndarray,
    training: np.ndarray,
    columns: list[int],
) -> dict:
    full = availability[:, columns].all(axis=1)
    factor_full = factor[:, columns].all(axis=1)
    training_full = training[:, columns].all(axis=1)
    # The fixed-universe rule also requires every bar through the longest
    # label window. This is retrospective evaluation availability, not a
    # permission to use future prices at signal time.
    bad_prefix = np.r_[0, np.cumsum(~full)]
    label_full = np.zeros(len(calendar), dtype=bool)
    for i in range(len(calendar) - MAX_HORIZON):
        label_full[i] = bad_prefix[i + MAX_HORIZON + 1] == bad_prefix[i]
    eligible = training_full & label_full
    return {
        "raw_all_sector_valid_sessions": int(full.sum()),
        "latest_first_complete_date": str(
            max(calendar[np.flatnonzero(availability[:, j])[0]] for j in columns).date()
        ),
        "continuous_common_start": _terminal_continuous_start(calendar, full),
        "continuous_common_end": str(calendar[-1].date()) if full[-1] else None,
        "factor_ready": _first_last_count(calendar, factor_full),
        "training_ready": _first_last_count(calendar, training_full),
        "label_ready": _first_last_count(calendar, label_full),
        "signal_eligible": _first_last_count(calendar, eligible),
    }


def audit_universe_feasibility(processed_dir: Path) -> dict:
    """Compare U0/U1/U2 using only the SHA-verified local common calendar."""
    metadata = json.loads((processed_dir / "sector_admission.json").read_text(encoding="utf-8"))
    if metadata.get("admission_level") != ADMISSION or metadata.get("strict_pit") is not False:
        raise ValueError("sector admission semantics changed")
    catalog = load_sector_catalog(processed_dir)
    codes = catalog["sector_code"].astype(str).tolist()
    if len(codes) != 124 or EXCLUDED_DIAGNOSTIC_CODE not in codes:
        raise ValueError("formal 124-sector catalog changed; diagnostic cannot proceed")
    panel = load_sector_panel(
        codes,
        metadata["common_start_date"],
        metadata["common_end_date"],
        processed_dir=processed_dir,
        allow_invalid_for_audit=True,
    )
    calendar = pd.DatetimeIndex(sorted(panel["date"].unique()))
    if (
        len(calendar) != 1158
        or str(calendar[0].date()) != metadata["common_start_date"]
        or str(calendar[-1].date()) != metadata["common_end_date"]
    ):
        raise ValueError("verified common calendar changed")
    availability_frame = panel.pivot(index="date", columns="sector_code", values="is_valid_ohlc")
    availability = (
        availability_frame.reindex(index=calendar, columns=codes).eq(True).to_numpy(dtype=bool)
    )
    factor, training = _history_masks(calendar, availability)
    u0_cols = list(range(len(codes)))
    u1_codes = [code for code in codes if code != EXCLUDED_DIAGNOSTIC_CODE]
    u1_cols = [codes.index(code) for code in u1_codes]
    u1_common_gaps = missing_blocks(calendar, availability[:, u1_cols].all(axis=1))

    u0_stage = _scenario_stage_summary(calendar, availability, factor, training, u0_cols)
    u1_stage = _scenario_stage_summary(calendar, availability, factor, training, u1_cols)
    u0_formal = load_and_audit(processed_dir)
    u1_panel = panel.loc[panel["sector_code"].isin(u1_codes)]
    u1_structural = audit_signal_range(u1_panel, u1_codes, metadata)
    if (
        u0_stage["signal_eligible"]["session_count"] != 239
        or u0_formal["signal_only_session_count"] != 239
        or u1_stage["signal_eligible"]["session_count"]
        != u1_structural["signal_only_session_count"]
    ):
        raise ValueError("universe feasibility does not reconcile to existing signal audit")

    focal = codes.index(EXCLUDED_DIAGNOSTIC_CODE)
    blocks = missing_blocks(calendar, availability[:, focal])
    focal_presence = panel.loc[panel["sector_code"].eq(EXCLUDED_DIAGNOSTIC_CODE), "date"]
    other_bottlenecks = []
    for j, code in enumerate(codes):
        if code == EXCLUDED_DIAGNOSTIC_CODE:
            continue
        gaps = missing_blocks(calendar, availability[:, j])
        if gaps:
            other_bottlenecks.append(
                {
                    "sector_code": code,
                    "unavailable_sessions": sum(b["sessions"] for b in gaps),
                    "last_unavailable": gaps[-1]["end"],
                }
            )
    other_bottlenecks.sort(key=lambda item: (-item["unavailable_sessions"], item["sector_code"]))

    # U2 membership is based on the complete *past* only. The raw calendar
    # must have enough later sessions to make labels eventually observable,
    # but a future sector bar never decides ex-ante membership.
    asof_count = training.sum(axis=1)
    u2_signal_mask = asof_count >= MIN_METRIC_SECTORS
    u2_signal_mask[len(calendar) - MAX_HORIZON :] = False
    u2_positions = np.flatnonzero(u2_signal_mask)
    if not len(u2_positions):
        raise ValueError("dynamic diagnostic has no signal dates")
    u2_sector_counts = asof_count[u2_positions]
    future_endpoint_counts = np.zeros(len(calendar), dtype=int)
    for i in u2_positions:
        evaluable = training[i].copy()
        for horizon in FORWARD_WINDOWS.values():
            evaluable &= availability[i + horizon]
        future_endpoint_counts[i] = int(evaluable.sum())

    signal_counts = {
        "U0": u0_formal["signal_only_session_count"],
        "U1": u1_structural["signal_only_session_count"],
        "U2": int(len(u2_positions)),
    }
    budgets = {
        scenario: {
            "strict_three_way_nonempty": strict_budget(count, MAX_HORIZON),
            "policies": {
                name: sample_budget_policy(name, phases, count)
                for name, phases in POLICY_SIGNAL_COUNTS.items()
            },
        }
        for scenario, count in signal_counts.items()
    }
    u0_raw_tail = int(calendar.get_loc(pd.Timestamp(u0_formal["signal_only_eligible_end"])))
    if len(calendar) - 1 - u0_raw_tail != MAX_HORIZON:
        raise ValueError("U0 label tail no longer exactly 120 trading sessions")
    return {
        "status": "SAMPLE_BUDGET_DECISION_REQUIRED",
        "data_snapshot_id": metadata["data_snapshot_id"],
        "formal_universe": {
            "mode": "FIXED_124_CURRENT_RULE",
            "sector_count": 124,
            "sector_codes_unchanged": True,
        },
        "common_calendar": {
            "start": str(calendar[0].date()),
            "end": str(calendar[-1].date()),
            "trading_sessions": len(calendar),
        },
        "U0": {
            "status": "FORMAL_CURRENT_RULE",
            **u0_stage,
            "signal_eligible_sessions": signal_counts["U0"],
        },
        "U1": {
            "status": "DIAGNOSTIC_ONLY_NOT_APPROVED_UNIVERSE_CHANGE",
            "excluded_sector": EXCLUDED_DIAGNOSTIC_CODE,
            "sector_count": len(u1_codes),
            **u1_stage,
            "common_unavailable_blocks": u1_common_gaps,
            "signal_eligible_sessions": signal_counts["U1"],
            "requires": "UNIVERSE_CHANGE_REQUIRES_READMISSION",
        },
        "U2": {
            "status": "DIAGNOSTIC_ONLY_NOT_APPROVED_DYNAMIC_UNIVERSE",
            "retained_catalog_sector_count": len(codes),
            "raw_dates_with_at_least_six_valid_bars": int(
                (availability.sum(axis=1) >= MIN_METRIC_SECTORS).sum()
            ),
            "signal_eligible": _first_last_count(calendar, u2_signal_mask),
            "signal_eligible_sessions": signal_counts["U2"],
            "asof_ready_sector_count": {
                "min": int(u2_sector_counts.min()),
                "median": float(np.median(u2_sector_counts)),
                "max": int(u2_sector_counts.max()),
            },
            "retrospective_all_horizon_endpoint_count": {
                "min": int(future_endpoint_counts[u2_positions].min()),
                "median": float(np.median(future_endpoint_counts[u2_positions])),
                "max": int(future_endpoint_counts[u2_positions].max()),
            },
            "membership_rule": "past_complete_history_only; future_endpoints_diagnostic_not_membership",
            "minimum_sector_count_policy": "NOT_APPROVED; six is only a metric-definition floor",
            "requires": "DYNAMIC_UNIVERSE_POLICY_AND_READMISSION",
        },
        "sector_801193": {
            "first_available": str(focal_presence.min().date()) if len(focal_presence) else None,
            "last_unavailable": blocks[-1]["end"] if blocks else None,
            "unavailable_sessions": sum(block["sessions"] for block in blocks),
            "missing_block_count": len(blocks),
            "largest_missing_block": max(blocks, key=lambda block: block["sessions"])
            if blocks
            else None,
            "missing_blocks": blocks,
            "cause_classification": "UNKNOWN_FROM_LOCAL_OHLCVA_ONLY",
        },
        "other_continuity_bottlenecks": {
            "affected_sector_count": len(other_bottlenecks),
            "unaffected_sector_codes": sorted(
                set(u1_codes) - {item["sector_code"] for item in other_bottlenecks}
            ),
            "first_ten_sectors": other_bottlenecks[:10],
            "shared_unavailable_blocks_for_fixed_123": u1_common_gaps,
        },
        "sample_budgets": budgets,
        "u0_additional_raw_sessions_if_continuity_persists": {
            name: budget["additional_eligible_sessions_needed"]
            for name, budget in budgets["U0"]["policies"].items()
        },
        "u0_raw_to_last_signal_tail_sessions": MAX_HORIZON,
        "prediction_metrics": prediction_metric_contract(),
        "rebalance_semantics": "REFERENCE_10_SESSIONS_ANCHOR_NOT_FROZEN",
        "synthetic_holding_semantics": "SYNTHETIC_PORTFOLIO_SEMANTICS_REQUIRES_APPROVAL",
        "strategy_config_hash": None,
        "oos_status": UNLOCKED,
        "oos_signal_start": None,
        "oos_signal_end": None,
        "performance_metrics_viewed": False,
        "strategy_parameters_changed": False,
        "level_b_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    args = parser.parse_args()
    print(
        json.dumps(
            audit_universe_feasibility(args.sector_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only trading-session split feasibility for sector-index research.

No model, return, ETF, execution, network, or Docker operation is performed.
Candidate dates for a single horizon are illustrative; they do not lock OOS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from research.sector_index_baseline import ADMISSION, load_and_audit
from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.common.temporal_integrity import temporal_boundaries
from strategies.sw_sector_rotation.src.factors.sector_rotation import TRAIN_FEATURES_PRICE
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA,
    DEFAULT_TOP_N,
    DEFAULT_TRAIN_MONTHS,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
)

SPLIT_POLICY_VERSION = "sector-index-strict-session-purge-v1"
UNLOCKED = "UNLOCKED_UNOPENED"
REBALANCE_FIELDS = ("interval_sessions", "anchor")
HOLDING_FIELDS = (
    "portfolio_formation",
    "entry_convention",
    "holding_convention",
    "overlap_policy",
    "return_measurement",
    "turnover_semantics",
)
SPLIT_FIELDS = (
    "policy_version",
    "development_signals",
    "validation_signals",
    "final_oos_signals",
    "boundary_purge_sessions",
    "oos_start",
    "oos_end",
)
UNIVERSE_FIELDS = ("mode", "sector_codes", "admission_mode")
EPHEMERAL_HASH_FIELDS = frozenset({"timestamp", "locked_at", "uuid", "run_id", "generated_at"})


def _calendar(dates: Sequence) -> pd.DatetimeIndex:
    calendar = pd.DatetimeIndex(dates)
    if (
        calendar.empty
        or calendar.hasnans
        or calendar.tz is not None
        or not calendar.equals(calendar.normalize())
        or not calendar.is_monotonic_increasing
        or calendar.has_duplicates
    ):
        raise ValueError("expected a nonempty, unique, ordered trading-session calendar")
    return calendar


def strict_budget(eligible_sessions: int, horizon: int, *, phases: int = 3) -> dict:
    """Strictly earlier realization needs *h* excluded sessions per boundary.

    If the last phase-A signal is at position i, its h-label ends at i+h.
    The next phase's first signal must be at least i+h+1. Thus exactly h
    sessions i+1..i+h are purged, including the label endpoint.
    """
    if (
        isinstance(eligible_sessions, bool)
        or not isinstance(eligible_sessions, int)
        or eligible_sessions < 0
        or isinstance(horizon, bool)
        or not isinstance(horizon, int)
        or horizon < 1
        or phases < 2
    ):
        raise ValueError("invalid session budget")
    purge = (phases - 1) * horizon
    minimum = phases + purge
    feasible = eligible_sessions >= minimum
    return {
        "eligible_sessions": eligible_sessions,
        "required_boundary_purge_sessions": horizon,
        "boundary_count": phases - 1,
        "total_purge_sessions": purge,
        "minimum_sessions_for_nonempty_phases": minimum,
        "available_minus_required": eligible_sessions - minimum,
        "feasible": feasible,
        "signal_slots_after_purge": eligible_sessions - purge if feasible else None,
    }


def candidate_three_way(dates: Sequence, horizon: int) -> dict | None:
    """Illustrative 60/20/20 allocation of *remaining* signal slots.

    The pre-existing ratio guidance is count-only and never uses prices or
    returns. No candidate is returned for an infeasible horizon.
    """
    calendar = _calendar(dates)
    budget = strict_budget(len(calendar), horizon)
    if not budget["feasible"]:
        return None
    slots = budget["signal_slots_after_purge"]
    development_count = max(1, int(slots * 0.60))
    validation_count = max(1, int(slots * 0.20))
    final_count = slots - development_count - validation_count
    if final_count < 1:
        raise ValueError("ratio guidance cannot allocate three nonempty phases")

    d0, d1 = 0, development_count - 1
    p10, p11 = d1 + 1, d1 + horizon
    v0, v1 = p11 + 1, p11 + validation_count
    p20, p21 = v1 + 1, v1 + horizon
    o0, o1 = p21 + 1, len(calendar) - 1
    assert o1 - o0 + 1 == final_count
    assert d1 + horizon == p11 < v0
    assert v1 + horizon == p21 < o0

    def _interval(first: int, last: int) -> dict:
        return {
            "start": str(calendar[first].date()),
            "end": str(calendar[last].date()),
            "count": last - first + 1,
        }

    return {
        "status": "ILLUSTRATIVE_HORIZON_ONLY_NOT_OOS_LOCK",
        "ratio_guidance_after_purge": [0.60, 0.20, 0.20],
        "development": _interval(d0, d1),
        "purge_1": _interval(p10, p11),
        "validation": _interval(v0, v1),
        "purge_2": _interval(p20, p21),
        "final_oos_candidate": _interval(o0, o1),
    }


def verify_training_label_availability(
    raw_calendar: Sequence,
    signal_dates: Sequence,
    horizons: Sequence[int],
) -> int:
    """Check each signal/horizon against the existing core's cutoff rule."""
    raw = _calendar(raw_calendar)
    signals = _calendar(signal_dates)
    verified = 0
    for signal in signals:
        for horizon in horizons:
            boundary = temporal_boundaries(raw, signal, horizon, DEFAULT_TRAIN_MONTHS)
            if boundary is None:
                raise ValueError("RESEARCH_LEAKAGE_BLOCKER: training boundary unavailable")
            cutoff_position = int(raw.get_loc(boundary.label_cutoff))
            if raw[cutoff_position + horizon] > signal:
                raise ValueError("RESEARCH_LEAKAGE_BLOCKER: unrealized training label")
            verified += 1
    return verified


def label_tail_end(raw_calendar: Sequence, signal_end, horizon: int) -> str | None:
    """Label-only endpoint; never a feature or model-training input."""
    raw = _calendar(raw_calendar)
    position = int(raw.get_loc(pd.Timestamp(signal_end)))
    endpoint = position + horizon
    return str(raw[endpoint].date()) if endpoint < len(raw) else None


def strategy_config_payload(
    data_snapshot_id: str,
    *,
    rebalance_policy: Mapping[str, object] | None = None,
    holding_policy: Mapping[str, object] | None = None,
    split_policy: Mapping[str, object] | None = None,
    universe_policy: Mapping[str, object] | None = None,
) -> dict:
    """Canonical hash input; missing portfolio semantics are explicit nulls."""
    if not data_snapshot_id:
        raise ValueError("data snapshot ID is required")
    return {
        "data_snapshot_id": data_snapshot_id,
        "data_admission_mode": ADMISSION,
        "features": list(TRAIN_FEATURES_PRICE),
        "model": "NumPyRidge",
        "ridge_alpha": DEFAULT_ALPHA,
        "horizons_sessions": dict(FORWARD_WINDOWS),
        "fusion_weights": dict(FUSION_WEIGHTS),
        "top_n": DEFAULT_TOP_N,
        "training_window_calendar_months": DEFAULT_TRAIN_MONTHS,
        "minimum_valid_training_days": MIN_TRAIN_DATES,
        "target": "absolute_close_to_close_forward_return",
        "rsrs_in_training": False,
        "macro_enabled": False,
        "flow_enabled": False,
        "risk_state": "record_only",
        "prediction_metric_spec_version": "sector-index-prediction-metrics-v1",
        "rebalance_policy": dict(rebalance_policy) if rebalance_policy is not None else None,
        "holding_policy": dict(holding_policy) if holding_policy is not None else None,
        "split_policy": dict(split_policy) if split_policy is not None else None,
        "universe_policy": dict(universe_policy) if universe_policy is not None else None,
    }


def strategy_config_hash(payload: Mapping[str, object]) -> str | None:
    """Return a deterministic hash only when all OOS-lock semantics exist."""
    for name, required in (
        ("rebalance_policy", REBALANCE_FIELDS),
        ("holding_policy", HOLDING_FIELDS),
        ("split_policy", SPLIT_FIELDS),
        ("universe_policy", UNIVERSE_FIELDS),
    ):
        policy = payload.get(name)
        if not isinstance(policy, Mapping) or any(
            policy.get(field) is None or policy.get(field) == "" for field in required
        ):
            return None
    split = payload["split_policy"]
    universe = payload["universe_policy"]
    if (
        split["boundary_purge_sessions"] != max(FORWARD_WINDOWS.values())
        or any(
            isinstance(split[field], bool) or not isinstance(split[field], int) or split[field] < 1
            for field in ("development_signals", "validation_signals", "final_oos_signals")
        )
        or split["oos_start"] > split["oos_end"]
        or not isinstance(universe["sector_codes"], (list, tuple))
        or not universe["sector_codes"]
    ):
        return None

    def _without_ephemeral(value):
        if isinstance(value, Mapping):
            return {
                key: _without_ephemeral(item)
                for key, item in value.items()
                if key not in EPHEMERAL_HASH_FIELDS
            }
        if isinstance(value, (list, tuple)):
            return [_without_ephemeral(item) for item in value]
        return value

    canonical = json.dumps(
        _without_ephemeral(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit_split(processed_dir: Path) -> dict:
    """Audit verified local sector data, without producing research metrics."""
    signal_audit = load_and_audit(processed_dir)
    catalog = load_sector_catalog(processed_dir)
    admission = json.loads((processed_dir / "sector_admission.json").read_text(encoding="utf-8"))
    panel = load_sector_panel(
        catalog["sector_code"].astype(str).tolist(),
        admission["common_start_date"],
        admission["common_end_date"],
        processed_dir=processed_dir,
        allow_invalid_for_audit=True,
    )
    raw = _calendar(sorted(panel["date"].unique()))
    start = pd.Timestamp(signal_audit["signal_only_eligible_start"])
    end = pd.Timestamp(signal_audit["signal_only_eligible_end"])
    eligible = raw[(raw >= start) & (raw <= end)]
    if len(eligible) != signal_audit["signal_only_session_count"]:
        raise ValueError("eligible calendar/count mismatch")
    horizons = dict(FORWARD_WINDOWS)
    checked = verify_training_label_availability(raw, eligible, list(horizons.values()))
    per_horizon = {}
    for name, horizon in horizons.items():
        budget = strict_budget(len(eligible), horizon)
        candidate = candidate_three_way(eligible, horizon)
        if candidate is not None:
            candidate["label_realization_tail_end"] = label_tail_end(
                raw, candidate["final_oos_candidate"]["end"], horizon
            )
        per_horizon[name] = {**budget, "candidate": candidate}
    combined_horizon = max(horizons.values())
    combined = strict_budget(len(eligible), combined_horizon)
    two_phase = strict_budget(len(eligible), combined_horizon, phases=2)
    first_raw_position = int(raw.get_loc(eligible[0]))
    earliest_validation_position = first_raw_position + combined_horizon + 1
    earliest_oos_position = earliest_validation_position + combined_horizon + 1
    strict_date_proof = {
        "first_possible_development_signal": str(raw[first_raw_position].date()),
        "first_development_label_end": str(raw[first_raw_position + combined_horizon].date()),
        "earliest_validation_signal": str(raw[earliest_validation_position].date()),
        "first_validation_label_end": str(
            raw[earliest_validation_position + combined_horizon].date()
        ),
        "earliest_final_oos_signal": str(raw[earliest_oos_position].date()),
        "last_eligible_signal": str(eligible[-1].date()),
        "earliest_oos_is_eligible": earliest_oos_position <= int(raw.get_loc(eligible[-1])),
    }
    payload = strategy_config_payload(admission["data_snapshot_id"])
    return {
        "split_policy_version": SPLIT_POLICY_VERSION,
        "status": "STRICT_3WAY_SPLIT_NOT_FEASIBLE"
        if not combined["feasible"]
        else "FEASIBLE_NOT_LOCKED",
        "data_snapshot_id": admission["data_snapshot_id"],
        "raw_common_start": str(raw[0].date()),
        "raw_common_end": str(raw[-1].date()),
        "raw_common_sessions": len(raw),
        "eligible_signal_start": str(eligible[0].date()),
        "eligible_signal_end": str(eligible[-1].date()),
        "eligible_signal_sessions": len(eligible),
        "training_label_checks": checked,
        "training_label_availability": "PASS",
        "horizon_feasibility": per_horizon,
        "combined_horizon_sessions": combined_horizon,
        "combined_three_way": combined,
        "combined_strict_date_proof": strict_date_proof,
        "combined_candidate": candidate_three_way(eligible, combined_horizon),
        "two_phase_dev_validation": two_phase,
        "two_phase_dev_final_oos": two_phase.copy(),
        "oos_status": UNLOCKED,
        "oos_signal_start": None,
        "oos_signal_end": None,
        "oos_label_tail_end": None,
        "locked_at": None,
        "rebalance_semantics": "REBALANCE_SEMANTICS_NOT_FROZEN",
        "holding_semantics": "HOLDING_SEMANTICS_NOT_FROZEN",
        "strategy_config_hash": strategy_config_hash(payload),
        "missing_for_config_hash": [
            "rebalance_policy",
            "holding_policy",
            "split_policy",
            "universe_policy",
        ],
        "performance_metrics_viewed": False,
        "executable": False,
        "level_b": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    args = parser.parse_args()
    print(json.dumps(audit_split(args.sector_dir), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

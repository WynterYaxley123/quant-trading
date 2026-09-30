"""Frozen, non-executing Development prediction protocol for Shenwan sectors.

Only ordinal/date availability and configuration semantics are exposed here.
No model fitting, prediction, performance metric, ETF, or portfolio run occurs.
Future runners must pass every evaluation request through ``guard_evaluation``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from research.sector_index_baseline import ADMISSION, load_and_audit
from research.sector_universe_feasibility import prediction_metric_contract
from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.factors.sector_rotation import TRAIN_FEATURES_PRICE
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA, DEFAULT_TOP_N, DEFAULT_TRAIN_MONTHS, FORWARD_WINDOWS,
    FUSION_WEIGHTS, MIN_TRAIN_DATES,
)

POLICY_NAME = "POLICY_C_FIXED124_STRICT120"
FORMAL_UNIVERSE = "SW_LEVEL2_FIXED_124"
FROZEN_PREFIX_COUNT = 239
FROZEN_PREFIX_SHA256 = "bcefa227f86a805677733defea63ed3954915548a6a140b0f654510c4267790b"
FROZEN_CODES_SHA256 = "f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a"
FROZEN_FEATURES_SHA256 = "ee1b70d4623b566451eae8c8a0c4878720049e506b05f4cd94b9d7c806e54c59"
FROZEN_HISTORY_END = "2026-09-18"
FROZEN_HISTORY_SHA256 = "a78ae9d6e3c0f7b985927e1d6ae721f94ae4bb85fb58440cfd76719846eff82c"
HISTORY_COLUMNS = (
    "date", "sector_code", "sector_name", "open", "high", "low", "close",
    "volume", "amount", "is_valid_ohlc",
)
FROZEN_BOUNDARY_DATES = {
    1: "2025-04-02", 100: "2025-08-26", 101: "2025-08-27",
    220: "2026-03-02", 221: "2026-03-03", 239: "2026-03-27",
}
PHASES = (
    ("development", 1, 100),
    ("purge_1", 101, 220),
    ("validation", 221, 280),
    ("purge_2", 281, 400),
    ("final_oos", 401, 460),
)


def canonical_hash(value: object) -> str:
    """Stable SHA256 of semantic JSON (never of timestamps or generated IDs)."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dates(dates: Sequence) -> list[str]:
    calendar = pd.DatetimeIndex(dates)
    if (calendar.empty or calendar.hasnans or calendar.tz is not None
            or not calendar.equals(calendar.normalize())
            or not calendar.is_monotonic_increasing or calendar.has_duplicates):
        raise ValueError("eligible signal calendar must be unique, ordered trading dates")
    return [str(day.date()) for day in calendar]


def split_policy_payload() -> dict:
    """Immutable policy only; intentionally excludes snapshot and observed dates."""
    return {
        "split_policy_name": POLICY_NAME,
        "formal_universe": FORMAL_UNIVERSE,
        "formal_universe_sector_count": 124,
        "formal_universe_codes_sha256": FROZEN_CODES_SHA256,
        "u1_exclude_801193": "DIAGNOSTIC_ONLY",
        "u2_dynamic": "DIAGNOSTIC_ONLY",
        "development_count": 100,
        "validation_count": 60,
        "final_oos_count": 60,
        "purge_1": 120,
        "purge_2": 120,
        "required_eligible_sessions": 460,
        "eligible_calendar_semantics": (
            "ordered canonical common trading sessions satisfying fixed-124 all-sector "
            "OHLC validity, factor warmup, 6-calendar-month/30-day training, "
            "10/40/120 label realization and per-horizon training-label purge; "
            "ordinal assigned from the first eligible signal date, never from returns"
        ),
        "ordinal_definition": [
            {"phase": phase, "start": start, "end": end}
            for phase, start, end in PHASES
        ],
        "strict_pit": False,
        "sector_data_admission": ADMISSION,
    }


def split_policy_hash() -> str:
    return canonical_hash(split_policy_payload())


def prediction_config_payload() -> dict:
    """Prediction-only semantics, independent of unresolved portfolio rules."""
    if (len(TRAIN_FEATURES_PRICE) != 19
            or canonical_hash(list(TRAIN_FEATURES_PRICE)) != FROZEN_FEATURES_SHA256
            or DEFAULT_ALPHA != 0.01 or DEFAULT_TOP_N != 5
            or DEFAULT_TRAIN_MONTHS != 6 or MIN_TRAIN_DATES != 30
            or dict(FORWARD_WINDOWS) != {"short": 10, "medium": 40, "long": 120}
            or dict(FUSION_WEIGHTS) != {"short": 0.25, "medium": 0.5, "long": 0.25}):
        raise ValueError("RESEARCH_SEMANTICS_FREEZE_REQUIRED: strategy prediction inputs changed")
    return {
        "formal_universe": FORMAL_UNIVERSE,
        "formal_universe_codes_sha256": FROZEN_CODES_SHA256,
        "sector_data_admission": ADMISSION,
        "strict_pit": False,
        "split_policy_hash": split_policy_hash(),
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
        "prediction_metric_contract": prediction_metric_contract(),
    }


def prediction_config_hash() -> str:
    return canonical_hash(prediction_config_payload())


def verify_frozen_prefix(eligible_dates: Sequence, sector_codes: Sequence[str]) -> list[str]:
    """Allow an append, but fail closed if historical ordinals or U0 changed."""
    dates = _dates(eligible_dates)
    codes = sorted(map(str, sector_codes))
    if (len(codes) != 124 or len(set(codes)) != 124
            or canonical_hash(codes) != FROZEN_CODES_SHA256
            or len(dates) < FROZEN_PREFIX_COUNT
            or canonical_hash(dates[:FROZEN_PREFIX_COUNT]) != FROZEN_PREFIX_SHA256):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: frozen U0 or E001-E239 changed")
    if any(dates[ordinal - 1] != expected
           for ordinal, expected in FROZEN_BOUNDARY_DATES.items()):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: frozen ordinal boundary changed")
    return dates


def historical_panel_hash(panel: pd.DataFrame, *, through: str = FROZEN_HISTORY_END) -> str:
    """Fingerprint historical economics; appended rows/source-file hashes are excluded."""
    if not set(HISTORY_COLUMNS).issubset(panel.columns):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: historical columns missing")
    old = panel.loc[panel["date"].le(pd.Timestamp(through)), list(HISTORY_COLUMNS)]
    if old.empty or old.duplicated(["date", "sector_code"]).any():
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: historical rows invalid")
    canonical = old.sort_values(["date", "sector_code"]).to_csv(
        index=False, float_format="%.17g", na_rep="<NULL>",
        date_format="%Y-%m-%d", lineterminator="\n",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def phase_for_ordinal(ordinal: int) -> str:
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise ValueError("ordinal must be a positive integer")
    for phase, start, end in PHASES:
        if start <= ordinal <= end:
            return phase
    raise ValueError("ordinal exceeds frozen Policy C budget")


def guard_evaluation(phase: str, ordinals: Sequence[int]) -> None:
    """Gate any future evaluation output, not training-label realization.

    Validation/OOS have no authorization mode in this phase of the project.
    Purged ordinals cannot produce evaluation output either.
    """
    if phase != "development":
        raise PermissionError("SEALED_PHASE_ACCESS_ERROR: only Development is authorized")
    if not ordinals:
        raise ValueError("evaluation request cannot be empty")
    for ordinal in ordinals:
        category = phase_for_ordinal(ordinal)
        if category in {"validation", "purge_2", "final_oos"}:
            raise PermissionError(f"SEALED_PHASE_ACCESS_ERROR: E{ordinal:03d} is sealed")
        if category != "development":
            raise PermissionError(f"PURGED_ORDINAL_ACCESS_ERROR: E{ordinal:03d} is not evaluable")


def guard_evaluation_dates(phase: str, requested_dates: Sequence,
                           eligible_dates: Sequence) -> list[int]:
    """Date-based wrapper prevents a future runner bypassing ordinal checks."""
    dates = _dates(eligible_dates)
    lookup = {day: index for index, day in enumerate(dates, 1)}
    requested = _dates(requested_dates)
    if any(day not in lookup for day in requested):
        raise ValueError("requested date is not on the eligible signal calendar")
    ordinals = [lookup[day] for day in requested]
    guard_evaluation(phase, ordinals)
    return ordinals


def availability_metadata(eligible_dates: Sequence, sector_codes: Sequence[str],
                          *, data_snapshot_id: str) -> dict:
    """Calendar counts and configuration only; never reads prices or metrics."""
    dates = verify_frozen_prefix(eligible_dates, sector_codes)
    if not data_snapshot_id:
        raise ValueError("verified data snapshot ID is required")
    availability = {}
    for phase, start, end in PHASES:
        available = max(0, min(len(dates), end) - start + 1)
        availability[phase] = {
            "ordinal_start": start, "ordinal_end": end,
            "required_count": end - start + 1,
            "available_count": available,
            "remaining_count": end - start + 1 - available,
            "available_start": dates[start - 1] if available else None,
            "available_end": dates[start + available - 2] if available else None,
        }
    return {
        "status": "DEVELOPMENT_PREDICTION_PROTOCOL_LOCKED",
        "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
        "executable": False,
        "strict_pit": False,
        "sector_data_admission": ADMISSION,
        "allowed_evaluation_phase": "development",
        "allowed_evaluation_ordinals": {"start": 1, "end": 100},
        "development_prediction_prepared_not_run": True,
        "data_snapshot_id": data_snapshot_id,
        "observed_eligible_count": len(dates),
        "frozen_prefix_count": FROZEN_PREFIX_COUNT,
        "frozen_prefix_sha256": FROZEN_PREFIX_SHA256,
        "split_policy": split_policy_payload(),
        "split_policy_hash": split_policy_hash(),
        "prediction_config": prediction_config_payload(),
        "prediction_config_hash": prediction_config_hash(),
        "prediction_metric_contract": prediction_metric_contract(),
        "synthetic_portfolio_config_hash": None,
        "synthetic_portfolio_enabled": False,
        "availability": availability,
        "validation_status": (
            "LOCKED_PARTIALLY_AVAILABLE_UNOPENED"
            if 0 < availability["validation"]["available_count"] < 60
            else "LOCKED_FULLY_AVAILABLE_UNOPENED"
            if availability["validation"]["available_count"] == 60
            else "LOCKED_NOT_YET_AVAILABLE_UNOPENED"
        ),
        "final_oos_status": (
            "FINAL_OOS_POLICY_LOCKED_DATES_NOT_YET_AVAILABLE"
            if availability["final_oos"]["available_count"] < 60
            else "FINAL_OOS_POLICY_LOCKED_DATES_AVAILABLE_UNOPENED"
        ),
        "oos_performance_status": "UNOPENED",
        "performance_metrics_viewed": False,
        "validation_metrics_viewed": False,
        "oos_metrics_viewed": False,
        "level_b_run": False,
    }


def audit_local_policy(processed_dir: Path) -> dict:
    """Read SHA-verified local sector files; no model, network, or ETF access."""
    admission = json.loads((processed_dir / "sector_admission.json").read_text(encoding="utf-8"))
    if admission.get("admission_level") != ADMISSION or admission.get("strict_pit") is not False:
        raise ValueError("RESEARCH_SEMANTICS_FREEZE_REQUIRED: admission mode changed")
    signal = load_and_audit(processed_dir)
    catalog = load_sector_catalog(processed_dir)
    codes = catalog["sector_code"].astype(str).tolist()
    panel = load_sector_panel(
        codes, admission["common_start_date"], admission["common_end_date"],
        processed_dir=processed_dir, allow_invalid_for_audit=True,
    )
    if historical_panel_hash(panel) != FROZEN_HISTORY_SHA256:
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: historical sector data revised")
    calendar = pd.DatetimeIndex(sorted(panel["date"].unique()))
    start = pd.Timestamp(signal["signal_only_eligible_start"])
    end = pd.Timestamp(signal["signal_only_eligible_end"])
    eligible = calendar[(calendar >= start) & (calendar <= end)]
    if len(eligible) != signal["signal_only_session_count"]:
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: eligible calendar/count mismatch")
    result = availability_metadata(eligible, codes, data_snapshot_id=signal["data_snapshot_id"])
    result["frozen_history_through"] = FROZEN_HISTORY_END
    result["frozen_history_sha256"] = FROZEN_HISTORY_SHA256
    # E100's 120-session label endpoint must be inside Purge 1 and before E221.
    last_dev = eligible[99]
    endpoint_i = int(calendar.get_loc(last_dev)) + 120
    if (endpoint_i >= len(calendar) or calendar[endpoint_i] != eligible[219]
            or not calendar[endpoint_i] < eligible[220]):
        raise ValueError("SPLIT_REPRODUCIBILITY_REVIEW: strict boundary purge changed")
    result["development_last_120_label_endpoint"] = str(calendar[endpoint_i].date())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    args = parser.parse_args()
    print(json.dumps(audit_local_policy(args.sector_dir), ensure_ascii=False,
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

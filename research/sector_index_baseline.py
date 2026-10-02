"""Read-only preparation for a non-executable Shenwan sector-index study.

This module audits signal eligibility and defines the future result contract.
It does not fit a model, calculate performance, load ETF data, or trade.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.loaders.shenwan_sector_loader import load_sector_catalog, load_sector_panel
from strategies.sw_sector_rotation.src.common.temporal_integrity import (
    make_forward_label,
    temporal_boundaries,
)
from strategies.sw_sector_rotation.src.factors.sector_rotation import (
    MA_WINDOWS,
    RANGE_WINDOWS,
    TRAIN_FEATURES_PRICE,
    compute_all_price_features,
)
from strategies.sw_sector_rotation.src.model.model import (
    DEFAULT_ALPHA,
    DEFAULT_TOP_N,
    DEFAULT_TRAIN_MONTHS,
    FORWARD_WINDOWS,
    FUSION_WEIGHTS,
    MIN_TRAIN_DATES,
)

RUN_TYPE = "SECTOR_INDEX_RESEARCH_ONLY"
ADMISSION = "FIXED_CLASSIFICATION_RESEARCH"
SYNTHETIC_RETURN_TYPE = "SYNTHETIC_SECTOR_INDEX_RETURN"
FEATURE_WARMUP = max(*MA_WINDOWS, *RANGE_WINDOWS)
MAX_HORIZON = max(FORWARD_WINDOWS.values())


@dataclass(frozen=True)
class SectorResearchResult:
    """Output contract for a future signal-only runner; no execution fields."""

    dates: tuple[str, ...]
    rankings: Mapping[str, list[dict]]
    selected_sector_codes: Mapping[str, list[str]]
    selected_sector_names: Mapping[str, list[str]]
    model_scores: Mapping[str, dict]
    horizon_scores: Mapping[str, dict]
    fused_scores: Mapping[str, dict]
    realized_forward_sector_returns: Mapping[str, dict]
    research_equity_curve: Mapping[str, float] | None
    turnover: Mapping[str, float] | None
    coverage: Mapping[str, object]
    missing_invalid_diagnostics: Mapping[str, object]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        required = {
            "run_type": RUN_TYPE,
            "executable": False,
            "strict_pit": False,
            "sector_data_admission": ADMISSION,
        }
        if any(self.metadata.get(key) != value for key, value in required.items()):
            raise ValueError(
                "sector-index result must retain non-executable fixed-classification semantics"
            )
        if self.metadata.get("level_b") is not False:
            raise ValueError("sector-index result is not LEVEL B")
        if any(
            self.metadata.get(key) is not None
            for key in (
                "etf_commission",
                "etf_slippage",
                "etf_fills",
                "orders",
                "trade_manager",
            )
        ):
            raise ValueError("ETF execution costs/fills must not appear in sector-index research")
        if (
            self.research_equity_curve is not None
            and self.metadata.get("return_type") != SYNTHETIC_RETURN_TYPE
        ):
            raise ValueError("research equity curve must be labeled synthetic and non-tradable")
        if any(len(codes) > DEFAULT_TOP_N for codes in self.selected_sector_codes.values()):
            raise ValueError("selected sector count exceeds frozen Top5 limit")


def research_metadata(data_snapshot_id: str, *, synthetic_returns: bool = False) -> dict:
    """Explicit signal-only metadata; unresolved performance fields stay null."""
    if not data_snapshot_id:
        raise ValueError("verified sector data snapshot is required")
    return {
        "run_type": RUN_TYPE,
        "executable": False,
        "strict_pit": False,
        "sector_data_admission": ADMISSION,
        "level_b": False,
        "data_snapshot_id": data_snapshot_id,
        "return_type": SYNTHETIC_RETURN_TYPE if synthetic_returns else None,
        "notices": [
            "NOT A TRADABLE PORTFOLIO BACKTEST",
            "NOT LEVEL B",
            "NOT ETF PERFORMANCE",
            "NOT EXECUTION VALIDATION",
            "NOT A STRICT HISTORICAL CLASSIFICATION PIT BACKTEST",
        ],
        "etf_commission": None,
        "etf_slippage": None,
        "etf_fills": None,
        "orders": None,
        "trade_manager": None,
    }


def audit_signal_range(
    panel: pd.DataFrame,
    sector_codes: Sequence[str],
    metadata: Mapping[str, object],
) -> dict:
    """Independently derive the conservative all-sector signal range.

    The only inputs are canonical sector OHLCVA, sector identifiers, and sector
    admission metadata. The study's 10/40/120 horizons are labels, never ETF
    execution delay or an inferred holding period.
    """
    if metadata.get("admission_level") != ADMISSION or metadata.get("strict_pit") is not False:
        raise ValueError("sector data admission changed; fixed-classification audit must stop")
    codes = {str(code) for code in sector_codes}
    if not codes or len(codes) != len(sector_codes):
        raise ValueError("sector catalog must be nonempty and unique")
    required = {"date", "sector_code", "is_valid_ohlc"}
    if not required.issubset(panel.columns) or panel.empty:
        raise ValueError("canonical sector panel columns/data missing")
    if (
        panel.duplicated(["date", "sector_code"]).any()
        or set(panel["sector_code"].astype(str)) != codes
    ):
        raise ValueError("canonical sector panel has duplicates or a different universe")
    if panel["is_valid_ohlc"].isna().any():
        raise ValueError("quality flags must be explicit")
    common_start = pd.Timestamp(metadata["common_start_date"])
    common_end = pd.Timestamp(metadata["common_end_date"])
    frame = panel.loc[panel["date"].between(common_start, common_end)]
    calendar = pd.DatetimeIndex(sorted(frame["date"].unique()))
    if (
        calendar.empty
        or calendar[0] != common_start
        or calendar[-1] != common_end
        or calendar.hasnans
        or calendar.has_duplicates
    ):
        raise ValueError("canonical common trading calendar does not match metadata")

    grouped = (
        frame.groupby("date", sort=True)
        .agg(
            observed=("sector_code", "nunique"),
            valid=("is_valid_ohlc", "sum"),
        )
        .reindex(calendar)
    )
    full = (grouped["observed"].eq(len(codes)) & grouped["valid"].eq(len(codes))).to_numpy()
    bad_positions = [i for i, ok in enumerate(full) if not ok]
    bad_prefix = [0]
    for ok in full:
        bad_prefix.append(bad_prefix[-1] + int(not ok))

    def _check(i: int) -> tuple[bool, dict]:
        t = calendar[i]
        detail: dict = {"signal_date": str(t.date()), "signal_session_index": i}
        if i + MAX_HORIZON >= len(calendar):
            return False, {**detail, "reason": "forward_label_endpoint_unavailable"}
        horizons = {}
        starts = []
        for period, h in FORWARD_WINDOWS.items():
            cutoff_i = i - h
            if cutoff_i < 0:
                return False, {**detail, "reason": f"{period}_purge_history_unavailable"}
            train_calendar_start = calendar[cutoff_i] - pd.DateOffset(months=DEFAULT_TRAIN_MONTHS)
            train_i = int(calendar.searchsorted(train_calendar_start))
            n_train = cutoff_i - train_i + 1
            if n_train < MIN_TRAIN_DATES:
                return False, {**detail, "reason": f"{period}_training_dates_below_minimum"}
            starts.append(train_i)
            horizons[period] = {
                "label_horizon_sessions": h,
                "label_cutoff": str(calendar[cutoff_i].date()),
                "rolling_training_calendar_start": str(train_calendar_start.date()),
                "first_training_session": str(calendar[train_i].date()),
                "training_session_count": n_train,
                "forward_label_end": str(calendar[i + h].date()),
            }
        first_train_i = min(starts)
        warmup_i = first_train_i - FEATURE_WARMUP
        if warmup_i < 0:
            return False, {**detail, "reason": "factor_warmup_unavailable"}
        bad_count = bad_prefix[i + MAX_HORIZON + 1] - bad_prefix[warmup_i]
        if bad_count:
            first_bad = next(j for j in range(warmup_i, i + MAX_HORIZON + 1) if not full[j])
            return False, {
                **detail,
                "reason": "missing_or_invalid_sector_session",
                "factor_warmup_start": str(calendar[warmup_i].date()),
                "first_bad_session": str(calendar[first_bad].date()),
                "bad_session_count_in_required_window": bad_count,
            }
        return True, {
            **detail,
            "factor_warmup_start": str(calendar[warmup_i].date()),
            "factor_warmup_prior_sessions": FEATURE_WARMUP,
            "horizons": horizons,
            "max_horizon_label_endpoint": str(calendar[i + MAX_HORIZON].date()),
        }

    eligible = [(i, detail[1]) for i in range(len(calendar)) if (detail := _check(i))[0]]
    indices = [i for i, _ in eligible]
    if indices and indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("signal-eligible dates are disjoint; no single continuous research range")
    start = str(calendar[indices[0]].date()) if indices else None
    end = str(calendar[indices[-1]].date()) if indices else None
    before = _check(indices[0] - 1)[1] if indices and indices[0] else None
    counts = frame.groupby("sector_code")["date"].nunique()
    missing_by_sector = {code: len(calendar) - int(counts.get(code, 0)) for code in sorted(codes)}
    return {
        "run_type": RUN_TYPE,
        "executable": False,
        "strict_pit": False,
        "sector_data_admission": ADMISSION,
        "data_snapshot_id": metadata.get("data_snapshot_id"),
        "raw_common_start": str(common_start.date()),
        "raw_common_end": str(common_end.date()),
        "sector_count": len(codes),
        "calendar_session_count": len(calendar),
        "all_sector_valid_session_count": int(full.sum()),
        "incomplete_or_invalid_session_count": len(bad_positions),
        "last_incomplete_session": str(calendar[bad_positions[-1]].date())
        if bad_positions
        else None,
        "first_full_session_after_last_gap": (
            str(calendar[bad_positions[-1] + 1].date())
            if bad_positions and bad_positions[-1] + 1 < len(calendar)
            else None
        ),
        "sector_801193_missing_common_sessions": missing_by_sector.get("801193"),
        "invalid_ohlc_in_common": int((~frame["is_valid_ohlc"]).sum()),
        "source_invalid_ohlc_total": metadata.get("invalid_ohlc_count"),
        "factor_warmup_prior_sessions": FEATURE_WARMUP,
        "feature_count": len(TRAIN_FEATURES_PRICE),
        "ridge_alpha": DEFAULT_ALPHA,
        "rolling_training_months": DEFAULT_TRAIN_MONTHS,
        "minimum_valid_training_days": MIN_TRAIN_DATES,
        "label_horizons_sessions": dict(FORWARD_WINDOWS),
        "fusion_weights": dict(FUSION_WEIGHTS),
        "top_n": DEFAULT_TOP_N,
        "max_label_horizon_and_purge_sessions": MAX_HORIZON,
        "execution_delay_sessions": None,
        "old_research_eligible_start": metadata.get("research_eligible_start"),
        "old_research_eligible_end": metadata.get("research_eligible_end"),
        "signal_only_eligible_start": start,
        "signal_only_eligible_end": end,
        "signal_only_session_count": len(indices),
        "old_range_matches_signal_only": (
            start == metadata.get("research_eligible_start")
            and end == metadata.get("research_eligible_end")
        ),
        "start_derivation": eligible[0][1] if eligible else None,
        "previous_session_rejection": before,
        "end_derivation": eligible[-1][1] if eligible else None,
        "signal_constraints": [
            "canonical sector common trading calendar",
            "all 124 sectors observed with valid OHLC through feature, training, signal and label windows",
            "120 prior sessions for factor warmup",
            "6 calendar months rolling training and >=30 valid training dates",
            "10/40/120-session forward labels and per-horizon training-label purge",
            "120 future sessions to realize the longest evaluation label",
        ],
        "excluded_execution_constraints": [
            "ETF mapping",
            "ETF listing",
            "ETF tradability",
            "next-session ETF execution",
            "ETF costs and fills",
        ],
    }


def load_and_audit(processed_dir: Path) -> dict:
    """Use only SHA-verified canonical sector files; no ETF or network access."""
    meta_path = processed_dir / "sector_admission.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    catalog = load_sector_catalog(processed_dir)
    panel = load_sector_panel(
        catalog["sector_code"].astype(str).tolist(),
        metadata["common_start_date"],
        metadata["common_end_date"],
        processed_dir=processed_dir,
        allow_invalid_for_audit=True,
    )
    result = audit_signal_range(panel, catalog["sector_code"].astype(str).tolist(), metadata)
    if result["signal_only_eligible_start"] is None:
        return result
    first = pd.Timestamp(result["signal_only_eligible_start"])
    warmup = pd.Timestamp(result["start_derivation"]["factor_warmup_start"])
    calendar = pd.DatetimeIndex(sorted(panel.loc[panel["date"] <= first, "date"].unique()))
    boundaries = {
        period: temporal_boundaries(calendar, first, h, DEFAULT_TRAIN_MONTHS)
        for period, h in FORWARD_WINDOWS.items()
    }
    valid_dates_by_period = {
        period: {day for day in calendar if b.train_start <= day <= b.label_cutoff}
        for period, b in boundaries.items()
        if b is not None
    }
    if len(valid_dates_by_period) != len(FORWARD_WINDOWS):
        raise ValueError("first signal lacks a horizon-specific training boundary")
    ready_at_signal = 0
    for code in catalog["sector_code"].astype(str):
        sector = panel.loc[
            panel["sector_code"].eq(code) & panel["date"].between(warmup, first),
            ["date", "open", "high", "low", "close", "volume", "amount"],
        ].set_index("date")
        if not sector.index.is_monotonic_increasing or not sector.index.is_unique:
            raise ValueError(f"{code}: sector frame dates invalid")
        features = compute_all_price_features(sector, include_rsrs=False)
        feature_ready = pd.Series(
            np.isfinite(features[TRAIN_FEATURES_PRICE].to_numpy()).all(axis=1),
            index=features.index,
        )
        ready_at_signal += bool(feature_ready.get(first, False))
        for period, h in FORWARD_WINDOWS.items():
            labels = make_forward_label(sector["close"], h, calendar=calendar)
            good = set(features.index[feature_ready & labels.notna()])
            valid_dates_by_period[period].intersection_update(good)
    counts = {period: len(dates) for period, dates in valid_dates_by_period.items()}
    if ready_at_signal != len(catalog) or any(n < MIN_TRAIN_DATES for n in counts.values()):
        raise ValueError("first signal fails actual feature/realized-label training eligibility")
    result["first_signal_feature_ready_sector_count"] = ready_at_signal
    result["first_signal_actual_valid_training_days"] = counts
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector-dir", type=Path, default=Path("data/processed/shenwan"))
    args = parser.parse_args()
    print(json.dumps(load_and_audit(args.sector_dir), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

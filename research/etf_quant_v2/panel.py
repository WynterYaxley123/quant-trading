"""Factual membership coverage and reusable industry features, outside Git."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from strategies.etf_quant.config import FACTORS_19
from strategies.etf_quant.domain.industry_level import load_taxonomy
from strategies.etf_quant.factors import compute_close_factors

from .coverage import digest, external_directory, scan
from .recovery import write_json


def reconstruction_completeness(
    root: Path, intervals: pl.DataFrame, identities: pl.DataFrame
) -> list[dict[str, Any]]:
    result = []
    for file in sorted((root / "rosters").glob("*.json")):
        if ".failure." in file.name:
            continue
        roster = json.loads(file.read_text())
        day = date.fromisoformat(roster["date"])
        members = (
            intervals.filter(pl.col("start_date") <= day)
            .sort("start_date")
            .unique("symbol", keep="last")
        )
        symbols = set(members.filter(pl.col("industry").is_not_null())["symbol"].to_list())
        actual = set(roster["symbols"])
        identified = identities.filter(pl.col("symbol").is_in(list(actual)))
        excluded = actual - symbols
        result.append(
            {
                "date": str(day),
                "year": day.year,
                "actual_roster": len(actual),
                "classified_roster": len(actual & symbols),
                "completeness_ratio": len(actual & symbols) / len(actual) if actual else None,
                "unclassified_roster": len(excluded),
                "identified_roster": identified.height,
                "roster_sha256": digest(file),
                "limitation": "ANNUAL_SH_SZ_ROSTER_CHECK;NO_INDEPENDENT_HISTORICAL_ASSIGNMENT_VERIFICATION",
            }
        )
    return result


def build_panel(
    dataset: Path, lake: Path, output: Path, *, end: date = date(2026, 9, 24)
) -> dict[str, Any]:
    """Freeze only factual artifacts here; label access is phase-gated by engine."""
    from cnequity.adapters.calendar.exchange_calendar import build_trading_calendar

    external_directory(output)
    recovery = json.loads((dataset / "recovery.json").read_text())
    membership = pl.read_parquet(dataset / "membership.parquet")
    identities = pl.read_parquet(dataset / "instruments.parquet")
    taxonomy = load_taxonomy()
    mapping = pl.DataFrame(
        {
            "industry_code": list(taxonomy.level3_to_level2),
            "industry": list(taxonomy.level3_to_level2.values()),
        }
    )
    intervals = membership.join(mapping, on="industry_code", how="left").sort(
        ["symbol", "start_date"]
    )
    completeness = reconstruction_completeness(dataset, intervals, identities)
    quality = {r["year"]: r["completeness_ratio"] for r in completeness}
    calendar = build_trading_calendar(date.fromisoformat(recovery["start"]), end).filter(
        pl.col("is_trading")
    )
    dates: list[date] = calendar["trade_date"].to_list()
    sessions = pl.DataFrame({"trade_date": dates, "session_index": range(len(dates))})
    # Private recovered bars are complemented by factual canonical bars, including
    # delisted history and the later Validation/Final-OOS raw-data reserve.
    # Never load the lake's derived industry_index or any old performance output.
    bar_paths = sorted((dataset / "bars").glob("*.parquet"))
    recovered = pl.concat(
        [
            pl.read_parquet(p).with_columns(pl.lit("RECOVERED_TDX").alias("bar_source"))
            for p in bar_paths
        ],
        how="diagonal_relaxed",
    )
    original = (
        scan(lake / "curated", "daily_bars")
        .filter(pl.col("trade_date").is_between(dates[0], end))
        .select(
            "symbol",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            pl.col("source").alias("bar_source"),
        )
        .collect()
    )
    bars = pl.concat([original, recovered], how="diagonal_relaxed").unique(
        ["symbol", "trade_date"], keep="last"
    )
    factors = []
    for p in sorted((dataset / "factors").glob("*.parquet")):
        factors.append(pl.read_parquet(p).with_columns(pl.lit(p.stem).alias("symbol")))
    events = pl.concat(factors, how="diagonal_relaxed").sort(["symbol", "trade_date"])
    # Sparse official provider event factors apply backward-as-of only. Missing
    # history is never replaced by a guessed multiplier or a future event.
    adjusted = (
        bars.sort(["symbol", "trade_date"])
        .join_asof(
            events, on="trade_date", by="symbol", strategy="backward", check_sortedness=False
        )
        .join(sessions, on="trade_date", how="inner")
        .sort(["symbol", "session_index"])
    )
    adjusted = adjusted.with_columns((pl.col("close") * pl.col("factor")).alias("adjusted_close"))
    adjusted = adjusted.with_columns(
        pl.when(
            (pl.col("session_index").shift(1).over("symbol") == pl.col("session_index") - 1)
            & (pl.col("factor") > 0)
            & pl.col("factor").is_finite()
            & (pl.col("adjusted_close").shift(1).over("symbol") > 0)
        )
        .then(pl.col("adjusted_close") / pl.col("adjusted_close").shift(1).over("symbol") - 1)
        .otherwise(None)
        .alias("stock_return")
    ).with_columns(
        pl.when(pl.col("stock_return").is_finite() & (pl.col("stock_return").abs() <= 0.5))
        .then(pl.col("stock_return"))
        .otherwise(None)
        .alias("stock_return")
    )
    # Price outliers are quarantined, including possible missed actions. Their
    # exclusion remains visible against the full reconstructed denominator.
    stocks = identities.filter(pl.col("asset_type") == "stock").select(
        "symbol", "list_date", "delist_date"
    )
    adjusted = adjusted.join(stocks, on="symbol", how="inner")
    adjusted = adjusted.filter(
        (pl.col("list_date").is_null() | (pl.col("list_date") <= pl.col("trade_date")))
        & (pl.col("delist_date").is_null() | (pl.col("delist_date") >= pl.col("trade_date")))
    )
    coverage_dir = output / "coverage"
    coverage_dir.mkdir(exist_ok=True)
    summary_frames = []
    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for year in sorted({d.year for d in dates}):
        days = sessions.filter(pl.col("trade_date").dt.year() == year)
        spine = (
            days.join(stocks, how="cross")
            .filter(
                (pl.col("list_date").is_null() | (pl.col("list_date") <= pl.col("trade_date")))
                & (
                    pl.col("delist_date").is_null()
                    | (pl.col("delist_date") >= pl.col("trade_date"))
                )
            )
            .sort(["symbol", "trade_date"])
        )
        universe = spine.join_asof(
            intervals.select("symbol", pl.col("start_date").alias("effective_date"), "industry"),
            left_on="trade_date",
            right_on="effective_date",
            by="symbol",
            strategy="backward",
            check_sortedness=False,
        )
        universe = (
            universe.join(
                adjusted.select(
                    "symbol", "trade_date", "close", "factor", "stock_return", "bar_source"
                ),
                on=["symbol", "trade_date"],
                how="left",
            )
            .with_columns(
                pl.when(pl.col("industry").is_null())
                .then(pl.lit("D"))
                .when(
                    (pl.col("trade_date") >= date(2021, 7, 31))
                    & pl.lit((quality.get(year, 0) or 0) >= 0.95)
                )
                .then(pl.lit("B"))
                .otherwise(pl.lit("C"))
                .alias("membership_tier"),
                pl.when(pl.col("list_date").is_null())
                .then(pl.lit("UNKNOWN_LISTING_BOUNDARY"))
                .otherwise(pl.lit("WITHIN_RECORDED_LISTING_BOUNDS"))
                .alias("listing_state"),
                pl.col("close").is_not_null().alias("market_bar_available"),
                ((pl.col("factor") > 0) & pl.col("factor").is_finite())
                .fill_null(False)
                .alias("adjustment_exact"),
                pl.col("stock_return").is_not_null().alias("factor_eligible"),
                pl.lit("OFFICIAL_SWS_INTERVAL_WORKBOOK").alias("membership_source"),
            )
            .with_columns(
                pl.when(pl.col("industry").is_null())
                .then(pl.lit("MEMBERSHIP_UNSUPPORTED"))
                .when(pl.col("close").is_null())
                .then(pl.lit("BAR_MISSING"))
                .when(~pl.col("adjustment_exact"))
                .then(pl.lit("ADJUSTMENT_MISSING"))
                .when(pl.col("stock_return").is_null())
                .then(pl.lit("RETURN_GAP_OR_OUTLIER"))
                .otherwise(None)
                .alias("rejection_reason"),
                *[
                    (pl.col("session_index") + h < len(dates)).alias(f"target_calendar_mature_h{h}")
                    for h in (10, 40, 80, 120)
                ],
            )
        )
        for row in universe.group_by("membership_tier").len().to_dicts():
            tier_counts[row["membership_tier"]] += row["len"]
        universe.write_parquet(coverage_dir / f"{year}.parquet")
        groups = (
            universe.filter(pl.col("industry").is_not_null())
            .group_by("trade_date", "industry")
            .agg(
                pl.len().alias("eligible"),
                pl.col("stock_return").count().alias("valid"),
                pl.col("stock_return").mean().alias("industry_return"),
                (pl.col("membership_tier") == "B").all().alias("high_confidence"),
            )
            .with_columns((pl.col("valid") / pl.col("eligible")).alias("coverage_ratio"))
            .with_columns(
                ((pl.col("valid") >= 5) & (pl.col("coverage_ratio") >= 0.80)).alias("date_valid")
            )
        )
        summary_frames.append(groups)
        print(json.dumps({"stage": "coverage", "year": year, "rows": universe.height}), flush=True)
    summary = pl.concat(summary_frames).sort(["industry", "trade_date"])
    summary.write_parquet(output / "industry-coverage.parquet")
    # Model universe is selected only from the first 120 observed high-confidence
    # sessions, using coverage, before any candidate performance is calculated.
    high_days = sorted(summary.filter(pl.col("high_confidence"))["trade_date"].unique().to_list())
    if len(high_days) < 120:
        raise ValueError("INSUFFICIENT_HIGH_CONFIDENCE_FACTUAL_SESSIONS")
    universe_cutoff = high_days[119]
    quality_rows = summary.filter(pl.col("trade_date").is_between(high_days[0], universe_cutoff))
    admitted = quality_rows.group_by("industry").agg(
        pl.col("date_valid").mean().alias("ratio"), pl.col("valid").min().alias("minimum")
    )
    industries = sorted(
        admitted.filter((pl.col("ratio") >= 0.95) & (pl.col("minimum") >= 5))["industry"].to_list()
    )
    if len(industries) < 12:
        raise ValueError("NO_DEFENSIBLE_CROSS_SECTIONAL_MODEL_UNIVERSE")
    arrays: dict[str, np.ndarray] = {}
    all_days = pd.DatetimeIndex(dates)
    for mode in ("HIGH_CONFIDENCE", "EXTENDED_HISTORY"):
        features = np.full((len(dates), len(industries), len(FACTORS_19)), np.nan)
        closes = np.full((len(dates), len(industries)), np.nan)
        segments = np.full((len(dates), len(industries)), -1, dtype=np.int64)
        for j, industry in enumerate(industries):
            values = summary.filter(pl.col("industry") == industry).to_dict(as_series=False)
            frame = (
                pd.DataFrame(values)
                .set_index(pd.to_datetime(values["trade_date"]))
                .reindex(all_days)
            )
            valid = frame["date_valid"].fillna(False)
            if mode == "HIGH_CONFIDENCE":
                valid &= frame["high_confidence"].fillna(False)
            returns = frame["industry_return"].where(valid)
            segment = (~valid).cumsum()
            close = (1 + returns).groupby(segment).cumprod() * 1000
            closes[:, j] = close.to_numpy()
            segments[:, j] = segment.to_numpy()
            features[:, j, :] = compute_close_factors(close).to_numpy()
        arrays[mode + "_X"], arrays[mode + "_close"], arrays[mode + "_segments"] = (
            features,
            closes,
            segments,
        )
    np.savez_compressed(
        output / "panel.npz",
        HIGH_CONFIDENCE_X=arrays["HIGH_CONFIDENCE_X"],
        HIGH_CONFIDENCE_close=arrays["HIGH_CONFIDENCE_close"],
        HIGH_CONFIDENCE_segments=arrays["HIGH_CONFIDENCE_segments"],
        EXTENDED_HISTORY_X=arrays["EXTENDED_HISTORY_X"],
        EXTENDED_HISTORY_close=arrays["EXTENDED_HISTORY_close"],
        EXTENDED_HISTORY_segments=arrays["EXTENDED_HISTORY_segments"],
    )
    # Original factual inputs are content-bound, including later raw reserve rows.
    source_files = {
        str(p.relative_to(lake)): digest(p)
        for name in ("daily_bars", "industry_members", "instruments")
        for p in sorted((lake / "curated" / name).rglob("*.parquet"))
    }
    result = {
        "start": str(dates[0]),
        "end": str(dates[-1]),
        "dates": list(map(str, dates)),
        "trading_sessions": len(dates),
        "history_years": (dates[-1] - dates[0]).days / 365.2425,
        "industries": industries,
        "universe_coverage_cutoff": str(universe_cutoff),
        "factors": list(FACTORS_19),
        "membership_tier_rows": tier_counts,
        "annual_roster_completeness": completeness,
        "tier_a_overlap": None,
        "tier_a_overlap_reason": "NO_INDEPENDENT_HISTORICAL_PUBLICATION_SNAPSHOT_AVAILABLE",
        "coverage_matrix_rows": sum(tier_counts.values()),
        "coverage_gate": {"minimum_valid": 5, "ratio": 0.80},
        "recovery_snapshot_sha256": recovery["snapshot_sha256"],
        "panel_sha256": digest(output / "panel.npz"),
        "coverage_sha256": {p.name: digest(p) for p in sorted(coverage_dir.glob("*.parquet"))},
        "source_files": source_files,
        "tier_d_used": False,
        "limitations": [
            "Annual SH/SZ roster coverage is a completeness proxy, not an assignment proof.",
            "Pre-2021 taxonomy is explicitly retrospective Tier C.",
            "Unclassified/delisted symbols remain excluded; survivorship exposure is measured.",
            "Raw finalized reserve facts are normalized; Final-OOS labels and performance are denied.",
        ],
    }
    result["data_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    write_json(output / "panel.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--lake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_panel(args.dataset, args.lake, args.output)
    print(
        json.dumps({k: v for k, v in result.items() if k not in ("dates", "source_files")}),
        flush=True,
    )


if __name__ == "__main__":
    main()

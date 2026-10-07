"""Inspect factual inputs before performance; private panels stay outside Git."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from strategies.etf_quant.factors import compute_close_factors

from .protocol import eligible_signals, split_sessions


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n"
    )


def taxonomy(workbook: Path) -> dict[str, Any]:
    """Read explicit hierarchy rows; never infer a historical parent from a prefix."""
    table = pd.read_excel(workbook, dtype={"行业代码": str})
    industries = [
        {"industry_code": row["行业代码"], "industry_name": row["一级行业名称"]}
        for row in table.to_dict("records")
        if row["行业代码"].endswith("0000")
    ]
    parents = {r["industry_name"]: r["industry_code"] for r in industries}
    if len(parents) != len(industries):
        raise ValueError("UNIQUE_OFFICIAL_PARENT_NAMES_REQUIRED")
    hierarchy = []
    for row in table.to_dict("records"):
        code = row["行业代码"]
        if code.endswith("0000"):
            continue
        else:
            if row["一级行业名称"] not in parents:
                raise ValueError("EXPLICIT_HIERARCHY_REQUIRED")
            hierarchy.append({"child_code": code, "parent_code": parents[row["一级行业名称"]]})
    return {
        "classification_version": "SWCLASS2021",
        "industry_level": 1,
        "source_url": "https://www.swsresearch.com/swindex/pdf/SwClass2021/SwClassCode_2021.xls",
        "source_sha256": sha(workbook),
        "industries": industries,
        "hierarchy": hierarchy,
        "historical_version_boundary": "2021-07-31",
        "boundary_source": "https://wxweb.swsresearch.com/swsreport/2021_08/328340.pdf",
        "limitation": "Version-specific reconstruction, not contemporaneous availability proof.",
    }


def audit(lake: Path, recovered: Path, evidence: Path, output: Path) -> dict[str, Any]:
    tax = taxonomy(evidence / "SwClassCode_2021.xls")
    write(output / "taxonomy.json", tax)
    source = json.loads((recovered / "membership-source.json").read_text())
    if sha(recovered / "membership.parquet") != source["parsed_sha256"]:
        raise ValueError("MEMBERSHIP_BYTES_MISMATCH")
    if sha(recovered / "membership-source.xls") != source["sha256"]:
        raise ValueError("MEMBERSHIP_SOURCE_MISMATCH")
    membership = pl.read_parquet(recovered / "membership.parquet")
    hierarchy = pl.DataFrame(tax["hierarchy"]).rename(
        {"child_code": "industry_code", "parent_code": "industry"}
    )
    membership = membership.join(hierarchy, on="industry_code", how="left").sort(
        ["symbol", "start_date"]
    )
    instruments = (
        pl.read_parquet(recovered / "instruments.parquet")
        .filter(pl.col("asset_type") == "stock")
        .select("symbol", "list_date", "delist_date")
    )
    calendar_files = sorted((lake / "curated/trading_calendar").glob("*/*.parquet"))
    calendar = (
        pl.concat([pl.read_parquet(p) for p in calendar_files])
        .filter(pl.col("is_trading") & (pl.col("trade_date") >= date(2021, 7, 31)))
        .select("trade_date")
        .unique()
        .sort("trade_date")
    )
    # Verify recovered source receipts. Neither existing research panels nor sealed results are read.
    input_hashes = {}
    recovered_frames: list[pl.DataFrame] = []
    factor_frames: list[pl.DataFrame] = []
    for kind, frames in (("bars", recovered_frames), ("factors", factor_frames)):
        for path in sorted((recovered / kind).glob("*.parquet")):
            receipt = json.loads(path.with_suffix(".json").read_text())
            checksum = sha(path)
            if (
                receipt["sha256"] != checksum
                or receipt["pin"] != "1650e384a3fd1f67a70144a489acc91432f1df27"
            ):
                raise ValueError("RECOVERED_SOURCE_RECEIPT_MISMATCH")
            input_hashes[f"{kind}/{path.name}"] = checksum
            frame = pl.read_parquet(path)
            if kind == "factors":
                frame = frame.with_columns(pl.lit(path.stem).alias("symbol"))
            frames.append(frame)
    bars = pl.concat(recovered_frames)
    columns = ["symbol", "trade_date", "close", "volume"]
    originals = (
        pl.scan_parquet(
            sorted((lake / "curated/daily_bars").glob("*/*.parquet")), hive_partitioning=False
        )
        .select(columns)
        .filter(pl.col("trade_date") >= date(2021, 7, 31))
        .collect()
    )
    bars = pl.concat([originals, bars.select(columns)]).unique(
        ["symbol", "trade_date"], keep="last"
    )
    cutoff = bars["trade_date"].max()
    calendar = calendar.filter(pl.col("trade_date") <= cutoff).with_row_index("session_index")
    dates = calendar["trade_date"].to_list()
    events = pl.concat(factor_frames).sort(["symbol", "trade_date"])
    adjusted = (
        bars.sort(["symbol", "trade_date"])
        .join_asof(
            events, on="trade_date", by="symbol", strategy="backward", check_sortedness=False
        )
        .join(calendar, on="trade_date", how="inner")
        .sort(["symbol", "session_index"])
    )
    adjusted = adjusted.with_columns((pl.col("close") * pl.col("factor")).alias("adj_close"))
    adjusted = adjusted.with_columns(
        pl.when(
            (pl.col("session_index").shift(1).over("symbol") == pl.col("session_index") - 1)
            & (pl.col("factor") > 0)
            & pl.col("factor").is_finite()
            & (pl.col("adj_close").shift(1).over("symbol") > 0)
            & (pl.col("volume") > 0)
            & (pl.col("volume").shift(1).over("symbol") > 0)
        )
        .then(pl.col("adj_close") / pl.col("adj_close").shift(1).over("symbol") - 1)
        .otherwise(None)
        .alias("stock_return")
    ).with_columns(
        pl.when(pl.col("stock_return").is_finite() & (pl.col("stock_return").abs() <= 0.5))
        .then(pl.col("stock_return"))
        .otherwise(None)
        .alias("stock_return")
    )
    summaries, tier_counts = [], {"A": 0, "B": 0, "C": 0, "D": 0}
    unknown_active = 0
    for year in sorted({d.year for d in dates}):
        spine = (
            calendar.filter(pl.col("trade_date").dt.year() == year)
            .join(instruments, how="cross")
            .filter(
                pl.col("list_date").is_not_null()
                & (pl.col("list_date") <= pl.col("trade_date"))
                & (
                    pl.col("delist_date").is_null()
                    | (pl.col("delist_date") >= pl.col("trade_date"))
                )
            )
        )
        spine = spine.sort(["symbol", "trade_date"]).join_asof(
            membership.select("symbol", pl.col("start_date").alias("effective_date"), "industry"),
            left_on="trade_date",
            right_on="effective_date",
            by="symbol",
            strategy="backward",
            check_sortedness=False,
        )
        supported = spine.filter(pl.col("industry").is_not_null())
        rejected = spine.height - supported.height
        unknown_active += rejected
        tier_counts["C"] += supported.height
        tier_counts["D"] += rejected
        joined = supported.join(
            adjusted.select("symbol", "trade_date", "stock_return"),
            on=["symbol", "trade_date"],
            how="left",
        )
        summaries.append(
            joined.group_by(["trade_date", "industry"]).agg(
                pl.len().alias("denominator"),
                pl.col("stock_return").count().alias("valid"),
                pl.col("stock_return").mean().alias("return"),
            )
        )
    coverage = pl.concat(summaries).sort(["industry", "trade_date"])
    coverage = coverage.with_columns((pl.col("valid") / pl.col("denominator")).alias("coverage"))
    admitted = coverage.filter((pl.col("valid") >= 5) & (pl.col("coverage") >= 0.8))
    taxonomy_codes = sorted(r["industry_code"] for r in tax["industries"])
    valid_day_counts = {
        row["industry"]: row["len"] for row in admitted.group_by("industry").len().to_dicts()
    }
    # Preserve the existing recursive-series contract: no restart after a factual gap.
    # The first exchange session has no previous close and is only a seed boundary.
    codes = [c for c in taxonomy_codes if valid_day_counts.get(c, 0) == len(dates) - 1]
    if not codes:
        raise ValueError("NO_COVERAGE_ADMITTED_INDUSTRIES")
    matrix = np.full((len(dates), len(codes)), np.nan)
    date_index, code_index = (
        {d: i for i, d in enumerate(dates)},
        {c: i for i, c in enumerate(codes)},
    )
    for row in admitted.to_dicts():
        if row["industry"] in code_index:
            matrix[date_index[row["trade_date"]], code_index[row["industry"]]] = row["return"]
    # Only continuously admitted industries enter this array; no rebasing after gaps.
    closes = np.full_like(matrix, np.nan)
    for col in range(len(codes)):
        level = 100.0
        for i in range(len(dates)):
            if np.isfinite(matrix[i, col]):
                level *= 1 + matrix[i, col]
                closes[i, col] = level
            else:
                level = 100.0
    features = np.stack(
        [
            compute_close_factors(pd.Series(closes[:, j], index=pd.DatetimeIndex(dates))).to_numpy()
            for j in range(len(codes))
        ],
        axis=1,
    )
    full_features = np.isfinite(features).all(axis=(1, 2))
    exact120 = np.array(
        [
            np.isfinite(matrix[i + 1 : i + 121]).all() and i + 120 < len(dates)
            for i in range(len(dates))
        ]
    )
    eligible = np.flatnonzero(full_features & exact120)
    # A first forecast needs a full 12-month span and >=30 complete mature training cross sections.
    eligible_training = [
        i
        for i in eligible
        if i >= 120
        and dates[i] >= (pd.Timestamp(dates[0]) + pd.DateOffset(months=12)).date()
        and np.sum(full_features[: i - 119] & exact120[: i - 119]) >= 30
    ]
    feasible = len(codes) >= 10 and len(eligible_training) >= 126 + 120 + 126 + 120 + 126
    # Purges count exchange sessions, not filtered eligible dates: this upper bound cannot authorize a split.
    report = {
        "schema_version": 1,
        "family_id": "swl1_ridge_v1",
        "performance_computed": False,
        "current_taxonomy_size": len(taxonomy_codes),
        "taxonomy_source": tax["source_url"],
        "taxonomy_sha256": tax["source_sha256"],
        "taxonomy_version": "SWCLASS2021",
        "history_start": str(dates[0]),
        "history_end": str(dates[-1]),
        "trading_sessions": len(dates),
        "membership_source": source,
        "membership_interval_rows": membership.height,
        "membership_tier_rows": tier_counts,
        "tier_count_unit": "listed stock/exchange-session rows",
        "historical_membership_confidence": "RECONSTRUCTED",
        "unknown_active_membership_rows": unknown_active,
        "minimum_constituents": 5,
        "minimum_coverage": 0.8,
        "coverage_quantiles": {
            str(q): coverage["coverage"].quantile(q) for q in (0, 0.25, 0.5, 0.75, 1)
        },
        "valid_industry_days": admitted.height,
        "total_industry_days": len(taxonomy_codes) * len(dates),
        "coverage_admission_rule": "Every post-seed industry day valid; >=5 exact adjacent constituents and >=80% daily constituent coverage. No recursive restart after a gap.",
        "coverage_admitted_industries": codes,
        "industry_valid_day_counts": valid_day_counts,
        "full_feature_sessions": int(full_features.sum()),
        "full_h120_mature_sessions": int(exact120.sum()),
        "eligible_training_signal_sessions_upper_bound": len(eligible_training),
        "latest_factual_cutoff": str(dates[-1]),
        "latest_fully_mature_h120_signal_date": str(dates[eligible[-1]]) if len(eligible) else None,
        "realized_series_type": "RECONSTRUCTED_SWL1_EQUAL_WEIGHT",
        "input_hash_manifest_sha256": hashlib.sha256(
            json.dumps(input_hashes, sort_keys=True).encode()
        ).hexdigest(),
        "scaling_policy": "STANDARDIZED",
        "model_universe_size": len(codes) if feasible else 0,
        "research_feasible_upper_bound": feasible,
        "limitations": [
            "Tier A = 0; later observation is not historical availability.",
            "No independent historical assignment verification.",
            "Legacy/unmapped classification spells excluded; current hierarchy never backfilled before 2021-07-31.",
            "Suspensions and missing exact adjacent returns remain missing.",
            "Data redistribution rights unverified; no market payload enters Git.",
        ],
    }
    np.savez_compressed(
        output / "factual_panel.npz",
        returns=matrix,
        features=features,
        closes=closes,
        dates=np.array([str(d) for d in dates]),
        codes=np.array(codes),
    )
    write(output / "input_hashes.json", input_hashes)
    report = finalize_feasibility(report, features, matrix, [str(d) for d in dates])
    write(output / "data_feasibility.json", report)
    return report


def finalize_feasibility(
    report: dict[str, Any], features: np.ndarray, returns: np.ndarray, dates: list[str]
) -> dict[str, Any]:
    complete = np.isfinite(features).all(axis=(1, 2))
    mature = np.array(
        [
            i + 120 < len(returns) and np.isfinite(returns[i + 1 : i + 121]).all()
            for i in range(len(returns))
        ]
    )
    mature_signals = np.flatnonzero(complete & mature)
    windows = {}
    for months in (12, 24):
        eligible = eligible_signals(features, returns, dates, months)
        split = split_sessions(dates, eligible)
        windows[str(months)] = {
            "eligible_signal_sessions": len(eligible),
            "split": split,
            "status": "ELIGIBLE" if split else "TECHNICALLY_INELIGIBLE",
        }
    feasible = len(report["coverage_admitted_industries"]) >= 10 and any(
        w["split"] for w in windows.values()
    )
    return {
        **report,
        "research_feasible": feasible,
        "training_windows": windows,
        "scientific_status": "READY_FOR_PREREGISTRATION"
        if feasible
        else "NOT_RESEARCHABLE_WITH_CURRENT_DATA",
        "minimum_training_dates": 30,
        "minimum_development_signals": 126,
        "minimum_phase_signals": 126,
        "purge_exchange_sessions": 120,
        "model_universe_size": len(report["coverage_admitted_industries"]),
        "full_feature_sessions": int(complete.sum()),
        "full_h120_mature_sessions": int(mature.sum()),
        "eligible_training_signal_sessions_upper_bound": None,
        "latest_fully_mature_h120_signal_date": dates[mature_signals[-1]]
        if len(mature_signals)
        else None,
        "feasibility_reason": "EXACT_WINDOW_AND_PURGED_SPLIT_ADMISSION"
        if feasible
        else "INSUFFICIENT_EXACT_WINDOW_ELIGIBLE_HISTORY_FOR_PURGED_PHASES",
    }


if __name__ == "__main__":
    print(
        json.dumps(
            audit(Path("/lake"), Path("/recovered"), Path("/research/evidence"), Path("/research")),
            indent=2,
        )
    )

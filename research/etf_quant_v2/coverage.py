"""Read-only CNEquity capability audit, with an external rejected-row inventory.

Effective classification dates are not publication/availability evidence. The
pinned schema cannot certify historical membership, so this audit never promotes
its reconstructed snapshots to a strict-PIT research denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import polars as pl

PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"
SOURCE_FILES = (
    "src/cnequity/adapters/sw/industry_history.py",
    "src/cnequity/domain/schemas.py",
    "src/cnequity/steps/reference.py",
    "src/cnequity/steps/structure.py",
    "src/cnequity/domain/datasets.py",
    "LICENSE",
)
REASONS = (
    "INSTRUMENT_UNRESOLVED",
    "MEMBERSHIP_UNSUPPORTED",
    "PRE_LISTING_EXPECTED",
    "POST_DELISTING_EXPECTED",
    "BAR_MISSING",
    "BAR_INVALID",
    "ADJUSTMENT_MISSING",
    "ADJUSTMENT_NON_EXACT",
    "SOURCE_UNAVAILABLE",
    "CODE_MAPPING_GAP",
    "PUBLICATION_NOT_FINALIZED",
    "UNSUPPORTED_ASSET_CLASS",
    "UNKNOWN",
)


def digest(path: Path) -> str:
    """Hash bytes without loading market files into memory."""
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def external_directory(path: Path) -> Path:
    """Reject repository storage, including resolved links into any checkout."""
    result = path.resolve(strict=True)
    if not result.is_dir() or any((p / ".git").exists() for p in (result, *result.parents)):
        raise ValueError("EXTERNAL_DIRECTORY_REQUIRED")
    return result


def immutable_bytes(path: Path, value: bytes) -> None:
    """Idempotent publication; changed bytes require a new identity."""
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError("IMMUTABLE_ARTIFACT_CONFLICT")
        return
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    # A single audit owns this external namespace. No upstream publication is changed.
    temporary.replace(path)


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, default=str, allow_nan=False) + "\n"
    ).encode()


def scan(root: Path, dataset: str) -> pl.LazyFrame:
    files = sorted(root.joinpath(dataset).rglob("*.parquet"))
    if not files:
        raise ValueError("DATASET_UNAVAILABLE:" + dataset)
    return pl.scan_parquet(files, hive_partitioning=False)


def lake_fingerprint(lake: Path) -> tuple[str, dict[str, str]]:
    """Only inspected factual datasets; sealed/derived industry results are excluded."""
    directories = [
        lake / "curated" / name
        for name in (
            "industry_members",
            "daily_bars",
            "trading_calendar",
            "instruments",
            "index_bars",
            "corporate_actions",
            "trading_status",
        )
    ] + [lake / "derived/adj_factors"]
    hashes = {
        p.relative_to(lake).as_posix(): digest(p)
        for directory in directories
        for p in sorted(directory.rglob("*.parquet"))
    }
    return hashlib.sha256(json_bytes(hashes)).hexdigest(), hashes


def summarize(frame: pl.LazyFrame, day_column: str | None) -> dict[str, Any]:
    schema = frame.collect_schema()
    expressions = [pl.len().alias("rows")]
    if day_column and day_column in schema:
        expressions += [
            pl.col(day_column).min().alias("start"),
            pl.col(day_column).max().alias("end"),
            pl.col(day_column).n_unique().alias("distinct_dates"),
        ]
    if "symbol" in schema:
        expressions.append(pl.col("symbol").n_unique().alias("symbols"))
    if "source" in schema:
        expressions.append(pl.col("source").unique().sort().implode().alias("sources"))
    if "fetched_at" in schema:
        expressions += [
            pl.col("fetched_at").min().alias("first_observed_at"),
            pl.col("fetched_at").max().alias("last_observed_at"),
        ]
    result = frame.select(expressions).collect(engine="streaming").to_dicts()[0]
    result["columns"] = sorted(schema.names())
    result["range_semantics"] = "STORED_OBSERVATIONS_NOT_ADMITTED_RESEARCH_RANGE"
    return result


def audit(lake: Path, source: Path, output: Path) -> dict[str, Any]:
    """Inspect factual tables only; never open derived industry/performance results."""
    lake, output = external_directory(lake), external_directory(output)
    source = source.resolve(strict=True)
    git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
    commit = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output([*git, "status", "--porcelain"], text=True).strip()
    if commit != PIN or dirty:
        raise ValueError("PINNED_SOURCE_BLOCKER")
    if output.is_relative_to(lake) or lake.is_relative_to(output):
        raise ValueError("RESEARCH_OUTPUT_MUST_BE_DISJOINT_FROM_LAKE")
    before, input_hashes = lake_fingerprint(lake)
    components: dict[str, Any] = {}
    curated = lake / "curated"
    members = scan(curated, "industry_members").filter(
        (pl.col("source") == "sw") & (pl.col("classification_system") == "sw")
    )
    frames = {
        "historical_membership": (members, "as_of_date"),
        "stock_bars": (scan(curated, "daily_bars"), "trade_date"),
        "calendar": (scan(curated, "trading_calendar").filter(pl.col("is_trading")), "trade_date"),
        "identities": (scan(curated, "instruments"), None),
        "benchmark": (scan(curated, "index_bars"), "trade_date"),
        "corporate_actions": (scan(curated, "corporate_actions"), "ex_date"),
        "trading_status": (scan(curated, "trading_status"), "trade_date"),
        "adjustments": (scan(lake / "derived", "adj_factors"), "trade_date"),
    }
    for name, (frame, day_column) in frames.items():
        components[name] = summarize(frame, day_column)
    instruments = frames["identities"][0].select("symbol", "asset_type").collect()
    etfs = instruments.filter(pl.col("asset_type") == "etf")["symbol"]
    bars = frames["stock_bars"][0]
    components["etf_bars"] = summarize(
        bars.filter(pl.col("symbol").is_in(etfs.implode())), "trade_date"
    )
    components["amount"] = (
        bars.select(pl.len().alias("rows"), pl.col("amount").null_count().alias("missing_rows"))
        .collect()
        .to_dicts()[0]
    )
    stock_symbols = instruments.filter(pl.col("asset_type") == "stock")["symbol"]
    components["stock_bars"] = summarize(
        bars.filter(pl.col("symbol").is_in(stock_symbols.implode())), "trade_date"
    )
    components["combined_daily_bars"] = summarize(bars, "trade_date")
    start, end = components["etf_bars"].get("start"), components["etf_bars"].get("end")
    if start is not None and end is not None:
        components["current_etf_window_calendar"] = summarize(
            frames["calendar"][0].filter(pl.col("trade_date").is_between(start, end)),
            "trade_date",
        )
    membership_schema = members.collect_schema()
    required = {"available_at", "source_published_at", "valid_from", "valid_to", "history_complete"}
    absent = sorted(required - set(membership_schema.names()))
    if not absent:
        # A future provider contract needs a separate reviewed admission adapter.
        raise ValueError("NEW_MEMBERSHIP_CONTRACT_REQUIRES_REVIEW")
    rows = members.select(
        pl.col("as_of_date").alias("trading_date"),
        pl.col("industry_code").str.slice(0, 4),
        "symbol",
        pl.col("symbol").str.slice(-2).alias("exchange"),
        pl.lit(False).alias("historical_membership_eligible"),
        pl.lit("NOT_EVALUATED_MEMBERSHIP_REJECTED").alias("identity_status"),
        pl.lit("NOT_EVALUATED_MEMBERSHIP_REJECTED").alias("bar_status"),
        pl.lit("NOT_EVALUATED_MEMBERSHIP_REJECTED").alias("adjustment_status"),
        pl.lit(None, dtype=pl.Boolean).alias("exactness"),
        pl.lit("UNKNOWN").alias("listing_status"),
        "source",
        "data_version",
        "fetched_at",
        pl.lit(None, dtype=pl.String).alias("source_published_at"),
        pl.lit(None, dtype=pl.String).alias("available_at"),
        pl.lit("MEMBERSHIP_UNSUPPORTED").alias("invalid_reason"),
        pl.lit("RECONSTRUCTED_SNAPSHOT_INVENTORY_ONLY").alias("observation_contract"),
    )
    source_hashes = {name: digest(source / name) for name in SOURCE_FILES}
    identity = hashlib.sha256(
        json_bytes({"source": source_hashes, "inputs": input_hashes})
    ).hexdigest()
    inventory_path = output / (identity + "-membership-rejections.parquet")
    if inventory_path.exists():
        if not rows.collect(engine="streaming").equals(pl.read_parquet(inventory_path)):
            raise ValueError("IMMUTABLE_REJECTION_INVENTORY_CONFLICT")
    else:
        temporary = inventory_path.with_suffix(".partial")
        rows.sink_parquet(temporary)
        temporary.replace(inventory_path)
    inventory_rows = pl.scan_parquet(inventory_path).select(pl.len()).collect().item()
    after, _ = lake_fingerprint(lake)
    if before != after:
        raise ValueError("CONCURRENT_LAKE_MUTATION_BLOCKER")
    result = {
        "contract": "ETF_QUANT_V2_DATA_CAPABILITY_AUDIT",
        "source_commit": commit,
        "source_hashes": source_hashes,
        "membership_snapshot_identity": identity,
        "lake_snapshot_sha256": before,
        "components": components,
        "strict_pit": False,
        "strict_pit_start": None,
        "strict_pit_end": None,
        "strict_pit_sessions": 0,
        "strict_pit_coverage_ratio": None,
        "limiting_component": "HISTORICAL_MEMBERSHIP",
        "missing_membership_evidence": absent,
        "coverage_matrix_status": "BLOCKED_HISTORICAL_DENOMINATOR_UNPROVEN",
        "rejected_snapshot_inventory": {
            "file": inventory_path.name,
            "sha256": digest(inventory_path),
            "rows": inventory_rows,
            "invalid_reasons": {"MEMBERSHIP_UNSUPPORTED": inventory_rows},
        },
        "reason_taxonomy": REASONS,
        "development_experiments_run": False,
        "validation_opened": False,
        "final_oos_opened": False,
        "sealed_performance_read": False,
    }
    report_identity = hashlib.sha256(json_bytes(result)).hexdigest()
    immutable_bytes(output / (report_identity + "-capability.json"), json_bytes(result))
    immutable_bytes(output / (before + "-input-hashes.json"), json_bytes(input_hashes))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.lake, args.source, args.output)
    sys.stdout.write(json_bytes(result).decode())


if __name__ == "__main__":
    main()

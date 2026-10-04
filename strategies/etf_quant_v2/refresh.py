"""Docker-only, pinned CNEquity factual ETF refresh into an external namespace."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import polars as pl

from strategies.etf_quant.runtime.storage import atomic_bytes, contained, external_root, json_bytes

from .mapping import liquidity_amount
from .runtime import SHANGHAI

PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_source(source: Path) -> None:
    argv = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    if (
        subprocess.check_output([*argv, "rev-parse", "HEAD"], text=True).strip() != PIN
        or subprocess.check_output(
            [*argv, "status", "--porcelain", "--untracked-files=no"], text=True
        ).strip()
    ):
        raise ValueError("PINNED_CNEQUITY_SOURCE_REQUIRED")


def refresh(symbols: list[str], day: date, output: Path, source: Path) -> dict[str, Any]:
    from cnequity.adapters.calendar.exchange_calendar import build_trading_calendar
    from cnequity.adapters.tdx_protocol.client import fetch_daily_bars
    from cnequity.config import Config

    verify_source(source)
    now = datetime.now(SHANGHAI)
    if day > now.date() or day == now.date() and now.time() < time(15, 5):
        raise ValueError("FINALIZED_CLOSED_SESSION_REQUIRED")
    calendar = build_trading_calendar(day - timedelta(days=100), day)
    sessions = calendar.filter(pl.col("is_trading"))["trade_date"].to_list()
    if not sessions or sessions[-1] != day:
        raise ValueError("OFFICIAL_COMPLETED_SESSION_REQUIRED")
    output = external_root(output)
    directory = output / day.isoformat()
    directory.mkdir(exist_ok=True)
    cfg = Config(
        data_root=output / "provider-cache",
        tdx_min_interval_ms=100,
        tdx_connect_timeout_sec=5,
        source_intervals={"tdx_protocol": 0.1},
        source_concurrency={"tdx_protocol": 4},
    )
    start = sessions[-min(40, len(sessions))]

    def one(symbol: str) -> dict[str, Any]:
        # A date-bound complete receipt is reusable; no historical cache backstamp.
        path = directory / (symbol + ".json")
        bars_path = directory / (symbol + ".parquet")
        if path.exists():
            value = json.loads(path.read_bytes())
            if bars_path.exists() and checksum(bars_path) != value["bars_sha256"]:
                raise ValueError("OPERATIONAL_BAR_CACHE_HASH_ERROR")
            if value.get("liquidity_amount") is not None:
                return value
        frame = None
        for _ in range(2):
            try:
                fetched = fetch_daily_bars(
                    [symbol], start, day, config=cfg, backfill=True, allow_mock=False
                )
                if fetched.height:
                    frame = fetched.filter(pl.col("trade_date").is_between(start, day))
                    break
            except (RuntimeError, ValueError, OSError):
                continue
        value = {
            "symbol": symbol,
            "source_commit": PIN,
            "data_cutoff": str(day),
            "observed_at": datetime.now(SHANGHAI).isoformat(),
            "liquidity_amount": None,
            "status": "MISSING_OR_INVALID_FINALIZED_20_SESSION_BARS",
        }
        if frame is not None:
            if (
                set(frame["symbol"].unique()) != {symbol}
                or frame.select("trade_date").is_duplicated().any()
            ):
                raise ValueError("CNEQUITY_BAR_IDENTITY_ERROR")
            frame.write_parquet(bars_path)
            rows = [
                {**r, "trade_date": str(r["trade_date"]), "finalized": r["trade_date"] <= day}
                for r in frame.to_dicts()
            ]
            amount = liquidity_amount(rows, sessions, day)
            value.update(
                bars_sha256=checksum(bars_path),
                rows=frame.height,
                liquidity_amount=amount,
                status="ADMITTED" if amount is not None else value["status"],
            )
        atomic_bytes(path, json_bytes(value))
        return value

    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(one, sorted(set(symbols))))
    result = {
        "source_commit": PIN,
        "data_cutoff": str(day),
        "completed_at": datetime.now(SHANGHAI).isoformat(),
        "symbols_requested": len(records),
        "symbols_admitted": sum(r["liquidity_amount"] is not None for r in records),
        "receipts": records,
        "calendar": list(map(str, sessions)),
        "window": list(map(str, sessions[-20:])),
        "allow_mock": False,
    }
    atomic_bytes(directory / "summary.json", json_bytes(result))
    return result


def verified_snapshot(root: Path) -> dict[str, Any]:
    if contained(root, "manifest.json").stat().st_size > 1024 * 1024:
        raise ValueError("FACTUAL_MANIFEST_SIZE_LIMIT")
    doc = json.loads(contained(root, "manifest.json").read_bytes())
    if doc.get("source_commit") != PIN or doc.get("source_identity") != "CNEQUITY_LOCAL_LAKE_V1":
        raise ValueError("PINNED_FACTUAL_SNAPSHOT_REQUIRED")
    if set(doc["files"]) != {
        "trading_calendar.csv",
        "stock_bars.csv",
        "industry_membership.csv",
        "etf_bars.csv",
        "instruments.csv",
        "trading_status.csv",
        "benchmark_csi300.csv",
    }:
        raise ValueError("CLOSED_FACTUAL_EXPORT_FILE_SET_REQUIRED")
    observed = datetime.fromisoformat(doc["created_at"])
    now = datetime.now(SHANGHAI)
    if (
        observed.tzinfo is None
        or observed > now
        or date.fromisoformat(doc["data_cutoff"]) > now.date()
    ):
        raise ValueError("FUTURE_FACTUAL_SNAPSHOT_DENIED")
    for name, expected in doc["files"].items():
        if checksum(contained(root, name)) != expected:
            raise ValueError("FACTUAL_SNAPSHOT_HASH_ERROR")
    return doc


def with_current_etf_bars(
    loader: Callable[..., pl.DataFrame], symbols: list[str], day: date, output: Path, source: Path
) -> Callable[..., pl.DataFrame]:
    """Inject verified public SDK ETF facts into the existing normalized exporter.

    Stock queries and upstream lake publication stay unchanged. Existing ETF keys
    retain their values; missing keys are supplemented from dated SDK receipts.
    """
    receipt = refresh(symbols, day, output, source)
    frames = []
    for row in receipt["receipts"]:
        if "bars_sha256" not in row:
            continue
        file = contained(output, str(day) + "/" + row["symbol"] + ".parquet")
        if checksum(file) != row["bars_sha256"]:
            raise ValueError("ETF_EXPORT_RECEIPT_HASH_ERROR")
        observed = datetime.fromisoformat(row["observed_at"])
        if (
            row["source_commit"] != PIN
            or row["data_cutoff"] != str(day)
            or observed.tzinfo is None
            or observed > datetime.now(SHANGHAI)
        ):
            raise ValueError("ETF_EXPORT_RECEIPT_IDENTITY_ERROR")
        # Direct public SDK rows have no lake publication provenance. Bind
        # supplemental rows to their actual receipt. The pinned SDK stock/ETF
        # path already converts lots to shares; v2 is that unit contract, not a
        # publication identifier. Keep the receipt identity in separate columns.
        frames.append(
            pl.read_parquet(file).with_columns(
                pl.lit("tdx_protocol").alias("source"),
                pl.lit("v2").alias("data_version"),
                pl.lit(row["bars_sha256"]).alias("sdk_receipt_sha256"),
                pl.lit(PIN).alias("sdk_receipt_source_commit"),
                pl.lit(observed.astimezone(timezone.utc)).alias("fetched_at"),
            )
        )
    current = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()

    def load(dataset: str, **kwargs: Any) -> pl.DataFrame:
        original = loader(dataset, **kwargs)
        requested = kwargs.get("symbols")
        if (
            dataset != "daily_bars"
            or kwargs.get("adjust") is not None
            or not requested
            or not set(requested).issubset(symbols)
            or current.is_empty()
        ):
            return original
        extra = current.filter(
            pl.col("symbol").is_in(requested)
            & pl.col("trade_date").is_between(
                date.fromisoformat(str(kwargs["start"])), date.fromisoformat(str(kwargs["end"]))
            )
        )
        if not original.is_empty():
            extra = extra.join(
                original.select("symbol", "trade_date"), on=["symbol", "trade_date"], how="anti"
            )
        return pl.concat([original, extra], how="diagonal_relaxed").sort("symbol", "trade_date")

    return load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if (args.discovery is None) == (args.registry is None):
        raise ValueError("ONE_EXPLICIT_REGISTRY_OR_DISCOVERY_REQUIRED")
    doc = json.loads((args.discovery or args.registry).read_bytes())
    result = refresh(
        [r["etf_code"] for r in doc["candidates" if args.discovery else "entries"]]
        + ["512880.SH", "159848.SZ"],
        args.day,
        args.output,
        args.source,
    )
    print(
        json.dumps({k: v for k, v in result.items() if k not in ("receipts", "calendar", "window")})
    )


if __name__ == "__main__":
    main()

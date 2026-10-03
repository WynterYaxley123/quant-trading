"""Resumable public CNEquity recovery into an independent external research lake.

No V1 mutation, private credentials, mock provider, or performance-result reader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from .coverage import PIN, digest, external_directory, scan


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n"
    )
    temporary.replace(path)


def store(root: Path, kind: str, symbol: str, frame: pl.DataFrame, source: str) -> None:
    target = root / kind / (symbol + ".parquet")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".partial")
    frame.sort("trade_date").write_parquet(temporary)
    temporary.replace(target)
    write_json(
        target.with_suffix(".json"),
        {
            "sha256": digest(target),
            "rows": frame.height,
            "source": source,
            "pin": PIN,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def cached(root: Path, kind: str, symbol: str) -> bool:
    target = root / kind / (symbol + ".parquet")
    metadata = target.with_suffix(".json")
    if not target.exists() or not metadata.exists():
        return False
    record = json.loads(metadata.read_text())
    return record["sha256"] == digest(target) and record["pin"] == PIN


def recover(lake: Path, output: Path, start: date, end: date) -> dict[str, Any]:
    """Use the unchanged pinned source; append only task-owned private artifacts."""
    from cnequity.adapters.calendar.exchange_calendar import build_trading_calendar
    from cnequity.adapters.sina.adj_factors import fetch_adj_factor_series
    from cnequity.adapters.sw.industry_history import (
        SW_INDUSTRY_XLS_URL,
        fetch_sw_industry_intervals,
        sw_client,
    )
    from cnequity.adapters.tdx_protocol.client import fetch_daily_bars
    from cnequity.config import Config

    external_directory(output)
    if end >= date(2026, 3, 3):
        raise ValueError("V1_SEALED_PERIOD_EXCLUDED_FROM_RESEARCH_RECOVERY")
    config = Config(
        data_root=output / "provider",
        tdx_min_interval_ms=100,
        tdx_connect_timeout_sec=5,
        source_intervals={"sina": 0.3, "sw": 1.0},
        source_concurrency={"tdx_protocol": 4, "sina": 4, "sw": 1},
    )
    membership_path = output / "membership.parquet"
    if not membership_path.exists():
        with sw_client(timeout=60) as client:
            captured: dict[str, Any] = {}

            def capture(response: Any) -> None:
                response.read()
                (output / "membership-source.xls").write_bytes(response.content)
                captured.update(
                    {
                        "url": SW_INDUSTRY_XLS_URL,
                        "sha256": hashlib.sha256(response.content).hexdigest(),
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "last_modified": response.headers.get("last-modified"),
                        "publication_proof": None,
                    }
                )

            client.event_hooks["response"].append(capture)
            intervals = fetch_sw_industry_intervals(client=client, config=config)
        intervals.write_parquet(membership_path)
        write_json(
            output / "membership-source.json", captured | {"parsed_sha256": digest(membership_path)}
        )
    instruments = scan(lake / "curated", "instruments").collect().unique("symbol", keep="last")
    instruments.write_parquet(output / "instruments.parquet")
    calendar = build_trading_calendar(start, end).filter(pl.col("is_trading"))
    calendar.write_parquet(output / "calendar.parquet")
    members = pl.read_parquet(membership_path).filter(pl.col("start_date") <= end)
    identities = instruments.filter(
        (pl.col("asset_type") == "stock")
        & (pl.col("list_date").is_null() | (pl.col("list_date") <= end))
    )
    symbols = sorted(set(members["symbol"].to_list()) & set(identities["symbol"].to_list()))
    # Full historical rosters independently measure universe survivorship/completeness.
    # The vendor's public single connection and batch cooling policy are preserved.
    from cnequity.adapters.baostock.delisted_bars import roster_on

    roster_dir = output / "rosters"
    roster_dir.mkdir(exist_ok=True)
    dates = calendar["trade_date"].to_list()
    for year in range(start.year, end.year + 1):
        year_days = [d for d in dates if d.year == year]
        if not year_days:
            continue
        day = year_days[len(year_days) // 2]
        target = roster_dir / (day.isoformat() + ".json")
        if target.exists():
            continue
        try:
            roster = roster_on(day, config=config)
            if roster:
                write_json(
                    target,
                    {
                        "date": day,
                        "symbols": sorted(roster),
                        "source": "CNEquity/baostock/roster_on",
                        "observed_at": datetime.now(timezone.utc),
                        "pin": PIN,
                    },
                )
        except Exception as error:
            write_json(target.with_suffix(".failure.json"), {"error_type": type(error).__name__})

    unresolved: dict[str, str] = {}
    pending = [s for s in symbols if not cached(output, "bars", s)]
    batches = [pending[k : k + 20] for k in range(0, len(pending), 20)]

    def fetch_batch(batch: list[str]) -> dict[str, str]:
        failures: dict[str, str] = {}
        for attempt in range(3):
            try:
                frame = fetch_daily_bars(
                    batch, start, end, config=config, backfill=True, allow_mock=False
                )
                for sym in batch:
                    rows = frame.filter(pl.col("symbol") == sym)
                    if not rows.is_empty():
                        store(output, "bars", sym, rows, "CNEquity/tdx_protocol")
                batch = [s for s in batch if not cached(output, "bars", s)]
                if not batch:
                    return failures
            except Exception as error:
                failures.update({s: type(error).__name__ for s in batch})
            time.sleep(2**attempt)
        return {s: failures.get(s, "SOURCE_UNAVAILABLE") for s in batch}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_batch, batch) for batch in batches]
        for number, future in enumerate(as_completed(futures), 1):
            unresolved.update(future.result())
            write_json(
                output / "recovery-checkpoint.json",
                {
                    "completed_batches": number,
                    "total_batches": len(batches),
                    "unresolved": unresolved,
                },
            )
            if number % 10 == 0:
                print(
                    json.dumps({"stage": "bars", "batches": number, "total": len(batches)}),
                    flush=True,
                )

    def fetch_factor(symbol: str) -> tuple[str, str | None]:
        if cached(output, "factors", symbol):
            return symbol, None
        existing = lake / "meta/adj_factors_cache" / (symbol.replace(".", "_") + "_hfq.parquet")
        if existing.exists():
            frame = pl.read_parquet(existing).select("trade_date", "factor")
            if not frame.is_empty():
                store(
                    output,
                    "factors",
                    symbol,
                    frame,
                    "CNEquity/sina/retained_event_cache:" + digest(existing),
                )
                return symbol, None
        for attempt in range(3):
            try:
                frame = fetch_adj_factor_series(symbol, "hfq", config=config)
                if not frame.is_empty():
                    store(output, "factors", symbol, frame, "CNEquity/sina")
                    return symbol, None
            except Exception as error:
                if attempt == 2:
                    return symbol, type(error).__name__
            time.sleep(2**attempt)
        return symbol, "SOURCE_UNAVAILABLE"

    with ThreadPoolExecutor(max_workers=4) as pool:
        for sym, factor_error in pool.map(fetch_factor, symbols):
            if factor_error:
                unresolved[sym + "/factor"] = factor_error
    files = {
        str(p.relative_to(output)): digest(p)
        for kind in ("bars", "factors", "rosters")
        for p in sorted((output / kind).glob("*"))
        if p.suffix in (".parquet", ".json")
    }
    for name in (
        "membership.parquet",
        "membership-source.xls",
        "membership-source.json",
        "instruments.parquet",
        "calendar.parquet",
    ):
        files[name] = digest(output / name)
    record = {
        "pin": PIN,
        "start": str(start),
        "end": str(end),
        "symbols_requested": len(symbols),
        "bar_symbols": len(list((output / "bars").glob("*.parquet"))),
        "factor_symbols": len(list((output / "factors").glob("*.parquet"))),
        "unresolved": unresolved,
        "files": files,
    }
    record["snapshot_sha256"] = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()
    ).hexdigest()
    write_json(output / "recovery.json", record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 2, 27))
    args = parser.parse_args()
    result = recover(args.lake, args.output, args.start, args.end)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

"""Synthetic provider/catalogue scale checks, without wall-clock pass thresholds."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

import numpy as np
import polars as pl
import tables

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/cnequity-sidecar"))
from catalogue_scan import repair_symbols, scan_catalogue  # noqa: E402 -- Standalone synthetic CLI.

from src.data.providers.etf_local import read_local_etf_snapshot  # noqa: E402


def provider_fixture(root: Path, symbols: int, sessions: int) -> None:
    """Write tiny synthetic HDF5/SQLite files, never captured market data."""
    with sqlite3.connect(root / "stock.db") as db:
        db.execute("CREATE TABLE stock(marketid,code,name,type,valid,startDate)")
        db.executemany(
            "INSERT INTO stock VALUES(?,?,?,?,?,?)",
            [(1, str(500000 + i), "SYNTHETIC", 5, 1, 20200101) for i in range(symbols)],
        )
    dtype = np.dtype(
        [(name, "i8") for name in ("datetime", "openPrice", "highPrice", "lowPrice", "closePrice")]
    )
    records = np.zeros(sessions, dtype=dtype)
    for i in range(sessions):
        records[i] = (
            int((date.fromordinal(date(2020, 1, 1).toordinal() + i)).strftime("%Y%m%d")) * 10000,
            1000,
            1100,
            900,
            1050,
        )
    with tables.open_file(root / "sh_day.h5", "w") as h5:
        group = h5.create_group("/", "data")
        for i in range(symbols):
            h5.create_table(group, "SH" + str(500000 + i), records)


def provider_scale(root: Path, symbols: int = 40, sessions: int = 250) -> dict[str, int | float]:
    """Exercise the real streaming reader; preflight has a separate fixture suite."""
    provider_fixture(root, symbols, sessions)
    started = perf_counter()
    with patch("src.data.providers.etf_local.preflight"):
        metadata, bars = read_local_etf_snapshot(root)
    elapsed = perf_counter() - started
    assert len(metadata) == symbols and len(bars) == symbols * sessions
    for row in metadata.itertuples():
        own = bars.loc[bars.etf_code.eq(row.etf_code), "date"].tolist()
        assert row.local_data_start == min(own) and row.local_data_end == max(own)
        assert row.bar_count == len(own)
    return {"symbols": symbols, "bars": len(bars), "seconds": round(elapsed, 6)}


def catalogue_scale(root: Path, rows: int = 10000) -> dict[str, int | float]:
    """Compare lazy/eager eligibility and schema-union output on synthetic revisions."""
    paths = []
    for revision in range(2):
        path = root / f"synthetic-{revision}.parquet"
        data = {
            "symbol": [f"{i:06d}.BJ" for i in range(revision * rows, (revision + 1) * rows)],
            "delist_date": [date(2026, 9, 28)] * rows,
        }
        if revision:
            data["revision"] = [revision] * rows
        pl.DataFrame(data).write_parquet(path)
        paths.append(path)
    active = {"000001.BJ", "000002.BJ"}
    baseline = {s: {"delist_date": None} for s in active}
    started = perf_counter()
    eager = pl.concat([pl.read_parquet(p) for p in paths], how="diagonal_relaxed")
    expected = {
        r["symbol"]
        for r in eager.to_dicts()
        if r["symbol"] in active and r["delist_date"] == date(2026, 9, 28)
    }
    eager_elapsed = perf_counter() - started
    lazy = scan_catalogue(paths)
    assert lazy is not None
    started = perf_counter()
    actual = repair_symbols(lazy, active, baseline)
    lazy_elapsed = perf_counter() - started
    assert actual == expected and lazy.collect(engine="streaming").equals(eager)
    return {
        "rows": 2 * rows,
        "eligible": len(actual),
        "eager_seconds": round(eager_elapsed, 6),
        "lazy_probe_seconds": round(lazy_elapsed, 6),
    }


def main() -> None:
    """Emit comparative engineering timings, without claiming production guarantees."""
    with TemporaryDirectory(prefix="quant-synthetic-scale-") as directory:
        root = Path(directory)
        print(
            json.dumps(
                {
                    "synthetic_only": True,
                    "provider": provider_scale(root),
                    "catalogue": catalogue_scale(root),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

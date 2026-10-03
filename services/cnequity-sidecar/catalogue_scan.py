"""Lazy catalogue probe; materialize full rows only when a correction is needed."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl


def scan_catalogue(files: list[Path]) -> pl.LazyFrame | None:
    """Preserve diagonal relaxed union semantics across schema revisions."""
    import polars as pl

    return (
        pl.concat([pl.scan_parquet(file) for file in files], how="diagonal_relaxed")
        if files
        else None
    )


def repair_symbols(frame: pl.LazyFrame, active: set[str], baseline: dict[str, dict]) -> set[str]:
    """Only the two admission fields cross the streaming probe boundary."""
    import polars as pl

    eligible = sorted(
        symbol
        for symbol in active
        if symbol in baseline and not baseline[symbol].get("delist_date")
    )
    probe = (
        frame.select("symbol", "delist_date")
        .filter(
            pl.col("symbol").str.ends_with(".BJ")
            & pl.col("symbol").is_in(eligible)
            & (pl.col("delist_date") == date(2026, 9, 28))
        )
        .collect(engine="streaming")
    )
    return set(probe["symbol"].to_list())

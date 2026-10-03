"""Exclude a known contradicted inference; absence stays UNKNOWN, never normal.

The catalogue correction supersedes inferred BJ delisting on 2026-09-28.
Its old derived status rows cannot prove no-bar after that date. Historical
source revisions remain immutable; this is the owned admission/read boundary.
"""

from datetime import date


def contradicted(row, identities):
    return (
        row.get("symbol") in identities
        and row.get("source") == "derived_delisted"
        and row.get("status") == "delisted"
        and row.get("is_trading") is False
        and isinstance(row.get("trade_date"), date)
        and row["trade_date"] >= date(2026, 9, 28)
    )


def validated(frame, identities):
    if (
        frame is None
        or not identities
        or not {"source", "status", "symbol", "trade_date", "is_trading"}.issubset(frame.columns)
    ):
        return frame
    import polars as pl

    rejected = pl.Series(
        [
            contradicted(r, identities)
            for r in frame.select(
                "source", "status", "symbol", "trade_date", "is_trading"
            ).iter_rows(named=True)
        ],
        dtype=pl.Boolean,
    )
    return frame.filter(~rejected)


def enable(identities):
    from cnequity.quality import bar_coverage
    from cnequity.steps import bars, common

    original = common.load_curated_trading_status
    if getattr(original, "__etf_validated_status__", False):
        return

    def read(*args, **kwargs):
        return validated(original(*args, **kwargs), identities)

    setattr(read, "__etf_validated_status__", True)
    common.load_curated_trading_status = read
    bars.load_curated_trading_status = read
    bar_coverage.load_curated_trading_status = read

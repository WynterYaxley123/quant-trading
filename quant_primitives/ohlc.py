"""Neutral daily OHLC admission; independent of any file provider."""

from collections.abc import Mapping

import pandas as pd


def valid_daily_open(bar: Mapping | pd.Series | None) -> bool:
    """Conservative daily-bar check; absence and malformed OHLC are not filled."""
    if bar is None:
        return False
    try:
        o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))  # noqa: E741 -- Established OHLC low-price name in frozen numerical helper.
    except (KeyError, TypeError, ValueError):
        return False
    from math import isfinite

    return (
        all(isfinite(x) and x > 0 for x in (o, h, l, c)) and h >= max(o, l, c) and l <= min(o, h, c)
    )

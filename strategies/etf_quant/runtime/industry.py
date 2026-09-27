"""Source C: internal equal-weight close series, NOT an official index."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

import numpy as np
import pandas as pd

from .storage import GateError

IDENTITY = "INTERNAL_SHENWAN_INDUSTRY_SERIES_V1"
METHOD = "INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1"
PIT_FLAG = "HISTORICAL_MEMBERSHIP_PIT_UNPROVEN"


@dataclass(frozen=True)
class IndustrySeries:
    closes: pd.DataFrame
    audit: tuple[dict, ...]
    universe: tuple[str, ...]
    identity: str = IDENTITY
    method: str = METHOD
    quality_flag: str = PIT_FLAG


def build_industry_series(provider, *, min_constituents=5, coverage_threshold=.8,
                          classification_version=None) -> IndustrySeries:
    """Calendar-adjacent exact-adjusted returns, backward-asof membership only.

    Unknown availability is never manufactured. Membership is reconstructed
    historical input, usable for current warmup, NOT ex-ante PIT research.
    After a broken recursive level, do not silently restart/rebase the series.
    """
    if (type(min_constituents) is not int or min_constituents < 5
            or not .8 <= coverage_threshold <= 1):
        raise ValueError("minimum coverage may not be weakened")
    if classification_version is None:
        raise GateError("CLASSIFICATION_VERSION_BLOCKER")
    members = provider.tables["industry_membership"]
    bars = provider.tables["stock_bars"]
    if members.empty or bars.empty:
        raise GateError("SOURCE_C_INPUT_BLOCKER")
    if (members.duplicated(["symbol", "as_of_date"]).any()
            or bars.duplicated(["symbol", "trade_date"]).any()
            or any(not re.fullmatch(r"[0-9]{6}", c) for c in members.industry_code)):
        raise GateError("SOURCE_C_MEMBERSHIP_SCHEMA_BLOCKER")
    days = tuple(d for d in provider.sessions if d <= provider.cutoff)
    universe = tuple(sorted(set(members.industry_code)))
    if len(universe) < 5:
        raise GateError("INSUFFICIENT_INDUSTRY_UNIVERSE")
    records = {(r["symbol"], r["trade_date"]): r for r in bars.to_dict("records")}
    changes = {}
    for r in members.to_dict("records"):
        changes.setdefault(r["as_of_date"], []).append(r)
    active, levels, started, broken, result, audit = {}, {}, set(), set(), [], []
    for i, day in enumerate(days):
        for change_day in sorted(d for d in changes if d <= day):
            for row in changes.pop(change_day):
                active[row["symbol"]] = row["industry_code"]
        closes = {}
        for code in universe:
            symbols = sorted(s for s, c in active.items() if c == code)
            values, rejected = [], []
            for symbol in symbols:
                cur = records.get((symbol, day))
                prev = records.get((symbol, days[i - 1])) if i else None
                needed = [cur, prev] if code in started else [cur]
                valid = all(r is not None and r["adj_is_exact"] is True
                            and np.isfinite(r["adj_close"]) and r["adj_close"] > 0
                            and r["volume"] > 0 for r in needed)
                if not valid:
                    rejected.append(symbol)
                    continue
                values.append(cur["adj_close"] / prev["adj_close"] - 1 if code in started else 0.)
            ratio = len(values) / len(symbols) if symbols else 0.
            valid = len(values) >= min_constituents and ratio >= coverage_threshold
            daily_return = float(np.mean(values)) if valid and code in started else None
            status = "VALID" if valid and code not in broken else "INVALID"
            if status == "VALID":
                levels[code] = levels[code] * (1 + daily_return) if code in started else 1000.
                started.add(code)
                closes[code] = levels[code]
            else:
                if code in started:
                    broken.add(code)
                closes[code] = np.nan
            audit.append({"trade_date": day.isoformat(), "industry_code": code, "status": status,
                "eligible_members": len(symbols), "valid_constituents": len(values), "coverage": ratio,
                "excluded_symbols": rejected, "daily_return": daily_return, "close": closes[code] if status == "VALID" else None,
                "classification_version": classification_version, "available_at": None, "source_published_at": None,
                "quality_flag": PIT_FLAG, "reason": "RECURSIVE_PREFIX_BROKEN" if code in broken else
                "INSUFFICIENT_COVERAGE" if not valid else None})
        result.append(closes)
    return IndustrySeries(pd.DataFrame(result, index=pd.DatetimeIndex(days), columns=universe), tuple(audit), universe)

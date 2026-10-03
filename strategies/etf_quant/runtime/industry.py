"""Source C: internal equal-weight close series, NOT an official index.

Production granularity is frozen at ``ETF_QUANT_INDUSTRY_LEVEL_V1`` (Shenwan
2021 Level 2). The stored membership layer publishes 6-digit Shenwan codes, so
every stored code is resolved through the sealed taxonomy artifact's explicit
``level3 -> level2`` relation before any series is built. String truncation is
deliberately not used: an unknown code is a blocker, not a shorter code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ..domain.industry_level import (
    ETF_QUANT_INDUSTRY_LEVEL_V1,
    TAXONOMY_IDENTITY,
    TaxonomyError,
    default_taxonomy,
)
from .storage import GateError

IDENTITY = "INTERNAL_SHENWAN_INDUSTRY_SERIES_V1"
METHOD = "INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1"
PIT_FLAG = "HISTORICAL_MEMBERSHIP_PIT_UNPROVEN"
INDUSTRY_LEVEL = ETF_QUANT_INDUSTRY_LEVEL_V1


@dataclass(frozen=True)
class IndustrySeries:
    closes: pd.DataFrame
    audit: tuple[dict, ...]
    universe: tuple[str, ...]
    identity: str = IDENTITY
    method: str = METHOD
    quality_flag: str = PIT_FLAG
    industry_level: str = INDUSTRY_LEVEL
    taxonomy_identity: str = TAXONOMY_IDENTITY
    taxonomy_sha256: str | None = None


def build_industry_series(
    provider,
    *,
    min_constituents=5,
    coverage_threshold=0.8,
    classification_version=None,
    taxonomy=None,
) -> IndustrySeries:
    """Calendar-adjacent exact-adjusted returns, backward-asof membership only.

    Unknown availability is never manufactured. Membership is reconstructed
    historical input, usable for current warmup, NOT ex-ante PIT research.
    After a broken recursive level, do not silently restart/rebase the series.
    """
    if (
        type(min_constituents) is not int
        or min_constituents < 5
        or not 0.8 <= coverage_threshold <= 1
    ):
        raise ValueError("minimum coverage may not be weakened")
    if classification_version is None:
        raise GateError("CLASSIFICATION_VERSION_BLOCKER")
    taxonomy = default_taxonomy() if taxonomy is None else taxonomy
    members = provider.tables["industry_membership"]
    contract = getattr(provider, "model_input_contract", None)
    seed = getattr(provider, "model_membership_seed", None)
    if seed is not None:
        # Model-only historical bootstrap, never current execution PIT.
        members = pd.concat(
            [seed, members.loc[members.as_of_date > seed.as_of_date.max()]], ignore_index=True
        )
    bars = provider.tables["stock_bars"]
    if members.empty or bars.empty:
        raise GateError("SOURCE_C_INPUT_BLOCKER")
    if (
        members.duplicated(["symbol", "as_of_date"]).any()
        or bars.duplicated(["symbol", "trade_date"]).any()
        or any(not re.fullmatch(r"[0-9]{6}", c) for c in members.industry_code)
    ):
        raise GateError("SOURCE_C_MEMBERSHIP_SCHEMA_BLOCKER")
    # Stored codes are Level 3; the production universe is Level 2 resolved by
    # an explicit sealed relation, never by truncating the string.
    try:
        resolved = {code: taxonomy.level2_of(code) for code in set(members.industry_code)}
    except TaxonomyError as error:
        raise GateError(error.code, error.details) from error
    first = date.fromisoformat(contract["warmup_start"]) if contract else None
    days = tuple(
        d for d in provider.sessions if d <= provider.cutoff and (first is None or d >= first)
    )
    universe = tuple(sorted(set(resolved.values())))
    if len(universe) < 5:
        raise GateError("INSUFFICIENT_INDUSTRY_UNIVERSE")
    records = {(r["symbol"], r["trade_date"]): r for r in bars.to_dict("records")}
    instruments = {r["symbol"]: r for r in provider.tables["instruments"].to_dict("records")}
    changes: dict[date, list[dict]] = {}
    for r in members.to_dict("records"):
        changes.setdefault(r["as_of_date"], []).append(r)
    active_by_industry: dict[str, list[str]] = {}
    change_days = sorted(changes)
    change_i = 0
    levels: dict[str, float] = {}
    started, broken, result, audit = set(), set(), [], []
    for i, day in enumerate(days):
        while change_i < len(change_days) and change_days[change_i] <= day:
            change_day = change_days[change_i]
            # Reference membership snapshots replace the complete constituent
            # set. Retaining absent symbols invents members after removal.
            active_by_industry = {}
            for r in changes[change_day]:
                active_by_industry.setdefault(resolved[r["industry_code"]], []).append(r["symbol"])
            for symbols in active_by_industry.values():
                symbols.sort()
            change_i += 1
        closes = {}
        for code in universe:
            symbols = active_by_industry.get(code, [])
            values, rejected = [], []
            for symbol in symbols:
                cur = records.get((symbol, day))
                prev = records.get((symbol, days[i - 1])) if i else None
                needed = [cur, prev] if code in started else [cur]
                valid = all(
                    r is not None
                    and r["adj_is_exact"] is True
                    and np.isfinite(r["adj_close"])
                    and r["adj_close"] > 0
                    and r["volume"] > 0
                    for r in needed
                )
                if code in started:
                    inst = instruments.get(symbol)
                    valid = (
                        valid
                        and inst is not None
                        and inst.get("asset_type") != "cdr"
                        and symbol != "689009.SH"
                    )
                if not valid:
                    rejected.append(symbol)
                    continue
                assert cur is not None  # valid proves every needed row exists.
                if code in started:
                    assert prev is not None
                    values.append(cur["adj_close"] / prev["adj_close"] - 1)
                else:
                    values.append(0.0)
            ratio = len(values) / len(symbols) if symbols else 0.0
            valid = len(values) >= min_constituents and ratio >= coverage_threshold
            daily_return = sum(values) / len(values) if valid and code in started else None
            status = "VALID" if valid and code not in broken else "INVALID"
            if status == "VALID":
                if code in started:
                    assert daily_return is not None
                    levels[code] = levels[code] * (1 + daily_return)
                else:
                    levels[code] = 1000.0
                started.add(code)
                closes[code] = levels[code]
            else:
                if code in started:
                    broken.add(code)
                closes[code] = np.nan
            audit.append(
                {
                    "trade_date": day.isoformat(),
                    "industry_code": code,
                    "industry_level": ETF_QUANT_INDUSTRY_LEVEL_V1,
                    "status": status,
                    "eligible_members": len(symbols),
                    "valid_constituents": len(values),
                    "coverage": ratio,
                    "excluded_symbols": rejected,
                    "daily_return": daily_return,
                    "close": closes[code] if status == "VALID" else None,
                    "classification_version": classification_version,
                    "available_at": None,
                    "source_published_at": None,
                    "quality_flag": PIT_FLAG,
                    "reason": "RECURSIVE_PREFIX_BROKEN"
                    if code in broken
                    else "INSUFFICIENT_COVERAGE"
                    if not valid
                    else None,
                }
            )
        result.append(closes)
    return IndustrySeries(
        pd.DataFrame(result, index=pd.DatetimeIndex(days), columns=universe),
        tuple(audit),
        universe,
        taxonomy_sha256=taxonomy.sha256,
    )

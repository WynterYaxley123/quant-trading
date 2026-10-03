"""Frozen 20-session ETF liquidity admission.

The rule is deliberately narrow and has no configuration surface:

* the window is the **20 exchange sessions ending at the signal session**,
  taken from the verified trading calendar, never from "the last 20 rows that
  happen to exist";
* every one of those 20 sessions must carry a finalized bar with finite
  positive ``open/high/low/close``, finite non-negative ``volume`` and a
  **present, finite, positive ``amount``**;
* a missing ``amount`` is exclusion. There is no ``drop-null`` mean, no zero
  fill and no ``close x volume`` substitution — the pinned upstream bar adapter
  refuses that inference, so the admission layer refuses it too;
* an ETF listed fewer than 20 sessions before the signal date is
  ``LIQUIDITY_HISTORY_INSUFFICIENT``. The window is never shortened to 5 or 10
  sessions to make a fund eligible;
* ranking among several admitted ETFs for one industry is by mean ``amount``
  over the same 20 sessions, descending, ties broken by ascending ETF code.

The module only reads already-verified bars. It never fetches, never infers and
never writes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import pandas as pd

#: Frozen window length. Not a parameter of any public entry point.
LIQUIDITY_SESSIONS = 20
#: The pinned source's own degenerate-feed floor ("below one yuan is a feed artefact").
MIN_TRADED_AMOUNT_CNY = 1.0
#: Bar provenance values already admitted by the export contract.
BAR_SOURCES = ("tdx_protocol", "sina", "eastmoney", "exchange", "ths")
#: Exchange/board status sources that may veto a bar.
VETO_SOURCES = ("exchange", "sse", "szse")

PASS = "LIQUIDITY_ADMISSION_PASS"
FAIL = "LIQUIDITY_ADMISSION_FAIL"
INSUFFICIENT = "LIQUIDITY_HISTORY_INSUFFICIENT"


@dataclass(frozen=True)
class LiquidityAdmission:
    etf_code: str
    status: str
    sessions_required: int
    sessions_present: int
    mean_amount_cny: float | None
    reason: str | None
    window: tuple[str, ...]
    daily: tuple[dict, ...]

    @property
    def passed(self) -> bool:
        return self.status == PASS


@dataclass(frozen=True)
class LiquidityLookup:
    """Call-scoped snapshot index; rebuild after any provider mutation.

    Lists retain duplicates so indexing never changes the fail-closed row-count gate.
    Mapping callers build one index for all their candidates, never a global mutable cache.
    """

    instruments: dict[str, list[dict]]
    bars: dict[tuple[str, date], list[dict]]
    status: dict[tuple[str, date], list[dict]]

    @classmethod
    def build(cls, tables: Mapping[str, pd.DataFrame]) -> LiquidityLookup:
        instruments: dict[str, list[dict]] = {}
        bars: dict[tuple[str, date], list[dict]] = {}
        status: dict[tuple[str, date], list[dict]] = {}
        for row in tables["instruments"].to_dict("records"):
            instruments.setdefault(row["symbol"], []).append(row)
        for name, target in (("etf_bars", bars), ("trading_status", status)):
            for row in tables[name].to_dict("records"):
                target.setdefault((row["symbol"], row["trade_date"]), []).append(row)
        return cls(instruments, bars, status)


def liquidity_window(provider, signal_day):
    """The 20 exchange sessions ending at ``signal_day``, or ``None`` if short.

    Returns ``(window, execution_day)``. The caller must already have proven
    that ``signal_day`` is a session of ``provider``.
    """
    if signal_day not in provider.sessions:
        return None, None
    index = provider.sessions.index(signal_day)
    if index < LIQUIDITY_SESSIONS - 1:
        return None, None
    execution_day = provider.sessions[index + 1] if index + 1 < len(provider.sessions) else None
    return tuple(provider.sessions[index - (LIQUIDITY_SESSIONS - 1) : index + 1]), execution_day


def _instrument(lookup: LiquidityLookup, etf_code: str) -> pd.Series | None:
    rows = lookup.instruments.get(etf_code, [])
    return None if len(rows) != 1 else pd.Series(rows[0])


def _status_veto(lookup: LiquidityLookup, etf_code: str, day: date) -> str | None:
    for row in lookup.status.get((etf_code, day), []):
        if row["source"] in VETO_SOURCES and (
            row["is_trading"] is not True or row["status"] != "normal"
        ):
            return "EXCHANGE_NONTRADABLE"
    return None


def _bar_failure(rows: list[dict]) -> str | None:
    """One session's admissibility. ``amount`` evidence is mandatory here."""
    if len(rows) != 1:
        return "BAR_MISSING_OR_DUPLICATE"
    bar = rows[0]
    prices = ("open", "high", "low", "close")
    if any(
        not pd.notna(bar[k]) or not math.isfinite(float(bar[k])) or float(bar[k]) <= 0
        for k in prices
    ):
        return "NON_POSITIVE_OR_UNKNOWN_PRICE"
    if float(bar["high"]) < max(
        float(bar["open"]), float(bar["close"]), float(bar["low"])
    ) or float(bar["low"]) > min(float(bar["open"]), float(bar["close"]), float(bar["high"])):
        return "IMPOSSIBLE_OHLC"
    volume = bar["volume"]
    if not pd.notna(volume) or not math.isfinite(float(volume)) or float(volume) < 0:
        return "INVALID_VOLUME_EVIDENCE"
    amount = bar["amount"]
    if not pd.notna(amount) or not math.isfinite(float(amount)):
        return "AMOUNT_EVIDENCE_MISSING"
    if float(amount) < MIN_TRADED_AMOUNT_CNY:
        return "AMOUNT_BELOW_FEED_FLOOR"
    return None


def assess_liquidity(
    provider, etf_code, window, *, lookup: LiquidityLookup | None = None
) -> LiquidityAdmission:
    """Frozen 20-session admission for one ETF over one explicit window."""
    if len(window) != LIQUIDITY_SESSIONS:
        # A caller-supplied short window would be a silent methodology change.
        raise ValueError(
            "the frozen liquidity window is exactly twenty sessions; it is never shortened"
        )
    days = tuple(str(day) for day in window)
    lookup = LiquidityLookup.build(provider.tables) if lookup is None else lookup
    instrument = _instrument(lookup, etf_code)
    if instrument is None or instrument.asset_type != "etf":
        return LiquidityAdmission(
            etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None, "LISTED_ETF_IDENTITY_UNPROVEN", days, ()
        )
    if instrument.prev_symbol is not None:
        return LiquidityAdmission(
            etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None, "SYMBOL_CONTINUITY_UNPROVEN", days, ()
        )
    list_date = instrument.list_date
    if list_date is None:
        return LiquidityAdmission(
            etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None, "LISTING_DATE_UNPROVEN", days, ()
        )
    if list_date > window[0]:
        # Not a data gap: the fund did not exist for the whole frozen window.
        return LiquidityAdmission(
            etf_code,
            INSUFFICIENT,
            LIQUIDITY_SESSIONS,
            0,
            None,
            "ETF_LISTED_FEWER_THAN_20_SESSIONS_BEFORE_SIGNAL",
            days,
            (),
        )
    amounts: list[float] = []
    daily = []
    for day in window:
        failure = None
        if instrument.delist_date is not None and instrument.delist_date <= day:
            failure = "ETF_DELISTED"
        if failure is None:
            failure = _status_veto(lookup, etf_code, day)
        rows = lookup.bars.get((etf_code, day), [])
        if failure is None:
            failure = _bar_failure(rows)
        if failure is not None:
            daily.append(
                {"trade_date": str(day), "admitted": False, "reason": failure, "amount_cny": None}
            )
            return LiquidityAdmission(
                etf_code, FAIL, LIQUIDITY_SESSIONS, len(amounts), None, failure, days, tuple(daily)
            )
        row = rows[0]
        amount = float(row["amount"])
        amounts.append(amount)
        daily.append(
            {"trade_date": str(day), "admitted": True, "reason": None, "amount_cny": amount}
        )
    mean = math.fsum(amounts) / LIQUIDITY_SESSIONS
    if not math.isfinite(mean) or mean <= 0:
        return LiquidityAdmission(
            etf_code,
            FAIL,
            LIQUIDITY_SESSIONS,
            len(amounts),
            None,
            "NON_POSITIVE_MEAN_AMOUNT",
            days,
            tuple(daily),
        )
    return LiquidityAdmission(
        etf_code, PASS, LIQUIDITY_SESSIONS, LIQUIDITY_SESSIONS, mean, None, days, tuple(daily)
    )


__all__ = [
    "BAR_SOURCES",
    "FAIL",
    "INSUFFICIENT",
    "LIQUIDITY_SESSIONS",
    "MIN_TRADED_AMOUNT_CNY",
    "PASS",
    "LiquidityAdmission",
    "assess_liquidity",
    "liquidity_window",
]

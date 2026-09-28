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

from dataclasses import dataclass
import math

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
    return tuple(provider.sessions[index - (LIQUIDITY_SESSIONS - 1):index + 1]), execution_day


def _instrument(provider, etf_code):
    instruments = provider.tables["instruments"]
    rows = instruments.loc[instruments.symbol == etf_code]
    return None if len(rows) != 1 else rows.iloc[0]


def _status_veto(provider, etf_code, day):
    status = provider.tables["trading_status"]
    rows = status.loc[(status.symbol == etf_code) & (status.trade_date == day)]
    for row in rows.to_dict("records"):
        if row["source"] in VETO_SOURCES and (row["is_trading"] is not True or row["status"] != "normal"):
            return "EXCHANGE_NONTRADABLE"
    return None


def _bar_failure(provider, etf_code, day):
    """One session's admissibility. ``amount`` evidence is mandatory here."""
    frame = provider.tables["etf_bars"]
    rows = frame.loc[(frame.symbol == etf_code) & (frame.trade_date == day)]
    if len(rows) != 1:
        return "BAR_MISSING_OR_DUPLICATE"
    bar = rows.iloc[0].to_dict()
    prices = ("open", "high", "low", "close")
    if any(not pd.notna(bar[k]) or not math.isfinite(float(bar[k])) or float(bar[k]) <= 0 for k in prices):
        return "NON_POSITIVE_OR_UNKNOWN_PRICE"
    if (float(bar["high"]) < max(float(bar["open"]), float(bar["close"]), float(bar["low"]))
            or float(bar["low"]) > min(float(bar["open"]), float(bar["close"]), float(bar["high"]))):
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


def assess_liquidity(provider, etf_code, window) -> LiquidityAdmission:
    """Frozen 20-session admission for one ETF over one explicit window."""
    if len(window) != LIQUIDITY_SESSIONS:
        # A caller-supplied short window would be a silent methodology change.
        raise ValueError("the frozen liquidity window is exactly twenty sessions; it is never shortened")
    days = tuple(str(day) for day in window)
    instrument = _instrument(provider, etf_code)
    if instrument is None or instrument.asset_type != "etf":
        return LiquidityAdmission(etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None,
                                  "LISTED_ETF_IDENTITY_UNPROVEN", days, ())
    if instrument.prev_symbol is not None:
        return LiquidityAdmission(etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None,
                                  "SYMBOL_CONTINUITY_UNPROVEN", days, ())
    list_date = instrument.list_date
    if list_date is None:
        return LiquidityAdmission(etf_code, FAIL, LIQUIDITY_SESSIONS, 0, None,
                                  "LISTING_DATE_UNPROVEN", days, ())
    if list_date > window[0]:
        # Not a data gap: the fund did not exist for the whole frozen window.
        return LiquidityAdmission(etf_code, INSUFFICIENT, LIQUIDITY_SESSIONS, 0, None,
                                  "ETF_LISTED_FEWER_THAN_20_SESSIONS_BEFORE_SIGNAL", days, ())
    amounts, daily = [], []
    for day in window:
        failure = None
        if instrument.delist_date is not None and instrument.delist_date <= day:
            failure = "ETF_DELISTED"
        if failure is None:
            failure = _status_veto(provider, etf_code, day)
        if failure is None:
            failure = _bar_failure(provider, etf_code, day)
        if failure is not None:
            daily.append({"trade_date": str(day), "admitted": False, "reason": failure, "amount_cny": None})
            return LiquidityAdmission(etf_code, FAIL, LIQUIDITY_SESSIONS, len(amounts), None,
                                      failure, days, tuple(daily))
        frame = provider.tables["etf_bars"]
        row = frame.loc[(frame.symbol == etf_code) & (frame.trade_date == day)].iloc[0]
        amount = float(row["amount"])
        amounts.append(amount)
        daily.append({"trade_date": str(day), "admitted": True, "reason": None, "amount_cny": amount})
    mean = math.fsum(amounts) / LIQUIDITY_SESSIONS
    if not math.isfinite(mean) or mean <= 0:
        return LiquidityAdmission(etf_code, FAIL, LIQUIDITY_SESSIONS, len(amounts), None,
                                  "NON_POSITIVE_MEAN_AMOUNT", days, tuple(daily))
    return LiquidityAdmission(etf_code, PASS, LIQUIDITY_SESSIONS, LIQUIDITY_SESSIONS, mean, None,
                              days, tuple(daily))


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

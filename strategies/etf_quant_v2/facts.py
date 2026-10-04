"""Prefix-preserving V2 warmup plus current finalized CNEquity stock facts.

Only raw factual prices are consumed. Labels stop at the signal session.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from numpy.typing import NDArray

from strategies.etf_quant.config import FACTORS_19
from strategies.etf_quant.domain.industry_level import load_taxonomy
from strategies.etf_quant.factors import compute_close_factors
from strategies.etf_quant.runtime.storage import contained

from .refresh import checksum, verified_snapshot
from .runtime import Observation

Array = NDArray[np.float64]


@dataclass(frozen=True)
class ForwardFacts:
    dates: tuple[date, ...]
    industries: tuple[str, ...]
    features: Array
    closes: Array
    segments: NDArray[np.int64]
    observed_at: datetime
    snapshot_sha256: str
    benchmark_close: dict[str, float]

    def prefix_hash(self, through: date) -> str:
        """Bind consumed prices, segmentation and features against later revisions."""
        end = self.dates.index(through) + 1
        digest = hashlib.sha256(
            json.dumps([list(map(str, self.dates[:end])), self.industries]).encode()
        )
        for values in (self.closes[:end], self.segments[:end], self.features[:end]):
            digest.update(np.ascontiguousarray(values).tobytes())
        return digest.hexdigest()

    def model_inputs(
        self, signal_day: date
    ) -> tuple[list[Observation], dict[str, tuple[float, ...]]]:
        t = self.dates.index(signal_day)
        if t != len(self.dates) - 1:
            raise ValueError("CURRENT_FINALIZED_PREFIX_ONLY")
        current = {
            code: tuple(map(float, self.features[t, j]))
            for j, code in enumerate(self.industries)
            if np.isfinite(self.features[t, j]).all()
        }
        eligible = np.asarray(np.isfinite(self.features).all(axis=2), dtype=np.bool_)
        returns: dict[int, Array] = {}
        for h in (10, 40, 120):
            y = np.full(self.closes.shape, np.nan)
            for i in range(max(0, t - h + 1)):
                active = eligible[i]
                if active.sum() < 12:
                    continue
                raw = self.closes[i + h] / self.closes[i] - 1
                good = np.isfinite(raw) & (self.segments[i + h] == self.segments[i])
                if good[active].all():
                    y[i, active] = raw[active]
            returns[h] = y
        # H120 cutoff minus 12 months is the earliest possible training row.
        earliest = (pd.Timestamp(signal_day) - pd.DateOffset(months=20)).date()
        records = []
        for i, day in enumerate(self.dates):
            if not earliest <= day <= signal_day:
                continue
            for j, code in enumerate(self.industries):
                if not eligible[i, j]:
                    continue
                available = {h: float(y[i, j]) for h, y in returns.items() if np.isfinite(y[i, j])}
                if available:
                    records.append(
                        Observation(
                            code,
                            day,
                            tuple(map(float, self.features[i, j])),
                            available,
                            {h: self.dates[i + h] for h in available},
                            self.observed_at,
                            "B",
                        )
                    )
        return records, current


def factors_from_closes(closes: Array, dates: tuple[date, ...]) -> Array:
    index = pd.DatetimeIndex(dates)
    return np.stack(
        [
            compute_close_factors(pd.Series(closes[:, j], index=index))
            .loc[:, list(FACTORS_19)]
            .to_numpy()
            for j in range(closes.shape[1])
        ],
        axis=1,
    )


def append_snapshot(warmup: Path, snapshot: Path, *, expected_panel_sha256: str) -> ForwardFacts:
    """No historical recomputation or overwriting of the frozen factual prefix."""
    if checksum(contained(warmup, "panel.npz")) != expected_panel_sha256:
        raise ValueError("FROZEN_WARMUP_PANEL_REQUIRED")
    metadata = json.loads(contained(warmup, "panel.json").read_bytes())
    if metadata["panel_sha256"] != expected_panel_sha256:
        raise ValueError("WARMUP_METADATA_HASH_ERROR")
    manifest = verified_snapshot(snapshot)
    cutoff = date.fromisoformat(manifest["data_cutoff"])
    observed_at = datetime.fromisoformat(manifest["created_at"])
    if observed_at.tzinfo is None:
        raise ValueError("FACTUAL_OBSERVATION_TIME_REQUIRED")
    dates = tuple(map(date.fromisoformat, metadata["dates"]))
    if dates[-1] > cutoff:
        raise ValueError("FUTURE_WARMUP_DATA_DENIED")
    industries = tuple(metadata["industries"])
    with np.load(warmup / "panel.npz", allow_pickle=False) as data:
        closes = np.array(data["HIGH_CONFIDENCE_close"], dtype=float)
        segments = np.array(data["HIGH_CONFIDENCE_segments"], dtype=np.int64)
        original_features = np.array(data["HIGH_CONFIDENCE_X"], dtype=float)
    calendar = pl.read_csv(contained(snapshot, "trading_calendar.csv"), try_parse_dates=True)
    extension = tuple(
        calendar.filter(
            pl.col("is_trading")
            & (pl.col("trade_date") > dates[-1])
            & (pl.col("trade_date") <= cutoff)
        )["trade_date"].to_list()
    )
    if cutoff != dates[-1] and (not extension or extension[-1] != cutoff):
        raise ValueError("OFFICIAL_SNAPSHOT_CALENDAR_REQUIRED")
    if extension:
        stock = (
            pl.scan_csv(contained(snapshot, "stock_bars.csv"), try_parse_dates=True)
            .filter(pl.col("trade_date") >= dates[-1])
            .collect()
        )
        membership = pl.read_csv(
            contained(snapshot, "industry_membership.csv"),
            schema_overrides={"industry_code": pl.String},
            try_parse_dates=True,
        )
        instruments = pl.read_csv(contained(snapshot, "instruments.csv"), try_parse_dates=True)
        active_stocks = {
            r["symbol"]: r for r in instruments.filter(pl.col("asset_type") == "stock").to_dicts()
        }
        records = {(r["symbol"], r["trade_date"]): r for r in stock.to_dicts()}
        taxonomy = load_taxonomy().level3_to_level2
        extra: list[Array] = []
        extra_segments: list[NDArray[np.int64]] = []
        previous_day = dates[-1]
        for day in extension:
            current_members = (
                membership.filter(pl.col("as_of_date") <= day)
                .sort("as_of_date")
                .unique("symbol", keep="last")
            )
            groups: dict[str, list[str]] = {}
            for r in current_members.to_dicts():
                instrument = active_stocks.get(r["symbol"])
                if (
                    instrument is None
                    or instrument["list_date"] is not None
                    and instrument["list_date"] > day
                    or instrument["delist_date"] is not None
                    and instrument["delist_date"] < day
                ):
                    continue
                industry = taxonomy.get(r["industry_code"])
                if industry in industries:
                    groups.setdefault(str(industry), []).append(r["symbol"])
            last = extra[-1] if extra else closes[-1]
            last_segment = extra_segments[-1] if extra_segments else segments[-1]
            next_close, next_segment = np.full(len(industries), np.nan), last_segment.copy()
            for j, code in enumerate(industries):
                symbols = groups.get(code, [])
                values = []
                for symbol in symbols:
                    a, b = records.get((symbol, previous_day)), records.get((symbol, day))
                    if (
                        a is None
                        or b is None
                        or a["adj_is_exact"] is not True
                        or b["adj_is_exact"] is not True
                    ):
                        continue
                    first, second = a["adj_close"], b["adj_close"]
                    if (
                        first is None
                        or second is None
                        or not np.isfinite([first, second]).all()
                        or first <= 0
                        or second <= 0
                    ):
                        continue
                    value = second / first - 1
                    if abs(value) <= 0.5:
                        values.append(value)
                if len(values) >= 5 and len(values) / len(symbols) >= 0.8:
                    next_close[j] = (last[j] if np.isfinite(last[j]) else 1000) * (
                        1 + float(np.mean(values))
                    )
                else:
                    next_segment[j] += 1
            extra.append(next_close)
            extra_segments.append(next_segment)
            previous_day = day
        closes = np.concatenate((closes, np.asarray(extra)))
        segments = np.concatenate((segments, np.asarray(extra_segments)))
        dates = (*dates, *extension)
        calculated = factors_from_closes(closes, dates)
        # Preserve all historical features exactly, including frozen warmup NaNs.
        calculated[: len(original_features)] = original_features
        features = calculated
    else:
        features = original_features
    benchmark = pl.read_csv(contained(snapshot, "benchmark_csi300.csv"), try_parse_dates=True)
    points = {
        str(r["trade_date"]): float(r["close"])
        for r in benchmark.to_dicts()
        if r["trade_date"] <= cutoff and r["close"] is not None and r["close"] > 0
    }
    return ForwardFacts(
        dates,
        industries,
        features,
        closes,
        segments,
        observed_at,
        checksum(snapshot / "manifest.json"),
        points,
    )


def load_liquidity(root: Path, day: date) -> dict[str, float]:
    path = contained(root, str(day) + "/summary.json")
    doc: dict[str, Any] = json.loads(path.read_bytes())
    if doc["data_cutoff"] != str(day):
        raise ValueError("CURRENT_LIQUIDITY_DATE_REQUIRED")
    result = {}
    for row in doc["receipts"]:
        if row["liquidity_amount"] is not None:
            bars = contained(root, str(day) + "/" + row["symbol"] + ".parquet")
            if checksum(bars) != row["bars_sha256"]:
                raise ValueError("LIQUIDITY_RECEIPT_HASH_ERROR")
            result[row["symbol"]] = float(row["liquidity_amount"])
    return result

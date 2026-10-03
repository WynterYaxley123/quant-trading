"""Test-only reference algorithms from BASE_SHA 1e2ffbd4.

Do not use for production, market data or formal cycles.
"""

import math
import re
import warnings
from datetime import date

import numpy as np
import pandas as pd

from strategies.etf_quant.domain.industry_level import (
    ETF_QUANT_INDUSTRY_LEVEL_V1,
    TaxonomyError,
    default_taxonomy,
)
from strategies.etf_quant.mapping.liquidity import (
    FAIL,
    INSUFFICIENT,
    LIQUIDITY_SESSIONS,
    MIN_TRADED_AMOUNT_CNY,
    PASS,
    VETO_SOURCES,
    LiquidityAdmission,
)
from strategies.etf_quant.models import TrainingObservation
from strategies.etf_quant.runtime.industry import PIT_FLAG, IndustrySeries
from strategies.etf_quant.runtime.storage import GateError, digest, json_bytes
from strategies.sw_sector_rotation.src.model.model import NumPyRidge


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
    active = {}
    levels: dict[str, float] = {}
    started, broken, result, audit = set(), set(), [], []
    for i, day in enumerate(days):
        for change_day in sorted(d for d in changes if d <= day):
            # Reference membership snapshots replace the complete constituent
            # set. Retaining absent symbols invents members after removal.
            active = {r["symbol"]: resolved[r["industry_code"]] for r in changes.pop(change_day)}
        closes = {}
        for code in universe:
            symbols = sorted(s for s, c in active.items() if c == code)
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


def _instrument(provider, etf_code):
    instruments = provider.tables["instruments"]
    rows = instruments.loc[instruments.symbol == etf_code]
    return None if len(rows) != 1 else rows.iloc[0]


def _status_veto(provider, etf_code, day):
    status = provider.tables["trading_status"]
    rows = status.loc[(status.symbol == etf_code) & (status.trade_date == day)]
    for row in rows.to_dict("records"):
        if row["source"] in VETO_SOURCES and (
            row["is_trading"] is not True or row["status"] != "normal"
        ):
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


def assess_liquidity(provider, etf_code, window) -> LiquidityAdmission:
    """Frozen 20-session admission for one ETF over one explicit window."""
    if len(window) != LIQUIDITY_SESSIONS:
        # A caller-supplied short window would be a silent methodology change.
        raise ValueError(
            "the frozen liquidity window is exactly twenty sessions; it is never shortened"
        )
    days = tuple(str(day) for day in window)
    instrument = _instrument(provider, etf_code)
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
            failure = _status_veto(provider, etf_code, day)
        if failure is None:
            failure = _bar_failure(provider, etf_code, day)
        if failure is not None:
            daily.append(
                {"trade_date": str(day), "admitted": False, "reason": failure, "amount_cny": None}
            )
            return LiquidityAdmission(
                etf_code, FAIL, LIQUIDITY_SESSIONS, len(amounts), None, failure, days, tuple(daily)
            )
        frame = provider.tables["etf_bars"]
        row = frame.loc[(frame.symbol == etf_code) & (frame.trade_date == day)].iloc[0]
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


def source_prefix(provider):
    result = {}
    from strategies.etf_quant.runtime.exports import KEYS

    for name, frame in provider.tables.items():
        date_key = (
            "list_date"
            if name == "instruments"
            else "as_of_date"
            if name == "industry_membership"
            else "trade_date"
        )
        if date_key not in frame:
            continue
        records = {}
        for row in frame.to_dict("records"):
            # Undated instrument evidence is not allowed to silently change
            # after it influenced listing/tradability admission. Future known
            # listings are not part of the already-consumed historical prefix.
            row_day = row[date_key]
            if row_day is not None and row_day > provider.cutoff:
                continue
            key = "|".join(str(row[k]) for k in KEYS[name])
            # Observation time can advance on re-fetch; economic values/identity
            # may not silently change in a consumed historical prefix.
            economic = {k: str(v) for k, v in row.items() if k != "fetched_at"}
            records[key] = {
                "date": str(row_day) if row_day is not None else None,
                "hash": digest(json_bytes(economic)),
            }
        result[name] = records
    return result


def training_rows(series, provider, spec, universe, features):
    """Date × sector rows; full cross-sections inside the admitted universe.

    Rows from nonadmitted taxonomy industries cannot veto a model date. A
    partial date *inside* the admitted universe is still rejected unchanged.
    """
    days = tuple(d.date() for d in series.closes.index)
    h = int(spec.horizon)
    if len(days) <= h:
        raise GateError("MODEL_WARMUP_INCOMPLETE")
    cutoff = days[-1 - h]
    start = (pd.Timestamp(cutoff) - pd.DateOffset(months=6)).date()
    observations = []
    accepted = []
    for i, day in enumerate(days):
        if not start <= day <= cutoff:
            continue
        end = days[i + h]
        a = series.closes.loc[pd.Timestamp(day), list(universe)].to_numpy(dtype=float)
        b = series.closes.loc[pd.Timestamp(end), list(universe)].to_numpy(dtype=float)
        x = [
            features[c].loc[pd.Timestamp(day), list(spec.factor_names)].to_numpy(dtype=float)
            for c in universe
        ]
        if not (
            np.isfinite(a).all() and np.isfinite(b).all() and all(np.isfinite(v).all() for v in x)
        ):
            continue
        accepted.append(day)
        for c, values, left, right in zip(universe, x, a, b):
            observations.append(
                TrainingObservation(
                    spec.horizon,
                    c,
                    day,
                    end,
                    provider.created_at,
                    spec.factor_names,
                    tuple(map(float, values)),
                    float(right / left - 1),
                )
            )
    return observations, {
        "horizon": h,
        "valid_observations": len(observations),
        "unique_valid_dates": len(accepted),
        "valid_sectors": len(universe) if observations else 0,
        "mature_cutoff": str(cutoff),
        "window_start": str(start),
        "minimum_valid_dates": spec.minimum_valid_training_days,
        "status": "PASS" if len(accepted) >= spec.minimum_valid_training_days else "FAIL",
    }


def fit_period_reference(
    self,
    period: str,
    panel: dict[str, pd.DataFrame],
    feature_names: list[str],
    train_dates: list[pd.Timestamp],
    label_col: str | None = None,
) -> NumPyRidge | None:
    """训练一个周期的 Ridge。

    ``train_dates`` 必须已经是**forward label 完全实现**的日期
    （由 :mod:`strategies.sw_sector_rotation.src.common.temporal_integrity` 计算）。
    有效训练日期 < :data:`MIN_TRAIN_DATES` 时返回 ``None``（不训练）。
    """
    if period not in self.forward_windows:
        raise KeyError(f"未知周期: {period}")
    self.models.pop(period, None)
    self.feature_schemas.pop(period, None)
    self.training_coverage.pop(period, None)
    self._validate_schema(feature_names, panel)
    train_dates = sorted(set(pd.Timestamp(d) for d in train_dates))
    if len(train_dates) < self.min_train_dates:
        return None

    label_col = label_col or f"fwd{self.forward_windows[period]}"
    dates = set(pd.Timestamp(d) for d in train_dates)

    xs, ys = [], []
    counts_by_date, counts_by_sector, dropped = {}, {}, {}
    for name, frame in sorted(panel.items()):
        if label_col not in frame.columns:
            raise ValueError(f"{name}: 缺少 label column {label_col}")
        sel = frame.loc[frame.index.isin(dates)]
        if np.isinf(sel[list(feature_names) + [label_col]].to_numpy(dtype=float)).any():
            raise ValueError(f"{name}: training data 含 Inf")
        before = len(sel)
        sel = sel.dropna(subset=list(feature_names) + [label_col])
        dropped[name] = before - len(sel)
        counts_by_sector[name] = len(sel)
        for d in sel.index:
            counts_by_date[str(d.date())] = counts_by_date.get(str(d.date()), 0) + 1
        if sel.empty:
            continue
        xs.append(sel[list(feature_names)].to_numpy(dtype=float))
        ys.append(sel[label_col].to_numpy(dtype=float))

    coverage = {
        "samples_by_date": counts_by_date,
        "samples_by_sector": counts_by_sector,
        "dropped_nan_rows": dropped,
        "n_train_dates": len(counts_by_date),
        "n_train_samples": sum(counts_by_sector.values()),
        "weighting": "one_weight_per_date_sector_sample",
    }
    self.training_coverage[period] = coverage
    if any(n != len(panel) for n in counts_by_date.values()):
        warnings.warn(
            "sector coverage 不一致；保留逐样本权重，详见 training_coverage",
            RuntimeWarning,
            stacklevel=2,
        )
    if not xs or len(counts_by_date) < self.min_train_dates:
        return None
    X = np.vstack(xs)
    y = np.concatenate(ys)
    model = NumPyRidge(alpha=self.alpha).fit(X, y)
    self.models[period] = model
    self.feature_schemas[period] = tuple(feature_names)
    return model

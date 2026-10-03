"""19 price factors copied from the baseline's authoritative pure formulas.

No RSRS, field mapping, source adapter or Research import. Returns warmup NaNs;
align's early NaN comparisons remain False, exactly as in the source formula.
"""

from types import MappingProxyType

import numpy as np
import pandas as pd

from ..config import FACTORS_19
from ..domain import FactorSpec

EPSILON = 1e-10
CANONICAL_COLUMNS = ("open", "high", "low", "close", "volume", "amount")


def _specs():
    result = [FactorSpec(f"d{n}", f"(close-MA{n})/MA{n}", n) for n in (5, 10, 20, 60, 120)]
    result += [
        FactorSpec(f"p{n}", f"clip((close-min{n})/(max{n}-min{n}+1e-10),0,1)", n)
        for n in (5, 10, 20, 60, 120)
    ]
    result += [
        FactorSpec("align", "(3*(MA5>MA10)+2*(MA10>MA20)+(MA20>MA60))/6", 60),
        FactorSpec("v5", "std(pct_change(close),5,ddof=1)", 6),
        FactorSpec("v20", "std(pct_change(close),20,ddof=1)", 21),
        FactorSpec("vc", "v5/(v20+1e-10)", 21),
        FactorSpec("rev5", "-mean(pct_change(close),5)", 6),
        FactorSpec("rev10", "-mean(pct_change(close),10)", 11),
        FactorSpec("dd20", "close/rolling_max(close,20)-1", 20),
        FactorSpec("dd60", "close/rolling_max(close,60)-1", 60),
        FactorSpec("rsi", "100-100/(1+mean(gain,14)/(mean(loss,14)+1e-10))", 15),
    ]
    return result


FACTOR_REGISTRY = MappingProxyType({s.name: s for s in _specs()})
assert tuple(FACTOR_REGISTRY) == FACTORS_19


def compute_price_factors(frame: pd.DataFrame) -> pd.DataFrame:
    """Explicit internal OHLCVA input only. Never fill, fetch or map columns."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("DataFrame required")
    if not set(CANONICAL_COLUMNS).issubset(frame.columns):
        raise ValueError("canonical OHLCVA columns required")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("DatetimeIndex required")
    if (
        frame.index.has_duplicates
        or frame.index.hasnans
        or frame.columns.has_duplicates
        or not frame.index.is_monotonic_increasing
        or frame.index.tz is not None
        or not frame.index.equals(frame.index.normalize())
    ):
        raise ValueError("unique sorted timezone-naive daily dates required")
    values = frame.loc[:, list(CANONICAL_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4:] < 0).any():
        raise ValueError("finite positive prices / nonnegative volume and amount required")
    return compute_close_factors(frame["close"])


def compute_close_factors(c: pd.Series) -> pd.DataFrame:
    """Genuine close-only input for internal series; never synthesize OHLCVA.

    Explicit NaN gaps remain NaN. No forward fill, interpolation or gap removal;
    rolling warmup restarts naturally after a missing close.
    """
    if not isinstance(c, pd.Series) or not isinstance(c.index, pd.DatetimeIndex):
        raise ValueError("dated close Series required")
    if (
        c.index.has_duplicates
        or c.index.hasnans
        or not c.index.is_monotonic_increasing
        or c.index.tz is not None
        or not c.index.equals(c.index.normalize())
    ):
        raise ValueError("unique sorted daily dates required")
    values = c.to_numpy(dtype=float)
    known = values[~np.isnan(values)]
    if not np.isfinite(known).all() or (known <= 0).any():
        raise ValueError("positive finite observed closes required")
    r = c.pct_change(fill_method=None)
    out = pd.DataFrame(index=c.index)
    mas = {n: c.rolling(n).mean() for n in (5, 10, 20, 60, 120)}
    for n, ma in mas.items():
        out[f"d{n}"] = (c - ma) / ma
    for n in (5, 10, 20, 60, 120):
        hi, lo = c.rolling(n).max(), c.rolling(n).min()
        out[f"p{n}"] = ((c - lo) / (hi - lo + EPSILON)).clip(0.0, 1.0)
    out["align"] = (
        sum(
            (mas[a] > mas[b]).astype(float) * w
            for a, b, w in ((5, 10, 3), (10, 20, 2), (20, 60, 1))
        )
        / 6.0
    )
    out["v5"], out["v20"] = r.rolling(5).std(), r.rolling(20).std()
    out["vc"] = out["v5"] / (out["v20"] + EPSILON)
    out["rev5"], out["rev10"] = -r.rolling(5).mean(), -r.rolling(10).mean()
    out["dd20"], out["dd60"] = c / c.rolling(20).max() - 1.0, c / c.rolling(60).max() - 1.0
    rs = r.clip(lower=0).rolling(14).mean() / ((-r).clip(lower=0).rolling(14).mean() + EPSILON)
    out["rsi"] = 100.0 - 100.0 / (1.0 + rs)
    return out.loc[:, list(FACTORS_19)]

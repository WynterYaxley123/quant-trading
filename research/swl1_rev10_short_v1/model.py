"""Pure REV10 scoring using the exact PR36 arithmetic-return implementation."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import numpy as np
from numpy.typing import NDArray

from research.swl1_short_horizon_exploration.signals import reversal_features

Array = NDArray[np.float64]
CODES = (
    "110000",
    "220000",
    "230000",
    "240000",
    "270000",
    "280000",
    "330000",
    "340000",
    "350000",
    "360000",
    "370000",
    "410000",
    "420000",
    "430000",
    "450000",
    "460000",
    "480000",
    "490000",
    "610000",
    "620000",
    "630000",
    "640000",
    "650000",
    "710000",
    "720000",
    "730000",
    "740000",
    "750000",
    "760000",
    "770000",
)


def validate_universe(codes: tuple[str, ...], returns: Array) -> None:
    if codes != CODES or returns.ndim != 2 or returns.shape[1] != len(CODES):
        raise ValueError("COMPLETE_FIXED_30_UNIVERSE_REQUIRED")
    if returns.dtype != np.dtype("float64"):
        raise ValueError("FLOAT64_RETURN_VIEW_REQUIRED")


def validate_asof(dates: tuple[str, ...], asof: str, cutoff: str) -> int:
    for value in (*dates, asof, cutoff):
        if (
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            or date.fromisoformat(value).isoformat() != value
        ):
            raise ValueError("EXCHANGE_SESSION_REQUIRED")
    if not dates or dates != tuple(sorted(set(dates))) or asof not in dates or asof > cutoff:
        raise ValueError("AUTHORIZED_ASOF_REQUIRED")
    return dates.index(asof)


def score(
    returns: Array, dates: tuple[str, ...], codes: tuple[str, ...], *, asof: str, cutoff: str
) -> dict[str, Array]:
    validate_universe(codes, returns)
    signal = validate_asof(dates, asof, cutoff)
    if len(dates) != len(returns) or signal < 9:
        raise ValueError("TEN_COMPLETE_SESSIONS_REQUIRED")
    # Never pass T+1 values to the shared feature implementation.
    past = returns[: signal + 1]
    window = past[-10:]
    if not np.isfinite(window).all() or np.any(window <= -1):
        raise ValueError("TEN_COMPLETE_FINITE_RETURNS_REQUIRED")
    raw = reversal_features(past)[-1, :, 1]
    if not np.isfinite(raw).all():
        raise ValueError("RECURSIVE_SEED_WARMUP_NOT_COMPLETE")
    return {"rev10_score": raw, "trailing_mean_return": -raw, "relative_score": raw - raw.mean()}


def rank(scores: Array, codes: tuple[str, ...] = CODES, *, ascending: bool = False) -> list[int]:
    if codes != CODES or scores.shape != (30,) or not np.isfinite(scores).all():
        raise ValueError("COMPLETE_FINITE_SCORE_UNIVERSE_REQUIRED")
    direction = scores if ascending else -scores
    return np.lexsort((np.asarray(codes), direction)).astype(int).tolist()


def summarize_ranking(
    scores: dict[str, Array], *, names: dict[str, str], asof: str, source_generation: str
) -> dict[str, Any]:
    raw = scores["rev10_score"]
    order = rank(raw)
    relative = scores["relative_score"]
    trailing = scores["trailing_mean_return"]
    if any(value.shape != (30,) or not np.isfinite(value).all() for value in scores.values()):
        raise ValueError("COMPLETE_FINITE_SCORE_UNIVERSE_REQUIRED")
    by_code: dict[str, dict[str, Any]] = {}
    for position, i in enumerate(order, 1):
        code = CODES[i]
        by_code[code] = {
            "rank": position,
            "industry_code": code,
            "industry_name": names.get(code, code),
            "name_verified": bool(names.get(code)),
            "rev10_score": float(raw[i]),
            "trailing_mean_return": float(trailing[i]),
            "relative_score": float(relative[i]),
            "data_asof": asof,
            "data_completeness": "10_OF_10_FINITE_SESSIONS",
            "source_generation": source_generation,
        }
    return {
        "status": "HISTORICAL_REPLAY",
        "namespace": "RESEARCH_REPLAY_ONLY",
        "asof": asof,
        "count": 30,
        "complete_universe": True,
        "ranking_basis": "REV10_DESCENDING_CODE_ASCENDING_TIES",
        "rows": [by_code[CODES[i]] for i in order],
        "top5": [by_code[CODES[i]] for i in order[:5]],
        "bottom5": [by_code[CODES[i]] for i in rank(raw, ascending=True)[:5]],
    }

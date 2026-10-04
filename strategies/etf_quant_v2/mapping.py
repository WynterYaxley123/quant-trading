"""Independent V2 primary-evidence admission; legacy V1 functions stay frozen."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from strategies.etf_quant.portfolio.policy import IndustryCandidate

DIRECT = "DIRECT_INDUSTRY_TRACKER"
PROXY = "VERIFIED_INDUSTRY_PROXY"
CASH = "NO_RELIABLE_MAPPING"
ALIASES = {"STRICT_MAPPING": DIRECT, "PROXY_EXPOSURE": PROXY, "CASH_UNEXECUTABLE_SIGNAL": CASH}


def canonical_class(value: str) -> str:
    result = ALIASES.get(value, value)
    if result not in (DIRECT, PROXY, CASH):
        raise ValueError("UNKNOWN_MAPPING_CLASS")
    return result


def finite_positive(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def liquidity_amount(
    bars: Sequence[Mapping[str, Any]], sessions: Sequence[date], signal_day: date
) -> float | None:
    """Exactly the last 20 official sessions; missing amount never becomes zero."""
    days = [d for d in sessions if d <= signal_day][-20:]
    if len(days) != 20:
        return None
    selected = [r for r in bars if date.fromisoformat(str(r["trade_date"])) in days]
    if len(selected) != 20 or {str(r["trade_date"]) for r in selected} != set(map(str, days)):
        return None
    if any(
        r.get("finalized") is not True
        or not all(finite_positive(r.get(k)) for k in ("open", "volume", "amount"))
        for r in selected
    ):
        return None
    return math.fsum(float(r["amount"]) for r in selected) / 20


def evidence_admitted(row: Mapping[str, Any], decision_at: datetime, threshold: float) -> bool:
    if decision_at.tzinfo is None or threshold not in (30, 40, 50):
        raise ValueError("EXPLICIT_MAPPING_TIME_AND_STUDIED_THRESHOLD_REQUIRED")
    try:
        available = datetime.fromisoformat(row["available_at"])
        effective = date.fromisoformat(row["evidence_date"])
        membership = date.fromisoformat(row["membership_date"])
        target, other, unknown = (
            float(row[k]) for k in ("target_exposure", "second_exposure", "unknown_exposure")
        )
        kind = canonical_class(row["mapping_class"])
    except (KeyError, ValueError, TypeError):
        return False
    if (
        available.tzinfo is None
        or available > decision_at
        or not 0 <= (decision_at.date() - effective).days <= 62
        or not 0 <= (decision_at.date() - membership).days <= 45
        or row.get("complete_weights") is not True
        or row.get("active") is not True
        or row.get("target_is_largest") is not True
        or not all(math.isfinite(v) and 0 <= v <= 100.5 for v in (target, other, unknown))
        or target < other + unknown
        or any(
            not isinstance(row.get(k), str)
            or len(row[k]) != 64
            or any(c not in "0123456789abcdef" for c in row[k])
            for k in ("weight_source_sha256", "product_source_sha256")
        )
    ):
        return False
    if kind == DIRECT:
        return (
            row.get("complete_constituent_containment") is True
            and unknown == 0
            and other == 0
            and target >= 99.5
        )
    return kind == PROXY and target >= threshold


def candidate_pools(
    registry: Mapping[str, Any], liquidity: Mapping[str, float], decision_at: datetime
) -> dict[str, tuple[IndustryCandidate, ...]]:
    threshold = registry["proxy_threshold"]
    result: dict[str, list[IndustryCandidate]] = {}
    for row in registry["entries"]:
        amount = liquidity.get(row["etf_code"])
        if not evidence_admitted(row, decision_at, threshold) or not finite_positive(amount):
            continue
        code = row["industry_code"]
        result.setdefault(code, []).append(
            IndustryCandidate(
                code,
                row.get("industry_name"),
                0.0,
                row["etf_code"],
                row["tracking_index"],
                "STRICT_MAPPING" if row["mapping_class"] == DIRECT else "PROXY_EXPOSURE",
                row["target_exposure"],
                row["second_exposure"],
                row["target_exposure"] - row["second_exposure"],
                True,
                "COMPLETE_WEIGHT_SET",
                "LIQUIDITY_ADMISSION_PASS",
                amount,
                row["confidence"],
                row["weight_source_url"],
            )
        )
    return {code: tuple(values) for code, values in result.items()}


def select_mappings(
    ranked: Sequence[tuple[str, float]], pools: Mapping[str, Sequence[IndustryCandidate]]
) -> tuple[IndustryCandidate, ...]:
    if len(ranked) != 5 or len({code for code, _ in ranked}) != 5:
        raise ValueError("ORIGINAL_DISTINCT_TOP5_REQUIRED")
    used: set[str] = set()
    result = []
    for code, score in ranked:
        if not math.isfinite(score):
            raise ValueError("FINITE_SCORE_REQUIRED")
        values = list(pools.get(code, ()))
        if any(c.l2_code != code or c.final_score != score for c in values):
            raise ValueError("MAPPING_SIGNAL_IDENTITY_MISMATCH")
        values = sorted(
            (c for c in values if c.passes_b40 and c.etf_code not in used),
            key=lambda c: (
                c.mapping_type != "STRICT_MAPPING",
                -(c.mean_amount_cny or 0),
                c.etf_code or "",
            ),
        )
        if values:
            winner = values[0]
            assert winner.etf_code is not None
            used.add(winner.etf_code)
            result.append(winner)
        else:
            result.append(
                IndustryCandidate(
                    code,
                    None,
                    score,
                    None,
                    None,
                    "CASH_UNEXECUTABLE_SIGNAL",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
            )
    return tuple(result)

"""Pure, explicitly opted-in B40 mapping selection over preverified candidate pools.

Evidence acquisition and historical availability are NOT inferred here. The
caller must supply independently verified candidates and frozen Top5 scores.
No strict registry or default five-member selector is changed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

from ..portfolio.policy import IndustryCandidate, POLICY_B40_WITH_CASH


def select_mappings_partial(
    ranked_signals: Sequence[tuple[str, float]],
    candidate_pools: Mapping[str, Sequence[IndustryCandidate]],
    *, execution_policy: str,
) -> tuple[IndustryCandidate, ...]:
    """Return five original signal slots, with unexecutable slots marked Cash.

    STRICT > PROXY > CASH. A present strict mapping cannot be displaced by a
    proxy even if the strict instrument fails today's evidence/liquidity gate.
    An ETF cannot appear twice. Selection never changes scores or rank order.
    """
    if execution_policy != POLICY_B40_WITH_CASH:
        raise ValueError("EXPLICIT_B40_WITH_CASH_POLICY_REQUIRED")
    signals = tuple(ranked_signals)
    if len(signals) != 5 or len({code for code, _ in signals}) != 5:
        raise ValueError("FROZEN_TOP5_SIGNAL_REQUIRED")
    chosen: list[IndustryCandidate] = []
    used: set[str] = set()
    for code, score in signals:
        if not isinstance(code, str) or not code or not isinstance(score, (float, int)) or not math.isfinite(score):
            raise ValueError("INVALID_FROZEN_SIGNAL")
        pool = tuple(candidate_pools.get(code, ()))
        if any(c.l2_code != code or c.final_score != score or c.mapping_type not in
               ("STRICT_MAPPING", "PROXY_EXPOSURE") for c in pool):
            raise ValueError("CANDIDATE_SIGNAL_IDENTITY_MISMATCH")
        strict = tuple(c for c in pool if c.mapping_type == "STRICT_MAPPING")
        eligible_pool = strict if strict else pool
        admitted = [c for c in eligible_pool if c.passes_b40 and c.etf_code not in used]
        if admitted:
            winner = sorted(admitted, key=lambda c: (-c.target_l2_exposure,
                -(c.dominance_margin or 0.0), -(c.mean_amount_cny or 0.0), c.etf_code))[0]
            chosen.append(winner)
            used.add(winner.etf_code)
        else:
            chosen.append(IndustryCandidate(code, None, float(score), None, None,
                "CASH_UNEXECUTABLE_SIGNAL", None, None, None, None, None, None, None))
    return tuple(chosen)

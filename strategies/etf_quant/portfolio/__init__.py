"""Deterministic capped softmax and Top5 SET-change contract only."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

import numpy as np

from ..domain import TargetPosition, finite, identifier


class AllocationStatus(str, Enum):
    READY = "READY"
    EMPTY = "EMPTY"
    INSUFFICIENT_ASSETS = "INSUFFICIENT_EXECUTABLE_ASSETS"
    INFEASIBLE = "INFEASIBLE_WEIGHT_CAP"


@dataclass(frozen=True)
class AllocationResult:
    status: AllocationStatus
    targets: tuple[TargetPosition, ...] = ()
    unallocated_weight: float = 1.0
    reason: str | None = None


def size_targets(
    scores: Mapping[str, float], *, max_weight: float = 0.35, required_assets: int = 5
) -> AllocationResult:
    """Only caller-supplied executable identities; never perform ETF mapping.

    Insufficient/infeasible cases return no allocations and explicitly retain
    100% unallocated. No invented asset, silently reduced Top5 or uncapped fallback.
    """
    cap = finite(max_weight, "weight cap")
    if not 0 < cap <= 1 or type(required_assets) is not int or required_assets <= 0:
        raise ValueError("invalid sizing constraint")
    codes = tuple(sorted(scores))
    for code in codes:
        identifier(code)
        finite(scores[code], "sizing score")
    if not codes:
        return AllocationResult(AllocationStatus.EMPTY, reason="NO_EXECUTABLE_ASSETS")
    if len(codes) > required_assets:
        raise ValueError("selection exceeds required asset count")
    if len(codes) * cap < 1:
        return AllocationResult(AllocationStatus.INFEASIBLE, reason="SELECTED_CAPACITY_BELOW_ONE")
    if len(codes) != required_assets:
        return AllocationResult(
            AllocationStatus.INSUFFICIENT_ASSETS, reason="REQUIRED_EXECUTABLE_COUNT_NOT_MET"
        )
    result: dict[str, float] = {}
    active, remaining = list(codes), 1.0
    while active:
        # Recompute on the remaining original scores, mathematically equivalent
        # to proportional redistribution. Avoids losing all residual mass when
        # exp() underflows against an already capped dominant asset.
        vals = np.asarray([scores[c] for c in active], dtype=float)
        with np.errstate(over="ignore", under="ignore"):
            mass = np.exp(vals - vals.max())
        proposed = remaining * mass / mass.sum()
        over = [code for code, weight in zip(active, proposed) if weight > cap]
        if not over:
            result.update(zip(active, map(float, proposed)))
            break
        for code in over:
            result[code] = cap
        remaining -= cap * len(over)
        active = [code for code in active if code not in over]
    total = math.fsum(result.values())
    if not math.isclose(total, 1.0, abs_tol=1e-12) or any(
        not 0 <= v <= cap for v in result.values()
    ):
        raise ValueError("sizing numerical feasibility blocker")
    return AllocationResult(
        AllocationStatus.READY,
        tuple(TargetPosition(code, result[code]) for code in codes),
        max(0.0, 1.0 - total),
    )


class RebalanceStatus(str, Enum):
    NO_REBALANCE = "NO_REBALANCE"
    REQUIRED = "REBALANCE_REQUIRED"


def rebalance_decision(
    previous_members: Sequence[str], current_members: Sequence[str]
) -> RebalanceStatus:
    previous, current = tuple(previous_members), tuple(current_members)
    for code in (*previous, *current):
        identifier(code)
    if (
        len(set(previous)) != len(previous)
        or len(set(current)) != len(current)
        or len(current) != 5
        or len(previous) not in (0, 5)
    ):
        raise ValueError("unique Top5 member sets (or initial empty set) required")
    return (
        RebalanceStatus.NO_REBALANCE if set(previous) == set(current) else RebalanceStatus.REQUIRED
    )

"""Explicit B40-with-cash member-set transition; strict Top5 API is untouched."""
from __future__ import annotations

from collections.abc import Sequence

from ..domain import identifier
from . import RebalanceStatus
from .policy import POLICY_B40_WITH_CASH


def rebalance_decision_v2(previous_members: Sequence[str], current_members: Sequence[str], *,
                          execution_policy: str) -> RebalanceStatus:
    """Compare executable ETF identities, including ETF→Cash and Cash→ETF flips.

    The caller must opt in. Cash is absence of an ETF, never a member identity.
    This pure decision does not create an intent, order, fill, or Shadow epoch.
    """
    if execution_policy != POLICY_B40_WITH_CASH:
        raise ValueError("EXPLICIT_B40_WITH_CASH_POLICY_REQUIRED")
    previous, current = tuple(previous_members), tuple(current_members)
    if (len(previous) > 5 or len(current) > 5
            or len(set(previous)) != len(previous) or len(set(current)) != len(current)):
        raise ValueError("UNIQUE_AT_MOST_FIVE_EXECUTABLE_ETFS_REQUIRED")
    for code in (*previous, *current):
        identifier(code)
        if code == "CASH":
            raise ValueError("CASH_IS_NOT_AN_INSTRUMENT")
    return RebalanceStatus.NO_REBALANCE if set(previous) == set(current) else RebalanceStatus.REQUIRED

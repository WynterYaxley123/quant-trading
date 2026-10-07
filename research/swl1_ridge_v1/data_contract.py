"""Version-specific Level-1 reconstruction without current-taxonomy backfill."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np


def parent_at(taxonomy: dict[str, Any], child: str, day: date) -> str:
    if day < date.fromisoformat(taxonomy["historical_version_boundary"]):
        raise ValueError("CURRENT_TAXONOMY_HISTORICAL_BACKFILL_FORBIDDEN")
    parents = {r["child_code"]: r["parent_code"] for r in taxonomy["hierarchy"]}
    if child not in parents:
        raise ValueError("UNSUPPORTED_HISTORICAL_CLASSIFICATION")
    return str(parents[child])


def available_at(observed: datetime, decision: datetime) -> None:
    """Forward availability guard; reconstructed history never claims this proof."""
    if observed.tzinfo is None or decision.tzinfo is None or observed > decision:
        raise ValueError("SOURCE_NOT_AVAILABLE_AT_DECISION")


def equal_weight(
    returns: dict[str, float | None], *, minimum: int = 5, coverage: float = 0.8
) -> float | None:
    if minimum < 5 or not 0.8 <= coverage <= 1:
        raise ValueError("COVERAGE_MAY_NOT_BE_WEAKENED")
    valid = [v for v in returns.values() if v is not None and np.isfinite(v)]
    if len(valid) < minimum or not returns or len(valid) / len(returns) < coverage:
        return None
    return float(np.mean(valid))

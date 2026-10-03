"""Explicit historical reconstruction quality, separate from V1 PIT admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class EvidenceTier(StrEnum):
    A = "STRICT_POINT_IN_TIME"
    B = "VERIFIED_HISTORICAL_RECONSTRUCTION"
    C = "RETROSPECTIVE_RECONSTRUCTION"
    D = "UNSUPPORTED"


@dataclass(frozen=True)
class HistoricalEvidence:
    source: str
    source_sha256: str
    effective: date
    observed_at: datetime
    official: bool
    historical_spells: bool
    completeness_ratio: float | None
    published_at: datetime | None = None
    taxonomy_effective: date = date(2021, 7, 31)

    def tier(self, decision: date) -> EvidenceTier:
        """Later observation is disclosed; it never masquerades as availability."""
        if (
            not self.source.startswith("https://")
            or len(self.source_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.source_sha256)
            or self.observed_at.tzinfo is None
            or not self.official
            or not self.historical_spells
            or self.effective > decision
        ):
            return EvidenceTier.D
        complete = self.completeness_ratio is not None and self.completeness_ratio >= 0.95
        if (
            complete
            and self.published_at is not None
            and self.published_at.tzinfo is not None
            and self.published_at <= self.observed_at
            and self.observed_at.date() <= decision
            and decision >= self.taxonomy_effective
        ):
            return EvidenceTier.A
        if complete and decision >= self.taxonomy_effective:
            return EvidenceTier.B
        return EvidenceTier.C


def overlap(
    left: dict[str, str], right: dict[str, str], *, independent: bool
) -> dict[str, float | int | str | None]:
    """Compare actual snapshots; dependent inputs cannot validate reconstruction."""
    union, shared = set(left) | set(right), set(left) & set(right)
    assignments = sum(left[k] != right[k] for k in shared)
    disagreement = len(set(left) ^ set(right)) + assignments
    return {
        "status": "INDEPENDENT_COMPARISON" if independent else "DEPENDENT_SOURCE_COMPARISON",
        "union_symbols": len(union),
        "shared_symbols": len(shared),
        "membership_jaccard": len(shared) / len(union) if union else None,
        "disagreement_rate": disagreement / len(union) if union else None,
        "industry_assignment_error": assignments / len(shared) if shared else None,
    }

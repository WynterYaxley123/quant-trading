"""Result-free V2 search specification and chronological admission gates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from itertools import product
from math import isfinite

import pandas as pd

from research.sector_development_protocol import FROZEN_BOUNDARY_DATES
from strategies.etf_quant.config import FACTORS_19, H10_FACTORS, TARGET_IDENTITY

ALPHAS = (0.001, 0.01, 0.1, 1.0, 10.0)
WINDOWS = (6, 12, 24)
SCALING = ("RAW", "TRAIN_ONLY_STANDARDIZED")
FAMILIES = (
    ("A", (10, 40, 120), (0.25, 0.50, 0.25)),
    ("B", (10, 40, 120), (0.30, 0.60, 0.10)),
    ("C", (10, 40), (1 / 3, 2 / 3)),
    ("D", (10, 40, 80), (0.25, 0.50, 0.25)),
)
# Conservative exclusion from the first V1 sealed signal onward. This also
# protects unknown future ordinal boundaries without reading result payloads.
V1_SEALED_FROM = date.fromisoformat(FROZEN_BOUNDARY_DATES[221])
# The later evidence-tiered experiment used these phases. The strict-PIT Split
# below remains the original 120-session proposal, never a description of the
# consumed 60-session Final OOS. This is a documented protocol deviation.
EVIDENCE_TIERED_PHASE_SESSIONS = {"tail": 120, "final": 60, "validation": 80, "gap": 120}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Candidate:
    family: str
    horizons: tuple[int, ...]
    fusion: tuple[float, ...]
    alpha: float
    training_months: int
    scaling: str

    @property
    def identifier(self) -> str:
        return f"{self.family}-{self.scaling}-m{self.training_months}-a{self.alpha:g}"

    def factors(self, horizon: int) -> tuple[str, ...]:
        if horizon not in self.horizons:
            raise ValueError("HORIZON_OUTSIDE_CANDIDATE")
        return H10_FACTORS if horizon == 10 else FACTORS_19


def candidates() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(name, horizons, fusion, alpha, months, scaling)
        for (name, horizons, fusion), alpha, months, scaling in product(
            FAMILIES, ALPHAS, WINDOWS, SCALING
        )
    )


def search_specification() -> dict[str, object]:
    """No dates or performance: the finite grid can be fixed before admission."""
    return {
        "contract": "ETF_QUANT_V2_PREREGISTERED_SEARCH_SPECIFICATION",
        "target": TARGET_IDENTITY,
        "factors_h10": H10_FACTORS,
        "factors_other_horizons": FACTORS_19,
        "candidates": [asdict(c) | {"id": c.identifier} for c in candidates()],
        "factor_subset_search": False,
        "training_anchor": "PER_HORIZON_MATURE_LABEL_CUTOFF",
        "minimum_training_dates": 30,
        "full_calendar_window_required": True,
        "zero_feature_variance": "REJECT_FIT",
        "feature_std_ddof": 0,
        "prediction_zscore": "CROSS_SECTIONAL_POPULATION_SEPARATE_FROM_FEATURE_SCALING",
        "signal_order": "SCORE_DESC_INDUSTRY_CODE_ASC",
        "selection": {
            "folds": 4,
            "fold_assignment": "CONTIGUOUS_EQUAL_SESSION_BLOCKS",
            "evaluation_horizon": 40,
            "spread_groups": "TOP5_MINUS_BOTTOM5",
            "bootstrap": {
                "method": "MOVING_BLOCK",
                "block_sessions": 120,
                "replications": 1000,
                "seed": 20261004,
            },
            "gates": {
                "minimum_signals_per_fold": 120,
                "mean_rank_ic_positive": True,
                "mean_spread_positive": True,
                "positive_rank_ic_and_spread_folds": 3,
                "maximum_positive_fold_contribution": 0.60,
                "minimum_worst_fold_rank_ic": -0.05,
                "maximum_coefficient_norm_cv": 1.0,
                "long_horizon_incremental_rank_ic": 0.005,
                "maximum_long_short_prediction_correlation": 0.95,
            },
            "lexicographic": [
                "MEDIAN_FOLD_RANK_IC",
                "MEDIAN_FOLD_SPREAD",
                "WORST_FOLD_RANK_IC",
                "LOWER_COEFFICIENT_NORM_CV",
            ],
            "effective_tie": {"rank_ic": 0.005, "spread": 0.001},
            "tie_preference": "BASELINE_A_RAW_6M_ALPHA_0.01_THEN_FEWER_HORIZONS_THEN_ID",
            "no_passing_candidate": "NO_CANDIDATE_FROZEN",
        },
        "validation_opened": False,
        "final_oos_opened": False,
    }


@dataclass(frozen=True)
class MembershipEvidence:
    """Explicit dated, complete interval evidence; an as-of snapshot is insufficient."""

    valid_from: date
    valid_to: date
    source_published_at: datetime
    available_at: datetime
    source_sha256: str
    complete_history_sha256: str

    def admit(self, signal_at: datetime) -> None:
        instants = (self.source_published_at, self.available_at, signal_at)
        if any(t.tzinfo is None or t.utcoffset() is None for t in instants):
            raise ValueError("PIT_TIMEZONE_REQUIRED")
        if not (
            self.valid_from <= signal_at.date() <= self.valid_to
            and self.source_published_at <= self.available_at <= signal_at
        ):
            raise ValueError("MEMBERSHIP_UNSUPPORTED")
        for value in (self.source_sha256, self.complete_history_sha256):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("MEMBERSHIP_PROVENANCE_REQUIRED")


@dataclass(frozen=True)
class Split:
    development: tuple[date, ...]
    purge_1: tuple[date, ...]
    validation: tuple[date, ...]
    purge_2: tuple[date, ...]
    final_oos: tuple[date, ...]
    label_tail: tuple[date, ...]

    def __post_init__(self) -> None:
        phases = (
            self.development,
            self.purge_1,
            self.validation,
            self.purge_2,
            self.final_oos,
            self.label_tail,
        )
        if any(type(phase) is not tuple for phase in phases):
            raise ValueError("IMMUTABLE_SPLIT_REQUIRED")
        calendar_dates(tuple(day for phase in phases for day in phase))
        if len(self.development) < 480 or any(len(phase) < 120 for phase in phases[1:]):
            raise ValueError("INSUFFICIENT_SPLIT_HISTORY")
        if self.development[-1] >= V1_SEALED_FROM:
            raise ValueError("OLD_V1_SEALED_DEVELOPMENT_BLOCKED")

    def guard(self, signal: date, label_end: date | None = None) -> None:
        """Gate before any payload access, including Development label outcomes."""
        if signal not in self.development or signal >= V1_SEALED_FROM:
            raise ValueError("SEALED_OR_NON_DEVELOPMENT_ACCESS")
        if label_end is not None and (
            label_end < signal or label_end >= V1_SEALED_FROM or label_end > self.purge_1[-1]
        ):
            raise ValueError("SEALED_LABEL_ACCESS")


def calendar_dates(sessions: Sequence[date]) -> tuple[date, ...]:
    days = tuple(sessions)
    if not days or any(type(day) is not date for day in days) or days != tuple(sorted(set(days))):
        raise ValueError("UNIQUE_ORDERED_CALENDAR_REQUIRED")
    return days


def chronological_split(sessions: Sequence[date], *, strict_pit_admitted: bool) -> Split:
    """Reserve 120-session evaluation phases plus maturity and a 24m warmup.

    A boolean does not admit market data: callers must first verify every dated
    MembershipEvidence and factual observation. This date-only utility cannot
    run models or read any results.
    """
    if strict_pit_admitted is not True:
        raise ValueError("STRICT_PIT_DATA_UNAVAILABLE")
    days = calendar_dates(sessions)
    # Reserve independent chronological holdouts before candidate performance.
    needed = 120 * 5
    if len(days) <= needed:
        raise ValueError("INSUFFICIENT_SPLIT_HISTORY")
    boundary = len(days) - needed
    # Development labels cannot mature in any old V1 sealed range.
    allowed = [i for i in range(boundary) if days[i + 120] < V1_SEALED_FROM]
    if not allowed:
        raise ValueError("NO_UNSEALED_DEVELOPMENT_HISTORY")
    end = allowed[-1] + 1
    dev = days[:end]
    earliest_fit = (pd.Timestamp(dev[-1]) - pd.DateOffset(months=24)).date()
    if days[0] > earliest_fit or len(dev) < 480:
        raise ValueError("INSUFFICIENT_DEVELOPMENT_REGIMES_OR_WINDOW")
    # Additional unused dates remain reserved; they never enter Development.
    return Split(
        dev,
        days[end : boundary + 120],
        days[boundary + 120 : boundary + 240],
        days[boundary + 240 : boundary + 360],
        days[boundary + 360 : boundary + 480],
        days[boundary + 480 :],
    )


def training_indices(
    sessions: Sequence[date], signal: date, horizon: int, months: int
) -> tuple[int, ...]:
    """Calendar months before the horizon cutoff, with explicit label maturity."""
    days = calendar_dates(sessions)
    if horizon not in (10, 40, 80, 120) or months not in WINDOWS:
        raise ValueError("UNREGISTERED_TRAINING_SPECIFICATION")
    pos = days.index(signal)
    if pos < horizon:
        raise ValueError("INSUFFICIENT_LABEL_HISTORY")
    cutoff = pos - horizon
    start = (pd.Timestamp(days[cutoff]) - pd.DateOffset(months=months)).date()
    if days[0] > start:
        raise ValueError("FULL_TRAINING_WINDOW_UNAVAILABLE")
    return tuple(i for i in range(cutoff + 1) if start <= days[i] < signal)


def validate_candidate(candidate: Candidate) -> None:
    if candidate not in candidates() or not isfinite(candidate.alpha):
        raise ValueError("CANDIDATE_OUTSIDE_FROZEN_GRID")

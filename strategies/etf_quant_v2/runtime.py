"""Explicit-input V2 forward signal preparation; no broker or automatic launch."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from strategies.etf_quant.config import FACTORS_19, H10_FACTORS
from strategies.etf_quant.models import NumPyRidge
from strategies.etf_quant.portfolio.policy import (
    POLICY_B40_WITH_CASH,
    BenchmarkExposureVector,
    IndustryCandidate,
    evaluate_policy,
)

from .mapping import select_mappings

SHANGHAI = ZoneInfo("Asia/Shanghai")


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class FrozenSpecification:
    identifier: str
    horizons: tuple[int, ...]
    fusion: tuple[float, ...]
    alpha: float
    training_months: int
    scaling: str
    candidate_sha256: str
    frozen_at: datetime
    final_oos_start: date
    final_oos_end: date
    validated: bool
    final_oos_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            not self.identifier
            or len(self.horizons) != len(self.fusion)
            or any(h not in (10, 40, 80, 120) for h in self.horizons)
            or len(set(self.horizons)) != len(self.horizons)
            or not math.isclose(sum(self.fusion), 1)
            or any(w <= 0 for w in self.fusion)
            or not math.isfinite(self.alpha)
            or self.alpha <= 0
            or self.training_months not in (6, 9, 12, 18, 24)
            or self.scaling not in ("RAW", "TRAIN_ONLY_STANDARDIZED")
            or len(self.candidate_sha256) != 64
            or self.frozen_at.tzinfo is None
            or self.final_oos_start > self.final_oos_end
        ):
            raise ValueError("INVALID_V2_FROZEN_SPECIFICATION")


@dataclass(frozen=True)
class Observation:
    industry: str
    day: date
    factors: tuple[float, ...]
    returns: Mapping[int, float]
    label_end: Mapping[int, date]
    observed_at: datetime
    evidence_tier: str


def prepare_signal(
    spec: FrozenSpecification,
    observations: Sequence[Observation],
    current_factors: Mapping[str, tuple[float, ...]],
    *,
    calendar: Sequence[date],
    signal_at: datetime,
    snapshot_available_at: datetime,
    finalized: bool,
    mapping_pools: Mapping[str, Sequence[IndustryCandidate]],
    exposure_vectors: dict[str, BenchmarkExposureVector],
    mapping_available_at: datetime,
    allow_unvalidated_research: bool = False,
) -> dict[str, Any]:
    """Fit coefficients from mature facts, then reuse frozen V1 execution functions."""
    if any(t.tzinfo is None for t in (signal_at, snapshot_available_at, mapping_available_at)):
        raise ValueError("FORWARD_TIMEZONE_REQUIRED")
    day = signal_at.astimezone(SHANGHAI).date()
    sessions = tuple(calendar)
    if (
        not finalized
        or sessions != tuple(sorted(set(sessions)))
        or day not in sessions
        or signal_at.astimezone(SHANGHAI).time() < time(15)
        or day <= spec.frozen_at.astimezone(SHANGHAI).date()
        or snapshot_available_at > signal_at
        or mapping_available_at > signal_at
        or (not spec.validated and not allow_unvalidated_research)
    ):
        raise ValueError("GENUINE_FINALIZED_FORWARD_DATE_REQUIRED")
    index = sessions.index(day)
    if index + 1 >= len(sessions):
        raise ValueError("OFFICIAL_T_PLUS_ONE_SESSION_REQUIRED")
    industries = sorted(current_factors)
    current = np.asarray([current_factors[i] for i in industries], dtype=float)
    if (
        current.shape != (len(industries), 19)
        or len(industries) < 12
        or not np.isfinite(current).all()
    ):
        raise ValueError("COMPLETE_CURRENT_FEATURE_CROSS_SECTION_REQUIRED")
    scores = np.zeros(len(industries))
    model_records = []
    for horizon, weight in zip(spec.horizons, spec.fusion, strict=True):
        if index < horizon:
            raise ValueError("MATURE_CALENDAR_HISTORY_REQUIRED")
        cutoff = sessions[index - horizon]
        window = (pd.Timestamp(cutoff) - pd.DateOffset(months=spec.training_months)).date()
        rows = [
            r
            for r in observations
            if window <= r.day <= cutoff
            and (
                spec.final_oos_authorized or not spec.final_oos_start <= r.day <= spec.final_oos_end
            )
        ]
        eligible = [
            r
            for r in rows
            if r.evidence_tier in ("A", "B", "C")
            and r.observed_at.tzinfo is not None
            and r.observed_at <= signal_at
            and horizon in r.returns
            and horizon in r.label_end
            and r.label_end[horizon] <= day
        ]
        for row in eligible:
            if row.day not in sessions:
                raise ValueError("UNKNOWN_TRAINING_SESSION")
            maturity = sessions.index(row.day) + horizon
            if maturity >= len(sessions) or row.label_end[horizon] != sessions[maturity]:
                raise ValueError("EXACT_HORIZON_MATURITY_REQUIRED")
            if (
                len(row.factors) != 19
                or not all(math.isfinite(v) for v in row.factors)
                or not math.isfinite(row.returns[horizon])
            ):
                raise ValueError("COMPLETE_FINITE_TRAINING_FACTS_REQUIRED")
        if len({r.day for r in eligible}) < 30:
            raise ValueError("INSUFFICIENT_MATURE_TRAINING")
        by_day: dict[date, list[Observation]] = {}
        for row in eligible:
            by_day.setdefault(row.day, []).append(row)
        if any(
            len({r.industry for r in values}) != len(values) or len(values) < 12
            for values in by_day.values()
        ):
            raise ValueError("COMPLETE_TRAINING_CROSS_SECTIONS_REQUIRED")
        names = H10_FACTORS if horizon == 10 else FACTORS_19
        columns = [FACTORS_19.index(n) for n in names]
        x = np.asarray([r.factors for r in eligible], dtype=float)[:, columns]
        centered_targets = {
            d: float(np.mean([r.returns[horizon] for r in values])) for d, values in by_day.items()
        }
        y = np.asarray([r.returns[horizon] - centered_targets[r.day] for r in eligible])
        mean, std = np.zeros(len(columns)), np.ones(len(columns))
        if spec.scaling == "TRAIN_ONLY_STANDARDIZED":
            mean, std = x.mean(axis=0), x.std(axis=0, ddof=0)
            if not np.isfinite(std).all() or (std <= 0).any():
                raise ValueError("ZERO_TRAIN_VARIANCE")
        fitted = NumPyRidge(spec.alpha).fit((x - mean) / std, y)
        predicted = fitted.predict((current[:, columns] - mean) / std)
        if float(predicted.std(ddof=0)) <= 1e-12:
            raise ValueError("DEGENERATE_CURRENT_PREDICTIONS")
        scores += weight * (predicted - predicted.mean()) / predicted.std(ddof=0)
        model_records.append(
            {
                "horizon": horizon,
                "factors": list(names),
                "alpha": spec.alpha,
                "coefficients": fitted.coef_.tolist(),
                "intercept": fitted.intercept_,
                "training_means": mean.tolist(),
                "training_stds": std.tolist(),
                "label_cutoff": str(cutoff),
                "training_window_start": str(window),
                "training_dates": len(by_day),
                "training_samples": len(eligible),
            }
        )
    ranked = sorted(zip(industries, map(float, scores), strict=True), key=lambda r: (-r[1], r[0]))
    # Caller obtains pools through the existing admitted mapping/evidence boundary.
    # Scores are injected only after fitting; proxies never rescale those scores.
    top = ranked[:5]
    pools = {
        code: tuple(
            IndustryCandidate(**(vars(c) | {"final_score": score}))
            for c in mapping_pools.get(code, ())
        )
        for code, score in top
    }
    chosen = select_mappings(top, pools)
    allocation = evaluate_policy(POLICY_B40_WITH_CASH, list(chosen), exposure_vectors, cap=0.35)
    return {
        "product": "ETF_QUANT_V2",
        "candidate_sha256": spec.candidate_sha256,
        "signal_date": str(day),
        "execution_date": str(sessions[index + 1]),
        "models": model_records,
        "rankings": ranked,
        "allocation": allocation.as_dict(),
        "accounting": "WAIT_FOR_GENUINE_FINALIZED_T_PLUS_ONE_RAW_OPEN",
        "mode": "SIMULATION_ONLY",
        "validation_accepted": spec.validated and not spec.final_oos_authorized,
        "historical_final_oos_accepted": spec.validated and spec.final_oos_authorized,
        "broker_enabled": False,
        "real_order_path": False,
    }


def publish_forward_plan(
    root: Path, plan: dict[str, Any], *, authorization: bool, frozen_at: datetime, now: datetime
) -> Path:
    """Explicit future human launch gate, independent immutable V2 namespace."""
    resolved = root.resolve()
    if not authorization:
        raise ValueError("EXPLICIT_FUTURE_SHADOW_LAUNCH_AUTHORIZATION_REQUIRED")
    if any(
        (p / ".git").exists() or p.name.lower() == "etf-quant-v1"
        for p in (resolved, *resolved.parents)
    ):
        raise ValueError("INDEPENDENT_EXTERNAL_V2_NAMESPACE_REQUIRED")
    if resolved.name != "etf-quant-v2" or now.tzinfo is None or frozen_at.tzinfo is None:
        raise ValueError("INDEPENDENT_EXTERNAL_V2_NAMESPACE_REQUIRED")
    signal_day = date.fromisoformat(plan["signal_date"])
    if (
        signal_day <= frozen_at.astimezone(SHANGHAI).date()
        or signal_day > now.astimezone(SHANGHAI).date()
    ):
        raise ValueError("RETROACTIVE_OR_FUTURE_EPOCH_DENIED")
    if (
        plan.get("product") != "ETF_QUANT_V2"
        or plan.get("broker_enabled")
        or plan.get("real_order_path")
        or plan.get("mode") != "SIMULATION_ONLY"
    ):
        raise ValueError("SIMULATION_ONLY_V2_REQUIRED")
    resolved.mkdir(parents=True, exist_ok=True)
    # One lock covers uniqueness and publication, so competing callers cannot
    # create two generations for one date. A crash leaves a closed gate.
    lock = resolved / ".publish.lock"
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        existing = sorted(resolved.glob("*/plan.json"))
        if (
            existing
            and max(date.fromisoformat(json.loads(p.read_text())["signal_date"]) for p in existing)
            >= signal_day
        ):
            raise ValueError("STRICTLY_FORWARD_UNIQUE_SIGNAL_REQUIRED")
        generation = resolved / (str(signal_day) + "_" + content_hash(plan)[:12])
        generation.mkdir()
        descriptor = os.open(generation / "plan.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n")
    finally:
        lock.unlink()
    return generation


def load_candidate(path: Path) -> dict[str, Any]:
    from strategies.etf_quant.runtime.implementation import verify_implementation

    repository = Path(__file__).resolve().parents[2]
    certified = verify_implementation(repository)
    name = "strategies/etf_quant_v2/config/candidate.json"
    if (
        path.resolve() != (repository / name).resolve()
        or certified.get(name) != hashlib.sha256(path.read_bytes()).hexdigest()
    ):
        raise ValueError("CERTIFIED_V2_CANDIDATE_PATH_REQUIRED")
    doc = json.loads(path.read_text())
    body = {k: v for k, v in doc.items() if k != "candidate_sha256"}
    if doc.get("candidate_sha256") != content_hash(body) or doc.get("product") != "ETF_QUANT_V2":
        raise ValueError("V2_CANDIDATE_INTEGRITY_ERROR")
    if doc.get("final_oos_opened") or doc.get("shadow_started") or doc.get("broker_enabled"):
        raise ValueError("V2_RESEARCH_SAFETY_CONTRACT_ERROR")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--authorize-future-shadow", action="store_true")
    parser.add_argument("--authorize-unvalidated-research", action="store_true")
    args = parser.parse_args()
    candidate = load_candidate(args.candidate)
    if not args.readiness_only:
        if not args.authorize_future_shadow or args.input is None or args.runtime_root is None:
            raise ValueError("EXPLICIT_FUTURE_LAUNCH_AND_FACT_INPUTS_REQUIRED")
        from .inputs import plan_from_inputs

        plan = plan_from_inputs(
            candidate,
            json.loads(args.input.read_text()),
            allow_unvalidated_research=args.authorize_unvalidated_research,
        )
        publish_forward_plan(
            args.runtime_root,
            plan,
            authorization=True,
            frozen_at=datetime.fromisoformat(candidate["frozen_at"]),
            now=datetime.now(SHANGHAI),
        )
        print(
            json.dumps(
                {
                    "product": "ETF_QUANT_V2",
                    "signal_date": plan["signal_date"],
                    "mode": "SIMULATION_ONLY",
                }
            )
        )
        return
    print(
        json.dumps(
            {
                "product": "ETF_QUANT_V2",
                "candidate_sha256": candidate["candidate_sha256"],
                "shadow_ready": True,
                "validation_accepted": candidate["validation_accepted"],
                "research_status": candidate["research_status"],
                "shadow_started": False,
                "next_start": "NEXT_GENUINE_FINALIZED_SESSION_AFTER_CANDIDATE_FREEZE",
                "epoch": 0,
                "signal": 0,
                "intent": 0,
                "fill": 0,
                "broker_enabled": False,
                "real_order_path": False,
                "final_oos_opened": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

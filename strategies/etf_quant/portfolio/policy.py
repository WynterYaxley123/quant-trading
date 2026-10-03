"""PROXY_EXECUTION_POLICY_V1 -- how a signalled industry that cannot be faithfully executed is handled.

The problem this module solves
------------------------------
The frozen model ranks Shenwan L2 industries and the Top5 is taken as given. The strict execution
mapping is structurally unsatisfiable (4 of 134 industries), so a proxy layer relaxes the *instrument*
and measures substitution quality as the target industry's share of the benchmark's official weight.

That still leaves one industry unserved. `3706 医疗服务` -- the model's **highest-ranked** industry --
has no liquid proxy in which it is the benchmark's dominant exposure at >= 40%. So the round must decide
what to do with a signal that exists but cannot be faithfully bought.

Three policies, one question
----------------------------
* ``A40_FULLY_INVESTED``  -- execute all five, accepting a proxy whose dominant exposure is a
  *different* industry. Nominally complete, but the strongest signal is carried by the weakest mapping.
* ``B40_RENORMALIZED``    -- drop the unexecutable industry and re-scale the survivors back to fully
  invested. Capital is fully deployed, but every surviving industry is now sized *larger* than the model
  asked for, and the deleted industry's signal is silently gone.
* ``B40_WITH_CASH``       -- drop the unexecutable industry and **retain its target weight as cash**.
  Survivors keep exactly the weights the model gave them; nothing is re-scaled and nothing is
  redistributed.

Design rules encoded here
-------------------------
1. **The alpha model is read, never written.** Weights come only from the frozen ``final_score`` softmax.
   Proxy purity selects instruments; it never scales a score.
2. **Cash is not an asset.** It is ``UNALLOCATED_EXECUTION_CAPACITY``: a named, measurable consequence of
   instrument unavailability. It is never a fifth ETF, never a benchmark substitute, and its return is
   deliberately undefined here.
3. **Cash is never silently redistributed.** ``B40_WITH_CASH`` must produce survivor weights *identical*
   to the survivors' original target weights. Any drift would mean capital was reallocated through the
   back door, which is the exact failure the policy exists to avoid.
4. **Nominal exposure is not actual exposure.** An ETF that is 45% the target industry is also 55%
   something else. The portfolio's true industry exposure is
   ``sum(etf_weight * benchmark_l2_weight / 100)`` and it is reported alongside the nominal weights,
   because the difference is the whole point of measuring proxy quality.

Pure functions over already-verified inputs: no network, no disk, no pandas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TypedDict

from . import AllocationStatus, size_targets

# ---------------------------------------------------------------------------
# Policy identity
# ---------------------------------------------------------------------------

POLICY_A40_FULLY_INVESTED = "A40_FULLY_INVESTED"
POLICY_B40_RENORMALIZED = "B40_RENORMALIZED"
POLICY_B40_WITH_CASH = "B40_WITH_CASH"

ALL_POLICIES = (POLICY_A40_FULLY_INVESTED, POLICY_B40_RENORMALIZED, POLICY_B40_WITH_CASH)

#: Rule identity for the B-type admissibility test.
MIN_TARGET_EXPOSURE_B40 = 40.0
REQUIRE_TARGET_IS_LARGEST_B40 = True

#: Cash is a *state*, not an instrument. The name is load-bearing: it prevents cash from being
#: modelled as a holding whose return someone later feels obliged to estimate.
CASH_INSTRUMENT_ID = "CASH"
CASH_SEMANTICS = "UNALLOCATED_EXECUTION_CAPACITY"
CASH_RETURN_DEFINITION = "UNDEFINED_IN_THIS_ROUND"
#: The cash contract's own field name, so the two documents cannot drift apart.
CASH_WEIGHT_FIELD = "unallocated_execution_capacity_weight"
#: Using 0.0 as an implicit risk-free rate is not neutral: it silently changes NAV and every
#: downstream ratio. The return is therefore explicitly unmodelled rather than defaulted.
CASH_RETURN_MODEL = "UNDEFINED_NOT_MODELLED_THIS_ROUND"
#: A single explicit switch, plus a string-typed zero so the "nothing was redistributed" claim can be
#: compared literally instead of through a float tolerance that would hide a small leak.
EXECUTION_REDISTRIBUTION_ENABLED = False
RENORMALISATION_MODE = "NEVER_RENORMALISE_ACROSS_EXECUTION_FILTER"
REDISTRIBUTED_WEIGHT_LITERAL = "0"
#: Cash generates no order at all. A zero-quantity intent or a sentinel instrument would both leak
#: cash into the member set and silently disable the executability rebalance trigger.
CASH_ORDER_OUTCOME = "NO_ORDER_UNEXECUTABLE_SIGNAL"

#: Redistribution behaviour. ``B40_WITH_CASH`` must use RETAIN_AS_CASH; the enum exists so that
#: "cash happened to stay put" and "cash was contractually retained" are distinguishable.
REDISTRIBUTE_TO_SURVIVORS = "REDISTRIBUTE_TO_SURVIVORS"
RETAIN_AS_CASH = "RETAIN_AS_CASH"

#: Why an industry was not executed. Never conflated with "the model stopped liking it".
REASON_TARGET_EXPOSURE_BELOW_THRESHOLD = "TARGET_EXPOSURE_BELOW_THRESHOLD"
REASON_TARGET_NOT_LARGEST_L2 = "TARGET_NOT_LARGEST_L2"
REASON_WEIGHT_SET_INCOMPLETE = "WEIGHT_SET_INCOMPLETE"
REASON_NO_LIQUID_ETF = "NO_LIQUID_ETF"
REASON_NO_CANDIDATE = "NO_CANDIDATE"

#: Rebalance trigger semantics. A change in *executability* is a change in the final executable
#: member set: an industry that was cash yesterday and executable today must be traded into, and a
#: policy that ignored this would leave the account permanently under-invested after a one-off data
#: gap. Worse, it would let the ranking, the persisted intent and the actual holdings describe three
#: different portfolios, and because a missed T+1 is blocking rather than back-filled, that
#: divergence is not repairable after the fact.
#:
#: Implementation note: the frozen ``rebalance_decision`` asserts an exactly-five-member set and must
#: NOT be relaxed to accept four -- that assertion is what validates identity on the strict path. The
#: executability rule therefore belongs in a *sibling* function in a new module, selected by an
#: explicit policy flag, with the frozen function left byte-identical and still the default.
REBALANCE_TRIGGER = "EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1"
REBALANCE_TRIGGER_FROZEN_PREDECESSOR = "EXECUTABLE_ETF_SET_CHANGE_ONLY"
REBALANCE_SIBLING_FUNCTION = "rebalance_decision_v2"
MAPPING_SELECTION_SIBLING_FUNCTION = "select_mappings_partial"

SINGLE_ETF_CAP = 0.35


class PolicyError(ValueError):
    """Raised when a policy cannot be evaluated under the contract."""


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndustryCandidate:
    """The chosen execution instrument for one signalled industry."""

    l2_code: str
    l2_name: str | None
    final_score: float
    etf_code: str | None
    benchmark_code: str | None
    mapping_type: str  # STRICT_MAPPING | PROXY_EXPOSURE
    target_l2_exposure: float | None  # percent, None when no candidate exists
    second_largest_l2_exposure: float | None
    dominance_margin: float | None
    target_is_largest_l2: bool | None
    weight_quality: str | None
    liquidity_status: str | None
    mean_amount_cny: float | None
    grade: str | None = None
    evidence_source: str | None = None

    @property
    def executable(self) -> bool:
        return self.etf_code is not None and self.target_l2_exposure is not None

    def a40_rejection_reason(self) -> str | None:
        """A40 relaxes dominance, never completeness or liquidity admission.

        This comparative policy keeps its historical sizing rule. Evidence must
        still describe a real, liquid instrument before any capital is assigned.
        """
        if (
            not self.executable
            or self.benchmark_code is None
            or self.mapping_type not in ("STRICT_MAPPING", "PROXY_EXPOSURE")
        ):
            return REASON_NO_CANDIDATE
        if self.weight_quality != "COMPLETE_WEIGHT_SET":
            return REASON_WEIGHT_SET_INCOMPLETE
        if (
            self.liquidity_status != "LIQUIDITY_ADMISSION_PASS"
            or not isinstance(self.mean_amount_cny, (int, float))
            or isinstance(self.mean_amount_cny, bool)
            or not math.isfinite(self.mean_amount_cny)
            or self.mean_amount_cny <= 0
        ):
            return REASON_NO_LIQUID_ETF
        if (
            not isinstance(self.target_l2_exposure, (int, float))
            or isinstance(self.target_l2_exposure, bool)
            or not math.isfinite(self.target_l2_exposure)
            or not 0 <= self.target_l2_exposure <= 100
        ):
            return REASON_TARGET_EXPOSURE_BELOW_THRESHOLD
        return None

    @property
    def passes_b40(self) -> bool:
        """The B-type admission test: >= 40%, the target is the dominant exposure, AND the evidence
        is complete.

        The weight-quality gate belongs here, not only in :meth:`b40_rejection_reason`. An earlier
        version checked the first two conditions and left the third to the reason string, which meant
        a caller using the boolean -- as ``evaluate_policy`` does -- would admit a benchmark whose
        official weights are short. Fail-closed means the predicate itself refuses.
        """
        return (
            self.executable
            and self.mapping_type in ("STRICT_MAPPING", "PROXY_EXPOSURE")
            and self.benchmark_code is not None
            and self.weight_quality == "COMPLETE_WEIGHT_SET"
            and self.liquidity_status == "LIQUIDITY_ADMISSION_PASS"
            and self.mean_amount_cny is not None
            and isinstance(self.mean_amount_cny, (int, float))
            and not isinstance(self.mean_amount_cny, bool)
            and math.isfinite(self.mean_amount_cny)
            and self.mean_amount_cny > 0
            and isinstance(self.target_l2_exposure, (int, float))
            and not isinstance(self.target_l2_exposure, bool)
            and math.isfinite(self.target_l2_exposure)
            and self.target_l2_exposure <= 100
            and self.target_l2_exposure >= MIN_TARGET_EXPOSURE_B40
            and bool(self.target_is_largest_l2)
        )

    def b40_rejection_reason(self) -> str | None:
        if not self.executable:
            return REASON_NO_CANDIDATE
        if self.weight_quality != "COMPLETE_WEIGHT_SET":
            return REASON_WEIGHT_SET_INCOMPLETE
        if (
            self.liquidity_status != "LIQUIDITY_ADMISSION_PASS"
            or not isinstance(self.mean_amount_cny, (int, float))
            or isinstance(self.mean_amount_cny, bool)
            or not math.isfinite(self.mean_amount_cny)
            or self.mean_amount_cny <= 0
        ):
            return REASON_NO_LIQUID_ETF
        if (
            not isinstance(self.target_l2_exposure, (int, float))
            or isinstance(self.target_l2_exposure, bool)
            or not math.isfinite(self.target_l2_exposure)
            or self.target_l2_exposure > 100
            or self.target_l2_exposure < MIN_TARGET_EXPOSURE_B40
        ):
            return REASON_TARGET_EXPOSURE_BELOW_THRESHOLD
        if not self.target_is_largest_l2:
            return REASON_TARGET_NOT_LARGEST_L2
        return None


@dataclass(frozen=True)
class BenchmarkExposureVector:
    """One benchmark's official weight attributed to Shenwan L2 industries (percent, ~100 total)."""

    benchmark_code: str
    weights_by_l2: dict[str, float]

    def exposure(self, l2_code: str) -> float:
        return float(self.weights_by_l2.get(l2_code, 0.0))


# ---------------------------------------------------------------------------
# Portfolio result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyResult:
    policy: str
    candidates: tuple[IndustryCandidate, ...]
    executed: tuple[IndustryCandidate, ...]
    skipped: tuple[tuple[IndustryCandidate, str], ...]  # (candidate, rejection reason)

    #: Weight the policy assigns to each executed industry, before any exposure leakage.
    nominal_weights: dict[str, float]
    #: Weight a skipped industry *would* have carried and has now forfeited. Distinct from
    #: ``nominal_weights``, which is zero for a skipped industry: reporting only the latter made a
    #: 35% cash retention print as "forfeited 0.000%", which is exactly backwards.
    forfeited_weights: dict[str, float]
    #: Cash retained, as a fraction of the whole account. 0.0 for fully-invested policies.
    cash_weight: float
    #: Weights actually assigned to ETFs (sums to risk_asset_weight).
    etf_weights: dict[str, float]

    #: Actual Shenwan L2 exposure of the account, including leakage from every ETF held.
    actual_l2_exposure: dict[str, float]
    #: Actual exposure restricted to the signalled industries.
    actual_target_exposure: dict[str, float]
    #: Nominal minus actual, per signalled industry. Negative means the industry got less than intended.
    fidelity_gap: dict[str, float]

    metrics: dict = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def risk_asset_weight(self) -> float:
        return math.fsum(self.etf_weights.values())

    def as_dict(self) -> dict:
        return {
            "policy": self.policy,
            "cash_weight": round(self.cash_weight, 12),
            "risk_asset_weight": round(self.risk_asset_weight, 12),
            "cash_instrument_id": CASH_INSTRUMENT_ID,
            "cash_semantics": CASH_SEMANTICS,
            "cash_return_definition": CASH_RETURN_DEFINITION,
            "rebalance_trigger": REBALANCE_TRIGGER,
            "executed": [
                {
                    "l2_code": c.l2_code,
                    "l2_name": c.l2_name,
                    "etf_code": c.etf_code,
                    "benchmark_code": c.benchmark_code,
                    "mapping_type": c.mapping_type,
                    "weight": round(self.etf_weights.get(c.l2_code or "", 0.0), 12),
                    "nominal_weight": round(self.nominal_weights.get(c.l2_code, 0.0), 12),
                    "target_l2_exposure": c.target_l2_exposure,
                    "second_largest_l2_exposure": c.second_largest_l2_exposure,
                    "dominance_margin": c.dominance_margin,
                    "target_is_largest_l2": c.target_is_largest_l2,
                    "mean_amount_cny_20d": c.mean_amount_cny,
                    "liquidity_status": c.liquidity_status,
                    "grade": c.grade,
                }
                for c in self.executed
            ],
            "skipped": [
                {
                    "l2_code": c.l2_code,
                    "l2_name": c.l2_name,
                    "reason": reason,
                    "weight_forfeited": round(self.forfeited_weights.get(c.l2_code, 0.0), 12),
                    "target_l2_exposure": c.target_l2_exposure,
                    "target_is_largest_l2": c.target_is_largest_l2,
                }
                for c, reason in self.skipped
            ],
            "actual_l2_exposure": {
                k: round(v, 8)
                for k, v in sorted(self.actual_l2_exposure.items(), key=lambda kv: (-kv[1], kv[0]))
            },
            "actual_target_exposure": {
                k: round(v, 8) for k, v in sorted(self.actual_target_exposure.items())
            },
            "fidelity_gap": {k: round(v, 8) for k, v in sorted(self.fidelity_gap.items())},
            "metrics": self.metrics,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Base target weights -- the frozen model's own sizing
# ---------------------------------------------------------------------------


def softmax(scores: list[float]) -> list[float]:
    """Numerically stable softmax, for reporting the *uncapped* reference only.

    Capped sizing must never be computed here. The frozen allocator ``size_targets`` distributes a
    cap breach by re-solving the softmax over the surviving names, which is **not** the same as
    spreading the excess over each name's remaining room (``cap - w``). Those two rules disagree by
    up to 1.51 percentage points on this round's actual Top5, so reimplementing the cap would put a
    second, silently different allocator in the tree. Everything that produces tradable weights
    delegates to the frozen function instead.
    """
    if not scores:
        raise PolicyError("SOFTMAX_NEEDS_AT_LEAST_ONE_SCORE")
    peak = max(scores)
    exps = [math.exp(s - peak) for s in scores]
    total = math.fsum(exps)
    if not math.isfinite(total) or total <= 0:
        raise PolicyError("SOFTMAX_DEGENERATE")
    return [e / total for e in exps]


def frozen_size(scores: dict[str, float], *, cap: float, required_assets: int) -> dict[str, float]:
    """The ONLY capped-sizing path: delegate to the frozen ``size_targets``.

    Returns ``{code: weight}`` or raises with the allocator's own status, so a caller can never
    mistake "the frozen contract refuses to size this set" for "the set sized to zero".
    """
    result = size_targets(scores, max_weight=cap, required_assets=required_assets)
    if result.status is not AllocationStatus.READY:
        raise PolicyError(f"SIZING_NOT_READY:{result.status.value}:{result.reason}")
    return {t.asset_id: t.target_weight for t in result.targets}


def frozen_size_status(
    scores: dict[str, float], *, cap: float, required_assets: int
) -> tuple[str, dict[str, float], float]:
    """Non-raising variant, so the contract's refusal behaviour can be *reported* rather than hidden.

    This is how the round documents that the frozen allocator, called the way the frozen runtime
    calls it (``required_assets=5``), returns ``INSUFFICIENT_EXECUTABLE_ASSETS`` with 100% unallocated
    for any four-asset policy.
    """
    result = size_targets(scores, max_weight=cap, required_assets=required_assets)
    return (
        result.status.value,
        {t.asset_id: t.target_weight for t in result.targets},
        float(result.unallocated_weight),
    )


def raw_softmax_weights(candidates: list["IndustryCandidate"]) -> dict[str, float]:
    """Uncapped softmax over the frozen scores -- the model's intent before any cap or policy."""
    if not candidates:
        raise PolicyError("NO_CANDIDATES")
    weights = softmax([c.final_score for c in candidates])
    return {c.l2_code: w for c, w in zip(candidates, weights)}


def base_target_weights(
    candidates: list["IndustryCandidate"], cap: float = SINGLE_ETF_CAP
) -> dict[str, float]:
    """The frozen model's sizing of a signal set: softmax(final_score) then the frozen cap.

    ``required_assets`` is set to the size of the set being sized. That parameterisation is the
    entire execution-policy extension: the frozen default of 5 is preserved for every existing
    caller, and a policy that declares a different executable count must say so explicitly rather
    than have the allocator guess.
    """
    if not candidates:
        raise PolicyError("NO_CANDIDATES")
    scores = {c.l2_code: c.final_score for c in candidates}
    return frozen_size(scores, cap=cap, required_assets=len(scores))


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


def _actual_exposure(
    etf_weights: dict[str, float],
    candidate_by_l2: dict[str, IndustryCandidate],
    vectors: dict[str, BenchmarkExposureVector],
) -> dict[str, float]:
    """Account-level Shenwan L2 exposure implied by what is actually held.

    ``etf_weight * benchmark_l2_weight / 100``, summed. This is where proxy leakage becomes visible:
    an ETF bought for one industry also buys whatever else is in its benchmark.
    """
    exposure: dict[str, float] = {}
    for l2_code, weight in etf_weights.items():
        cand = candidate_by_l2[l2_code]
        vector = vectors.get(cand.benchmark_code or "")
        if vector is None:
            # No official vector: the only honest attribution is the instrument itself, and that
            # would overstate purity, so leave it unattributed rather than invent one.
            continue
        for other_l2, pct in vector.weights_by_l2.items():
            exposure[other_l2] = exposure.get(other_l2, 0.0) + weight * (pct / 100.0)
    return exposure


def _fidelity_metrics(
    result_weights: dict[str, float],
    executed: tuple[IndustryCandidate, ...],
    cash_weight: float,
    actual: dict[str, float],
    target_l2s: set[str],
) -> dict:
    """Execution-quality metrics. These describe the instrument, never an expected return."""
    risk = math.fsum(result_weights.values())
    purities = [c.target_l2_exposure or 0.0 for c in executed]
    if risk > 0:
        weighted_purity = math.fsum(
            (result_weights[c.l2_code] / risk) * (c.target_l2_exposure or 0.0) for c in executed
        )
        weighted_leakage = math.fsum(
            (result_weights[c.l2_code] / risk) * (100.0 - (c.target_l2_exposure or 0.0))
            for c in executed
        )
    else:
        weighted_purity = 0.0
        weighted_leakage = 0.0

    unintended = {k: v for k, v in actual.items() if k not in target_l2s and v > 0}
    unintended_ranked = sorted(unintended.items(), key=lambda kv: (-kv[1], kv[0]))

    # A target industry can appear in the actual exposure two ways: because we bought it, or as
    # incidental leakage from an instrument bought for something else. Only the first is intended,
    # and conflating them would let leakage masquerade as delivery of the signal.
    executed_l2s = {c.l2_code for c in executed}
    incidental_targets = {
        k: round(v, 8)
        for k, v in actual.items()
        if k in target_l2s and k not in executed_l2s and v > 0
    }

    amounts = [
        (result_weights.get(c.l2_code, 0.0), c.mean_amount_cny)
        for c in executed
        if c.mean_amount_cny
    ]
    if amounts and risk > 0:
        weighted_amount = math.fsum((w / risk) * a for w, a in amounts)
        min_amount = min(a for _, a in amounts)
        thinnest = min(executed, key=lambda c: c.mean_amount_cny or float("inf"))
        thinnest_code = thinnest.etf_code
    else:
        weighted_amount, min_amount, thinnest_code = None, None, None

    actual_risk = math.fsum(actual.values())
    hhi_actual = (
        math.fsum((v / actual_risk) ** 2 for v in actual.values()) if actual_risk > 0 else 0.0
    )
    hhi_etf = math.fsum((v / risk) ** 2 for v in result_weights.values()) if risk > 0 else 0.0
    return {
        "weighted_target_l2_purity": round(weighted_purity, 6),
        "minimum_individual_purity": round(min(purities), 6) if purities else 0.0,
        "maximum_individual_purity": round(max(purities), 6) if purities else 0.0,
        "weighted_leakage": round(weighted_leakage, 6),
        "largest_unintended_l2_code": unintended_ranked[0][0] if unintended_ranked else None,
        "largest_unintended_l2_weight": round(unintended_ranked[0][1], 8)
        if unintended_ranked
        else 0.0,
        "top5_unintended_l2s": [
            {"l2_code": k, "weight": round(v, 8)} for k, v in unintended_ranked[:5]
        ],
        "actual_l2_hhi": round(hhi_actual, 8),
        "etf_weight_hhi": round(hhi_etf, 8),
        "incidental_target_exposure": incidental_targets,
        "incidental_target_weight_total": round(math.fsum(incidental_targets.values()), 8),
        "weighted_mean_amount_cny_20d": round(weighted_amount, 2) if weighted_amount else None,
        "min_etf_mean_amount_cny_20d": min_amount,
        "thinnest_etf_code": thinnest_code,
        "cash_weight": round(cash_weight, 12),
        "risk_asset_weight": round(risk, 12),
        "risk_asset_count": len(result_weights),
        "max_etf_weight": round(max(result_weights.values()), 12) if result_weights else 0.0,
    }


def evaluate_policy(
    policy: str,
    candidates: list[IndustryCandidate],
    vectors: dict[str, BenchmarkExposureVector],
    *,
    cap: float = SINGLE_ETF_CAP,
) -> PolicyResult:
    """Evaluate one execution policy over one signal set.

    ``candidates`` must be ordered by descending model rank; the softmax is taken over exactly the
    industries the policy decides to execute, which is what makes the policies genuinely different.
    """
    if policy not in ALL_POLICIES:
        raise PolicyError(f"UNKNOWN_POLICY:{policy}")
    if not candidates:
        raise PolicyError("NO_CANDIDATES")
    target_l2s = {c.l2_code for c in candidates}
    candidate_by_l2 = {c.l2_code: c for c in candidates}
    notes: list[str] = []

    if policy == POLICY_A40_FULLY_INVESTED:
        # A40 relaxes dominance only. Quality and liquidity remain prerequisites.
        executed = tuple(c for c in candidates if c.a40_rejection_reason() is None)
        skipped = tuple(
            (c, reason) for c in candidates if (reason := c.a40_rejection_reason()) is not None
        )
        if not executed:
            raise PolicyError("A40_FULLY_INVESTED_NO_SURVIVOR")
        weights = base_target_weights(list(executed), cap)
        cash = 0.0
        reference = base_target_weights(candidates, cap)
        if skipped:
            notes.append(
                "A40: industries without an admissible candidate were dropped; A40 makes no promise "
                "about how many survive, only that it never applies a dominance test."
            )
    elif policy == POLICY_B40_RENORMALIZED:
        survivors = [c for c in candidates if c.passes_b40]
        skipped = tuple(
            (c, c.b40_rejection_reason() or REASON_NO_CANDIDATE)
            for c in candidates
            if not c.passes_b40
        )
        if not survivors:
            raise PolicyError("B40_RENORMALIZED_NO_SURVIVOR")
        weights = base_target_weights(survivors, cap)
        executed = tuple(survivors)
        cash = 0.0
        reference = base_target_weights(candidates, cap)
        notes.append(
            "B40_RENORMALIZED: survivors re-softmaxed over the survivor set, so each survivor "
            "is sized larger than the model asked for. The deleted signal is gone entirely."
        )
    else:  # POLICY_B40_WITH_CASH
        survivors = [c for c in candidates if c.passes_b40]
        skipped = tuple(
            (c, c.b40_rejection_reason() or REASON_NO_CANDIDATE)
            for c in candidates
            if not c.passes_b40
        )
        # The reference sizing is the FULL signal set. Survivors keep exactly their reference weight;
        # the forfeited weight becomes cash and is never handed to anyone else.
        reference = base_target_weights(candidates, cap)
        weights = {c.l2_code: reference[c.l2_code] for c in survivors}
        executed = tuple(survivors)
        cash = math.fsum(reference[c.l2_code] for c, _ in skipped)
        if abs(math.fsum(weights.values()) + cash - 1.0) > 1e-9:
            raise PolicyError("CASH_BROKE_SUM_TO_ONE")
        notes.append(
            "B40_WITH_CASH: survivor weights are the original target weights, unchanged. "
            "Cash equals the forfeited target weights exactly; redistribution is zero."
        )
        for c, _ in skipped:
            if reference.get(c.l2_code, 0.0) > 0:
                notes.append(
                    f"UNEXECUTED_SIGNAL_WEIGHT {c.l2_code}={reference[c.l2_code]:.6f} "
                    f"retained as cash, not redistributed."
                )

    nominal = {c.l2_code: weights.get(c.l2_code, 0.0) for c in candidates}
    # A skipped industry forfeits the weight it would have carried under the full-signal reference.
    forfeited = {
        c.l2_code: (reference.get(c.l2_code, 0.0) if not weights.get(c.l2_code) else 0.0)
        for c, _ in skipped
    }
    actual = _actual_exposure(weights, candidate_by_l2, vectors)
    actual_target = {l2: actual.get(l2, 0.0) for l2 in sorted(target_l2s)}
    gap = {l2: actual_target[l2] - nominal.get(l2, 0.0) for l2 in sorted(target_l2s)}
    metrics = _fidelity_metrics(weights, executed, cash, actual, target_l2s)
    metrics["single_etf_cap"] = cap
    metrics["cap_respected"] = (max(weights.values()) <= cap + 1e-12) if weights else True
    metrics["sum_risk_plus_cash"] = round(math.fsum(weights.values()) + cash, 12)

    return PolicyResult(
        policy=policy,
        candidates=tuple(candidates),
        executed=executed,
        skipped=skipped,
        nominal_weights={k: round(v, 12) for k, v in nominal.items()},
        forfeited_weights={k: round(v, 12) for k, v in forfeited.items()},
        cash_weight=round(cash, 12),
        etf_weights={k: round(v, 12) for k, v in weights.items()},
        actual_l2_exposure=actual,
        actual_target_exposure=actual_target,
        fidelity_gap=gap,
        metrics=metrics,
        notes=tuple(notes),
    )


class DistortionRow(TypedDict):
    weight_reference: float
    weight_renormalized: float
    absolute_uplift: float
    relative_uplift: float | None


def renormalization_distortion(reference: dict[str, float], renormalized: dict[str, float]) -> dict:
    """How much each surviving industry is inflated by dropping a signal and re-scaling.

    Reported as an absolute weight change and a relative uplift, because "3703 went from 24.5% to 32%"
    and "3703 grew by 31%" are both true and describe different risks.
    """
    rows: dict[str, DistortionRow] = {}
    for l2, new in sorted(renormalized.items()):
        old = reference.get(l2, 0.0)
        rows[l2] = {
            "weight_reference": round(old, 12),
            "weight_renormalized": round(new, 12),
            "absolute_uplift": round(new - old, 12),
            "relative_uplift": round((new - old) / old, 8) if old > 0 else None,
        }
    return {
        "rows": rows,
        "max_absolute_uplift": round(
            max((r["absolute_uplift"] for r in rows.values()), default=0.0), 12
        ),
        "max_relative_uplift": round(
            max((r["relative_uplift"] or 0.0 for r in rows.values()), default=0.0), 8
        ),
        "total_uplift": round(math.fsum(r["absolute_uplift"] for r in rows.values()), 12),
    }


__all__ = [
    "ALL_POLICIES",
    "BenchmarkExposureVector",
    "CASH_INSTRUMENT_ID",
    "CASH_ORDER_OUTCOME",
    "CASH_RETURN_DEFINITION",
    "CASH_RETURN_MODEL",
    "CASH_SEMANTICS",
    "CASH_WEIGHT_FIELD",
    "EXECUTION_REDISTRIBUTION_ENABLED",
    "MAPPING_SELECTION_SIBLING_FUNCTION",
    "RENORMALISATION_MODE",
    "REDISTRIBUTED_WEIGHT_LITERAL",
    "REBALANCE_SIBLING_FUNCTION",
    "REBALANCE_TRIGGER",
    "REBALANCE_TRIGGER_FROZEN_PREDECESSOR",
    "IndustryCandidate",
    "MIN_TARGET_EXPOSURE_B40",
    "POLICY_A40_FULLY_INVESTED",
    "POLICY_B40_RENORMALIZED",
    "POLICY_B40_WITH_CASH",
    "PolicyError",
    "PolicyResult",
    "REASON_NO_CANDIDATE",
    "REASON_NO_LIQUID_ETF",
    "REASON_TARGET_EXPOSURE_BELOW_THRESHOLD",
    "REASON_TARGET_NOT_LARGEST_L2",
    "REASON_WEIGHT_SET_INCOMPLETE",
    "REBALANCE_TRIGGER",
    "REDISTRIBUTE_TO_SURVIVORS",
    "REQUIRE_TARGET_IS_LARGEST_B40",
    "RETAIN_AS_CASH",
    "SINGLE_ETF_CAP",
    "base_target_weights",
    "evaluate_policy",
    "frozen_size",
    "frozen_size_status",
    "raw_softmax_weights",
    "renormalization_distortion",
    "softmax",
]

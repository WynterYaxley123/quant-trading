"""PROXY_EXPOSURE_V1 -- industry exposure through a benchmark's official weights.

Why this module exists
----------------------
The frozen model emits a **Shenwan Level-2 industry code**. The strict execution mapping
(`mapping/registry.py`) only admits an ETF when the index it tracks *is* the target industry's
index. That rule is correct but structurally unsatisfiable: only 4 of 134 current-active L2
industries have such an ETF, so a strict Top5 cannot be built.

A proxy relaxes the *instrument*, never the *signal*. The model still ranks Shenwan L2
industries; execution may then use an ETF whose official tracked index carries a large weight
of the target industry. The quality of that substitution is a measurable number -- the target
industry's share of the benchmark's official weight -- and that number is what this module
computes and gates on.

Non-negotiables encoded here
----------------------------
* **Never assume equal weight.** An unweighted constituent list is discovery evidence only and
  can never be admitted. :data:`ADMISSIBLE_WEIGHT_SOURCES` is the whitelist, and a source
  outside it fails closed.
* **Never normalise away missing data.** A benchmark whose weights are short of complete is
  labelled :data:`INCOMPLETE_WEIGHT_SET` and is not admissible. The raw sum is reported.
* **STRICT beats PROXY.** An industry that has a strict ETF is never downgraded to a proxy.
* **Purity never touches alpha.** Proxy quality selects an instrument. It never scales a score.

Pure functions over already-verified inputs: no network, no disk, no pandas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Mapping identity
# ---------------------------------------------------------------------------

MAPPING_TYPE_STRICT = "STRICT_MAPPING"
MAPPING_TYPE_PROXY = "PROXY_EXPOSURE"

# ---------------------------------------------------------------------------
# Evidence levels. Only the first two may ever admit an instrument.
# ---------------------------------------------------------------------------

OFFICIAL_WEIGHT = "OFFICIAL_WEIGHT"  # LEVEL 1: index provider's own weights
PCF_DERIVED_WEIGHT = "PCF_DERIVED_WEIGHT"  # LEVEL 2: official PCF basket x legit prices
UNWEIGHTED_DIAGNOSTIC = "UNWEIGHTED_DIAGNOSTIC"  # LEVEL 3: constituents only, discovery only

ADMISSIBLE_WEIGHT_SOURCES = (OFFICIAL_WEIGHT, PCF_DERIVED_WEIGHT)

#: Quality labels attached to a benchmark's weight vector.
COMPLETE_WEIGHT_SET = "COMPLETE_WEIGHT_SET"
INCOMPLETE_WEIGHT_SET = "INCOMPLETE_WEIGHT_SET"

#: A reconstructed vector must land inside this band *and* account for every officially
#: declared constituent before it counts as complete. The band absorbs two-decimal rounding
#: in the published weights; it is not a licence to renormalise.
WEIGHT_SUM_BAND = (99.0, 100.5)

#: Research-only purity ladder. These are descriptive labels for reporting; they are NOT
#: production thresholds and no admission decision reads them.
GRADE_STRICT = "STRICT"
GRADE_HIGH = "HIGH_PURITY_PROXY"
GRADE_MEDIUM = "MEDIUM_PURITY_PROXY"
GRADE_LOW = "LOW_PURITY_PROXY"
GRADE_UNSUITABLE = "UNSUITABLE"

HIGH_PURITY_FLOOR = 80.0
MEDIUM_PURITY_FLOOR = 60.0
LOW_PURITY_FLOOR = 50.0

#: The lowest target exposure this round is willing to *test*. Below this the substitution
#: stops describing the industry at all. This is a research boundary, not a recommendation.
RESEARCH_MIN_THRESHOLD = 40.0


class ProxyError(ValueError):
    """Raised when a proxy decision cannot be made under the contract."""


# ---------------------------------------------------------------------------
# Weight parsing
# ---------------------------------------------------------------------------


def parse_weight_pct(value) -> float | None:
    """Parse an official weight into a percentage number, or ``None`` if unusable.

    Published weights arrive as strings such as ``"2.53%"``. The placeholder the provider
    renders for a security with no published weight is ``"- -"``. Both must be handled
    explicitly: a parse failure is *missing evidence*, and silently treating it as 0.0 would
    understate the target industry's exposure.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if text in {"-", "--", "- -", "—", "N/A", "n/a"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


# ---------------------------------------------------------------------------
# Benchmark -> L2 exposure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkExposure:
    """One benchmark's official weight attributed to Shenwan L2 industries."""

    benchmark_code: str
    benchmark_name: str | None
    index_provider: str | None
    constituent_date: str | None
    weight_source_type: str
    weight_source_url: str | None
    evidence_observed_at: str | None

    constituent_count: int  # constituents carrying a usable weight
    constituent_count_declared: int | None  # the provider's own declared count, if published
    weight_sum: float
    weights_by_l2: dict[str, float]
    unmapped_weight: float  # constituent weight with no Shenwan L2 attribution
    unparsed_weight_count: int  # constituents whose weight could not be parsed
    weight_quality: str
    notes: tuple[str, ...] = ()

    # -- derived views ------------------------------------------------------

    @property
    def ranked_l2(self) -> list[tuple[str, float]]:
        """(l2_code, weight) descending, ties broken by ascending code for determinism."""
        return sorted(self.weights_by_l2.items(), key=lambda kv: (-kv[1], kv[0]))

    @property
    def largest_l2(self) -> tuple[str, float] | None:
        ranked = self.ranked_l2
        return ranked[0] if ranked else None

    @property
    def second_l2(self) -> tuple[str, float] | None:
        ranked = self.ranked_l2
        return ranked[1] if len(ranked) > 1 else None

    @property
    def weights_complete(self) -> bool:
        return self.weight_quality == COMPLETE_WEIGHT_SET

    def exposure(self, l2_code: str) -> float:
        return float(self.weights_by_l2.get(l2_code, 0.0))

    def rank_of(self, l2_code: str) -> int | None:
        for position, (code, _) in enumerate(self.ranked_l2, start=1):
            if code == l2_code:
                return position
        return None

    def purity(self, l2_code: str) -> "ProxyPurity":
        return assess_proxy_purity(self, l2_code)


def build_benchmark_exposure(
    *,
    benchmark_code: str,
    benchmark_name: str | None,
    constituents: list[dict],
    stock_to_l2: dict[str, str],
    weight_source_type: str,
    constituent_date: str | None = None,
    constituent_count_declared: int | None = None,
    index_provider: str | None = None,
    weight_source_url: str | None = None,
    evidence_observed_at: str | None = None,
) -> BenchmarkExposure:
    """Aggregate one benchmark's official constituent weights into Shenwan L2 exposure.

    ``constituents`` rows must carry ``security_code`` (a bare six-digit code, optionally
    exchange-suffixed) and ``weight_pct``. ``stock_to_l2`` maps a six-digit code to a
    four-digit Shenwan L2 code.

    Attribution is deliberately conservative: a constituent whose code has no Shenwan L2
    mapping is accumulated into ``unmapped_weight`` and reported, never redistributed across
    the mapped names -- redistributing it would inflate every industry's apparent exposure.
    """
    if constituent_count_declared is not None and (
        type(constituent_count_declared) is not int or constituent_count_declared <= 0
    ):
        raise ProxyError("INVALID_FIELD:constituent_count_declared:positive_integer_required")
    weights: dict[str, float] = {}
    weight_sum = 0.0
    unmapped = 0.0
    unparsed = 0
    counted = 0
    notes: list[str] = []

    for row in constituents:
        raw_code = str(row.get("security_code") or "").strip()
        bare = raw_code.split(".")[0].strip()
        weight = parse_weight_pct(row.get("weight_pct"))
        if weight is None:
            unparsed += 1
            continue
        counted += 1
        weight_sum += weight
        l2_code = stock_to_l2.get(bare)
        if not l2_code:
            unmapped += weight
            continue
        weights[l2_code] = weights.get(l2_code, 0.0) + weight

    low, high = WEIGHT_SUM_BAND
    quality = COMPLETE_WEIGHT_SET
    if unparsed:
        quality = INCOMPLETE_WEIGHT_SET
        notes.append(f"UNPARSED_WEIGHT_ROWS={unparsed}")
    if not (low <= weight_sum <= high):
        quality = INCOMPLETE_WEIGHT_SET
        notes.append(f"WEIGHT_SUM_OUT_OF_BAND={weight_sum:.4f}")
    if constituent_count_declared is not None and counted < constituent_count_declared:
        quality = INCOMPLETE_WEIGHT_SET
        notes.append(f"CONSTITUENTS_MISSING={constituent_count_declared - counted}")
    if weight_source_type not in ADMISSIBLE_WEIGHT_SOURCES:
        quality = INCOMPLETE_WEIGHT_SET
        notes.append(f"NON_ADMISSIBLE_WEIGHT_SOURCE={weight_source_type}")
    if unmapped > 0.0:
        notes.append(f"UNMAPPED_L2_WEIGHT={unmapped:.4f}")

    return BenchmarkExposure(
        benchmark_code=benchmark_code,
        benchmark_name=benchmark_name,
        index_provider=index_provider,
        constituent_date=constituent_date,
        weight_source_type=weight_source_type,
        weight_source_url=weight_source_url,
        evidence_observed_at=evidence_observed_at,
        constituent_count=counted,
        constituent_count_declared=constituent_count_declared,
        weight_sum=round(weight_sum, 6),
        weights_by_l2={k: round(v, 6) for k, v in sorted(weights.items())},
        unmapped_weight=round(unmapped, 6),
        unparsed_weight_count=unparsed,
        weight_quality=quality,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Purity metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProxyPurity:
    """How well one benchmark stands in for one target Shenwan L2 industry."""

    target_l2_code: str
    target_l2_exposure: float
    second_largest_l2_code: str | None
    second_largest_l2_exposure: float
    target_is_largest_l2: bool
    target_rank: int | None
    benchmark_code: str
    weight_quality: str
    weight_source_type: str

    @property
    def dominance_margin(self) -> float:
        """Target exposure minus the largest non-target industry exposure.

        ``51 vs 49`` and ``51 vs 12`` are both "51% target" and are not the same instrument.
        The margin is what separates them. The serialized legacy
        ``second_largest_l2_exposure`` field means the largest non-target
        exposure even when the target is not the largest industry.
        """
        return self.target_l2_exposure - self.second_largest_l2_exposure

    @property
    def leakage(self) -> float:
        """Everything in the benchmark that is *not* the target industry."""
        return 100.0 - self.target_l2_exposure

    def as_dict(self) -> dict:
        return {
            "target_l2_code": self.target_l2_code,
            "target_l2_exposure": round(self.target_l2_exposure, 6),
            "second_largest_l2_code": self.second_largest_l2_code,
            "second_largest_l2_exposure": round(self.second_largest_l2_exposure, 6),
            "dominance_margin": round(self.dominance_margin, 6),
            "target_is_largest_l2": self.target_is_largest_l2,
            "target_rank": self.target_rank,
            "benchmark_code": self.benchmark_code,
            "weight_quality": self.weight_quality,
            "weight_source_type": self.weight_source_type,
        }


def assess_proxy_purity(exposure: BenchmarkExposure, target_l2_code: str) -> ProxyPurity:
    """Measure one (benchmark, target industry) pair.

    The largest industry excluding the target is the comparison that
    matters for dominance: if the target is not the largest, the largest industry is the one
    the instrument actually tracks, and that is what the margin must be measured against.
    """
    ranked = exposure.ranked_l2
    target_exposure = exposure.exposure(target_l2_code)
    others = [(code, weight) for code, weight in ranked if code != target_l2_code]
    if others:
        second_code, second_weight = max(others, key=lambda kv: (kv[1], [-ord(c) for c in kv[0]]))
    else:
        second_code, second_weight = None, 0.0
    largest = ranked[0] if ranked else None
    return ProxyPurity(
        target_l2_code=target_l2_code,
        target_l2_exposure=target_exposure,
        second_largest_l2_code=second_code,
        second_largest_l2_exposure=second_weight,
        target_is_largest_l2=bool(largest and largest[0] == target_l2_code),
        target_rank=exposure.rank_of(target_l2_code),
        benchmark_code=exposure.benchmark_code,
        weight_quality=exposure.weight_quality,
        weight_source_type=exposure.weight_source_type,
    )


def research_grade(purity: ProxyPurity) -> str:
    """Descriptive purity band. Reporting only -- no admission path reads this."""
    if purity.weight_quality != COMPLETE_WEIGHT_SET:
        return GRADE_UNSUITABLE
    if not purity.target_is_largest_l2:
        return GRADE_UNSUITABLE
    if purity.target_l2_exposure >= HIGH_PURITY_FLOOR:
        return GRADE_HIGH
    if purity.target_l2_exposure >= MEDIUM_PURITY_FLOOR:
        return GRADE_MEDIUM
    if purity.target_l2_exposure >= LOW_PURITY_FLOOR:
        return GRADE_LOW
    return GRADE_UNSUITABLE


# ---------------------------------------------------------------------------
# Admission rules (threshold sensitivity)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProxyRule:
    """One point in the threshold-sensitivity grid.

    ``min_dominance_margin`` is in percentage points, or ``None`` when the rule does not
    constrain dominance at all.

    That ``None`` matters more than it looks. ``dominance_margin >= 0`` is *equivalent* to the
    target being the largest industry, so a rule that asks only for a threshold but passes
    ``0.0`` here is silently identical to the "target must be largest" rule and the two decision
    shapes collapse into one. Scheme A is therefore genuinely threshold-only: it imposes no
    dominance constraint, and its lower fidelity is reported through the grade rather than
    hidden behind a constraint nobody asked for.
    """

    name: str
    threshold: float
    require_largest: bool = False
    min_dominance_margin: float | None = None

    def __post_init__(self):
        if self.threshold < RESEARCH_MIN_THRESHOLD:
            raise ProxyError(
                f"threshold {self.threshold} is below the research floor {RESEARCH_MIN_THRESHOLD}; "
                "this round does not widen the search further"
            )

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "require_largest": self.require_largest,
            "min_dominance_margin": self.min_dominance_margin,
        }


#: The four decision shapes the round compares, per the research design.
def rule_grid(thresholds=(90.0, 80.0, 70.0, 60.0, 50.0, 40.0)) -> list[ProxyRule]:
    rules: list[ProxyRule] = []
    for threshold in thresholds:
        tag = f"{threshold:.0f}"
        rules.append(ProxyRule(f"A{tag}", threshold, False, None))
        rules.append(ProxyRule(f"B{tag}", threshold, True, None))
        rules.append(ProxyRule(f"C{tag}", threshold, True, 10.0))
        rules.append(ProxyRule(f"D{tag}", threshold, True, 20.0))
    return rules


def admit_proxy(purity: ProxyPurity, rule: ProxyRule) -> tuple[bool, str | None]:
    """Fail-closed admission. Returns ``(admitted, rejection_reason)``.

    Order matters: evidence quality is checked before any threshold, so a benchmark whose
    weights are incomplete can never be admitted by lowering the threshold.
    """
    if purity.weight_source_type not in ADMISSIBLE_WEIGHT_SOURCES:
        return False, f"NON_ADMISSIBLE_WEIGHT_SOURCE:{purity.weight_source_type}"
    if purity.weight_quality != COMPLETE_WEIGHT_SET:
        return False, f"WEIGHT_SET_{purity.weight_quality}"
    if purity.target_l2_exposure < rule.threshold:
        return False, "TARGET_EXPOSURE_BELOW_THRESHOLD"
    if rule.require_largest and not purity.target_is_largest_l2:
        return False, "TARGET_NOT_LARGEST_L2"
    if (
        rule.min_dominance_margin is not None
        and purity.dominance_margin < rule.min_dominance_margin
    ):
        return False, "DOMINANCE_MARGIN_BELOW_MINIMUM"
    return True, None


# ---------------------------------------------------------------------------
# STRICT precedence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionCandidate:
    """One way to execute one target industry."""

    target_l2_code: str
    etf_code: str
    benchmark_code: str
    mapping_type: str  # MAPPING_TYPE_STRICT | MAPPING_TYPE_PROXY
    target_l2_exposure: float
    second_largest_l2_exposure: float
    dominance_margin: float
    target_is_largest_l2: bool
    weight_quality: str
    weight_source_type: str
    mean_amount_cny: float | None = None
    liquidity_status: str | None = None
    evidence_source: str | None = None
    grade: str | None = None

    @property
    def is_strict(self) -> bool:
        return self.mapping_type == MAPPING_TYPE_STRICT

    @property
    def liquidity_ok(self) -> bool:
        return self.liquidity_rejection_reason is None

    @property
    def liquidity_rejection_reason(self) -> str | None:
        """No admission without both a passing verdict and finite positive amount."""
        amount = self.mean_amount_cny
        if (
            self.liquidity_status != "LIQUIDITY_ADMISSION_PASS"
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount <= 0
        ):
            return "LIQUIDITY_ADMISSION_BLOCKED"
        return None

    def as_dict(self) -> dict:
        return {
            "target_l2_code": self.target_l2_code,
            "etf_code": self.etf_code,
            "benchmark_code": self.benchmark_code,
            "mapping_type": self.mapping_type,
            "target_l2_exposure": round(self.target_l2_exposure, 6),
            "second_largest_l2_exposure": round(self.second_largest_l2_exposure, 6),
            "dominance_margin": round(self.dominance_margin, 6),
            "target_is_largest_l2": self.target_is_largest_l2,
            "weight_quality": self.weight_quality,
            "weight_source_type": self.weight_source_type,
            "mean_amount_cny": self.mean_amount_cny,
            "liquidity_status": self.liquidity_status,
            "evidence_source": self.evidence_source,
            "grade": self.grade,
        }


def select_execution_candidate(candidates: list[ExecutionCandidate]) -> ExecutionCandidate | None:
    """Apply STRICT-over-PROXY precedence, then liquidity, then purity, then size.

    A strict mapping is never discarded in favour of a proxy for the same industry. Doing so
    would replace a proven identity match with a statistical approximation, which is a
    methodology change dressed up as an optimisation.
    """
    if not candidates:
        return None
    strict = [c for c in candidates if c.is_strict]
    pool = strict if strict else [c for c in candidates if not c.is_strict]
    if not pool:
        return None
    liquid = [c for c in pool if c.liquidity_ok]
    if not liquid:
        return None
    pool = liquid
    return sorted(
        pool, key=lambda c: (-c.target_l2_exposure, -(c.mean_amount_cny or 0.0), c.etf_code)
    )[0]


# ---------------------------------------------------------------------------
# Distinct-ETF assignment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Assignment:
    """One resolution of "which ETF executes which industry"."""

    pairs: tuple[tuple[str, str], ...]  # (target_l2_code, etf_code)
    total_target_exposure: float
    minimum_target_exposure: float
    mean_target_exposure: float
    mean_dominance_margin: float
    distinct_etfs: int
    targets_covered: int
    solver: str
    collisions_avoided: int = 0
    unmapped_targets: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "pairs": [{"target_l2_code": t, "etf_code": e} for t, e in self.pairs],
            "total_target_exposure": round(self.total_target_exposure, 6),
            "minimum_target_exposure": round(self.minimum_target_exposure, 6),
            "mean_target_exposure": round(self.mean_target_exposure, 6),
            "mean_dominance_margin": round(self.mean_dominance_margin, 6),
            "distinct_etfs": self.distinct_etfs,
            "targets_covered": self.targets_covered,
            "solver": self.solver,
            "collisions_avoided": self.collisions_avoided,
            "unmapped_targets": list(self.unmapped_targets),
        }


def _summarise(pairs, candidates_by_target, solver, unmapped, collisions=0) -> Assignment:
    exposures = [candidates_by_target[t][e].target_l2_exposure for t, e in pairs]
    margins = [candidates_by_target[t][e].dominance_margin for t, e in pairs]
    n = len(pairs)
    return Assignment(
        pairs=tuple(sorted(pairs)),
        total_target_exposure=math.fsum(exposures),
        minimum_target_exposure=min(exposures) if exposures else 0.0,
        mean_target_exposure=(math.fsum(exposures) / n) if n else 0.0,
        mean_dominance_margin=(math.fsum(margins) / n) if n else 0.0,
        distinct_etfs=len({e for _, e in pairs}),
        targets_covered=n,
        solver=solver,
        collisions_avoided=collisions,
        unmapped_targets=tuple(sorted(unmapped)),
    )


def solve_distinct_assignment(
    targets, candidates_by_target, *, require_all_targets=True
) -> Assignment:
    """Exact maximum-quality assignment of distinct ETFs to target industries.

    Optimality, not greed. One ETF can be the best proxy for several industries at once, and a
    greedy first-come choice can consume the only instrument that made a later industry
    executable. With the five targets of a Top5 this is small enough to solve exactly by
    dynamic programming over subsets of targets, so it is.

    Lexicographic objective, matching the round's stated priorities:
      1. cover as many targets as possible;
      2. then maximise the *minimum* target exposure (nobody is carried by the average);
      3. then maximise the total target exposure;
      4. then maximise the total dominance margin (equivalent to mean at equal coverage);
      5. then maximise traded amount.

    Step 5 is not decoration. Several ETFs track the same benchmark and therefore carry *identical*
    exposure for a target, so steps 1-4 tie exactly. Without a size term the tie falls to whatever
    order the candidate codes happen to be in, which can select an ETF trading a few million yuan a
    day over one trading more than a billion for the very same index -- a real, avoidable execution
    defect that no exposure metric would ever reveal.
    """
    targets = list(targets)
    if not targets:
        raise ProxyError("ASSIGNMENT_NEEDS_AT_LEAST_ONE_TARGET")
    for target in targets:
        if not candidates_by_target.get(target) and require_all_targets:
            raise ProxyError(f"NO_CANDIDATE_FOR_TARGET:{target}")

    eligible = {t: sorted({e for e in candidates_by_target.get(t, {})}) for t in targets}

    full = (1 << len(targets)) - 1
    # best[mask] = objective tuple using the ETF assigned for each target in mask.
    best: dict[int, tuple] = {0: (0, 0.0, 0.0, 0.0, 0.0, ())}
    for mask in range(full + 1):
        if mask not in best:
            continue
        covered, min_exp, total_exp, total_margin, total_liq, pairs = best[mask]
        used = {e for _, e in pairs}
        for index, target in enumerate(targets):
            if mask & (1 << index):
                continue
            for etf in eligible[target]:
                if etf in used:
                    continue
                cand = candidates_by_target[target][etf]
                new_pairs = pairs + ((target, etf),)
                new_min = (
                    min(min_exp, cand.target_l2_exposure) if pairs else cand.target_l2_exposure
                )
                objective = (
                    covered + 1,
                    round(new_min, 9),
                    round(total_exp + cand.target_l2_exposure, 9),
                    round(total_margin + cand.dominance_margin, 9),
                    round(total_liq + (cand.mean_amount_cny or 0.0), 6),
                )
                key = mask | (1 << index)
                prior = best.get(key)
                if prior is None or objective > prior[:5]:
                    best[key] = (*objective, new_pairs)

    if full in best:
        chosen = best[full][5]
        return _summarise(list(chosen), candidates_by_target, "exact_subset_dp", [])

    reachable = max(best, key=lambda m: best[m][:5])
    chosen = best[reachable][5]
    covered_targets = {t for t, _ in chosen}
    unmapped = [t for t in targets if t not in covered_targets]
    return _summarise(list(chosen), candidates_by_target, "exact_subset_dp_partial", unmapped)


def greedy_assignment(targets, candidates_by_target, *, require_all_targets=False) -> Assignment:
    """Greedy comparison baseline. Never used for production decisions.

    Reported alongside the exact solver precisely so the cost of greed is visible: if the two
    agree, the collision structure is benign; if they disagree, a greedy production rule would
    silently lose quality.
    """
    targets = list(targets)
    edges = []
    for target in targets:
        for etf, cand in candidates_by_target.get(target, {}).items():
            edges.append(
                (
                    cand.target_l2_exposure,
                    cand.dominance_margin,
                    cand.mean_amount_cny or 0.0,
                    target,
                    etf,
                )
            )
    edges.sort(key=lambda e: (-e[0], -e[1], -e[2], e[3], e[4]))
    used_etfs = set()
    chosen: list[tuple[str, str]] = []
    for _, _, _, target, etf in edges:
        if etf in used_etfs or any(t == target for t, _ in chosen):
            continue
        used_etfs.add(etf)
        chosen.append((target, etf))
    unmapped = [t for t in targets if t not in {t for t, _ in chosen}]
    return _summarise(
        chosen,
        candidates_by_target,
        "greedy",
        unmapped,
        collisions=sum(1 for t in targets if len(candidates_by_target.get(t, {})) > 1),
    )


# ---------------------------------------------------------------------------
# Portfolio construction (weights only; the alpha model is untouched)
# ---------------------------------------------------------------------------

SINGLE_ETF_CAP = 0.35


def softmax_weights(scores: list[float]) -> list[float]:
    """Numerically stable softmax over the model's own final scores.

    Proxy purity is deliberately absent from this signature: quality selects the instrument,
    it does not reweight the signal.
    """
    if not scores:
        raise ProxyError("SOFTMAX_NEEDS_AT_LEAST_ONE_SCORE")
    peak = max(scores)
    exps = [math.exp(s - peak) for s in scores]
    total = math.fsum(exps)
    if not math.isfinite(total) or total <= 0:
        raise ProxyError("SOFTMAX_DEGENERATE")
    return [e / total for e in exps]


def apply_cap(
    weights: list[float], cap: float = SINGLE_ETF_CAP, *, max_rounds: int = 100
) -> list[float]:
    """Enforce a single-name cap by redistributing excess to the uncapped names.

    Redistribution is proportional to remaining capacity (cap minus weight). If every name is
    capped the excess cannot be placed and the function refuses rather than returning a
    portfolio that quietly violates either the cap or the sum-to-one contract.
    """
    if not weights:
        raise ProxyError("CAP_NEEDS_AT_LEAST_ONE_WEIGHT")
    if cap <= 0 or cap * len(weights) < 1.0 - 1e-12:
        raise ProxyError("CAP_INFEASIBLE_FOR_NAME_COUNT")
    current = [float(w) for w in weights]
    if any(w < 0 for w in current):
        raise ProxyError("NEGATIVE_WEIGHT")
    for _ in range(max_rounds):
        excess = math.fsum(max(0.0, w - cap) for w in current)
        if excess <= 1e-12:
            break
        free = [i for i, w in enumerate(current) if w < cap - 1e-12]
        if not free:
            raise ProxyError("CAP_REDISTRIBUTION_IMPOSSIBLE")
        room = [max(0.0, cap - current[i]) for i in free]
        capacity = math.fsum(room)
        if capacity <= 1e-12:
            raise ProxyError("CAP_REDISTRIBUTION_IMPOSSIBLE")
        placed = min(excess, capacity)
        for i, r in zip(free, room):
            current[i] += placed * (r / capacity)
        for i, w in enumerate(current):
            if w > cap:
                current[i] = cap
    else:
        raise ProxyError("CAP_DID_NOT_CONVERGE")
    total = math.fsum(current)
    if abs(total - 1.0) > 1e-9:
        raise ProxyError(f"CAP_BROKE_SUM_TO_ONE:{total}")
    return current


def portfolio_quality_metrics(weights: list[float], purities: list[float]) -> dict:
    """Execution-quality metrics. These describe the instrument, never the expected return."""
    if len(weights) != len(purities):
        raise ProxyError("WEIGHT_PURITY_LENGTH_MISMATCH")
    total = math.fsum(weights)
    if total <= 0:
        raise ProxyError("NON_POSITIVE_PORTFOLIO_WEIGHT")
    normalised = [w / total for w in weights]
    weighted_purity = math.fsum(w * p for w, p in zip(normalised, purities))
    weighted_leakage = math.fsum(w * (100.0 - p) for w, p in zip(normalised, purities))
    return {
        "weighted_average_target_l2_purity": round(weighted_purity, 6),
        "minimum_target_l2_purity": round(min(purities), 6),
        "weighted_proxy_leakage": round(weighted_leakage, 6),
        "max_weight": round(max(normalised), 9),
        "weight_sum": round(total, 12),
        "name_count": len(normalised),
    }


__all__ = [
    "ADMISSIBLE_WEIGHT_SOURCES",
    "Assignment",
    "BenchmarkExposure",
    "COMPLETE_WEIGHT_SET",
    "ExecutionCandidate",
    "GRADE_HIGH",
    "GRADE_LOW",
    "GRADE_MEDIUM",
    "GRADE_STRICT",
    "GRADE_UNSUITABLE",
    "HIGH_PURITY_FLOOR",
    "INCOMPLETE_WEIGHT_SET",
    "LOW_PURITY_FLOOR",
    "MAPPING_TYPE_PROXY",
    "MAPPING_TYPE_STRICT",
    "MEDIUM_PURITY_FLOOR",
    "OFFICIAL_WEIGHT",
    "PCF_DERIVED_WEIGHT",
    "ProxyError",
    "ProxyPurity",
    "ProxyRule",
    "RESEARCH_MIN_THRESHOLD",
    "SINGLE_ETF_CAP",
    "UNWEIGHTED_DIAGNOSTIC",
    "WEIGHT_SUM_BAND",
    "admit_proxy",
    "apply_cap",
    "assess_proxy_purity",
    "build_benchmark_exposure",
    "greedy_assignment",
    "parse_weight_pct",
    "portfolio_quality_metrics",
    "research_grade",
    "rule_grid",
    "select_execution_candidate",
    "softmax_weights",
    "solve_distinct_assignment",
]

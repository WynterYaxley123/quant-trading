"""Preregistered, non-executing Factor Set V2 / Alpha Hypothesis V2 protocol.

This module freezes the V2 candidate family, the D2 control identity, all
model/target/metric settings, and the advancement rules BEFORE any Factor
Set V2 result exists. It performs no data I/O beyond reading the frozen
machine-readable candidate config, never fits a model, never scores a date,
and never produces V2 predictions or metrics. The future V2 runner must fail
closed on any semantic drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from research.sector_development_baseline import EXPECTED_FEATURES
from research.sector_development_protocol import canonical_hash, guard_evaluation

PROTOCOL_NAME = "SHENWAN_FACTOR_SET_V2_PREREGISTRATION"
AUDIT_TYPE = "FACTOR_SET_V2_PREREGISTRATION"
CONFIG_RELPATH = "research/configs/factor_set_v2_candidates.json"
SCHEMA_VERSION = 1

FROZEN_FACTOR_ORDER: tuple[str, ...] = tuple(EXPECTED_FEATURES)
FAMILY_PROCESSING_ORDER = (
    "TREND_MOMENTUM", "RANGE_POSITION", "OSCILLATOR_ALIGNMENT",
    "VOLATILITY", "REVERSAL", "DRAWDOWN",
)
FAMILY_MEMBERS = {
    "TREND_MOMENTUM": ("d5", "d10", "d20", "d60", "d120"),
    "RANGE_POSITION": ("p5", "p10", "p20", "p60", "p120"),
    "OSCILLATOR_ALIGNMENT": ("align", "rsi"),
    "VOLATILITY": ("v5", "v20", "vc"),
    "REVERSAL": ("rev5", "rev10"),
    "DRAWDOWN": ("dd20", "dd60"),
}
CANONICAL_PREFERENCE = {
    "TREND_MOMENTUM": ("d20", "d60", "d120", "d10", "d5"),
    "RANGE_POSITION": ("p20", "p60", "p120", "p10", "p5"),
    "OSCILLATOR_ALIGNMENT": ("rsi", "align"),
    "VOLATILITY": ("v20", "v5", "vc"),
    "REVERSAL": ("rev10", "rev5"),
    "DRAWDOWN": ("dd20", "dd60"),
}
FAMILY_DEFINITIONS = {
    "TREND_MOMENTUM": "(close - MA_n) / MA_n; trend-strength deviation from n-session moving average",
    "RANGE_POSITION": "(close - min_n) / (max_n - min_n) clipped to [0,1]; position in n-session range",
    "OSCILLATOR_ALIGNMENT": "bounded discrete oscillators of trend state: RSI14 and MA-ordering score /6",
    "VOLATILITY": "v5/v20 rolling std of daily returns; vc = v5/(v20+eps) volatility-shape ratio",
    "REVERSAL": "negative rolling mean of daily returns over n sessions",
    "DRAWDOWN": "close / rolling n-session high - 1; drawdown from rolling peak",
}

FROZEN_SETTINGS = {
    "model": "NumPyRidge",
    "alpha": 0.01,
    "target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN",
    "preprocessing": "NONE_RAW",
    "trainWindowCalendarMonths": 6,
    "trainWindowAnchor": "per_horizon_label_cutoff",
    "minimumValidTrainingDays": 30,
    "horizons": [10, 40, 120],
    "fusion": [0.25, 0.5, 0.25],
    "topK": 5,
    "topKSelection": "FUSED_SCORE_TOP5",
    "universe": "U0_FIXED_124",
    "sectorCount": 124,
    "developmentIds": "E001-E100",
    "sharedFactorSetAcrossHorizons": True,
}
CANDIDATE_BUDGET = {"maxNewCandidates": 4, "totalWithControl": 5,
                    "adaptiveSearch": "FORBIDDEN", "closedAfterPreregistration": True}

CONTROL_ID = "C0"
CONTROL_SOURCE = "D2"
CONTROL_SOURCE_RUN_ID = "iteration1_20260924_163607_787266_utc"
FROZEN_C0_METRICS = {
    "weightedRankIc": 0.08810651455546813,
    "weightedSpread": 0.037216498377093545,
    "rankIcByHorizon": {"10": 0.025446168371361138,
                        "40": 0.049692399685287166,
                        "120": 0.22759509047993703},
    "spreadByHorizon": {"10": 0.005297457266283392,
                        "40": 0.01278764643554297,
                        "120": 0.11799324337100485},
}

CANDIDATE_IDS = ("V2_A", "V2_B", "V2_D")
CANDIDATE_FACTORS = {
    "V2_A": ("v20",),
    "V2_B": ("v5", "v20"),
    "V2_D": ("d20", "p60", "align", "v20", "rev5", "dd20"),
}
V2_D_HARD_CAP = 6
V2_D_REGIME_UNSTABLE = ("d20", "p60", "align", "rev5", "dd20")
EXCLUDED_CANDIDATE_IDS = ("V2_C",)

REDUNDANCY_THRESHOLD = 0.80
FROZEN_HIGH_REDUNDANCY_PAIRS = (
    ("d5", "d10", 0.81061922895357996),
    ("d5", "p5", 0.86661702245582306),
    ("d10", "d20", 0.8282715342250192),
    ("d10", "p10", 0.8565248011150518),
    ("d10", "rev5", -0.89118300550747453),
    ("d10", "rev10", -0.80091172305271441),
    ("d20", "p20", 0.84134157545946198),
    ("d20", "rev10", -0.89370152635719935),
    ("d20", "rsi", 0.8646634146341462),
    ("d60", "d120", 0.84447112509834743),
    ("d60", "p60", 0.82280389108637497),
    ("d120", "p120", 0.84425807519747564),
    ("p5", "p10", 0.82156748214870345),
    ("p10", "p20", 0.80801828605279713),
    ("p20", "dd20", 0.8828444948312163),
    ("p60", "dd60", 0.90458650209327429),
)
V2_B_PREMISE_V5_V20_SPEARMAN = 0.6298417623918176

ADVANCEMENT = {
    "level1": "weightedRankIc > 0 AND weightedSpread > 0",
    "level2_optionA": "weightedRankIc > C0 AND weightedSpread >= C0",
    "level2_optionB": "weightedSpread > C0 AND weightedRankIc >= C0",
    "horizonRedFlagRankIc": -0.02,
    "simplicityPreference": True,
    "simplicityRankIcTieBand": 0.01,
    "simplicitySpreadTieBand": 0.01,
}
STABILITY_BLOCKS = ((1, 1, 25), (2, 26, 50), (3, 51, 75), (4, 76, 100))
EXTREME_DATE_TAIL_COUNT = 5

# Set only after the canonical payload (including the frozen candidate
# config) is frozen. Never derive this constant dynamically at import.
FROZEN_FACTOR_SET_V2_PROTOCOL_HASH = (
    "3fbba8e5b41c0b5b839dab2788f1e000b9add95406bb14cbaf4c13f31664b4f4"
)


def config_path(base: Path | None = None) -> Path:
    root = base if base is not None else Path(__file__).resolve().parents[1]
    return root / CONFIG_RELPATH


def load_candidate_config(base: Path | None = None) -> dict:
    """Read and hard-validate the frozen machine-readable candidate config."""
    raw = json.loads(config_path(base).read_text(encoding="utf-8"))
    _validate_config(raw)
    return raw


def _validate_config(raw: dict) -> None:
    if raw.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("FACTOR_SET_V2_CONFIG_SCHEMA_MISMATCH")
    if tuple(raw.get("frozenFactorOrder", ())) != FROZEN_FACTOR_ORDER:
        raise ValueError("FACTOR_ORDER_FROZEN_VIOLATION")
    families = {row["family"]: row for row in raw.get("familyMapping", [])}
    if (tuple(raw.get("familyProcessingOrder", ())) != FAMILY_PROCESSING_ORDER
            or set(families) != set(FAMILY_PROCESSING_ORDER)):
        raise ValueError("FACTOR_SET_V2_FAMILY_MAPPING_MISMATCH")
    for name, members in FAMILY_MEMBERS.items():
        row = families[name]
        if tuple(row["members"]) != members:
            raise ValueError("FACTOR_SET_V2_FAMILY_MAPPING_MISMATCH: members")
        if tuple(row["canonicalPreference"]) != CANONICAL_PREFERENCE[name]:
            raise ValueError("FACTOR_SET_V2_FAMILY_MAPPING_MISMATCH: preference")
        if set(members) & set().union(*[set(v) for k, v in FAMILY_MEMBERS.items() if k != name]):
            raise ValueError("FACTOR_SET_V2_FAMILY_MAPPING_MISMATCH: overlap")
    if set().union(*map(set, FAMILY_MEMBERS.values())) != set(FROZEN_FACTOR_ORDER):
        raise ValueError("FACTOR_SET_V2_FAMILY_MAPPING_MISMATCH: coverage")
    settings = raw.get("frozenSettings", {})
    for key, expected in FROZEN_SETTINGS.items():
        if settings.get(key) != expected:
            raise ValueError(f"FACTOR_SET_V2_FROZEN_SETTINGS_MISMATCH: {key}")
    budget = raw.get("candidateBudget", {})
    if (budget.get("maxNewCandidates") != CANDIDATE_BUDGET["maxNewCandidates"]
            or budget.get("totalWithControl") != CANDIDATE_BUDGET["totalWithControl"]
            or budget.get("closedAfterPreregistration") is not True
            or budget.get("adaptiveSearch") != "FORBIDDEN"):
        raise ValueError("FACTOR_SET_V2_BUDGET_MISMATCH")
    control = raw.get("control", {})
    if (control.get("candidateId") != CONTROL_ID or control.get("isControl") is not True
            or control.get("sourceCandidate") != CONTROL_SOURCE
            or control.get("sourceRunId") != CONTROL_SOURCE_RUN_ID
            or tuple(control.get("factorList", ())) != FROZEN_FACTOR_ORDER
            or control.get("factorCount") != 19
            or control.get("frozenMetrics") != FROZEN_C0_METRICS):
        raise ValueError("FACTOR_SET_V2_CONTROL_IDENTITY_MISMATCH")
    if control.get("target") != FROZEN_SETTINGS["target"] or control.get("preprocessing") != "NONE_RAW" \
            or control.get("alpha") != 0.01:
        raise ValueError("FACTOR_SET_V2_CONTROL_SETTINGS_MISMATCH")
    candidates = raw.get("candidates", [])
    if tuple(row["candidateId"] for row in candidates) != CANDIDATE_IDS:
        raise ValueError("FACTOR_SET_V2_CANDIDATE_BUDGET_VIOLATION")
    if len(candidates) > CANDIDATE_BUDGET["maxNewCandidates"] \
            or len(candidates) + 1 > CANDIDATE_BUDGET["totalWithControl"]:
        raise ValueError("FACTOR_SET_V2_CANDIDATE_BUDGET_VIOLATION")
    for row in candidates:
        cid = row["candidateId"]
        factors = tuple(row.get("factorList", ()))
        if factors != CANDIDATE_FACTORS[cid]:
            raise ValueError(f"FACTOR_SET_V2_CANDIDATE_LIST_MISMATCH: {cid}")
        if len(factors) != row.get("factorCount") or not factors or len(set(factors)) != len(factors):
            raise ValueError(f"FACTOR_SET_V2_CANDIDATE_LIST_INVALID: {cid}")
        if not all(f in FROZEN_FACTOR_ORDER for f in factors):
            raise ValueError(f"FACTOR_SET_V2_FACTOR_NAME_INVALID: {cid}")
        positions = [FROZEN_FACTOR_ORDER.index(f) for f in factors]
        if positions != sorted(positions):
            raise ValueError(f"FACTOR_SET_V2_FACTOR_ORDER_NOT_DETERMINISTIC: {cid}")
        if row.get("target") != FROZEN_SETTINGS["target"] \
                or row.get("preprocessing") != FROZEN_SETTINGS["preprocessing"] \
                or row.get("model") != FROZEN_SETTINGS["model"] \
                or row.get("alpha") != FROZEN_SETTINGS["alpha"] \
                or row.get("trainWindow") != "6 calendar months" \
                or row.get("horizons") != FROZEN_SETTINGS["horizons"] \
                or row.get("fusion") != FROZEN_SETTINGS["fusion"] \
                or row.get("topK") != FROZEN_SETTINGS["topK"]:
            raise ValueError(f"FACTOR_SET_V2_CANDIDATE_SETTINGS_MISMATCH: {cid}")
    if len(CANDIDATE_FACTORS["V2_D"]) > V2_D_HARD_CAP \
            or not 3 <= len(CANDIDATE_FACTORS["V2_D"]) <= V2_D_HARD_CAP:
        raise ValueError("FACTOR_SET_V2_D_SIZE_VIOLATION")
    if tuple(candidates[2].get("regimeUnstableFactors", ())) != V2_D_REGIME_UNSTABLE:
        raise ValueError("FACTOR_SET_V2_REGIME_LABEL_MISMATCH")
    if tuple(row["candidateId"] for row in raw.get("excludedCandidates", [])) != EXCLUDED_CANDIDATE_IDS \
            or raw["excludedCandidates"][0].get("status") != "NOT_ADMISSIBLE":
        raise ValueError("FACTOR_SET_V2_EXCLUSION_RECORD_MISMATCH")
    redundancy = raw.get("redundancyRule", {})
    frozen_pairs = [(a, b, v) for a, b, v in FROZEN_HIGH_REDUNDANCY_PAIRS]
    config_pairs = [(row["factorA"], row["factorB"], row["meanSpearman"])
                    for row in redundancy.get("highRedundancyPairs", [])]
    if (redundancy.get("threshold") != REDUNDANCY_THRESHOLD
            or config_pairs != frozen_pairs
            or redundancy.get("v2dInternalPairsAllBelowThreshold") is not True):
        raise ValueError("FACTOR_SET_V2_REDUNDANCY_RULE_MISMATCH")
    advancement = raw.get("advancementRule", {})
    red_flag = advancement.get("horizonRedFlag", {})
    simplicity = raw.get("simplicityRule", {})
    if (red_flag.get("threshold") != ADVANCEMENT["horizonRedFlagRankIc"]
            or red_flag.get("frozenBeforeResults") is not True
            or simplicity.get("SIMPLICITY_PREFERENCE") is not True
            or simplicity.get("rankIcTieBand") != ADVANCEMENT["simplicityRankIcTieBand"]
            or simplicity.get("spreadTieBand") != ADVANCEMENT["simplicitySpreadTieBand"]):
        raise ValueError("FACTOR_SET_V2_ADVANCEMENT_RULE_MISMATCH")
    seals = raw.get("seals", {})
    if (seals.get("developmentOnly") is not True or seals.get("validationSealed") is not True
            or seals.get("finalOosSealed") is not True or seals.get("noSignFlip") is not True):
        raise ValueError("FACTOR_SET_V2_SEAL_MISMATCH")
    if _has_banned_sign_key(raw):
        raise ValueError("FACTOR_SET_V2_SIGN_MANIPULATION_FORBIDDEN")


BANNED_SIGN_KEYS = frozenset({
    "sign", "signs", "signflip", "sign_multiplier", "signmultiplier",
    "direction", "directionflip", "invert", "inverted", "orientation",
})


def _has_banned_sign_key(value) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in BANNED_SIGN_KEYS or _has_banned_sign_key(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_has_banned_sign_key(child) for child in value)
    return False


def factor_indices(factor_list: Sequence[str]) -> tuple[int, ...]:
    """Factor subset routing: frozen-order column indices for a candidate list."""
    factors = tuple(factor_list)
    if not factors or len(set(factors)) != len(factors):
        raise ValueError("FACTOR_SET_V2_FACTOR_LIST_INVALID")
    try:
        positions = tuple(FROZEN_FACTOR_ORDER.index(name) for name in factors)
    except ValueError as exc:
        raise ValueError("FACTOR_SET_V2_FACTOR_NAME_INVALID") from exc
    if positions != tuple(sorted(positions)):
        raise ValueError("FACTOR_SET_V2_FACTOR_ORDER_NOT_DETERMINISTIC")
    return positions


def is_high_redundancy(factor_a: str, factor_b: str) -> bool:
    """Frozen 0.80 mean-daily-Spearman redundancy rule; diagnostic only."""
    for a, b, value in FROZEN_HIGH_REDUNDANCY_PAIRS:
        if {a, b} == {factor_a, factor_b}:
            return abs(value) >= REDUNDANCY_THRESHOLD
    return False


def guard_factor_set_v2_scope(phase: str, ordinals: Sequence[int]) -> None:
    """Structural guard: V2 work may only touch Development ordinals."""
    guard_evaluation(phase, ordinals)


def factor_set_v2_payload(base: Path | None = None) -> dict:
    """One canonical, result-free preregistration identity; no result I/O."""
    config = load_candidate_config(base)
    return {
        "protocol_name": PROTOCOL_NAME,
        "audit_type": AUDIT_TYPE,
        "research_identity": {
            "POST_AUDIT_DEVELOPMENT_RESEARCH": True,
            "POST_AUDIT_DEVELOPMENT_HYPOTHESIS": True,
            "NOT_INDEPENDENT_VALIDATION": True,
            "NOT_OOS_EVIDENCE": True,
            "phase": "DEVELOPMENT",
            "validation_access": "SEALED",
            "final_oos_access": "SEALED",
            "run_type": "SECTOR_INDEX_RESEARCH_ONLY",
            "executable": False,
            "tradable": False,
        },
        "candidate_config_path": CONFIG_RELPATH,
        "candidate_config": config,
        "frozen_settings": dict(FROZEN_SETTINGS),
        "candidate_budget": dict(CANDIDATE_BUDGET),
        "control_identity": {
            "candidateId": CONTROL_ID, "sourceCandidate": CONTROL_SOURCE,
            "sourceRunId": CONTROL_SOURCE_RUN_ID,
            "frozenMetrics": {
                "weightedRankIc": FROZEN_C0_METRICS["weightedRankIc"],
                "weightedSpread": FROZEN_C0_METRICS["weightedSpread"],
                "rankIcByHorizon": dict(FROZEN_C0_METRICS["rankIcByHorizon"]),
                "spreadByHorizon": dict(FROZEN_C0_METRICS["spreadByHorizon"]),
            },
        },
        "advancement": dict(ADVANCEMENT),
        "stability_blocks": [list(block) for block in STABILITY_BLOCKS],
        "redundancy_threshold": REDUNDANCY_THRESHOLD,
        "extreme_date_tail_count": EXTREME_DATE_TAIL_COUNT,
        "research_questions": {
            "Q1": "reducing redundant/regime-unstable inputs lets Ridge use volatility information more effectively",
            "Q2": "v20-only is a simple interpretable baseline",
            "Q3": "v5+v20 provides stable incremental information over v20-only",
            "Q4": "preregistered low-redundancy cross-family representatives improve volatility-only",
            "Q5": "D2 under-extraction stems from redundancy/unstable-sign dilution rather than target failure",
        },
        "prohibitions": list(config["prohibitions"]),
    }


def factor_set_v2_protocol_hash(payload: Mapping | None = None) -> str:
    """SHA-256 of canonical sorted JSON; excludes timestamps and results."""
    return canonical_hash(factor_set_v2_payload() if payload is None else payload)


def verify_frozen_factor_set_v2_protocol(*, supplied_hash: str | None = None,
                                         base: Path | None = None) -> dict:
    """Hard fail if the committed payload or config drifts from the freeze."""
    payload = factor_set_v2_payload(base)
    actual = factor_set_v2_protocol_hash(payload)
    if (actual != FROZEN_FACTOR_SET_V2_PROTOCOL_HASH
            or (supplied_hash is not None and supplied_hash != actual)):
        raise ValueError("FACTOR_SET_V2_PROTOCOL_HASH_MISMATCH")
    return payload

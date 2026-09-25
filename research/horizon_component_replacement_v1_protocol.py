"""Frozen, non-executing Horizon Component Replacement V1 preregistration.

Component-replacement / fixed-fusion hypotheses only. This module reads no
market data, trains nothing, and produces no fused output. It freezes the
scheme identities, fusion semantics identity, advancement rules and source
manifest identity before any formal result exists. A future runner must
fail closed on semantic drift.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from research.sector_development_protocol import canonical_hash, guard_evaluation

RESEARCH_TYPE = "HORIZON_COMPONENT_REPLACEMENT_V1"
CONFIG_RELPATH = "research/configs/horizon_component_replacement_v1.json"
SOURCES_RELPATH = "research/configs/horizon_component_replacement_v1_sources.json"
PROTOCOL_RELPATH = "docs/research/shenwan_horizon_component_replacement_v1.md"
TRACE_RELPATH = "docs/research/shenwan_horizon_component_replacement_v1_selection_trace.md"

CANDIDATE_IDS = ("F0_CONTROL", "F1_H10_REPLACEMENT", "F2_H10_H40_REPLACEMENT")
COMPONENT_MAPPINGS = {
    "F0_CONTROL": {"h10": "C0_H10", "h40": "C0_H40", "h120": "C0_H120"},
    "F1_H10_REPLACEMENT": {"h10": "H10_C", "h40": "C0_H40", "h120": "C0_H120"},
    "F2_H10_H40_REPLACEMENT": {"h10": "H10_C", "h40": "H40_S", "h120": "C0_H120"},
}
FROZEN_FACTORS_19 = (
    "d5", "d10", "d20", "d60", "d120", "p5", "p10", "p20", "p60", "p120",
    "align", "v5", "v20", "vc", "rev5", "rev10", "dd20", "dd60", "rsi",
)
EXACT_FACTOR_LISTS = {
    "C0_H10": FROZEN_FACTORS_19,
    "C0_H40": FROZEN_FACTORS_19,
    "C0_H120": FROZEN_FACTORS_19,
    "H10_C": ("d10", "p5", "align", "vc", "dd20"),
    "H40_S": ("vc",),
}
FUSION_WEIGHTS = {"h10": 0.25, "h40": 0.50, "h120": 0.25}
HORIZONS = (10, 40, 120)
HORIZON_RED_FLAG_THRESHOLD = -0.02
BLOCKS = (("B1", 1, 25), ("B2", 26, 50), ("B3", 51, 75), ("B4", 76, 100))
TEMPORAL_POSITIVE_BLOCKS_AT_LEAST = 3
TEMPORAL_RED_BLOCKS_AT_MOST = 1
MINIMAL_TIE_BAND = 0.01
STATUS_CONTROL = "CONTROL_NOT_A_CANDIDATE"
STATUS_ADVANCED = "FUSION_ADVANCED_FOR_FURTHER_REVIEW"
STATUS_NOT_ADVANCED = "FUSION_NOT_ADVANCED"
FORBIDDEN_RESULT_LABELS = ("WINNER", "BEST", "VALIDATED", "PRODUCTION",
                           "TRADABLE", "LIVE_READY")
NEXT_RESEARCH_GATE_VALUES = (
    "COMPONENT_REPLACEMENT_SUPPORTED_FOR_FURTHER_REVIEW",
    "H10_REPLACEMENT_ONLY_SUPPORTED",
    "H10_H40_REPLACEMENT_SUPPORTED",
    "COMPONENT_REPLACEMENT_NOT_SUPPORTED",
    "MIXED_COMPONENT_REPLACEMENT_EVIDENCE",
    "DIAGNOSTIC_INCONCLUSIVE",
)
SOURCE_RESULT_COMMIT = "de8b77a8da3aeac99fa5ac1fd52d6431cedf2d62"
SOURCE_HANDOFF_COMMIT = "98dfe5c9c256fe31339a2c3ca63ea1753180a7cc"
SOURCE_PROTOCOL_HASH = "d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4"
FROZEN_CONFIG_HASH = "4c2f18815e47f9352a34f4f6bba222a260cbfff73cf6c49fc3e55438dc78adf6"
FROZEN_SOURCES_HASH = "35af45f03a8c04490c5bb5ce009476fac266b0ae0027b2b9db9d50d9d6786c3f"
FROZEN_PROTOCOL_HASH = "4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7"


def _root(root: Path | None) -> Path:
    return root or Path(__file__).resolve().parents[1]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _self_sha256() -> str:
    # Normalize only the self-referential frozen-hash assignments; any other
    # change to this module alters the identity before formal use.
    source = Path(__file__).read_bytes()
    normalized = source
    for name in ("FROZEN_CONFIG_HASH", "FROZEN_SOURCES_HASH", "FROZEN_PROTOCOL_HASH"):
        normalized, count = re.subn(
            (rb"^" + name.encode() + rb' = "[0-9a-f]{64}"$'),
            name.encode() + b' = "<SELF>"', normalized, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_PROTOCOL_HASH_MISMATCH")
    return hashlib.sha256(normalized).hexdigest()


def load_config(root: Path | None = None) -> dict:
    config = json.loads((_root(root) / CONFIG_RELPATH).read_text(encoding="utf-8"))
    if canonical_hash(config) != FROZEN_CONFIG_HASH:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_CONFIG_DRIFT_BLOCKER")
    if (config["researchType"] != RESEARCH_TYPE
            or config["phase"] != "PREREGISTERED"
            or config["sourceResultCommit"] != SOURCE_RESULT_COMMIT
            or config["sourceHandoffCommit"] != SOURCE_HANDOFF_COMMIT
            or config["candidateIds"] != list(CANDIDATE_IDS)
            or config["componentMappings"] != COMPONENT_MAPPINGS
            or {k: tuple(v) for k, v in config["factorLists"].items()} != EXACT_FACTOR_LISTS
            or config["fusionWeights"] != FUSION_WEIGHTS
            or config["fusionSemantics"]["promptRawLinearCombinationSuperseded"] is not True):
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_CONFIG_DRIFT_BLOCKER")
    if (config["horizonRedFlag"]["threshold"] != HORIZON_RED_FLAG_THRESHOLD
            or config["minimalReplacementPreference"]["absoluteWeightedRankIcDeltaLt"] != MINIMAL_TIE_BAND
            or config["temporalGate"]["positiveWeightedRankIcBlocksAtLeast"] != TEMPORAL_POSITIVE_BLOCKS_AT_LEAST
            or config["temporalGate"]["weightedRankIcStrictlyBelowMinus002BlocksAtMost"] != TEMPORAL_RED_BLOCKS_AT_MOST
            or [b["id"] for b in config["blocks"]] != [b[0] for b in BLOCKS]):
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_CONFIG_DRIFT_BLOCKER")
    for flag in ("noWeightSearch", "noDynamicFusion", "noDropHorizon", "noRetraining",
                 "noParameterSearch", "noNewFactor", "noSignFlip", "noComponentSearch",
                 "noModelSearch", "validationSealed", "finalOosSealed",
                 "developmentReuseWarning", "h40WeakEvidenceWarning", "neutralityCaveat"):
        if config.get(flag) is not True:
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_CONFIG_DRIFT_BLOCKER")
    if (config["advancementStatusLabels"] != [STATUS_CONTROL, STATUS_ADVANCED, STATUS_NOT_ADVANCED]
            or tuple(config["nextResearchGateAllowedValues"]) != NEXT_RESEARCH_GATE_VALUES
            or config["candidateBudget"]["totalSchemes"] != 3
            or config["candidateBudget"]["newHypotheses"] != 2):
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_CONFIG_DRIFT_BLOCKER")
    return config


def load_sources(root: Path | None = None) -> dict:
    sources = json.loads((_root(root) / SOURCES_RELPATH).read_text(encoding="utf-8"))
    if canonical_hash(sources) != FROZEN_SOURCES_HASH:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_SOURCES_DRIFT_BLOCKER")
    expected = set(EXACT_FACTOR_LISTS)
    if (sources["sourceResultCommit"] != SOURCE_RESULT_COMMIT
            or sources["sourceHandoffCommit"] != SOURCE_HANDOFF_COMMIT
            or sources["sourceProtocolHash"] != SOURCE_PROTOCOL_HASH
            or set(sources["components"]) != expected):
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_SOURCES_DRIFT_BLOCKER")
    for name, entry in sources["components"].items():
        if (tuple(entry["factorList"]) != EXACT_FACTOR_LISTS[name]
                or entry["firstRerunIdentical"] is not True
                or entry["sourceCurrentExistenceVerified"] is not True
                or not re.fullmatch(r"[0-9a-f]{64}", entry["predictionsSha256"])
                or not re.fullmatch(r"[0-9a-f]{64}", entry["metricsSha256"])):
            raise ValueError("HORIZON_COMPONENT_REPLACEMENT_SOURCES_DRIFT_BLOCKER")
    if sources["componentScaleAudit"]["rawComponentScaleDependenceWarning"] is not False:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_SOURCES_DRIFT_BLOCKER")
    return sources


def protocol_payload(root: Path | None = None) -> dict:
    repo = _root(root)
    config = load_config(repo)
    sources = load_sources(repo)
    return {
        "researchType": RESEARCH_TYPE,
        "phase": "PREREGISTERED",
        "sourceIdentity": {
            "sourceResearchType": "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1",
            "sourceResultCommit": SOURCE_RESULT_COMMIT,
            "sourceHandoffCommit": SOURCE_HANDOFF_COMMIT,
            "sourceProtocolHash": SOURCE_PROTOCOL_HASH,
        },
        "configPath": CONFIG_RELPATH,
        "configExactContent": config,
        "sourceManifestPath": SOURCES_RELPATH,
        "sourceManifestSha256": _file_sha256(repo / SOURCES_RELPATH),
        "documentIdentity": {
            "protocol": {"path": PROTOCOL_RELPATH,
                         "sha256": _file_sha256(repo / PROTOCOL_RELPATH)},
            "selectionTrace": {"path": TRACE_RELPATH,
                               "sha256": _file_sha256(repo / TRACE_RELPATH)},
        },
        "implementationSha256": {
            "protocolModule": _self_sha256(),
        },
        "frozenConstants": {
            "candidateIds": list(CANDIDATE_IDS),
            "componentMappings": COMPONENT_MAPPINGS,
            "exactFactorLists": {k: list(v) for k, v in EXACT_FACTOR_LISTS.items()},
            "fusionWeights": dict(FUSION_WEIGHTS),
            "fusionSemantics": (
                "PER_DATE_CROSS_SECTIONAL_Z_SCORE_THEN_0.25_0.50_0.25_WEIGHTED_AVERAGE"
                "_OVER_COMMON_UNIVERSE_DESCENDING_TIE_SECTOR_CODE_ASCENDING_TOP5"),
            "evaluationContract": "D2_C0_15_METRIC_CONTRACT_PLUS_WEIGHTED_RANKIC_SPREAD_0.25_0.50_0.25",
            "advancement": (
                "LEVEL1_POSITIVE_BOTH_THEN_PARETO_VS_F0_AND_FOR_F2_VS_F1"
                "_HORIZON_RED_FLAG_MINUS_0.02_THEN_TEMPORAL_3_OF_4_BLOCK_WEIGHTED_RANKIC"),
            "minimalReplacementPreference": (
                "IF_BOTH_PASS_ALL_GATES_AND_BOTH_ABSOLUTE_PRIMARY_DELTAS_LT_0.01_PREFER_F1"),
            "scope": "DEVELOPMENT_E001_E100_ONLY_VALIDATION_AND_FINAL_OOS_SEALED",
        },
    }


def protocol_hash(root: Path | None = None) -> str:
    return canonical_hash(protocol_payload(root))


def verify_protocol(root: Path | None = None) -> dict:
    payload = protocol_payload(root)
    if canonical_hash(payload) != FROZEN_PROTOCOL_HASH:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_PROTOCOL_HASH_MISMATCH")
    return payload


def guard_scope(phase: str, ordinals: list[int]) -> None:
    guard_evaluation(phase, ordinals)
    if not ordinals or min(ordinals) < 1 or max(ordinals) > 100:
        raise PermissionError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")


RESULT_LEAK_PATTERNS = (
    "horizon_component_replacement_v1_*",
    "component_replacement_v1_*",
    "fusion_replacement_v1_*",
)


def result_leak_scan(reports_root: Path,
                     patterns: tuple[str, ...] = RESULT_LEAK_PATTERNS) -> dict:
    """Lifecycle-aware scan: findings returned as data, never hard-coded."""
    if not Path(reports_root).exists():
        return {"clean": True, "leaks": [], "root": str(reports_root)}
    leaks = sorted({match.name for pattern in patterns
                    for match in Path(reports_root).glob(pattern)})
    return {"clean": not leaks, "leaks": leaks, "root": str(reports_root)}


def guard_no_formal_results(reports_root: Path) -> dict:
    """Runtime preregistration leak gate over the live reports root."""
    scan = result_leak_scan(reports_root)
    if not scan["clean"]:
        raise ValueError(f"PREREGISTRATION_RESULT_LEAK_BLOCKER: {scan['leaks']}")
    return scan


def _finite(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)):
        raise ValueError(f"HORIZON_FUSION_METRIC_INCOMPLETE: {name}")
    return float(value)


def pareto_relative(*, candidate_rankic: float, candidate_spread: float,
                    reference_rankic: float, reference_spread: float) -> bool:
    """Strict improvement in one primary, non-decrease in the other."""
    cwr = _finite("candidate_rankic", candidate_rankic)
    cws = _finite("candidate_spread", candidate_spread)
    rwr = _finite("reference_rankic", reference_rankic)
    rws = _finite("reference_spread", reference_spread)
    return (cwr > rwr and cws >= rws) or (cws > rws and cwr >= rwr)


def horizon_red_flag(rankic_by_horizon: dict) -> tuple[bool, list[str]]:
    if set(rankic_by_horizon) != {str(h) for h in HORIZONS}:
        raise ValueError("HORIZON_FUSION_METRIC_INCOMPLETE: horizon set")
    flagged = [h for h in map(str, HORIZONS)
               if _finite(f"rankic_{h}", rankic_by_horizon[h]) < HORIZON_RED_FLAG_THRESHOLD]
    return bool(flagged), flagged


def temporal_gate(block_weighted_rankic: dict) -> bool:
    if set(block_weighted_rankic) != {b[0] for b in BLOCKS}:
        raise ValueError("HORIZON_FUSION_METRIC_INCOMPLETE: block set")
    values = {b: _finite(f"block_{b}", v) for b, v in block_weighted_rankic.items()}
    return (sum(v > 0 for v in values.values()) >= TEMPORAL_POSITIVE_BLOCKS_AT_LEAST
            and sum(v < HORIZON_RED_FLAG_THRESHOLD for v in values.values())
            <= TEMPORAL_RED_BLOCKS_AT_MOST)


def advancement_decision(*, candidate_id: str, weighted_rankic: float,
                         weighted_spread: float, f0_rankic: float, f0_spread: float,
                         f1_rankic: float | None = None, f1_spread: float | None = None,
                         rankic_by_horizon: dict,
                         block_weighted_rankic: dict) -> dict:
    """Frozen gate stack for F1/F2; F0 is a control and never advances."""
    if candidate_id not in CANDIDATE_IDS:
        raise ValueError("HORIZON_COMPONENT_REPLACEMENT_UNKNOWN_CANDIDATE")
    wr = _finite("weighted_rankic", weighted_rankic)
    ws = _finite("weighted_spread", weighted_spread)
    if candidate_id == "F0_CONTROL":
        return {"candidateId": candidate_id, "advancementStatus": STATUS_CONTROL,
                "frozenGateResult": STATUS_CONTROL, "level1": "NOT_APPLICABLE",
                "vsF0": "NOT_APPLICABLE", "vsF1": "NOT_APPLICABLE",
                "temporalStability": "NOT_APPLICABLE", "horizonRedFlag": False,
                "redFlagHorizons": [], "minimalReplacementPreference": "NOT_APPLICABLE"}
    level1 = wr > 0 and ws > 0
    vs_f0 = pareto_relative(candidate_rankic=wr, candidate_spread=ws,
                            reference_rankic=f0_rankic, reference_spread=f0_spread)
    if candidate_id == "F2_H10_H40_REPLACEMENT":
        if f1_rankic is None or f1_spread is None:
            raise ValueError("HORIZON_FUSION_METRIC_INCOMPLETE: F2 requires F1 reference")
        vs_f1 = pareto_relative(candidate_rankic=wr, candidate_spread=ws,
                                reference_rankic=f1_rankic, reference_spread=f1_spread)
    else:
        vs_f1 = None
    red, flagged = horizon_red_flag(rankic_by_horizon)
    temporal = temporal_gate(block_weighted_rankic)
    all_ok = level1 and vs_f0 and temporal and not red \
        and (vs_f1 is not False if vs_f1 is not None else True)
    if not level1:
        frozen_result = "LEVEL1_FAIL"
    elif not vs_f0:
        frozen_result = "F1_RELATIVE_GATE_FAIL" if candidate_id == "F1_H10_REPLACEMENT" \
            else "F2_VS_F0_GATE_FAIL"
    elif vs_f1 is False:
        frozen_result = "H40_INCREMENTAL_REPLACEMENT_NOT_SUPPORTED"
    elif red:
        frozen_result = "HORIZON_RED_FLAG"
    elif not temporal:
        frozen_result = "FUSION_TEMPORAL_STABILITY_GATE_FAIL"
    else:
        frozen_result = STATUS_ADVANCED
    return {
        "candidateId": candidate_id,
        "advancementStatus": STATUS_ADVANCED if all_ok else STATUS_NOT_ADVANCED,
        "frozenGateResult": frozen_result,
        "level1": "LEVEL1_PASS" if level1 else "LEVEL1_FAIL",
        "vsF0": "VS_F0_PASS" if vs_f0 else "VS_F0_FAIL",
        "vsF1": ("NOT_APPLICABLE" if vs_f1 is None
                 else ("VS_F1_PASS" if vs_f1 else "VS_F1_FAIL")),
        "temporalStability": "TEMPORAL_PASS" if temporal else "TEMPORAL_FAIL",
        "horizonRedFlag": red,
        "redFlagHorizons": flagged,
        "minimalReplacementPreference": "NOT_APPLICABLE",
    }


def prefer_minimal_replacement(*, f1_status: str, f2_status: str,
                               f1_rankic: float, f2_rankic: float,
                               f1_spread: float, f2_spread: float) -> bool:
    """Near-tie discipline only; never a statistical claim."""
    values = (f1_rankic, f2_rankic, f1_spread, f2_spread)
    for value in values:
        _finite("minimal_replacement_input", value)
    return (f1_status == f2_status == STATUS_ADVANCED
            and abs(float(f2_rankic) - float(f1_rankic)) < MINIMAL_TIE_BAND
            and abs(float(f2_spread) - float(f1_spread)) < MINIMAL_TIE_BAND)

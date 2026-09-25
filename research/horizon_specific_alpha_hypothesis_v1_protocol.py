"""Frozen, non-executing horizon-local Alpha Hypothesis V1 preregistration.

No market data, labels, model training, or candidate results are read here.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from research.factor_set_v2_protocol import (
    FAMILY_MEMBERS, FAMILY_PROCESSING_ORDER, FROZEN_FACTOR_ORDER,
)
from research.horizon_specific_alpha_hypothesis_v1_selection import (
    HORIZONS, RANK_FIELDS, REDUNDANCY_THRESHOLD, SOURCE_SHA256,
    derive_selection,
)
from research.sector_development_protocol import canonical_hash, guard_evaluation

RESEARCH_TYPE = "HORIZON_SPECIFIC_ALPHA_HYPOTHESIS_V1"
CONFIG_RELPATH = "research/configs/horizon_specific_alpha_hypothesis_v1.json"
PROTOCOL_RELPATH = "docs/research/shenwan_horizon_specific_alpha_hypothesis_v1.md"
TRACE_RELPATH = "docs/research/shenwan_horizon_specific_alpha_hypothesis_v1_selection_trace.md"
CANDIDATE_IDS = ("H10_S", "H10_C", "H40_S", "H40_C", "H120_S", "H120_C")
EXACT_CANDIDATES = {
    "H10_S": ("p5",),
    "H10_C": ("d10", "p5", "align", "vc", "dd20"),
    "H40_S": ("vc",),
    "H40_C": ("d120", "p60", "align", "vc", "rev5", "dd20"),
    "H120_S": ("vc",),
    "H120_C": ("d5", "p20", "vc", "rev10", "dd60", "rsi"),
}
FROZEN_CONFIG_HASH = "ddaaa1c761bf1ab37d86bd5228ad306d54af66575fbe2c06ed4df576e01446ec"
FROZEN_PROTOCOL_HASH = "d598efd34fe2a6c03832e3faaeadd738cc63a604e5da4c8f1a3740c33e69b8d4"


def _root(root: Path | None) -> Path:
    return root or Path(__file__).resolve().parents[1]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _self_sha256() -> str:
    # Normalize only the self-referential frozen-hash assignment. Any other
    # protocol implementation change alters the identity before formal use.
    source = Path(__file__).read_bytes()
    normalized, count = re.subn(
        rb'^FROZEN_PROTOCOL_HASH = "[^"]+"$',
        b'FROZEN_PROTOCOL_HASH = "<SELF>"', source, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("HORIZON_SPECIFIC_PROTOCOL_HASH_MISMATCH")
    return hashlib.sha256(normalized).hexdigest()


def load_config(root: Path | None = None) -> dict:
    config = json.loads((_root(root) / CONFIG_RELPATH).read_text(encoding="utf-8"))
    if canonical_hash(config) != FROZEN_CONFIG_HASH:
        raise ValueError("HORIZON_SPECIFIC_CONFIG_DRIFT_BLOCKER")
    if (config["researchType"] != RESEARCH_TYPE
            or config["phase"] != "DEVELOPMENT"
            or config["developmentIds"] != "E001-E100"
            or config["factorPipelineOrder"] != list(FROZEN_FACTOR_ORDER)
            or config["factorFamilies"] != {k: list(v) for k, v in FAMILY_MEMBERS.items()}
            or config["familyProcessingOrder"] != list(FAMILY_PROCESSING_ORDER)
            or config["stabilityRankFields"] != list(RANK_FIELDS)
            or config["redundancyThreshold"] != REDUNDANCY_THRESHOLD
            or config["candidateIds"] != list(CANDIDATE_IDS)
            or {name: tuple(item["factorList"]) for name, item in config["candidates"].items()}
            != EXACT_CANDIDATES):
        raise ValueError("HORIZON_SPECIFIC_CONFIG_DRIFT_BLOCKER")
    return config


def protocol_payload(root: Path | None = None) -> dict:
    repo = _root(root)
    config = load_config(repo)
    return {
        "researchType": RESEARCH_TYPE,
        "configPath": CONFIG_RELPATH,
        "configExactContent": config,
        "protocolDocument": {"path": PROTOCOL_RELPATH,
                             "sha256": _file_sha256(repo / PROTOCOL_RELPATH)},
        "selectionTrace": {"path": TRACE_RELPATH,
                           "sha256": _file_sha256(repo / TRACE_RELPATH)},
        "implementationSha256": {
            "protocolModule": _self_sha256(),
            "selectionModule": _file_sha256(repo / "research/horizon_specific_alpha_hypothesis_v1_selection.py"),
        },
        "sourceSha256": SOURCE_SHA256,
        "frozenConstants": {
            "factorOrder": list(FROZEN_FACTOR_ORDER),
            "familyOrder": list(FAMILY_PROCESSING_ORDER),
            "familyMembers": {k: list(v) for k, v in FAMILY_MEMBERS.items()},
            "horizons": list(HORIZONS), "rankFields": list(RANK_FIELDS),
            "redundancyThreshold": REDUNDANCY_THRESHOLD,
            "candidateIds": list(CANDIDATE_IDS),
            "exactCandidates": {k: list(v) for k, v in EXACT_CANDIDATES.items()},
            "advancement": "LEVEL1_POSITIVE_BOTH_THEN_SAME_HORIZON_C0_PARETO_STRICT_THEN_3_OF_4_POSITIVE_AND_AT_MOST_ONE_LT_MINUS_0.02",
            "simplicity": "IF_BOTH_ADVANCED_AND_BOTH_ABSOLUTE_PRIMARY_DELTAS_LT_0.01_PREFER_SINGLE",
            "scope": "DEVELOPMENT_E001_E100_ONLY_VALIDATION_AND_FINAL_OOS_SEALED",
        },
    }


def protocol_hash(root: Path | None = None) -> str:
    return canonical_hash(protocol_payload(root))


def verify_protocol(root: Path | None = None) -> dict:
    payload = protocol_payload(root)
    if canonical_hash(payload) != FROZEN_PROTOCOL_HASH:
        raise ValueError("HORIZON_SPECIFIC_PROTOCOL_HASH_MISMATCH")
    selected = derive_selection(_root(root))
    if selected["candidates"] != {k: list(v) for k, v in EXACT_CANDIDATES.items()}:
        raise ValueError("HORIZON_SPECIFIC_SELECTION_DRIFT_BLOCKER")
    return payload


def guard_scope(phase: str, ordinals: list[int]) -> None:
    guard_evaluation(phase, ordinals)
    if not ordinals or min(ordinals) < 1 or max(ordinals) > 100:
        raise PermissionError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")


def advancement_status(*, candidate_horizon: int, control_horizon: int,
                       mean_rankic: float, mean_spread: float,
                       c0_mean_rankic: float, c0_mean_spread: float,
                       block_mean_rankic: dict[str, float]) -> str:
    """Pure synthetic-testable future gate; never evaluates a formal result here."""
    if candidate_horizon not in HORIZONS or control_horizon != candidate_horizon:
        raise ValueError("SAME_HORIZON_C0_REQUIRED")
    values = (mean_rankic, mean_spread, c0_mean_rankic, c0_mean_spread)
    if (set(block_mean_rankic) != {"B1", "B2", "B3", "B4"}
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) for x in (*values, *block_mean_rankic.values()))):
        raise ValueError("HORIZON_PRIMARY_OR_BLOCK_METRIC_INCOMPLETE")
    if mean_rankic <= 0 or mean_spread <= 0:
        return "HORIZON_NOT_ADVANCED"
    pareto = ((mean_rankic > c0_mean_rankic and mean_spread >= c0_mean_spread)
              or (mean_spread > c0_mean_spread and mean_rankic >= c0_mean_rankic))
    if not pareto:
        return "HORIZON_NOT_ADVANCED"
    block_values = list(block_mean_rankic.values())
    if (sum(x > 0 for x in block_values) < 3
            or sum(x < -0.02 for x in block_values) > 1):
        return "TEMPORAL_STABILITY_GATE_FAIL"
    return "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"


def prefer_single_if_near_tie(*, single_status: str, compact_status: str,
                              single_mean_rankic: float, compact_mean_rankic: float,
                              single_mean_spread: float, compact_mean_spread: float) -> bool:
    advanced = "HORIZON_ADVANCED_FOR_FURTHER_REVIEW"
    values = (single_mean_rankic, compact_mean_rankic,
              single_mean_spread, compact_mean_spread)
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) for x in values):
        raise ValueError("HORIZON_PRIMARY_METRIC_INCOMPLETE")
    return (single_status == compact_status == advanced
            and abs(single_mean_rankic - compact_mean_rankic) < 0.01
            and abs(single_mean_spread - compact_mean_spread) < 0.01)

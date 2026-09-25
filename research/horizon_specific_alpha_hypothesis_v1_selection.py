"""Preregistration-only selection from frozen Development diagnostic tables.

This module reads two existing summary CSVs; it never opens market data,
training labels, predictions, or a model runner.
"""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

from research.factor_set_v2_protocol import (
    FAMILY_MEMBERS, FAMILY_PROCESSING_ORDER, FROZEN_FACTOR_ORDER,
)

ALPHA_REL = (
    "reports/research/shenwan_sector_index/"
    "alpha_stability_regime_audit_20260925_103645_877103_utc/"
    "factor_transfer_summary.csv"
)
FACTOR_REL = (
    "reports/research/shenwan_sector_index/"
    "factor_alpha_audit_20260925_071934_967164_utc/"
    "factor_correlation_spearman.csv"
)
SOURCE_SHA256 = {
    ALPHA_REL: "ae6f052926fbc2bdf128d89082dcd0f3709ed6af6adb37c672cb6c5692aa69c4",
    FACTOR_REL: "2bd2090af103b37f9db26d9114f04679e55723a4cb21de1aae38ee9b10c595b7",
}
HORIZONS = (10, 40, 120)
RANK_FIELDS = (
    "hard_flip_rate_ascending", "raw_sign_agreement_rate_descending",
    "transfer_spearman_descending", "frozen_pipeline_index_ascending",
)
REDUNDANCY_THRESHOLD = 0.80


def _finite(row: dict, field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE") from exc
    if not math.isfinite(value):
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE")
    return value


def _rows(root: Path, relpath: str) -> list[dict[str, str]]:
    path = root / relpath
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE") from exc
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256[relpath]:
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: source hash drift")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def derive_selection(root: Path | None = None) -> dict:
    """Return deterministic lists and a complete, non-performance trace."""
    root = root or Path(__file__).resolve().parents[1]
    factors = tuple(FROZEN_FACTOR_ORDER)
    pipeline_index = {name: i for i, name in enumerate(factors)}
    family_of = {factor: family for family, members in FAMILY_MEMBERS.items()
                 for factor in members}
    if set(family_of) != set(factors) or len(family_of) != len(factors):
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: family identity")

    transfer = _rows(root, ALPHA_REL)
    if len(transfer) != len(factors) * len(HORIZONS):
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: row count")
    keyed = {}
    for row in transfer:
        try:
            horizon = int(row["horizon"])
            factor = row["factor"]
            dates = int(row["valid_signal_dates"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE") from exc
        key = (horizon, factor)
        if (horizon not in HORIZONS or factor not in factors or key in keyed
                or dates != 100):
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: identity")
        flip = _finite(row, "hard_flip_rate")
        agreement = _finite(row, "raw_sign_agreement_rate")
        spearman = _finite(row, "transfer_spearman")
        if not (0 <= flip <= 1 and 0 <= agreement <= 1 and -1 <= spearman <= 1):
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: range")
        keyed[key] = (flip, agreement, spearman)

    correlations = _rows(root, FACTOR_REL)
    if len(correlations) != len(factors) ** 2:
        raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: correlation count")
    rho = {}
    for row in correlations:
        try:
            pair = (row["factor_a"], row["factor_b"])
            dates = int(row["valid_dates"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE") from exc
        if (pair[0] not in factors or pair[1] not in factors or pair in rho
                or dates != 100):
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: correlation identity")
        value = _finite(row, "mean_daily_spearman")
        if abs(value) > 1 + 1e-12:
            raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: correlation range")
        rho[pair] = value
    for a in factors:
        for b in factors:
            if (a, b) not in rho or abs(rho[a, b] - rho[b, a]) > 1e-12:
                raise ValueError("HORIZON_STABILITY_EVIDENCE_INCOMPLETE: correlation symmetry")

    candidates = {}
    traces = {}
    for horizon in HORIZONS:
        def rank_key(factor: str) -> tuple:
            flip, agreement, spearman = keyed[horizon, factor]
            return (flip, -agreement, -spearman, pipeline_index[factor])

        ordered = sorted(factors, key=rank_key)
        single = ordered[0]
        selected = []
        decisions = []
        for family in FAMILY_PROCESSING_ORDER:
            for factor in sorted(FAMILY_MEMBERS[family], key=rank_key):
                conflicts = [
                    {"with": previous, "rho": rho[factor, previous]}
                    for previous in selected
                    if abs(rho[factor, previous]) >= REDUNDANCY_THRESHOLD
                ]
                decisions.append({"family": family, "factor": factor,
                                  "decision": "REDUNDANT" if conflicts else "SELECTED",
                                  "conflicts": conflicts})
                if not conflicts:
                    selected.append(factor)
                    break
        compact = [factor for factor in factors if factor in selected]
        candidates[f"H{horizon}_S"] = [single]
        candidates[f"H{horizon}_C"] = compact
        traces[str(horizon)] = {
            "ranked": [
                {"rank": n, "factor": factor, "family": family_of[factor],
                 "hardFlipRate": keyed[horizon, factor][0],
                 "rawSignAgreementRate": keyed[horizon, factor][1],
                 "transferSpearman": keyed[horizon, factor][2],
                 "pipelineIndex": pipeline_index[factor]}
                for n, factor in enumerate(ordered, 1)
            ],
            "compactAdmission": decisions,
            "compactSelectionOrder": selected,
            "compactPipelineOrder": compact,
            "compactCollapsedToSingle": len(compact) == 1,
        }
    return {"sourceSha256": SOURCE_SHA256, "rankFields": list(RANK_FIELDS),
            "candidates": candidates, "trace": traces}

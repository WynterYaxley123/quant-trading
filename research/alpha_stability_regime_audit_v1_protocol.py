"""Frozen, result-free Alpha Stability & Regime Audit V1 contract."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.factor_set_v2_protocol import CANDIDATE_FACTORS, FROZEN_FACTOR_ORDER
from research.sector_development_protocol import canonical_hash, guard_evaluation

CONFIG_RELPATH = "research/configs/alpha_stability_regime_audit_v1.json"
AUDIT_TYPE = "ALPHA_STABILITY_REGIME_AUDIT_V1"
FACTOR_ORDER = tuple(FROZEN_FACTOR_ORDER)
HORIZONS = (10, 40, 120)
SCHEMES = {"C0": FACTOR_ORDER, **CANDIDATE_FACTORS}
LAGS = (1, 5, 10, 20)
BLOCKS = (("B1", 1, 25), ("B2", 26, 50), ("B3", 51, 75), ("B4", 76, 100))
MIN_PAIRS = 30
DIRECTION_THRESHOLD = 0.02
CANCELLATION_EPS = 1e-12
FROZEN_PROTOCOL_HASH = "7bdf79df7c95134cdbdedb04ce825614c35a2bc72b4f757dd09ecf5e588fb4c1"


def config_path(root: Path | None = None) -> Path:
    return (root or Path(__file__).resolve().parents[1]) / CONFIG_RELPATH


def load_config(root: Path | None = None) -> dict:
    config = json.loads(config_path(root).read_text(encoding="utf-8"))
    expected = {
        "schemaVersion": 1, "auditType": AUDIT_TYPE, "phase": "DEVELOPMENT",
        "developmentIds": "E001-E100", "universe": "U0_FIXED_124", "sectorCount": 124,
        "factorOrder": list(FACTOR_ORDER), "horizons": list(HORIZONS),
        "schemes": {name: list(factors) for name, factors in SCHEMES.items()},
        "minSectorPairs": MIN_PAIRS, "directionThreshold": DIRECTION_THRESHOLD,
        "directionClasses": ["POSITIVE", "NEUTRAL", "NEGATIVE"],
        "hardFlipDefinition": "POSITIVE_TO_NEGATIVE_OR_NEGATIVE_TO_POSITIVE",
        "autocorrelationLags": list(LAGS),
        "blocks": [{"id": name, "first": first, "last": last}
                   for name, first, last in BLOCKS],
        "cancellationEps": CANCELLATION_EPS, "ridgeAlpha": 0.01,
        "trainWindowCalendarMonths": 6, "minimumValidTrainingDays": 30,
        "target": "CROSS_SECTIONAL_EXCESS_FORWARD_RETURN", "preprocessing": "NONE_RAW",
        "validationSealed": True, "finalOosSealed": True, "diagnosticOnly": True,
        "noFactorSelection": True, "noParameterSearch": True, "noNewCandidate": True,
    }
    if config != expected:
        raise ValueError("ALPHA_STABILITY_CONFIG_DRIFT_BLOCKER")
    return config


def protocol_payload(root: Path | None = None) -> dict:
    return {
        "configPath": CONFIG_RELPATH,
        "configExactContent": load_config(root),
        "sources": {
            "trainingDates": "SWSectorRotationCore.boundaries + formal V2 labelled intersection",
            "trainingTarget": "development_iteration1_protocol.cross_sectional_excess_training_target",
            "ridge": "NumPyRidge(alpha=0.01, raw X, fit_intercept=True)",
            "evaluationLabel": "make_forward_label common calendar t+h, absolute return",
            "ic": "factor_alpha_audit_v1_protocol.cross_sectional_ic, average-rank ties",
            "aggregation": "equal-date descriptive; population std ddof=0",
            "coefficientScale": "beta * population std of legal stacked X_train; diagnostic only",
            "betaFutureHardFlip": "exact nonzero beta sign opposite non-neutral evaluation RankIC class; paired-date denominator",
            "centeredContribution": "beta * (X_signal - cross-sectional X_signal mean)",
            "share": "sum_sector abs(centered contribution factor) / sum_factor_sector abs(centered contribution)",
            "cancellation": "clip(1 - abs(sum_factor centered contribution)/(sum_factor abs(centered contribution)+eps),0,1)",
            "diversification": "std_sector(sum_factor centered contribution)/(sum_factor std_sector(centered contribution)+eps)",
            "contributionCorrelation": "mean daily cross-sectional Spearman by factor pair",
            "modelMetrics": "read-only existing C0/V2 formal artifacts; no new performance metric",
            "missing": "null and exclude invalid pair; never fill, shift or interpolate",
        },
        "identitySamples": {
            "factors": [1, 50, 100], "targets": [1, 50, 100],
            "trainingWindows": [1, 25, 50, 75, 100],
            "coefficients": [1, 50, 100], "sectors": 10,
            "toleranceFactors": 1e-9, "toleranceTargets": 1e-12,
            "tolerancePredictions": 1e-10, "toleranceContributions": 1e-10,
        },
        "selectionBias": "POST-V2 DEVELOPMENT DIAGNOSTIC RESEARCH; NOT INDEPENDENT VALIDATION; NOT OOS",
        "statisticalPolicy": "DESCRIPTIVE ONLY; no p-value, winner or threshold optimization",
    }


def protocol_hash(root: Path | None = None) -> str:
    return canonical_hash(protocol_payload(root))


def verify_protocol(root: Path | None = None) -> dict:
    payload = protocol_payload(root)
    if canonical_hash(payload) != FROZEN_PROTOCOL_HASH:
        raise ValueError("ALPHA_STABILITY_PROTOCOL_HASH_DRIFT_BLOCKER")
    return payload


def guard_scope(phase: str, ordinals: list[int]) -> None:
    guard_evaluation(phase, ordinals)
    if not ordinals or min(ordinals) < 1 or max(ordinals) > 100:
        raise PermissionError("SEALED_OR_NON_DEVELOPMENT_ACCESS_BLOCKER")


def direction(value: float | None) -> str | None:
    if value is None or not np.isfinite(value):
        return None
    if value > DIRECTION_THRESHOLD:
        return "POSITIVE"
    if value < -DIRECTION_THRESHOLD:
        return "NEGATIVE"
    return "NEUTRAL"


def hard_flip(train: float | None, evaluation: float | None) -> bool | None:
    a, b = direction(train), direction(evaluation)
    if a is None or b is None:
        return None
    return (a, b) in {("POSITIVE", "NEGATIVE"), ("NEGATIVE", "POSITIVE")}


def raw_sign_agreement(train: float | None, evaluation: float | None) -> bool | None:
    if train is None or evaluation is None or not (np.isfinite(train) and np.isfinite(evaluation)):
        return None
    return bool(np.sign(train) == np.sign(evaluation))


def beta_evaluation_hard_flip(beta: float | None, evaluation: float | None) -> bool | None:
    """Beta has raw units, so only its exact sign is compared with IC class."""
    evaluated = direction(evaluation)
    if beta is None or not np.isfinite(beta) or evaluated is None:
        return None
    return bool((beta > 0 and evaluated == "NEGATIVE")
                or (beta < 0 and evaluated == "POSITIVE"))


def block_id(ordinal: int) -> str:
    guard_scope("development", [ordinal])
    return next(name for name, first, last in BLOCKS if first <= ordinal <= last)


def lag_autocorrelation(values: list[float], lag: int) -> float | None:
    if lag not in LAGS:
        raise ValueError("UNREGISTERED_AUTOCORRELATION_LAG")
    series = np.asarray(values, dtype=float)
    if len(series) <= lag:
        return None
    left, right = series[:-lag], series[lag:]
    valid = np.isfinite(left) & np.isfinite(right)
    if valid.sum() < 2 or np.std(left[valid]) == 0 or np.std(right[valid]) == 0:
        return None
    return float(np.corrcoef(left[valid], right[valid])[0, 1])


def cross_sectional_spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < MIN_PAIRS:
        return None
    rx = pd.Series(x[valid]).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(y[valid]).rank(method="average").to_numpy(dtype=float)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])

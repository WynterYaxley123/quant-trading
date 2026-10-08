"""Finite descriptive diagnostics; no model selection, inferential tests or gates."""

from __future__ import annotations

from typing import Any

import numpy as np

from research.swl1_ridge_v1.evaluation import rank_ic


def distribution(values: Any) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not len(array):
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "minimum": None,
            "maximum": None,
            "q05": None,
            "median": None,
            "q95": None,
        }
    quantiles = np.quantile(array, [0.05, 0.5, 0.95])
    return {
        "count": len(array),
        "mean": float(array.mean()),
        "std": float(array.std()),
        "minimum": float(array.min()),
        "maximum": float(array.max()),
        "q05": float(quantiles[0]),
        "median": float(quantiles[1]),
        "q95": float(quantiles[2]),
    }


def conditioning(z: np.ndarray, alpha: float) -> dict[str, Any]:
    if alpha <= 0 or not np.isfinite(z).all():
        raise ValueError("INVALID_RIDGE_DIAGNOSTIC_INPUT")
    eigenvalues = np.maximum(np.linalg.eigvalsh(z.T @ z), 0)
    maximum, minimum = float(eigenvalues[-1]), float(eigenvalues[0])
    shrink = eigenvalues / (eigenvalues + alpha)
    return {
        "gram_min": minimum,
        "gram_eigenvalues": eigenvalues.tolist(),
        "gram_max": maximum,
        "condition_unregularized": maximum / minimum if minimum > maximum * 1e-12 else None,
        "condition_regularized": (maximum + alpha) / (minimum + alpha),
        "effective_df_slope": float(shrink.sum()),
        "intercept_df": 1,
        "alpha": alpha,
        "alpha_per_row": alpha / len(z),
        "singular_min": float(np.sqrt(minimum)),
        "singular_max": float(np.sqrt(maximum)),
        "shrink_min": float(shrink.min()),
        "shrink_max": float(shrink.max()),
    }


def coefficient_accounting(
    current_z: np.ndarray, coefficients: np.ndarray | None
) -> dict[str, Any]:
    if coefficients is None:
        return {"status": "NOT_COMPUTABLE_WITH_ADMITTED_EVIDENCE"}
    if current_z.shape[1] != len(coefficients) or not np.isfinite(coefficients).all():
        raise ValueError("COEFFICIENT_SHAPE_OR_FINITE_FAILURE")
    contributions = current_z * coefficients
    exposure = np.std(contributions, axis=0)
    total = float(exposure.sum())
    return {
        "status": "COMPUTED",
        "coefficient_norm": float(np.linalg.norm(coefficients)),
        "contribution_l1_shares": (exposure / total).tolist()
        if total
        else [0.0] * len(coefficients),
        "contribution_top3_share": float(np.sort(exposure)[-3:].sum() / total) if total else 0.0,
        "prediction_std": float(np.std(contributions.sum(axis=1))),
        "accounting_max_error": float(
            np.max(np.abs(contributions.sum(axis=1) - current_z @ coefficients))
        ),
        "interpretation": "Correlated factor contributions are not causal or independent effects.",
    }


def effective_dimension(values: np.ndarray) -> float | None:
    eigen = np.maximum(np.linalg.eigvalsh(np.cov(values, rowvar=False)), 0)
    denominator = float(eigen @ eigen)
    return float(eigen.sum() ** 2 / denominator) if denominator else None


def loo_ic(prediction: np.ndarray, actual: np.ndarray) -> dict[str, Any]:
    reference = rank_ic(prediction, actual)
    if reference is None:
        return {"maximum_absolute_ic_change": None}
    changes = []
    for index in range(len(actual)):
        keep = np.arange(len(actual)) != index
        value = rank_ic(prediction[keep], actual[keep])
        if value is not None:
            changes.append(value - reference)
    return {
        "maximum_absolute_ic_change": max(map(abs, changes), default=None),
        "minimum_ic": reference + min(changes) if changes else None,
        "maximum_ic": reference + max(changes) if changes else None,
        "label": "EXPLORATORY_LEAVE_ONE_OUT_DIAGNOSTIC",
    }


def comparison_eligibility(left: dict[str, Any], right: dict[str, Any]) -> dict[str, bool]:
    keys = ("universe", "panel", "dates", "horizon", "target", "outcomes", "evaluation", "role")
    return {"same_" + key: left[key] == right[key] for key in keys}


def assert_parity(actual: Any, expected: Any, path: str = "metrics") -> None:
    """Original public metric trees must agree, including null/count/block semantics."""
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key not in actual:
                raise ValueError(f"REPLAY_PARITY_FAILURE:{path}.{key}")
            assert_parity(actual[key], value, path + "." + key)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError(f"REPLAY_PARITY_FAILURE:{path}")
        for index, value in enumerate(expected):
            assert_parity(actual[index], value, f"{path}[{index}]")
    elif isinstance(expected, float):
        if not np.isclose(actual, expected, rtol=1e-10, atol=1e-12):
            raise ValueError(f"REPLAY_PARITY_FAILURE:{path}")
    elif actual != expected:
        raise ValueError(f"REPLAY_PARITY_FAILURE:{path}")

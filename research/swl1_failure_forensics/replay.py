"""Replay only selected frozen fits; keep every per-date diagnostic private."""

from __future__ import annotations

from typing import Any

import numpy as np

from research.swl1_ridge_v1.evaluation import rank_ic
from research.swl1_ridge_v1.evaluation import summarize as summarize_v1
from research.swl1_ridge_v1.protocol import HORIZONS, WEIGHTS, body, digest, exact_targets
from research.swl1_ridge_v1.protocol import Spec as SpecV1
from research.swl1_ridge_v1.protocol import fit_predict as fit_v1
from research.swl1_ridge_v2.evaluation import calendar_blocks, extremes
from research.swl1_ridge_v2.evaluation import summarize as summarize_v2
from research.swl1_ridge_v2.protocol import Spec as SpecV2
from research.swl1_ridge_v2.protocol import fit_predict as fit_v2
from strategies.etf_quant.config import FACTORS_19

from .diagnostics import (
    assert_parity,
    coefficient_accounting,
    conditioning,
    distribution,
    effective_dimension,
    loo_ic,
)


def factor_correlation(values: np.ndarray) -> list[list[float | None]]:
    covariance = np.cov(values, rowvar=False)
    divisor = np.sqrt(np.outer(np.diag(covariance), np.diag(covariance)))
    correlations = np.divide(
        covariance, divisor, out=np.full_like(covariance, np.nan), where=divisor > 0
    )
    return [[float(v) if np.isfinite(v) else None for v in row] for row in correlations]


def phase_replay(
    version: str,
    phase: str,
    features: np.ndarray,
    returns: np.ndarray,
    dates: list[str],
    codes: list[str],
    signals: list[int],
    selected: dict[str, Any],
    expected: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = SpecV1(**selected) if version == "v1" else SpecV2(**selected)
    targets = {h: exact_targets(returns[: max(signals) + 121], h) for h in HORIZONS}
    rows: list[dict[str, Any]] = []
    fit_records: list[dict[str, Any]] = []
    private: dict[str, Any] = {"signals": signals, "rows": rows, "fits": []}
    predictions: dict[int, list[np.ndarray]] = {h: [] for h in HORIZONS}
    coefficients: dict[int, list[np.ndarray]] = {h: [] for h in HORIZONS}
    numerics: dict[int, list[dict[str, Any]]] = {h: [] for h in HORIZONS}
    max_prediction_error = 0.0
    target_center_error = 0.0
    for signal in signals:
        parts: dict[str, Any] = {}
        for horizon in HORIZONS:
            prediction, metadata = (
                fit_v1(features, targets[horizon], dates, signal, horizon, spec)
                if isinstance(spec, SpecV1)
                else fit_v2(features, targets[horizon], dates, signal, horizon, spec)
            )
            names = spec.factors(horizon)
            columns = [FACTORS_19.index(name) for name in names]
            valid = [
                i
                for i in range(signal - horizon + 1)
                if dates[i] >= metadata["window_start"]
                and np.isfinite(features[i][:, columns]).all()
                and np.isfinite(targets[horizon][i]).all()
            ]
            if dates[max(valid) + horizon] > dates[signal]:
                raise ValueError("IMMATURE_TRAINING_LABEL")
            x = features[valid][:, :, columns].reshape(-1, len(columns))
            y0 = targets[horizon][valid]
            centered = y0 - y0.mean(axis=1, keepdims=True)
            target_center_error = max(
                target_center_error, float(np.max(np.abs(centered.mean(axis=1))))
            )
            y = centered.reshape(-1)
            scale = x.std(axis=0, ddof=0)
            scale = np.where(scale > 1e-12, scale, 1.0)
            z = (x - x.mean(axis=0)) / scale
            alpha = spec.alpha if isinstance(spec, SpecV1) else spec.penalty * len(y)
            gram = z.T @ z + alpha * np.eye(len(columns))
            rhs = z.T @ (y - y.mean())
            beta = np.linalg.solve(gram, rhs)
            current_z = (features[signal][:, columns] - x.mean(axis=0)) / scale
            recreated = current_z @ beta + y.mean()
            error = float(np.max(np.abs(prediction - recreated)))
            max_prediction_error = max(max_prediction_error, error)
            if error > 1e-12:
                raise ValueError("FROZEN_PREDICTION_PARITY_FAILURE")
            actual = targets[horizon][signal]
            ic = rank_ic(prediction, actual)
            centered_ic = rank_ic(prediction, actual - actual.mean())
            if ic is None or centered_ic is None or abs(ic - centered_ic) > 1e-12:
                raise ValueError("TARGET_RANK_CENTERING_FAILURE")
            if version == "v1":
                order = np.lexsort((np.array(codes), -prediction))
                top, bottom = order[:5], order[-5:]
            else:
                top, bottom = extremes(prediction, codes)
            parts[str(horizon)] = {
                "rank_ic": ic,
                "top5": float(actual[top].mean()),
                "bottom5": float(actual[bottom].mean()),
                "spread": float(actual[top].mean() - actual[bottom].mean()),
            }
            numeric = {
                **conditioning(z, alpha),
                **coefficient_accounting(current_z, beta),
                **loo_ic(prediction, actual),
                "relative_solve_residual": float(
                    np.linalg.norm(gram @ beta - rhs) / max(float(np.linalg.norm(rhs)), 1e-30)
                ),
                "actual_target_std": float(actual.std()),
                "training_dates": metadata["valid_training_dates"],
                "industry_rows": metadata["industry_rows"],
            }
            _, directions = np.linalg.eigh(z.T @ z)
            direction_exposure = np.std((current_z @ directions) * (directions.T @ beta), axis=0)
            exposure_sum = max(float(direction_exposure.sum()), 1e-30)
            numeric["weakest5_eigendirection_contribution_share"] = float(
                direction_exposure[:5].sum() / exposure_sum
            )
            numeric["strongest5_eigendirection_contribution_share"] = float(
                direction_exposure[-5:].sum() / exposure_sum
            )
            numerics[horizon].append(numeric)
            predictions[horizon].append(prediction)
            coefficients[horizon].append(beta)
            fit_records.append(
                {
                    "signal_date": dates[signal],
                    "phase": phase,
                    "spec": spec.identifier,
                    "horizon": horizon,
                    **metadata,
                }
            )
            private["fits"].append(
                {
                    "signal_date": dates[signal],
                    "horizon": horizon,
                    "coefficients": beta.tolist(),
                    "prediction": prediction.tolist(),
                    "diagnostics": numeric,
                }
            )
        rows.append({"date": dates[signal], "horizons": parts})
    original = (
        summarize_v1(rows, len(signals))
        if version == "v1"
        else summarize_v2(rows, [], len(signals), dates[signals[0]], dates[signals[-1]])
    )
    if version == "v2":
        original.update(
            {
                "fit_count": len(fit_records),
                "fit_records_sha256": digest(body(fit_records)),
                "ridge_alpha_by_horizon": {
                    str(h): {
                        "minimum": min(f["ridge_alpha"] for f in fit_records if f["horizon"] == h),
                        "maximum": max(f["ridge_alpha"] for f in fit_records if f["horizon"] == h),
                        "fits": len(signals),
                    }
                    for h in HORIZONS
                },
            }
        )
    assert_parity(original, expected)
    assignments = calendar_blocks(
        [dates[i] for i in signals], dates[signals[0]], dates[signals[-1]]
    )
    blocks = []
    for block in range(4):
        selected_rows = [r for r, b in zip(rows, assignments, strict=True) if b == block]
        hmeans = {
            str(h): float(np.mean([r["horizons"][str(h)]["rank_ic"] for r in selected_rows]))
            if selected_rows
            else None
            for h in HORIZONS
        }
        blocks.append(
            {
                "block": block + 1,
                "signals": len(selected_rows),
                "first": selected_rows[0]["date"] if selected_rows else None,
                "last": selected_rows[-1]["date"] if selected_rows else None,
                "horizon_rank_ic": hmeans,
                "composite": sum(
                    w * value
                    for w, value in zip(WEIGHTS, hmeans.values(), strict=True)
                    if value is not None
                )
                if selected_rows
                else None,
            }
        )
    horizon_diagnostics: dict[str, Any] = {}
    for h in HORIZONS:
        c = np.stack(coefficients[h])
        p = np.stack(predictions[h])
        cosine = np.sum(c[1:] * c[:-1], axis=1) / np.maximum(
            np.linalg.norm(c[1:], axis=1) * np.linalg.norm(c[:-1], axis=1), 1e-30
        )
        values = numerics[h]
        fields = (
            "gram_min",
            "gram_max",
            "condition_unregularized",
            "condition_regularized",
            "effective_df_slope",
            "alpha",
            "alpha_per_row",
            "singular_min",
            "singular_max",
            "shrink_min",
            "shrink_max",
            "coefficient_norm",
            "contribution_top3_share",
            "prediction_std",
            "maximum_absolute_ic_change",
            "minimum_ic",
            "maximum_ic",
            "relative_solve_residual",
            "actual_target_std",
            "training_dates",
            "industry_rows",
            "weakest5_eigendirection_contribution_share",
            "strongest5_eigendirection_contribution_share",
        )
        horizon_diagnostics[str(h)] = {
            "gram_eigenvalue_spectrum_mean": np.mean(
                [v["gram_eigenvalues"] for v in values], axis=0
            ).tolist(),
            "numerical": {
                key: distribution([v[key] if v[key] is not None else np.nan for v in values])
                for key in fields
            },
            "coefficient_mean": c.mean(axis=0).tolist(),
            "coefficient_mean_absolute": np.abs(c).mean(axis=0).tolist(),
            "coefficient_positive_fraction": (c > 0).mean(axis=0).tolist(),
            "coefficient_sign_persistence": (np.sign(c[1:]) == np.sign(c[:-1]))
            .mean(axis=0)
            .tolist(),
            "successive_coefficient_cosine": distribution(cosine),
            "successive_relative_coefficient_change": distribution(
                np.linalg.norm(c[1:] - c[:-1], axis=1)
                / np.maximum(np.linalg.norm(c[:-1], axis=1), 1e-30)
            ),
            "contribution_share_mean": np.mean(
                [v["contribution_l1_shares"] for v in values], axis=0
            ).tolist(),
            "successive_prediction_rank_correlation": distribution(
                [rank_ic(a, b) for a, b in zip(p[1:], p[:-1], strict=True)]
            ),
            "ic_lag1_autocorrelation": float(
                np.corrcoef(
                    [r["horizons"][str(h)]["rank_ic"] for r in rows[:-1]],
                    [r["horizons"][str(h)]["rank_ic"] for r in rows[1:]],
                )[0, 1]
            ),
            "maximum_nonoverlapping_signal_windows": (signals[-1] - signals[0]) // h + 1,
        }
    pairs = {}
    for a, b in ((10, 40), (10, 120), (40, 120)):
        ca, cb = np.stack(coefficients[a]), np.stack(coefficients[b])
        pairs[f"{a}_{b}"] = {
            "prediction_rank_correlation": distribution(
                [rank_ic(x, y) for x, y in zip(predictions[a], predictions[b], strict=True)]
            ),
            "realized_rank_correlation": distribution(
                [rank_ic(targets[a][i], targets[b][i]) for i in signals]
            ),
            "top5_overlap_fraction": distribution(
                [
                    len(set(extremes(x, codes)[0]) & set(extremes(y, codes)[0])) / 5
                    for x, y in zip(predictions[a], predictions[b], strict=True)
                ]
            ),
            "coefficient_sign_disagreement_fraction": distribution(
                (np.sign(ca) != np.sign(cb)).mean(axis=1)
            ),
        }
    signal_features = features[signals]
    flattened = signal_features.reshape(-1, len(FACTORS_19))
    past_returns = returns[signals]
    market = returns.mean(axis=1)
    regime = {
        "mean_daily_industry_return": distribution(past_returns.mean(axis=1)),
        "daily_cross_section_return_std": distribution(past_returns.std(axis=1)),
        "common_direction_fraction": distribution(
            np.maximum((past_returns > 0).mean(axis=1), (past_returns < 0).mean(axis=1))
        ),
        "trailing20_market_compound_return": distribution(
            [np.prod(1 + market[i - 19 : i + 1]) - 1 for i in signals]
        ),
        "trailing20_market_volatility": distribution(
            [np.std(market[i - 19 : i + 1], ddof=1) for i in signals]
        ),
        "industry_covariance_effective_dimension": effective_dimension(past_returns),
        "industry_covariance_first_pc_share": float(
            np.linalg.eigvalsh(np.cov(past_returns, rowvar=False))[-1]
            / np.trace(np.cov(past_returns, rowvar=False))
        ),
    }
    public = {
        "parity": "PASS",
        "original_metrics": original,
        "unified_calendar_blocks": blocks,
        "prediction_max_absolute_reconstruction_error": max_prediction_error,
        "training_target_center_max_error": target_center_error,
        "factor_names": list(FACTORS_19),
        "horizons": horizon_diagnostics,
        "horizon_pairs": pairs,
        "regime": regime,
        "factor_correlation": factor_correlation(flattened),
        "factors": {
            name: {
                "missing_fraction": float(np.mean(~np.isfinite(flattened[:, j]))),
                "pooled_distribution": distribution(flattened[:, j]),
                "daily_cross_section_mean_distribution": distribution(
                    signal_features[:, :, j].mean(axis=1)
                ),
                "cross_section_std": distribution(signal_features[:, :, j].std(axis=1)),
                "nearly_constant_cross_sections": int(
                    np.sum(signal_features[:, :, j].std(axis=1) < 1e-12)
                ),
                "factor_target_rank_ic_mean": {
                    str(h): distribution(
                        [rank_ic(features[i, :, j], targets[h][i]) for i in signals]
                    )
                    for h in HORIZONS
                },
            }
            for j, name in enumerate(FACTORS_19)
        },
    }
    return public, private


def shared_development(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    lrows = {r["date"]: r for r in left["rows"]}
    rrows = {r["date"]: r for r in right["rows"]}
    shared = sorted(lrows.keys() & rrows.keys())
    if not shared:
        return {"status": "NOT_COMPUTABLE_WITH_ADMITTED_EVIDENCE"}
    result: dict[str, Any] = {
        "dates": {"first": shared[0], "last": shared[-1], "count": len(shared)},
        "label": "SHARED_DATE_DESCRIPTIVE_COMPARISON_NOT_CAUSAL",
        "horizons": {},
    }
    for h in HORIZONS:
        lfits = {f["signal_date"]: f for f in left["fits"] if f["horizon"] == h}
        rfits = {f["signal_date"]: f for f in right["fits"] if f["horizon"] == h}
        result["horizons"][str(h)] = {
            "v1_mean_ic": float(np.mean([lrows[d]["horizons"][str(h)]["rank_ic"] for d in shared])),
            "v2_mean_ic": float(np.mean([rrows[d]["horizons"][str(h)]["rank_ic"] for d in shared])),
            "between_models_prediction_rank_correlation": distribution(
                [
                    rank_ic(np.asarray(lfits[d]["prediction"]), np.asarray(rfits[d]["prediction"]))
                    for d in shared
                ]
            ),
            "rank_order_changed_dates": sum(
                not np.array_equal(
                    np.argsort(lfits[d]["prediction"]), np.argsort(rfits[d]["prediction"])
                )
                for d in shared
            ),
        }
    return result

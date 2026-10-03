"""Current-snapshot warmup only; no historical performance or walk-forward."""

from datetime import datetime

import numpy as np
import pandas as pd

from ..domain import ModelPrediction, StrategyConfig, TradingCalendar
from ..factors import compute_close_factors
from ..models import NumPyRidge, TrainingObservation, fit_horizon, predict_industries
from ..models.fusion import fuse_predictions
from .storage import GateError


def current_predictions(series, provider, *, signal_at: datetime, config=None):
    config = StrategyConfig() if config is None else config
    if signal_at.date() != provider.cutoff or signal_at < provider.created_at:
        raise GateError("MODEL_SNAPSHOT_AVAILABILITY_BLOCKER")
    days = tuple(d.date() for d in series.closes.index)
    calendar = TradingCalendar(days)
    signal_i = len(days) - 1
    universe, features = model_features(series, provider)
    models, predictions = {}, {}
    for spec in config.horizons:
        h = int(spec.horizon)
        if signal_i < h:
            raise GateError("MODEL_WARMUP_INCOMPLETE")
        observations, _ = training_rows(series, provider, spec, universe, features)
        # available_at here is the actual CURRENT snapshot observation time,
        # not a claimed historical publication timestamp. Source timing stays
        # UNKNOWN/null in the export, Source C audit and public model metadata.
        try:
            model = fit_horizon(
                spec,
                observations,
                calendar=calendar,
                signal_at=signal_at,
                industry_universe=universe,
            )
            current = {c: tuple(features[c].iloc[-1][list(spec.factor_names)]) for c in universe}
            predictions[spec.horizon] = predict_industries(
                model, current, factor_names=spec.factor_names, signal_date=provider.cutoff
            )
        except (ValueError, FloatingPointError) as error:
            raise GateError("MODEL_WARMUP_INCOMPLETE", {"horizon": h}) from error
        models[spec.horizon] = model
    return (
        models,
        predictions,
        fuse_predictions(predictions, config=config, industry_universe=universe),
    )


def model_features(series, provider):
    """The admitted universe is explicit; no data/performance-based deletion."""
    contract = getattr(provider, "model_input_contract", None)
    universe = tuple(contract["industries"]) if contract else series.universe
    if not set(universe).issubset(series.universe):
        raise GateError("ADMITTED_MODEL_INDUSTRY_MISSING")
    return universe, {code: compute_close_factors(series.closes[code]) for code in universe}


def training_rows(series, provider, spec, universe, features):
    """Date × sector rows; full cross-sections inside the admitted universe.

    Rows from nonadmitted taxonomy industries cannot veto a model date. A
    partial date *inside* the admitted universe is still rejected unchanged.
    """
    days = tuple(d.date() for d in series.closes.index)
    h = int(spec.horizon)
    if len(days) <= h:
        raise GateError("MODEL_WARMUP_INCOMPLETE")
    cutoff = days[-1 - h]
    start = (pd.Timestamp(cutoff) - pd.DateOffset(months=6)).date()
    observations = []
    accepted = []
    for i, day in enumerate(days):
        if not start <= day <= cutoff:
            continue
        end = days[i + h]
        a = series.closes.loc[pd.Timestamp(day), list(universe)].to_numpy(dtype=float)
        b = series.closes.loc[pd.Timestamp(end), list(universe)].to_numpy(dtype=float)
        x = [
            features[c].loc[pd.Timestamp(day), list(spec.factor_names)].to_numpy(dtype=float)
            for c in universe
        ]
        if not (
            np.isfinite(a).all() and np.isfinite(b).all() and all(np.isfinite(v).all() for v in x)
        ):
            continue
        accepted.append(day)
        for c, values, left, right in zip(universe, x, a, b):
            observations.append(
                TrainingObservation(
                    spec.horizon,
                    c,
                    day,
                    end,
                    provider.created_at,
                    spec.factor_names,
                    tuple(map(float, values)),
                    float(right / left - 1),
                )
            )
    return observations, {
        "horizon": h,
        "valid_observations": len(observations),
        "unique_valid_dates": len(accepted),
        "valid_sectors": len(universe) if observations else 0,
        "mature_cutoff": str(cutoff),
        "window_start": str(start),
        "minimum_valid_dates": spec.minimum_valid_training_days,
        "status": "PASS" if len(accepted) >= spec.minimum_valid_training_days else "FAIL",
    }


def model_readiness_reference(series, provider, *, config=None):
    """Shared production inputs, nonformal math only; never writes runtime.

    The historical cutoff labels this reference, not a backdated decision or
    availability timestamp. Formal cycles retain current_predictions' gates.
    """
    config = StrategyConfig() if config is None else config
    universe, features = model_features(series, provider)
    reports, predictions = {}, {}
    for spec in config.horizons:
        rows, stats = training_rows(series, provider, spec, universe, features)
        if stats["status"] != "PASS":
            raise GateError("MODEL_WARMUP_INCOMPLETE", stats)
        targets = np.asarray([r.raw_forward_return for r in rows]).reshape(-1, len(universe))
        y = (targets - targets.mean(axis=1, keepdims=True)).reshape(-1)
        model = NumPyRidge(alpha=spec.alpha).fit([r.features for r in rows], y)
        current = [
            features[c].iloc[-1][list(spec.factor_names)].to_numpy(dtype=float) for c in universe
        ]
        scores = model.predict(current)
        predictions[spec.horizon] = tuple(
            ModelPrediction(spec.horizon, provider.cutoff, c, float(v))
            for c, v in zip(universe, scores)
        )
        reports[str(int(spec.horizon))] = {
            **stats,
            "coefficients": dict(zip(spec.factor_names, model.coef_.tolist())),
            "intercept": model.intercept_,
            "raw_predictions": dict(zip(universe, scores.tolist())),
        }
    fused = fuse_predictions(predictions, config=config, industry_universe=universe)
    return {
        "artifact": "MODEL_READINESS_REFERENCE",
        "formal_signal": False,
        "formal_epoch_created": False,
        "intent_created": False,
        "historical_available_at": None,
        "historical_membership_pit_proven": False,
        "reference_date": str(provider.cutoff),
        "universe": list(universe),
        "horizons": reports,
        "horizon_zscores": {
            str(int(h)): {p.industry_code: p.prediction for p in rows}
            for h, rows in fused.horizon_zscores
        },
        "ranking": [
            {"rank": r.rank, "industry_code": r.industry_code, "score": r.score}
            for r in fused.rankings
        ],
    }

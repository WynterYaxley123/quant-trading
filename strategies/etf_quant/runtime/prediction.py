"""Current-snapshot warmup only; no historical performance or walk-forward."""
from datetime import datetime

import numpy as np
import pandas as pd

from ..domain import Horizon, StrategyConfig, TradingCalendar
from ..factors import compute_close_factors
from ..models import TrainingObservation, fit_horizon, predict_industries
from ..models.fusion import fuse_predictions
from .storage import GateError


def current_predictions(series, provider, *, signal_at: datetime, config=None):
    config = StrategyConfig() if config is None else config
    if signal_at.date() != provider.cutoff or signal_at < provider.created_at:
        raise GateError("MODEL_SNAPSHOT_AVAILABILITY_BLOCKER")
    days = tuple(d for d in provider.sessions if d <= provider.cutoff)
    calendar = TradingCalendar(days)
    signal_i = len(days) - 1
    features = {code: compute_close_factors(series.closes[code]) for code in series.universe}
    models, predictions = {}, {}
    for spec in config.horizons:
        h = int(spec.horizon)
        if signal_i < h:
            raise GateError("MODEL_WARMUP_INCOMPLETE")
        cutoff = days[signal_i - h]
        start = (pd.Timestamp(cutoff) - pd.DateOffset(months=6)).date()
        observations = []
        for i, day in enumerate(days):
            if not start <= day <= cutoff:
                continue
            end = days[i + h]  # structurally mature before reading any targets
            start_values = series.closes.loc[pd.Timestamp(day)]
            end_values = series.closes.loc[pd.Timestamp(end)]
            cross_section = [features[c].loc[pd.Timestamp(day), list(spec.factor_names)].to_numpy(dtype=float)
                             for c in series.universe]
            if not (np.isfinite(start_values).all() and np.isfinite(end_values).all()
                    and all(np.isfinite(v).all() for v in cross_section)):
                continue  # whole date rejected, never partial cross-sectional centering
            for code, x in zip(series.universe, cross_section):
                observations.append(TrainingObservation(spec.horizon, code, day, end,
                    provider.created_at, spec.factor_names, tuple(map(float, x)),
                    float(end_values[code] / start_values[code] - 1)))
        # available_at here is the actual CURRENT snapshot observation time,
        # not a claimed historical publication timestamp. Source timing stays
        # UNKNOWN/null in the export, Source C audit and public model metadata.
        try:
            model = fit_horizon(spec, observations, calendar=calendar, signal_at=signal_at,
                                industry_universe=series.universe)
            current = {c: tuple(features[c].iloc[-1][list(spec.factor_names)]) for c in series.universe}
            predictions[spec.horizon] = predict_industries(model, current, factor_names=spec.factor_names,
                                                         signal_date=provider.cutoff)
        except (ValueError, FloatingPointError) as error:
            raise GateError("MODEL_WARMUP_INCOMPLETE", {"horizon": h}) from error
        models[spec.horizon] = model
    return models, predictions, fuse_predictions(predictions, config=config, industry_universe=series.universe)

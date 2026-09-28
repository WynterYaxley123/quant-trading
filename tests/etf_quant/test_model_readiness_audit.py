"""Synthetic tests only: retrospective fit must keep the full cross-section."""
from datetime import date
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategies.etf_quant.domain import StrategyConfig


PATH = Path(__file__).resolve().parents[2] / "scripts" / "audit_etf_quant_models.py"
SPEC = importlib.util.spec_from_file_location("etf_quant_model_audit", PATH)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture():
    spec = StrategyConfig().horizons[0]
    sessions = tuple(pd.bdate_range("2025-08-01", periods=200))
    universe = tuple(f"{i:04d}" for i in range(5))
    rows = []
    for t, day in enumerate(sessions):
        for i, code in enumerate(universe):
            rows.append({"trade_date": day, "industry_code": code,
                         "source_c_close": 100.0 + t + i * .1 + .01 * t * i,
                         **{f: float(i + t / 100 + j / 10) for j, f in enumerate(spec.factor_names)}})
    frame = pd.DataFrame(rows).set_index(["trade_date", "industry_code"]).sort_index()
    cutoff = sessions[-1 - int(spec.horizon)]
    start = cutoff - pd.DateOffset(months=6)
    days = [d for d in sessions if start <= d <= cutoff]
    report = {"label_cutoff": cutoff.date().isoformat(), "window_start": start.date().isoformat(),
              "candidate_training_dates": len(days),
              "training_dates_diagnostic_common_universe": len(days)}
    return frame, sessions, universe, spec, report


def test_retro_fit_uses_frozen_dimensions_and_full_dates():
    frame, sessions, universe, spec, report = fixture()
    result, predictions = audit.fit_retrospective_horizon(frame, sessions, universe, spec, report)
    assert result["training_dates"] == report["candidate_training_dates"]
    assert result["training_observations"] == len(universe) * result["training_dates"]
    assert result["feature_dimensions"] == 5 and len(predictions) == len(universe)
    assert np.isfinite(list(result["coefficients"].values())).all()
    assert result["formal_available_at_hypothetical_signal"] is None


def test_partial_cross_section_cannot_be_counted_as_full_training_day():
    frame, sessions, universe, spec, report = fixture()
    day = sessions[-1 - int(spec.horizon)]
    frame.loc[(day, universe[0]), spec.factor_names[0]] = np.nan
    with pytest.raises(ValueError, match="READINESS_TRAINING_DATE_MISMATCH"):
        audit.fit_retrospective_horizon(frame, sessions, universe, spec, report)


def test_model_evidence_path_must_be_external(tmp_path):
    (tmp_path / ".git").mkdir()
    path = tmp_path / "not-real.csv"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="EXTERNAL_EVIDENCE_PATH_REQUIRED"):
        audit._external(path, directory=False)

"""Expose actual frozen raw/z/fused model outputs without the ETF product layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from strategies.etf_quant.config import FUSION_WEIGHTS, HORIZON_FACTORS
from strategies.etf_quant.domain import Horizon, HorizonModelSpec
from strategies.etf_quant.runtime.prediction import current_predictions
from strategies.etf_quant_v2.model import FrozenSpecification, predict_forecast

from .registry import ROOT, verify_model


def ranks(scores: dict[str, float]) -> dict[str, int]:
    return {code: i + 1 for i, code in enumerate(sorted(scores, key=lambda c: (-scores[c], c)))}


@dataclass(frozen=True)
class ForecastConfig:
    """Only the frozen numerical contract; no execution configuration."""

    horizons: tuple[HorizonModelSpec, ...] = tuple(
        HorizonModelSpec(Horizon(h), names) for h, names in HORIZON_FACTORS
    )
    fusion_weights: tuple[tuple[int, float], ...] = FUSION_WEIGHTS
    top_k: int = 5


def v1_prediction(series: Any, provider: Any, signal_at: datetime) -> dict[str, Any]:
    config = ForecastConfig()
    models, predictions, fused = current_predictions(
        series, provider, signal_at=signal_at, config=config
    )
    components = {
        str(int(h)): {
            p.industry_code: {
                "raw_prediction": p.prediction,
                "cross_section_zscore": z.prediction,
            }
            for p, z in zip(predictions[h], dict(fused.horizon_zscores)[h], strict=True)
        }
        for h in predictions
    }
    return {
        "rankings": [(r.industry_code, r.score) for r in fused.rankings],
        "components": components,
        "models": [
            {"horizon": int(h), "alpha": next(s.alpha for s in config.horizons if s.horizon == h)}
            for h in models
        ],
    }


def v2_specification(root: Path = ROOT) -> FrozenSpecification:
    candidate = json.loads((root / "strategies/etf_quant_v2/config/candidate.json").read_bytes())
    selected = candidate["specification"]
    # The consumed OOS period's already-opened raw facts may enter mature fitting.
    # No result/performance artifact is read. The immutable candidate remains unchanged.
    return FrozenSpecification(
        selected["identifier"],
        tuple(selected["horizons"]),
        tuple(selected["fusion"]),
        selected["alpha"],
        selected["training_months"],
        selected["scaling"],
        candidate["candidate_sha256"],
        datetime.fromisoformat(candidate["frozen_at"]),
        date.fromisoformat(candidate["final_oos_start"]),
        date.fromisoformat(candidate["final_oos_end"]),
        True,
        final_oos_authorized=True,
    )


def prediction(family: dict[str, Any], inputs: dict[str, Any], now: datetime) -> dict[str, Any]:
    verify_model(family)
    if family["generation"] == 1:
        result = v1_prediction(inputs["series"], inputs["provider"], now)
    else:
        result = predict_forecast(
            v2_specification(),
            inputs["observations"],
            inputs["current_factors"],
            calendar=inputs["calendar"],
            signal_at=now,
            snapshot_available_at=inputs["available_at"],
            finalized=True,
        )
    rows = []
    component_ranks = {
        h: ranks({c: v["raw_prediction"] for c, v in scores.items()})
        for h, scores in result["components"].items()
    }
    for rank, (code, score) in enumerate(result["rankings"], 1):
        rows.append(
            {
                "industry_code": code,
                "industry_name": inputs["names"][code],
                "fused_score": score,
                "fused_rank": rank,
                "horizons": {
                    h: {**scores[code], "rank": component_ranks[h][code]}
                    for h, scores in result["components"].items()
                },
            }
        )
    if (
        len(rows) != family["model_universe_size"]
        or sorted(r["industry_code"] for r in rows) != family["industry_codes"]
    ):
        raise ValueError("FULL_FROZEN_UNIVERSE_REQUIRED")
    return {"cross_section": rows, "models": result["models"]}

"""Data-free SWL2 forecast/maturity demonstration; all values and clocks synthetic."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from research.swl1_ridge_v1.protocol import Spec, exact_targets, fit_predict
from strategies.etf_quant.runtime.industry import IndustrySeries
from strategies.etf_quant.runtime.storage import digest, json_bytes
from strategies.etf_quant_v2.facts import ForwardFacts, factors_from_closes
from strategies.swl2_ridge.adapter import prediction
from strategies.swl2_ridge.engine import SHANGHAI, mature, publish, view
from strategies.swl2_ridge.facts import SERIES_TYPE
from strategies.swl2_ridge.registry import families


def run_demo() -> dict[str, Any]:
    """Exercise real frozen fits and temporary ledger without any external data."""
    days = tuple(d.date() for d in pd.bdate_range("2025-01-02", periods=900))
    signal = datetime.combine(days[700], datetime.min.time().replace(hour=16), SHANGHAI)
    results = []
    with tempfile.TemporaryDirectory(prefix="swl2-synthetic-") as temporary:
        for family in families():
            codes = family["industry_codes"]
            rng = np.random.default_rng(501 + family["generation"])
            frame = pd.DataFrame(
                100 * np.exp(np.cumsum(rng.normal(0, 0.008, (900, len(codes))), axis=0)),
                index=pd.DatetimeIndex(days),
                columns=codes,
            )
            prefix = frame.iloc[:701]
            inputs: dict[str, Any] = {
                "calendar": days,
                "closes": prefix,
                "cutoff": signal.date(),
                "available_at": signal,
                "segments": None,
                "names": {c: f"Synthetic {c}" for c in codes},
                "taxonomy_identity": family["taxonomy_identity"],
                "provenance": {
                    "data_source": "SYNTHETIC_ONLY",
                    "source_commit": "a" * 40,
                    "snapshot_sha256": "b" * 64,
                    "data_cutoff": str(signal.date()),
                    "available_at": signal.isoformat(),
                    "realized_series_type": SERIES_TYPE,
                    "historical_membership": "SYNTHETIC",
                    "signal_levels_hash": digest(json_bytes(prefix.iloc[-1].to_dict())),
                },
            }
            if family["generation"] == 1:
                inputs.update(
                    series=IndustrySeries(prefix, (), tuple(codes)),
                    provider=SimpleNamespace(
                        cutoff=signal.date(),
                        created_at=signal,
                        model_input_contract={"industries": codes},
                    ),
                )
            else:
                forward = ForwardFacts(
                    days[:701],
                    tuple(codes),
                    factors_from_closes(prefix.to_numpy(), days[:701]),
                    prefix.to_numpy(),
                    np.zeros(prefix.shape, dtype=np.int64),
                    signal,
                    "c" * 64,
                    {},
                )
                observations, current = forward.model_inputs(signal.date())
                inputs.update(observations=observations, current_factors=current)
            binding = {
                "schema_version": 1,
                "family_id": family["family_id"],
                "source_commit": "d" * 40,
                "merge_commit": "e" * 40,
                "merge_at": (signal - timedelta(days=4)).isoformat(),
                "freeze_at": (signal - timedelta(days=1)).isoformat(),
                "model_contract_hash": family["model_contract_hash"],
            }
            namespace = Path(temporary) / "industry-forecast" / family["family_id"]
            predicted = prediction(family, inputs, signal)
            publish(namespace, family, binding, inputs, predicted, signal)
            before = view(namespace, family)
            final = datetime.combine(days[820], datetime.min.time().replace(hour=16), SHANGHAI)
            inputs.update(closes=frame.iloc[:821], cutoff=final.date(), available_at=final)
            inputs["provenance"].update(
                data_cutoff=str(final.date()), available_at=final.isoformat()
            )
            evaluations = mature(namespace, inputs, final)
            assert len(evaluations) == 3
            assert before["metrics"][0]["mean_rank_ic"] is None
            results.append(
                {
                    "family": family["display_name"],
                    "industry_count": len(predicted["cross_section"]),
                    "synthetic_matured_horizons": [e["horizon"] for e in evaluations],
                }
            )
    # Independent synthetic Level-1 fit: no real candidate/result, factual lake or publication.
    synthetic_days = pd.bdate_range("2020-01-02", periods=800).strftime("%Y-%m-%d").tolist()
    generator = np.random.default_rng(1101)
    synthetic_returns = generator.normal(0, 0.005, (800, 12))
    synthetic_features = generator.normal(0, 1, (800, 12, 19))
    for horizon in (10, 40, 120):
        values, metadata = fit_predict(
            synthetic_features,
            exact_targets(synthetic_returns, horizon),
            synthetic_days,
            650,
            horizon,
            Spec(1, 12, "A"),
        )
        assert (
            len(values) == 12 and metadata["mature_label_cutoff"] == synthetic_days[650 - horizon]
        )
    results.append(
        {
            "family": "SWL1-Ridge-V1",
            "mode": "SYNTHETIC_ONLY",
            "industry_count": 12,
            "synthetic_fit_horizons": [10, 40, 120],
            "formal_publications": 0,
        }
    )
    return {
        "mode": "SYNTHETIC_ONLY",
        "families": results,
        "live_events_created": 0,
        "etf_events_created": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), allow_nan=False))

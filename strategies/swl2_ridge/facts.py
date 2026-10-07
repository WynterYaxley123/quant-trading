"""Read admitted Source-C stock facts; neither ETF mapping nor product inputs are read."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategies.etf_quant.domain.industry_level import CLASSIFICATION_VERSION, load_taxonomy
from strategies.etf_quant.runtime.exports import ExportProvider
from strategies.etf_quant.runtime.industry import build_industry_series
from strategies.etf_quant.runtime.model_inputs import bind_model_inputs
from strategies.etf_quant.runtime.storage import digest
from strategies.etf_quant_v2.facts import append_snapshot
from strategies.etf_quant_v2.refresh import PIN

SERIES_TYPE = "RECONSTRUCTED_SWL2_EQUAL_WEIGHT"
TARGET = "SAME_DATE_CROSS_SECTION_EXCESS_INDUSTRY_RETURN"


def prefix_hash(inputs: dict[str, Any], through: date) -> str:
    """Bind every consumed industry factual level, including gaps and segment identity."""
    import hashlib
    import json

    frame: pd.DataFrame = inputs["closes"].loc[: pd.Timestamp(through)]
    result = hashlib.sha256(
        json.dumps(
            [list(map(str, pd.DatetimeIndex(frame.index).date)), list(frame.columns)]
        ).encode()
    )
    result.update(np.ascontiguousarray(frame.to_numpy(dtype=float)).tobytes())
    if inputs["segments"] is not None:
        result.update(np.ascontiguousarray(inputs["segments"][: len(frame)]).tobytes())
    return result.hexdigest()


def external_read(path: str) -> Path:
    root = Path(path)
    if not root.is_absolute():
        raise ValueError("EXPLICIT_EXTERNAL_FACTS_REQUIRED")
    root = root.resolve(strict=True)
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("EXPLICIT_EXTERNAL_FACTS_REQUIRED")
    return root


def load(family: dict[str, Any], config: dict[str, Any], now: datetime) -> dict[str, Any]:
    snapshot = external_read(config["snapshot"])
    provider = ExportProvider(
        snapshot,
        expected_identity={"source_commit": PIN, "source_identity": "CNEQUITY_LOCAL_LAKE_V1"},
        now=now,
        industry_only=True,
    )
    taxonomy = load_taxonomy()
    provenance = {
        "data_source": "CNEQUITY_LOCAL_LAKE_V1",
        "source_commit": PIN,
        "snapshot_sha256": digest((snapshot / "manifest.json").read_bytes()),
        "data_cutoff": str(provider.cutoff),
        "available_at": provider.created_at.isoformat(),
        "realized_series_type": SERIES_TYPE,
        "historical_membership": "RECONSTRUCTED",
        "authorization": "EXISTING_ADMITTED_LOCAL_RESEARCH_USE_NO_REDISTRIBUTION_RIGHTS_GRANTED",
    }
    if family["generation"] == 1:
        contract = bind_model_inputs(provider, external_read(config["model_reference_snapshot"]))
        series = build_industry_series(provider, classification_version=CLASSIFICATION_VERSION)
        industries = tuple(contract["industries"])
        if sorted(industries) != family["industry_codes"]:
            raise ValueError("FROZEN_MODEL_UNIVERSE_MISMATCH")
        return {
            "provider": provider,
            "series": series,
            "calendar": provider.sessions,
            "closes": series.closes.loc[:, list(industries)],
            "segments": None,
            "names": {c: taxonomy.name_of(c) for c in industries},
            "available_at": provider.created_at,
            "cutoff": provider.cutoff,
            "provenance": provenance,
            "taxonomy_identity": taxonomy.identity,
        }
    candidate_hash = family["frozen_model_reference"]["warmup_panel_sha256"]
    warmup = external_read(config["warmup"])
    if (
        digest((warmup / "panel.json").read_bytes())
        != family["frozen_model_reference"]["warmup_metadata_sha256"]
    ):
        raise ValueError("FROZEN_WARMUP_METADATA_REQUIRED")
    forward = append_snapshot(
        warmup,
        snapshot,
        expected_panel_sha256=candidate_hash,
        industry_only=True,
    )
    observations, current = forward.model_inputs(provider.cutoff)
    if sorted(forward.industries) != family["industry_codes"] or set(current) != set(
        forward.industries
    ):
        raise ValueError("FULL_CURRENT_INDUSTRY_CROSS_SECTION_REQUIRED")
    return {
        "observations": observations,
        "current_factors": current,
        "calendar": provider.sessions,
        "closes": pd.DataFrame(
            forward.closes, index=pd.DatetimeIndex(forward.dates), columns=forward.industries
        ),
        "segments": forward.segments,
        "names": {c: taxonomy.name_of(c) for c in forward.industries},
        "available_at": forward.observed_at,
        "cutoff": provider.cutoff,
        "provenance": provenance,
        "taxonomy_identity": taxonomy.identity,
    }


def outcomes(
    inputs: dict[str, Any], signal: date, maturity: date, codes: list[str], now: datetime
) -> tuple[dict[str, float], list[dict[str, Any]]] | None:
    if inputs["available_at"] > now or maturity > inputs["cutoff"]:
        return None
    frame = inputs["closes"]
    days = tuple(d.date() for d in frame.index)
    if signal not in days or maturity not in days or not set(codes).issubset(frame.columns):
        return None
    start, end = days.index(signal), days.index(maturity)
    required = frame.loc[pd.Timestamp(signal) : pd.Timestamp(maturity), codes].to_numpy(dtype=float)
    # Exact calendar adjacency and every factual point are required. No gap bridging.
    calendar = tuple(d for d in inputs["calendar"] if signal <= d <= maturity)
    if (
        days[start : end + 1] != calendar
        or not np.isfinite(required).all()
        or (required <= 0).any()
    ):
        return None
    segments = inputs["segments"]
    if segments is not None:
        indices = [list(frame.columns).index(c) for c in codes]
        if not (segments[start : end + 1, indices] == segments[start, indices]).all():
            return None
    returns = {c: float(v) for c, v in zip(codes, required[-1] / required[0] - 1, strict=True)}
    trends = [
        {
            "date": str(day),
            "values": {c: float(v) for c, v in zip(codes, row / required[0], strict=True)},
        }
        for day, row in zip(calendar, required, strict=True)
    ]
    return returns, trends

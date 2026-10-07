"""Forward-only publication and exact trading-session maturity; no product pipeline."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from strategies.etf_quant.runtime.storage import digest, json_bytes

from . import ledger
from .facts import TARGET, outcomes, prefix_hash
from .metrics import aggregate, evaluate

SHANGHAI = ZoneInfo("Asia/Shanghai")
HORIZONS = (10, 40, 120)


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("FORECAST_TIMEZONE_REQUIRED")
    return result


def first_session(binding: dict[str, Any], calendar: tuple[date, ...]) -> str | None:
    boundary = max(timestamp(binding["merge_at"]), timestamp(binding["freeze_at"]))
    return next((str(d) for d in calendar if d > boundary.astimezone(SHANGHAI).date()), None)


def publication_gate(binding: dict[str, Any], inputs: dict[str, Any], now: datetime) -> date:
    if now.tzinfo is None:
        raise ValueError("FORECAST_TIMEZONE_REQUIRED")
    day = now.astimezone(SHANGHAI).date()
    calendar = tuple(inputs["calendar"])
    if calendar != tuple(sorted(set(calendar))) or day not in calendar:
        raise ValueError("OFFICIAL_TRADING_CALENDAR_REQUIRED")
    first = first_session(binding, calendar)
    if first is None or day < date.fromisoformat(first):
        raise ValueError("PRE_TRANSITION_FORWARD_DATE_DENIED")
    if inputs["cutoff"] != day:
        raise ValueError("RETROSPECTIVE_OR_FUTURE_FORECAST_DENIED")
    if inputs["available_at"].tzinfo is None or inputs["available_at"] > now:
        raise ValueError("FUTURE_FACTUAL_ACCESS_DENIED")
    if (
        inputs["available_at"].astimezone(SHANGHAI).date() != day
        or inputs["available_at"].astimezone(SHANGHAI).time() < time(15, 5)
        or now.astimezone(SHANGHAI).time() < time(15, 5)
    ):
        raise ValueError("CURRENT_FINALIZED_FACTS_REQUIRED")
    return day


def event_metadata(binding: dict[str, Any]) -> dict[str, Any]:
    return {k: binding[k] for k in ("family_id", "source_commit", "model_contract_hash")}


def publish(
    root: Path,
    family: dict[str, Any],
    binding: dict[str, Any],
    inputs: dict[str, Any],
    predicted: dict[str, Any],
    now: datetime,
) -> str:
    day = publication_gate(binding, inputs, now)
    if (
        binding["family_id"] != family["family_id"]
        or binding["model_contract_hash"] != family["model_contract_hash"]
    ):
        raise ValueError("MODEL_OR_SOURCE_BINDING_MISMATCH")
    rows = predicted["cross_section"]
    expected = set(family["industry_codes"])
    if (
        len(rows) != len(expected)
        or {r["industry_code"] for r in rows} != expected
        or inputs["taxonomy_identity"] != family["taxonomy_identity"]
    ):
        raise ValueError("FULL_FROZEN_UNIVERSE_REQUIRED")
    body = {
        "schema_version": 1,
        "kind": "FORECAST",
        **event_metadata(binding),
        "display_name": family["display_name"],
        "legacy_identity": family["legacy_identity"],
        "model_generation": family["generation"],
        "signal_date": str(day),
        "published_at": now.isoformat(),
        "data_cutoff": str(inputs["cutoff"]),
        "taxonomy_identity": inputs["taxonomy_identity"],
        "industry_count": len(rows),
        "taxonomy_universe_size": family["taxonomy_universe_size"],
        "model_universe_size": family["model_universe_size"],
        "model_universe_hash": family["model_universe_hash"],
        "forecast_row_count": len(rows),
        "transition_binding": dict(binding),
        "realized_series_type": inputs["provenance"]["realized_series_type"],
        "horizons": list(HORIZONS),
        "target_contract": TARGET,
        "provenance": {**inputs["provenance"], "factual_prefix_hash": prefix_hash(inputs, day)},
        **predicted,
    }
    return ledger.append(root, binding, "forecast_" + str(day), body)


def mature(root: Path, inputs: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    state = ledger.read(root)
    if state is None:
        return []
    binding, events = state["binding"], state["events"]
    evaluations = [e["body"] for e in events if e["body"]["kind"] == "EVALUATION"]
    known = {(e["signal_date"], e["horizon"]) for e in evaluations}
    sessions = tuple(inputs["calendar"])
    if (
        sessions != tuple(sorted(set(sessions)))
        or inputs["available_at"].tzinfo is None
        or inputs["available_at"] > now
    ):
        raise ValueError("FINALIZED_EVALUATION_CALENDAR_REQUIRED")
    for evaluation in evaluations:
        if evaluation["provenance"].get("factual_prefix_hash") != prefix_hash(
            inputs, date.fromisoformat(evaluation["maturity_date"])
        ):
            raise ValueError("PUBLISHED_EVALUATION_FACTS_REVISED")
    for event in events:
        forecast = event["body"]
        if forecast["kind"] != "FORECAST":
            continue
        signal = date.fromisoformat(forecast["signal_date"])
        if forecast["provenance"]["factual_prefix_hash"] != prefix_hash(inputs, signal):
            raise ValueError("PUBLISHED_SIGNAL_FACTS_REVISED")
        if signal not in sessions or forecast["taxonomy_identity"] != inputs["taxonomy_identity"]:
            raise ValueError("FORECAST_TAXONOMY_OR_CALENDAR_MISMATCH")
        for horizon in HORIZONS:
            index = sessions.index(signal) + horizon
            if (str(signal), horizon) in known or index >= len(sessions):
                continue
            maturity = sessions[index]
            if maturity > now.astimezone(SHANGHAI).date() or maturity > inputs["cutoff"]:
                continue  # Do not access outcome values until the exact session matures.
            codes = sorted(r["industry_code"] for r in forecast["cross_section"])
            result = outcomes(inputs, signal, maturity, codes, now)
            if result is None:
                continue
            raw, trends = result
            # Bind the original signal factual levels against later revisions.
            original = forecast["provenance"].get("signal_levels_hash")
            current = inputs["closes"].loc[str(signal), codes].to_dict()
            if original != digest(json_bytes(current)):
                raise ValueError("PUBLISHED_SIGNAL_FACTS_REVISED")
            metrics = evaluate(forecast["cross_section"], raw, horizon)
            selected = set(metrics["predicted_top5"]) | {
                r["industry_code"] for r in forecast["cross_section"][:5]
            }
            diagnostic = [
                {
                    "date": r["date"],
                    "values": {c: v for c, v in r["values"].items() if c in selected},
                    "universe_equal_weight": sum(r["values"].values()) / len(codes),
                }
                for r in trends
            ]
            body = {
                "schema_version": 1,
                "kind": "EVALUATION",
                **event_metadata(binding),
                "signal_date": str(signal),
                "horizon": horizon,
                "maturity_date": str(maturity),
                "maturity_sessions": list(map(str, sessions[sessions.index(signal) : index + 1])),
                "evaluated_at": now.isoformat(),
                "forecast_hash": event["body_hash"],
                "taxonomy_identity": forecast["taxonomy_identity"],
                "target_contract": TARGET,
                "realized_series_type": inputs["provenance"]["realized_series_type"],
                "target_cross_section_hash": digest(json_bytes(raw)),
                "provenance": {
                    **inputs["provenance"],
                    "factual_prefix_hash": prefix_hash(inputs, maturity),
                },
                "metrics": metrics,
                "visual_trend_diagnostic": {
                    "type": "NORMALIZED_RESEARCH_INDEX",
                    "start": 1.0,
                    "label": "NON_TRADABLE_RESEARCH_DIAGNOSTIC",
                    "points": diagnostic,
                },
            }
            status = ledger.append(root, binding, f"evaluation_{signal}_{horizon}", body)
            if status == "APPENDED":
                evaluations.append(body)
    return evaluations


def view(root: Path, family: dict[str, Any]) -> dict[str, Any]:
    state = ledger.read(root)
    events = [e["body"] for e in state["events"]] if state else []
    forecasts = [e for e in events if e["kind"] == "FORECAST"]
    evaluations = [e for e in events if e["kind"] == "EVALUATION"]
    return {
        "family": family,
        "status": "FORWARD_FORECAST" if forecasts else "NO_FORWARD_FORECASTS",
        "current": forecasts[-1] if forecasts else None,
        "history": forecasts,
        "evaluations": evaluations,
        "metrics": [aggregate(evaluations, h) for h in HORIZONS],
    }

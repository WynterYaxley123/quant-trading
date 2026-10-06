"""Docker adapter for the shared one-shot transport's ETF_QUANT_V2 version."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from strategies.etf_quant.domain import TradingCalendar
from strategies.etf_quant.portfolio.policy import BenchmarkExposureVector
from strategies.etf_quant.runtime.storage import atomic_bytes, external_root, json_bytes
from strategies.etf_quant_v2.facts import append_snapshot, load_liquidity
from strategies.etf_quant_v2.mapping import candidate_pools
from strategies.etf_quant_v2.refresh import checksum, verified_snapshot
from strategies.etf_quant_v2.release import load_release
from strategies.etf_quant_v2.runtime import SHANGHAI, FrozenSpecification, prepare_signal
from strategies.etf_quant_v2.shadow import cycle, load_state, public_view, temporal_gate

REPO = Path(__file__).resolve().parents[2]


def next_signal_session(
    sessions: tuple[date, ...], now: datetime, available_at: datetime, state: dict[str, Any] | None
) -> str | None:
    """A waiting current T stays eligible until it is committed; never skip it."""
    today = now.astimezone(SHANGHAI).date()
    freeze = available_at.astimezone(SHANGHAI).date()
    if state and not state.get("signals"):
        raise ValueError("V2_EMPTY_SIGNAL_STATE_DENIED")
    last = date.fromisoformat(state["signals"][-1]["signal_date"]) if state else date.min
    eligible = [d for d in sessions[:-1] if d >= today and d > freeze and d > last]
    return str(eligible[0]) if eligible else None


def run_once(config: dict[str, Any], code_commit: str) -> dict[str, Any]:
    from strategies.swl2_ridge.retirement import guard_legacy_write

    guard_legacy_write(Path(config["runtime_root"]))

    release, candidate, registry = load_release(REPO)
    now = datetime.now(timezone.utc)
    snapshot = Path(config["snapshot"])
    manifest = verified_snapshot(snapshot)
    calendar = pl.read_csv(snapshot / "trading_calendar.csv", try_parse_dates=True)
    sessions = tuple(calendar.filter(pl.col("is_trading"))["trade_date"].to_list())
    runtime = Path(config["runtime_root"])
    state = load_state(runtime) if runtime.exists() else None
    cutoff = date.fromisoformat(manifest["data_cutoff"])
    gate = temporal_gate(now, sessions, cutoff, datetime.fromisoformat(release["available_at"]))
    if gate != "ELIGIBLE":
        view = public_view(
            state, release, latest_data_date=str(cutoff), armed=True, waiting_reason=gate
        )
        view["latest_data_time"] = manifest["created_at"]
        view["next_eligible_signal_date"] = next_signal_session(
            sessions, now, datetime.fromisoformat(release["available_at"]), state
        )
        result = {
            "status": gate,
            "strategy_version": "ETF_QUANT_V2",
            "shadow_runtime_armed": True,
            "shadow_start_gate": "ARMED_FOR_NEXT_ELIGIBLE_T",
            "data_cutoff": str(cutoff),
            "code_commit": code_commit,
            "view": view,
        }
    else:
        facts = append_snapshot(
            Path(config["warmup_panel"]),
            snapshot,
            expected_panel_sha256=release["warmup_panel_sha256"],
        )
        if (
            state
            and state["signals"]
            and facts.prefix_hash(date.fromisoformat(state["signals"][-1]["signal_date"]))
            != state["factual_prefix_sha256"]
        ):
            raise ValueError("CONSUMED_FACTUAL_PREFIX_REVISION_DENIED")
        specification = candidate["specification"]
        observations, current = facts.model_inputs(
            cutoff,
            training_months=specification["training_months"],
            horizons=tuple(specification["horizons"]),
        )
        liquidity = load_liquidity(Path(config["liquidity_root"]), cutoff)
        vector_path = Path(config["exposure_vectors"])
        if checksum(vector_path) != registry["exposure_vectors_sha256"]:
            raise ValueError("V2_EXPOSURE_VECTOR_IDENTITY_ERROR")
        vectors = {
            code: BenchmarkExposureVector(**row)
            for code, row in json.loads(vector_path.read_bytes()).items()
        }
        selected = candidate["specification"]
        spec = FrozenSpecification(
            selected["identifier"],
            tuple(selected["horizons"]),
            tuple(selected["fusion"]),
            selected["alpha"],
            selected["training_months"],
            selected["scaling"],
            candidate["candidate_sha256"],
            datetime.fromisoformat(release["available_at"]),
            date.fromisoformat(candidate["final_oos_start"]),
            date.fromisoformat(candidate["final_oos_end"]),
            release["historical_classification"] != "FAIL",
            final_oos_authorized=True,
        )
        plan = prepare_signal(
            spec,
            observations,
            current,
            calendar=tuple(sorted(set(facts.dates) | set(sessions))),
            signal_at=now,
            snapshot_available_at=facts.observed_at,
            finalized=True,
            mapping_pools=candidate_pools(registry, liquidity, now.astimezone(SHANGHAI)),
            exposure_vectors=vectors,
            mapping_available_at=datetime.fromisoformat(registry["available_at"]),
            allow_unvalidated_research=release["historical_classification"] == "FAIL",
        )
        required = {r["etf_code"] for r in plan["allocation"]["executed"]}
        if state:
            required.update(p["asset_id"] for p in state["portfolio"]["positions"])
            if state["pending"]:
                required.update(state["pending"]["weights"])
        opens, closes = {}, {}
        for symbol in sorted(required):
            bars_path = Path(config["liquidity_root"]) / str(cutoff) / (symbol + ".parquet")
            if not bars_path.exists():
                raise ValueError("CURRENT_HELD_OR_SELECTED_RAW_BARS_REQUIRED")
            receipt = json.loads(bars_path.with_suffix(".json").read_bytes())
            if (
                receipt["data_cutoff"] != str(cutoff)
                or checksum(bars_path) != receipt["bars_sha256"]
            ):
                raise ValueError("EXECUTION_BAR_RECEIPT_IDENTITY_ERROR")
            bar = pl.read_parquet(bars_path).filter(pl.col("trade_date") == cutoff)
            if bar.height != 1:
                raise ValueError("UNIQUE_FINALIZED_EXECUTION_BAR_REQUIRED")
            row = bar.to_dicts()[0]
            opens[symbol], closes[symbol] = Decimal(str(row["open"])), Decimal(str(row["close"]))
        result = cycle(
            runtime,
            release,
            plan,
            calendar=TradingCalendar(tuple(sorted(set(facts.dates) | set(sessions)))),
            now=now,
            snapshot_observed_at=facts.observed_at,
            code_commit=code_commit,
            registry_entries=registry["entries"],
            raw_opens=opens,
            raw_closes=closes,
            benchmark_close=facts.benchmark_close.get(str(cutoff)),
            factual_prefix_sha256=facts.prefix_hash(cutoff),
        )
        result.update(
            strategy_version="ETF_QUANT_V2",
            shadow_runtime_armed=True,
            data_cutoff=str(cutoff),
            code_commit=code_commit,
        )
    control = external_root(Path(config["control_root"]))
    atomic_bytes(control / "latest_observation.json", json_bytes(result))
    return result


def main():
    print(json.dumps({"status": "SWL2_ETF_PRODUCTIZATION_RETIRED", "role": "LEGACY_READ_ONLY"}))
    return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_bytes())
    if config.get("strategy_version") != "ETF_QUANT_V2":
        raise ValueError("EXPLICIT_V2_STRATEGY_VERSION_REQUIRED")
    print(json.dumps(run_once(config, args.commit), allow_nan=False))


if __name__ == "__main__":
    main()

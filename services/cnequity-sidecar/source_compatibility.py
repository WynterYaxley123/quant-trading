"""Owned compatibility for tip identities and an evidenced catalogue correction.

No vendor file change, no price fallback, no direct curated write. The pinned
compact/publish chain receives a corrected COW merge input; prior revisions stay
immutable. Current identity is never represented as historical PIT evidence.
"""
import csv
from datetime import date, datetime, timezone
import json
from pathlib import Path

from finalization import checksum
from strategies.etf_quant.runtime.storage import GateError, atomic_bytes, json_bytes


def correction_symbols(rows, active, baseline):
    return {r["symbol"] for r in rows if r["symbol"].endswith(".BJ")
            and r["symbol"] in active and r["symbol"] in baseline
            and r.get("delist_date") == date(2026, 9, 28)
            and not baseline[r["symbol"]].get("delist_date")}


def enable(cfg, settings):
    import polars as pl
    from cnequity.domain.market_time import shanghai_today
    from cnequity.adapters.bse.trading_status import board_names, read_board, _parse_date
    from cnequity.steps.common import is_trading_day
    from cnequity.steps.common import load_curated_instruments
    from cnequity.steps import finalize
    import bse_tip_bridge
    control = Path(settings["paths"]["export_root"]).parent
    config = json.loads((control / "config.json").read_bytes())
    baseline_root = Path(config["snapshot"])
    manifest = json.loads((baseline_root / "manifest.json").read_bytes())
    leaf = baseline_root / "instruments.csv"
    if checksum(leaf) != manifest["files"]["instruments.csv"]:
        raise GateError("BJ_BASELINE_HASH_BLOCKER")
    with leaf.open(encoding="utf-8", newline="") as f:
        baseline = {r["symbol"]: r for r in csv.DictReader(f)}
    raw, _total = read_board(config=cfg)
    quoted_sessions = [_parse_date(r.get("hqjsrq")) for r in raw]
    quoted_sessions = [d for d in quoted_sessions if d is not None]
    board_day = max(quoted_sessions) if quoted_sessions else None
    if board_day is None or board_day > shanghai_today() or not is_trading_day(cfg, board_day):
        raise ProviderUnavailable("BSE_SNAPSHOT_SESSION_UNAVAILABLE")
    active, complete = board_names(board_day, config=cfg)
    if not complete or not active:
        raise ProviderUnavailable("BSE_CURRENT_IDENTITY_SNAPSHOT_INCOMPLETE")
    bse_tip_bridge.enable(registry_path=control / "bj_routing_identity.json", board_session=board_day)
    existing = load_curated_instruments(cfg)
    bad = correction_symbols(existing.to_dicts(), active, baseline) if existing is not None else set()
    from status_evidence import enable as enable_validated_status
    # Current routing identity does not assert historical normal trading.
    # It contradicts only the known inferred delisting. The dated old rows
    # are retained on disk and become UNKNOWN in completeness decisions.
    validated_ids = {s for s in active if s.endswith(".BJ") and s in baseline
                     and not baseline[s].get("delist_date")}
    enable_validated_status(validated_ids)
    atomic_bytes(control / "status_evidence_invalidation.json", json_bytes({
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "reason_code": "CONTRADICTED_BJ_INFERRED_DELISTING",
        "symbols": sorted(validated_ids), "inference_start": "2026-09-28",
        "source_snapshot_session": str(board_day), "historical_normal_asserted": False,
        "prior_revisions_modified": False, "missing_bar_remains_required": True}))
    original = finalize.compact_instruments
    if getattr(original, "__etf_quant_catalogue_correction__", False):
        return {"repair_required": bool(bad), "current_bj_count": len(active)}

    def compact(staging_root, curated_root, run_id, trade_date, *, changed_files=None, base_root=None):
        source = Path(base_root) if base_root is not None else Path(curated_root) / "instruments"
        files = sorted(source.rglob("*.parquet"))
        frame = pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed") if files else None
        repair = correction_symbols(frame.to_dicts(), active, baseline) if frame is not None else set()
        if repair:
            # A fresh complete official board plus the byte-verified prior
            # catalogue contradicts only this known absence-inference defect.
            # Preserve every unrelated delisting and every original revision.
            corrected = frame.with_columns(pl.when(pl.col("symbol").is_in(sorted(repair)))
                .then(pl.lit(None, dtype=pl.Date)).otherwise(pl.col("delist_date")).alias("delist_date"))
            stage = control / "catalogue_corrections" / run_id
            stage.mkdir(parents=True, exist_ok=True)
            corrected.write_parquet(stage / "base.parquet")
            atomic_bytes(stage / "evidence.json", json_bytes({
                "observed_at": datetime.now(timezone.utc).isoformat(), "source": "OFFICIAL_BSE_CURRENT_BOARD",
                "source_snapshot_session": str(board_day),
                "usage": "CURRENT_ROUTING_IDENTITY_NOT_HISTORICAL_PIT", "board_complete": True,
                "board_count": len(active), "corrected_symbols": sorted(repair),
                "prior_catalogue_sha256": manifest["files"]["instruments.csv"],
                "superseded_inference_date": "2026-09-28", "prior_revisions_modified": False}))
            base_root = stage
            # Only Parquet is consumed by the pinned compact. No mutable lake
            # parquet is edited here; SDK revision publication remains owner.
        result = original(staging_root, curated_root, run_id, trade_date,
                          changed_files=changed_files, base_root=base_root)
        if repair and not result[0]:
            raise GateError("CATALOGUE_CORRECTION_NOT_PUBLISHED")
        bse_tip_bridge.write_registry()
        return result
    compact.__etf_quant_catalogue_correction__ = True
    finalize.compact_instruments = compact
    return {"repair_required": bool(bad), "current_bj_count": len(active),
            "contradictory_bj_delistings": len(bad)}


class ProviderUnavailable(RuntimeError):
    pass

"""Memory-bounded streaming twin of runner.export_lake.

Same gates, CSV bytes and manifest as the batch exporter, but stock bars are
scanned one calendar session per pinned query and every dataset is encoded
incrementally, so peak row memory is one day partition (~5.6K rows) plus one
encode slice instead of the full materialized export.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
import hashlib
import io
import math
import os
from pathlib import Path
import re
import shutil
import sys
from uuid import uuid4

# File boundary utilities only. Quant models execute exclusively in Docker.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from strategies.etf_quant.runtime.exports import KEYS, PROVENANCE, SCHEMAS, SHANGHAI, observed_time
from strategies.etf_quant.runtime.storage import (GateError, atomic_bytes, closed_id, digest,
    external_root, json_bytes)

from runner import DATASETS, IDENTITY, lake_fingerprint

SLICE_ROWS = 50_000
_FILENAME = re.compile(r"[a-z0-9_]+\.(json|csv)")


class _StreamTable:
    """Incremental CSV writer byte-identical to exports.encode_table output."""

    def __init__(self, stage, name):
        self.name = name
        self.required = {**SCHEMAS[name], **PROVENANCE}
        self.columns = None
        self.row_count = 0
        self.date_min = None
        self.date_max = None
        self.max_fetched = None
        self.keys = set()
        self._hash = hashlib.sha256()
        self._handle = (stage / (name + ".csv")).open("xb")

    def _emit(self, text):
        payload = text.encode("utf-8")
        self._hash.update(payload)
        self._handle.write(payload)

    def prepare(self, columns):
        if self.columns is not None:
            if set(columns) != set(self.columns):
                raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER", {"dataset": self.name})
            return
        if not set(self.required).issubset(columns):
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER", {"dataset": self.name})
        self.columns = list(columns)
        stream = io.StringIO(newline="")
        csv.DictWriter(stream, fieldnames=self.columns, extrasaction="raise", lineterminator="\n").writeheader()
        self._emit(stream.getvalue())

    def write_chunk(self, columns, rows):
        if not rows:
            return
        self.prepare(columns)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=self.columns, extrasaction="raise", lineterminator="\n")
        for row in rows:
            writer.writerow({k: "" if v is None else "true" if v is True else "false" if v is False
                             else v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in row.items()})
        self._emit(stream.getvalue())
        self.row_count += len(rows)

    def check_key(self, row):
        key = tuple(row[k] for k in KEYS[self.name])
        if key in self.keys:
            raise GateError("CNE_SNAPSHOT_DUPLICATE_BLOCKER")
        self.keys.add(key)

    def track_date(self, value):
        if self.date_min is None or value < self.date_min:
            self.date_min = value
        if self.date_max is None or value > self.date_max:
            self.date_max = value

    def finish(self):
        if self.columns is None:
            self.prepare(sorted(self.required))
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()

    def abort(self):
        try:
            self._handle.close()
        except OSError:
            pass

    @property
    def hexdigest(self):
        return self._hash.hexdigest()


def _check_cells(row, required):
    """parse_cell parity: decode-side rejection before bytes are published."""
    for key, kind in required.items():
        value = row[key]
        if kind.startswith("optional_"):
            if value is None:
                continue
            kind = kind.removeprefix("optional_")
        if kind == "str":
            if not isinstance(value, str) or not value:
                raise ValueError("empty identity")
        elif kind == "bool":
            if not isinstance(value, bool):
                raise ValueError("explicit boolean required")
        elif kind == "date":
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ValueError("invalid date field")
        elif kind == "timestamp":
            observed_time(value)
        else:
            if isinstance(value, bool):
                raise ValueError("finite numeric field required")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError("finite numeric field required") from None
            if not float("-inf") < number < float("inf"):
                raise ValueError("finite numeric field required")


def _validate_row(name, row, cutoff, session_set, table):
    """ExportProvider._validate semantics applied per published row."""
    fetched = observed_time(row["fetched_at"])
    if table.max_fetched is None or fetched > table.max_fetched:
        table.max_fetched = fetched
    field = "as_of_date" if name == "industry_membership" else "trade_date"
    # Announced calendar sessions may extend past the market cutoff; others never may.
    if name != "trading_calendar" and field in row and row[field] > cutoff:
        raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
    if name in ("stock_bars", "etf_bars"):
        if row["data_version"] != "v2":
            raise GateError("CNE_VOLUME_UNIT_BLOCKER")
        amount = row["amount"]
        if (min(row[k] for k in ("open", "high", "low", "close")) <= 0 or row["volume"] < 0
                or amount is not None and not (isinstance(amount, float) and math.isnan(amount)) and amount < 0
                or row["high"] < max(row["open"], row["close"], row["low"])
                or row["low"] > min(row["open"], row["close"], row["high"])):
            raise GateError("CNE_PRICE_SCHEMA_BLOCKER")
        shanghai = fetched.astimezone(SHANGHAI)
        if (shanghai.date() < row["trade_date"]
                or shanghai.date() == row["trade_date"] and shanghai.time() < time(15, 5)):
            raise GateError("CNE_PARTIAL_SESSION_BLOCKER")
    if name == "stock_bars" and (row["adj_is_exact"] is not True or row["adj_close"] <= 0):
        raise GateError("ADJUSTMENT_SEMANTICS_BLOCKER")
    if name == "industry_membership" and (row["classification_system"] != "sw" or row["source"] != "sw"):
        raise GateError("INDUSTRY_CLASSIFICATION_BLOCKER")
    if name == "benchmark_csi300" and (row["symbol"] != "000300.SH" or row["frequency"] != "1d" or row["close"] <= 0):
        raise GateError("BENCHMARK_IDENTITY_BLOCKER")
    if name in ("stock_bars", "etf_bars", "trading_status", "benchmark_csi300") and row["trade_date"] not in session_set:
        raise GateError("CNE_CALENDAR_BLOCKER")


def _stream_dataset(name, frame, table, accept, cutoff, session_set, stats, each=None):
    field = "as_of_date" if name == "industry_membership" else "trade_date"
    for chunk in frame.iter_slices(SLICE_ROWS):
        rows = chunk.to_dicts()
        stats["peak_chunk_rows"] = max(stats["peak_chunk_rows"], len(rows))
        accepted = [row for row in rows if accept(row)]
        if accepted:
            table.prepare(chunk.columns)
        for row in accepted:
            _check_cells(row, table.required)
            table.check_key(row)
            _validate_row(name, row, cutoff, session_set, table)
            if field in row:
                table.track_date(row[field])
            if each is not None:
                each(row)
        table.write_chunk(chunk.columns, accepted)


def export_lake_streaming(config, load, *, observed_at=None):
    """Same contract as runner.export_lake; diagnostics are returned, never manifested."""
    started = datetime.now(timezone.utc) if observed_at is None else observed_at
    settings = config["export"]
    if any(not isinstance(config["paths"].get(k), str) or not config["paths"][k].strip()
           or not Path(config["paths"][k]).is_absolute() for k in ("lake_root", "export_root")):
        raise GateError("EXPLICIT_EXTERNAL_PATHS_REQUIRED")
    if settings.get("classification_version") != IDENTITY["classification_version"]:
        raise GateError("CLASSIFICATION_VERSION_BLOCKER")
    start, cutoff = date.fromisoformat(settings["start"]), date.fromisoformat(settings["cutoff"])
    calendar_end = date.fromisoformat(settings["calendar_end"])
    if start > cutoff or calendar_end < cutoff:
        raise GateError("EXPORT_DATE_RANGE_BLOCKER")
    etfs = settings["etf_symbols"]
    if not isinstance(etfs, list) or len(set(etfs)) != len(etfs) or any(not re.fullmatch(r"\d{6}\.(SH|SZ)", s) for s in etfs):
        raise GateError("EXPLICIT_ETF_SCOPE_BLOCKER")
    lake = external_root(Path(config["paths"]["lake_root"]))
    export_path = Path(config["paths"]["export_root"])
    root_existed = export_path.exists()
    root = external_root(export_path)
    before = lake_fingerprint(lake)
    stats = {"peak_chunk_rows": 0}
    stage = root / (".stage_" + uuid4().hex)
    stage.mkdir()
    tables = {}
    try:
        tables = {name: _StreamTable(stage, name) for name in SCHEMAS}
        queries = {}
        # Membership must be complete, not narrowed to stocks with available prices.
        symbols_seen = set()
        _stream_dataset("industry_membership",
            load(DATASETS["industry_membership"], start=start.isoformat(), end=cutoff.isoformat(), data_root=lake),
            tables["industry_membership"],
            lambda r: r["source"] == "sw" and r["classification_system"] == "sw",
            cutoff, None, stats, each=lambda r: symbols_seen.add(r["symbol"]))
        symbols = sorted(symbols_seen)
        if not symbols:
            raise GateError("SHENWAN_MEMBERSHIP_UNAVAILABLE")
        queries["industry_membership"] = {"dataset": DATASETS["industry_membership"], "start": str(start),
            "end": str(cutoff), "source_filter": "sw", "classification_system": "sw", "as_of": None,
            "availability_evidence": "HISTORICAL_MEMBERSHIP_PIT_UNPROVEN"}
        traded = []
        _stream_dataset("trading_calendar",
            load(DATASETS["trading_calendar"], start=str(start), end=str(calendar_end), data_root=lake),
            tables["trading_calendar"], lambda r: True, cutoff, None, stats,
            each=lambda r: traded.append(r["trade_date"]) if r["is_trading"] is True else None)
        queries["trading_calendar"] = {"dataset": DATASETS["trading_calendar"], "start": str(start),
            "end": str(calendar_end), "as_of": None}
        sessions = tuple(sorted(traded))
        if not sessions or cutoff not in sessions:
            raise GateError("CNE_CALENDAR_BLOCKER")
        session_set = set(sessions)
        # One hive partition (single trade_date) per pinned query keeps peak memory
        # at one day frame; per-day chunks are disjoint sessions by construction.
        stock = tables["stock_bars"]
        adjustment_rejected_rows = 0
        adjustment_exact_rows = 0
        for day in (d for d in sessions if start <= d <= cutoff):
            day_symbols = set()
            frame = load(DATASETS["stock_bars"], symbols=symbols, adjust="hfq", strict_adj=False,
                         start=day.isoformat(), end=day.isoformat(), data_root=lake)
            for chunk in frame.iter_slices(SLICE_ROWS):
                rows = chunk.to_dicts()
                stats["peak_chunk_rows"] = max(stats["peak_chunk_rows"], len(rows))
                # The frozen constituent denominator includes the CDR; exclude only
                # non-exact *price rows* here, never membership rows.
                adjustment_rejected_rows += sum(r.get("adj_is_exact") is not True for r in rows)
                accepted = [r for r in rows if r.get("adj_is_exact") is True]
                if accepted:
                    stock.prepare(chunk.columns)
                for r in accepted:
                    _check_cells(r, stock.required)
                    if r["trade_date"] != day or r["symbol"] in day_symbols:
                        raise GateError("CNE_SNAPSHOT_DUPLICATE_BLOCKER", {"dataset": "stock_bars"})
                    day_symbols.add(r["symbol"])
                    _validate_row("stock_bars", r, cutoff, session_set, stock)
                    stock.track_date(r["trade_date"])
                stock.write_chunk(chunk.columns, accepted)
                adjustment_exact_rows += len(accepted)
        queries["stock_bars"] = {"dataset": DATASETS["stock_bars"], "start": str(start), "end": str(cutoff),
            "symbols": symbols, "adjust": "hfq", "strict_adj": False, "as_of": None,
            "published_exact_only": True, "rejected_nonexact_rows": adjustment_rejected_rows}
        if not etfs:
            queries["etf_bars"] = {"dataset": DATASETS["etf_bars"], "symbols": [], "adjust": None,
                "status": "NO_VERIFIED_ETF_SCOPE"}
        else:
            _stream_dataset("etf_bars",
                load(DATASETS["etf_bars"], start=str(start), end=str(cutoff), data_root=lake,
                     symbols=etfs, adjust=None),
                tables["etf_bars"], lambda r: True, cutoff, session_set, stats)
            queries["etf_bars"] = {"dataset": DATASETS["etf_bars"], "start": str(start), "end": str(cutoff),
                "symbols": etfs, "adjust": None, "as_of": None}
        _stream_dataset("instruments", load(DATASETS["instruments"], data_root=lake),
            tables["instruments"], lambda r: True, cutoff, session_set, stats)
        queries["instruments"] = {"dataset": DATASETS["instruments"], "as_of": None}
        if not etfs:
            queries["trading_status"] = {"dataset": DATASETS["trading_status"], "symbols": [],
                "status": "NO_VERIFIED_ETF_SCOPE"}
        else:
            _stream_dataset("trading_status",
                load(DATASETS["trading_status"], start=str(start), end=str(cutoff), data_root=lake, symbols=etfs),
                tables["trading_status"], lambda r: True, cutoff, session_set, stats)
            queries["trading_status"] = {"dataset": DATASETS["trading_status"], "start": str(start),
                "end": str(cutoff), "symbols": etfs, "as_of": None}
        _stream_dataset("benchmark_csi300",
            load(DATASETS["benchmark_csi300"], start=str(start), end=str(cutoff), data_root=lake,
                 symbols=["000300.SH"]),
            tables["benchmark_csi300"], lambda r: r.get("frequency") == "1d", cutoff, session_set, stats)
        queries["benchmark_csi300"] = {"dataset": DATASETS["benchmark_csi300"], "start": str(start),
            "end": str(cutoff), "symbols": ["000300.SH"], "as_of": None}
        for table in tables.values():
            table.finish()
        completed = datetime.now(timezone.utc) if observed_at is None else observed_at
        if lake_fingerprint(lake) != before:
            raise GateError("SOURCE_LAKE_CHANGED_DURING_EXPORT_BLOCKER")
        if not observed_time(started) <= observed_time(completed) <= observed_time(completed):
            raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
        if any(t.max_fetched is not None and t.max_fetched > completed for t in tables.values()):
            raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
        datasets = {}
        for name, table in tables.items():
            datasets[name] = {"file": name + ".csv", "row_count": table.row_count, "columns": table.columns,
                "file_sha256": table.hexdigest,
                "date_start": str(table.date_min) if table.date_min is not None else None,
                "date_end": str(table.date_max) if table.date_max is not None else None,
                "query": queries.get(name, {})}
        metadata = {**IDENTITY, "lake_fingerprint_sha256": before,
            "created_at": completed.isoformat(), "fetch_started_at": started.isoformat(),
            "fetch_completed_at": completed.isoformat(), "data_cutoff": cutoff.isoformat(),
            "datasets": datasets,
            "warnings": ["NOT_EX_ANTE_AVAILABILITY_PROOF", "ETF_MAPPING_EXTERNAL_EVIDENCE_REQUIRED",
                         "CALENDAR_FUTURE_SESSIONS_ARE_NOT_FUTURE_PRICES", "NO_THIRD_PARTY_DATA_REDISTRIBUTION"],
            "quality_flags": ["HISTORICAL_MEMBERSHIP_PIT_UNPROVEN", "SOURCE_LICENSING_UNRESOLVED"],
            "historical_uses": ["MODEL_WARMUP", "TRAINING_INPUT", "ENGINEERING_VALIDATION"],
            "available_at": None, "source_published_at": None,
            "adjustment_exact_rows": adjustment_exact_rows,
            "adjustment_rejected_rows": adjustment_rejected_rows}
        snapshot_id = digest(json_bytes(metadata))
        metadata["snapshot_id"] = snapshot_id
        closed_id(snapshot_id)
        destination = root / snapshot_id
        if destination.exists():
            raise GateError("IMMUTABLE_GENERATION_EXISTS")
        hashes = {}
        for name, table in tables.items():
            if not _FILENAME.fullmatch(name + ".csv"):
                raise GateError("RUNTIME_INTEGRITY_BLOCKER")
            hashes[name + ".csv"] = table.hexdigest
        manifest = {**metadata, "schema_version": "1.0.0", "run_id": snapshot_id, "files": hashes}
        manifest_bytes = json_bytes(manifest)
        atomic_bytes(stage / "manifest.json", manifest_bytes)
        # Destination becomes discoverable only after every file and manifest closes.
        os.rename(stage, destination)
    except BaseException:
        for table in tables.values():
            table.abort()
        shutil.rmtree(stage, ignore_errors=True)
        if not root_existed:
            try:
                root.rmdir()
            except OSError:
                pass
        raise
    return {"run_id": snapshot_id, "manifest_sha256": digest(manifest_bytes), "snapshot_id": snapshot_id,
            "streaming": True, "peak_chunk_rows": stats["peak_chunk_rows"]}

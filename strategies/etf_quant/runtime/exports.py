"""Generic file provider: immutable CSV+JSON snapshots, no client/network imports."""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
import io
import json
from pathlib import Path
import re

import pandas as pd

from .storage import GateError, contained, digest, external_root, json_bytes, publish_generation

SHANGHAI = timezone(timedelta(hours=8))
SCHEMAS = {
    "trading_calendar": {"trade_date": "date", "is_trading": "bool"},
    "stock_bars": {"symbol": "str", "trade_date": "date", "open": "float", "high": "float", "low": "float",
                   "close": "float", "volume": "float", "amount": "optional_float", "adj_close": "float", "adj_is_exact": "bool"},
    "industry_membership": {"symbol": "str", "classification_system": "str", "industry_code": "str",
                            "industry_name": "str", "as_of_date": "date"},
    "etf_bars": {"symbol": "str", "trade_date": "date", "open": "float", "high": "float", "low": "float",
                 "close": "float", "volume": "float", "amount": "optional_float"},
    "instruments": {"symbol": "str", "name": "str", "exchange": "str", "asset_type": "str",
                    "list_date": "optional_date", "delist_date": "optional_date", "prev_symbol": "optional_str"},
    "trading_status": {"symbol": "str", "trade_date": "date", "is_trading": "bool", "status": "str"},
    "benchmark_csi300": {"symbol": "str", "trade_date": "date", "close": "float", "frequency": "str"},
}
PROVENANCE = {"source": "str", "data_version": "str", "fetched_at": "timestamp"}
KEYS = {"trading_calendar": ["trade_date"], "stock_bars": ["symbol", "trade_date"],
        "etf_bars": ["symbol", "trade_date"], "industry_membership": ["symbol", "classification_system", "as_of_date"],
        "instruments": ["symbol"], "trading_status": ["symbol", "trade_date"],
        "benchmark_csi300": ["symbol", "trade_date", "frequency"]}


def observed_time(value):
    if not isinstance(value, (str, datetime)):
        raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
    return result


def parse_cell(value, kind):
    if kind.startswith("optional_"):
        if value == "":
            return None
        kind = kind.removeprefix("optional_")
    if kind == "str":
        if not value:
            raise ValueError("empty identity")
        return value
    if kind == "bool":
        if value not in ("true", "false"):
            raise ValueError("explicit boolean required")
        return value == "true"
    if kind == "date":
        return date.fromisoformat(value)
    if kind == "timestamp":
        return observed_time(value)
    number = float(value)
    if not pd.notna(number) or not float("-inf") < number < float("inf"):
        raise ValueError("finite numeric field required")
    return number


def encode_table(rows: list[dict], columns: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "" if v is None else "true" if v is True else "false" if v is False
                         else v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in row.items()})
    return stream.getvalue().encode("utf-8")


def decode_table(body, columns, required):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
    if (reader.fieldnames != columns or len(set(columns)) != len(columns)
            or not set(required).issubset(columns)):
        raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
        rows.append({k: parse_cell(v, required[k]) if k in required else v for k, v in row.items()})
    return pd.DataFrame(rows, columns=columns)


def export_snapshot(root: Path, tables: dict[str, list[dict]], *, identity: dict,
                    created_at: datetime, fetch_started_at: datetime, fetch_completed_at: datetime,
                    cutoff: date, queries: dict, warnings=()) -> dict:
    if set(tables) != set(SCHEMAS):
        raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
    files, datasets, frames = {}, {}, {}
    for name, rows in tables.items():
        required = {**SCHEMAS[name], **PROVENANCE}
        columns = sorted(required) if not rows else list(rows[0])
        if not set(required).issubset(columns) or any(set(r) != set(columns) for r in rows):
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER", {"dataset": name})
        payload = encode_table(rows, columns)
        frames[name] = decode_table(payload, columns, required)
        if frames[name].duplicated(KEYS[name]).any():
            raise GateError("CNE_SNAPSHOT_DUPLICATE_BLOCKER")
        files[name + ".csv"] = payload
        date_field = "as_of_date" if name == "industry_membership" else "trade_date"
        dates = sorted(r[date_field] for r in rows if date_field in r)
        datasets[name] = {"file": name + ".csv", "row_count": len(rows), "columns": columns,
                          "file_sha256": digest(payload), "date_start": str(dates[0]) if dates else None,
                          "date_end": str(dates[-1]) if dates else None, "query": queries.get(name, {})}
    if not observed_time(fetch_started_at) <= observed_time(fetch_completed_at) <= observed_time(created_at):
        raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
    validator = object.__new__(ExportProvider)
    validator.tables, validator.cutoff, validator.created_at = frames, cutoff, created_at
    validator._validate()  # Reject malformed snapshots BEFORE immutable publication.
    metadata = {**identity, "created_at": created_at.isoformat(), "fetch_started_at": fetch_started_at.isoformat(),
                "fetch_completed_at": fetch_completed_at.isoformat(), "data_cutoff": cutoff.isoformat(),
                "datasets": datasets, "warnings": list(warnings),
                "quality_flags": ["HISTORICAL_MEMBERSHIP_PIT_UNPROVEN", "SOURCE_LICENSING_UNRESOLVED"],
                "historical_uses": ["MODEL_WARMUP", "TRAINING_INPUT", "ENGINEERING_VALIDATION"],
                "available_at": None, "source_published_at": None,
                "adjustment_exact_rows": int(frames["stock_bars"].adj_is_exact.sum()), "adjustment_rejected_rows": 0}
    snapshot_id = digest(json_bytes(metadata))
    metadata["snapshot_id"] = snapshot_id
    pointer = publish_generation(external_root(root), snapshot_id, files, metadata)
    return {**pointer, "snapshot_id": snapshot_id}


class ExportProvider:
    def __init__(self, path: Path, *, expected_identity: dict, now: datetime):
        try:
            self.path = path.resolve(strict=True)
            self.manifest = json.loads(contained(self.path, "manifest.json").read_bytes())
            m = self.manifest
            candidate = {k: v for k, v in m.items() if k not in ("snapshot_id", "schema_version", "run_id", "files")}
            if (m.get("schema_version") != "1.0.0" or m.get("snapshot_id") != self.path.name
                    or digest(json_bytes(candidate)) != m["snapshot_id"]
                    or not re.fullmatch(r"[0-9a-f]{64}", m["snapshot_id"])
                    or any(m.get(k) != v for k, v in expected_identity.items())
                    or set(m.get("datasets", {})) != set(SCHEMAS)
                    or m.get("available_at") is not None or m.get("source_published_at") is not None
                    or "HISTORICAL_MEMBERSHIP_PIT_UNPROVEN" not in m.get("quality_flags", [])):
                raise GateError("CNE_SNAPSHOT_BLOCKER")
            self.created_at = observed_time(m["created_at"])
            self.cutoff = date.fromisoformat(m["data_cutoff"])
            if (not observed_time(m["fetch_started_at"]) <= observed_time(m["fetch_completed_at"]) <= self.created_at <= now
                    or self.cutoff > self.created_at.astimezone(SHANGHAI).date()
                    or self.created_at.astimezone(SHANGHAI).date() == self.cutoff
                    and self.created_at.astimezone(SHANGHAI).time() < time(15, 5)):
                raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
            self.tables = {name: self._read(name) for name in SCHEMAS}
            self._validate()
        except GateError:
            raise
        except (OSError, ValueError, KeyError, TypeError, csv.Error) as error:
            raise GateError("CNE_SNAPSHOT_BLOCKER") from error

    def _read(self, name):
        entry = self.manifest["datasets"][name]
        if entry["file"] != name + ".csv":
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
        body = contained(self.path, entry["file"]).read_bytes()
        if digest(body) != entry["file_sha256"] or self.manifest["files"].get(entry["file"]) != digest(body):
            raise GateError("CNE_SNAPSHOT_HASH_BLOCKER")
        required = {**SCHEMAS[name], **PROVENANCE}
        frame = decode_table(body, entry["columns"], required)
        if type(entry["row_count"]) is not int or entry["row_count"] < 0:
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
        if len(frame) != entry["row_count"]:
            raise GateError("CNE_SNAPSHOT_SCHEMA_BLOCKER")
        if frame.duplicated(KEYS[name]).any():
            raise GateError("CNE_SNAPSHOT_DUPLICATE_BLOCKER")
        return frame

    def _validate(self):
        for name, frame in self.tables.items():
            date_col = "as_of_date" if name == "industry_membership" else "trade_date"
            # Announced calendar sessions may extend past the market cutoff.
            # Future prices/status/membership never may.
            if name != "trading_calendar" and date_col in frame and any(d > self.cutoff for d in frame[date_col]):
                raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
            if any(t > self.created_at for t in frame.fetched_at):
                raise GateError("CNE_SNAPSHOT_TIME_BLOCKER")
            if name in ("stock_bars", "etf_bars"):
                if any(frame.data_version != "v2"):
                    raise GateError("CNE_VOLUME_UNIT_BLOCKER")
                for row in frame.to_dict("records"):
                    if (min(row[k] for k in ("open", "high", "low", "close")) <= 0 or row["volume"] < 0
                            or pd.notna(row["amount"]) and row["amount"] < 0
                            or row["high"] < max(row["open"], row["close"], row["low"])
                            or row["low"] > min(row["open"], row["close"], row["high"])):
                        raise GateError("CNE_PRICE_SCHEMA_BLOCKER")
                    fetched = row["fetched_at"].astimezone(SHANGHAI)
                    if fetched.date() < row["trade_date"] or fetched.date() == row["trade_date"] and fetched.time() < time(15, 5):
                        raise GateError("CNE_PARTIAL_SESSION_BLOCKER")
            if name == "stock_bars" and any((frame.adj_is_exact != True) | (frame.adj_close <= 0)):
                raise GateError("ADJUSTMENT_SEMANTICS_BLOCKER", {
                    "exact_rows": int((frame.adj_is_exact == True).sum()),
                    "rejected_rows": int((frame.adj_is_exact != True).sum())})
            if name == "industry_membership" and any((frame.classification_system != "sw") | (frame.source != "sw")):
                raise GateError("INDUSTRY_CLASSIFICATION_BLOCKER")
            if name == "benchmark_csi300" and (any(frame.symbol != "000300.SH") or any(frame.frequency != "1d") or any(frame.close <= 0)):
                raise GateError("BENCHMARK_IDENTITY_BLOCKER")
        calendar = self.tables["trading_calendar"]
        self.sessions = tuple(sorted(calendar.loc[calendar.is_trading == True, "trade_date"]))
        if not self.sessions or self.cutoff not in self.sessions:
            raise GateError("CNE_CALENDAR_BLOCKER")
        session_set = set(self.sessions)
        for name in ("stock_bars", "etf_bars", "trading_status", "benchmark_csi300"):
            if any(day not in session_set for day in self.tables[name].trade_date):
                raise GateError("CNE_CALENDAR_BLOCKER")

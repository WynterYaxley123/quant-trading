"""Crash-safe contiguous factual publication; no model or Shadow state."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path

from strategies.etf_quant.runtime.storage import GateError, atomic_bytes, external_root, json_bytes

PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def admission(results, steps):
    """A terminal success is necessary, never a substitute for stage receipts."""
    rows = {(r["dataset"], r["stage"]): r for r in results}
    required = {(d, s) for d in steps if d not in
                ("compact", "derive_adj_factors", "trading_status_derive", "audit")
                for s in ("fetch", "stage", "compact")}
    required |= {("compact", "compact"), ("adj_factors", "derive"),
                 ("adj_factors", "publish_revision"), ("audit", "audit"),
                 ("trading_status_derive", "fetch"), ("trading_status_derive", "stage")}
    return sorted(f"{d}:{s}" for d, s in required
                  if (d, s) not in rows or rows[d, s]["status"] != "success")


class SessionJournal:
    """Export first, immutable session receipt second, monotone cursor last.

    A crash after receipt publication is recovered by walking the exact official
    session sequence. A later failure cannot retract a committed earlier day.
    """
    def __init__(self, settings, after, sessions):
        self.exports = external_root(Path(settings["paths"]["export_root"]))
        self.root = external_root(self.exports.parent / "finalization")
        (self.root / "sessions").mkdir(exist_ok=True)
        self.days = tuple(sorted(sessions))
        lake = Path(settings["paths"]["lake_root"]).stat()
        scope = {"export": {k: v for k, v in settings["export"].items() if k != "cutoff"},
                 "lake": [lake.st_dev, lake.st_ino], "source_commit": PIN}
        self.scope = hashlib.sha256(json_bytes(scope)).hexdigest()
        header = self.root / "contract.json"
        if not header.exists():
            atomic_bytes(header, json_bytes({"anchor": str(after), "scope": self.scope}))
        contract = json.loads(header.read_bytes())
        if contract["scope"] != self.scope:
            raise GateError("FINALIZATION_SCOPE_DRIFT")
        self.anchor = date.fromisoformat(contract["anchor"])
        self.latest = None
        cursor = self.anchor
        for day in self.days:
            if day <= self.anchor:
                continue
            leaf = self.root / "sessions" / (str(day) + ".json")
            if not leaf.exists():
                break
            record = json.loads(leaf.read_bytes())
            if (record["previous_cutoff"] != str(cursor) or record["session"] != str(day)
                    or record["scope"] != self.scope):
                raise GateError("FINALIZATION_CONTINUITY_BLOCKER")
            self.verify(record)
            self.latest = record
            cursor = day
        if after > cursor:
            raise GateError("FINALIZATION_CURSOR_AHEAD_OF_EVIDENCE")
        self.cutoff = cursor
        pending = self.root / "prepared.json"
        if pending.exists():
            prepared = json.loads(pending.read_bytes())
            next_day = next((d for d in self.days if d > cursor), None)
            if (prepared["scope"] != self.scope or prepared["previous_cutoff"] != str(cursor)):
                # A prepared marker may outlive its committed session. It is
                # never authority to advance beyond the recovered cursor.
                if prepared["session"] > str(cursor):
                    raise GateError("FINALIZATION_PREPARED_STATE_DRIFT")
            elif str(next_day) == prepared["session"]:
                for folder in sorted(self.exports.iterdir()):
                    manifest = folder / "manifest.json"
                    if len(folder.name) != 64 or not manifest.is_file():
                        continue
                    doc = json.loads(manifest.read_bytes())
                    if (doc.get("data_cutoff") == prepared["session"]
                            and doc.get("lake_fingerprint_sha256") == prepared["lake_fingerprint_sha256"]
                            and doc.get("created_at", "") >= prepared["prepared_at"]):
                        self.publish(next_day, {"snapshot_id": folder.name}, prepared["source_run_id"])
                        break
        if self.latest:
            atomic_bytes(self.root / "latest.json", json_bytes(self.latest))

    def prepare(self, session, run_id, lake_fingerprint):
        if session != next((d for d in self.days if d > self.cutoff), None):
            raise GateError("FINALIZATION_CONTINUITY_BLOCKER")
        atomic_bytes(self.root / "prepared.json", json_bytes({
            "scope": self.scope, "session": str(session), "previous_cutoff": str(self.cutoff),
            "source_run_id": run_id, "lake_fingerprint_sha256": lake_fingerprint,
            "prepared_at": datetime.now(timezone.utc).isoformat()}))

    def verify(self, record):
        ident = record["snapshot_id"]
        if len(ident) != 64 or any(c not in "0123456789abcdef" for c in ident):
            raise GateError("FINALIZATION_SNAPSHOT_ID_BLOCKER")
        folder = self.exports / ident
        manifest = folder / "manifest.json"
        if checksum(manifest) != record["manifest_sha256"]:
            raise GateError("FINALIZATION_MANIFEST_HASH_BLOCKER")
        doc = json.loads(manifest.read_bytes())
        if (doc["snapshot_id"] != ident or doc["data_cutoff"] != record["session"]
                or doc["source_commit"] != PIN):
            raise GateError("FINALIZATION_EXPORT_PROVENANCE_BLOCKER")
        expected = {n + ".csv" for n in ("trading_calendar", "stock_bars",
                    "industry_membership", "etf_bars", "instruments",
                    "trading_status", "benchmark_csi300")}
        if set(doc["files"]) != expected or any(checksum(folder / n) != h
                                               for n, h in doc["files"].items()):
            raise GateError("FINALIZATION_EXPORT_BYTES_BLOCKER")

    def publish(self, session, result, run_id):
        if session != next((d for d in self.days if d > self.cutoff), None):
            raise GateError("FINALIZATION_CONTINUITY_BLOCKER")
        record = {"session": str(session), "previous_cutoff": str(self.cutoff),
                  "scope": self.scope, "source_run_id": run_id,
                  "snapshot_id": result["snapshot_id"],
                  "manifest_sha256": checksum(self.exports / result["snapshot_id"] / "manifest.json")}
        self.verify(record)
        leaf = self.root / "sessions" / (str(session) + ".json")
        if leaf.exists() and json.loads(leaf.read_bytes()) != record:
            raise GateError("FINALIZATION_IMMUTABLE_RECEIPT_COLLISION")
        atomic_bytes(leaf, json_bytes(record))
        atomic_bytes(self.root / "latest.json", json_bytes(record))
        self.cutoff, self.latest = session, record
        return record

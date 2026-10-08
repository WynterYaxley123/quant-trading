"""Independent, bounded synthetic ledger on the existing atomic journal primitives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategies.etf_quant.runtime.storage import (
    atomic_bytes,
    external_root,
    process_lock,
    publish_account_generation,
    read_generation,
    recover_publication,
)

from .contracts import Proof, SyntheticAuthority, canonical, identity, instant, require, sha
from .prospective import (
    Observation,
    Protocol,
    activation,
    maturity,
    verify_observation,
    verify_source,
)
from .source_admission import SourceRegistry

LIMIT = 4 * 1024 * 1024
EVENT_LIMIT = 1000


def namespace(root: Path) -> Path:
    require(
        root.is_absolute()
        and root.resolve() == root
        and root.parent.name == "prospective"
        and root.name.startswith("synthetic-"),
        "SYNTHETIC_NAMESPACE_REQUIRED",
    )
    for parent in (root, *root.parents):
        require(not parent.is_symlink(), "PATH_ESCAPE_DENIED")
    return external_root(root)


def read(root: Path) -> list[dict[str, Any]]:
    root = namespace(root)
    pointer_path = root / "latest.json"
    if not pointer_path.exists():
        require(
            not (root / "runs").exists() and not (root / "objects").exists(), "LEDGER_RESET_DENIED"
        )
        return []
    require(
        pointer_path.resolve() == pointer_path
        and pointer_path.stat().st_nlink == 1
        and pointer_path.stat().st_size <= 4096,
        "LEDGER_SIZE_LIMIT",
    )
    pointer = json.loads(pointer_path.read_bytes())
    # Bound the generation before the reusable primitive reads it.
    identity(pointer["run_id"])
    run = root / "runs" / pointer["run_id"]
    require(run.resolve() == run and not run.is_symlink(), "PATH_ESCAPE_DENIED")
    for name, limit in (("manifest.json", 8192), ("events.json", LIMIT)):
        path = run / name
        require(path.resolve() == path and path.stat().st_size <= limit, "LEDGER_SIZE_LIMIT")
    preview = json.loads((run / "manifest.json").read_bytes())
    require(set(preview.get("files", {})) == {"events.json"}, "LEDGER_CONTRACT_MISMATCH")
    manifest, files = read_generation(root / "runs", pointer)
    require(
        manifest.get("contract") == "SYNTHETIC_PROSPECTIVE_EVIDENCE"
        and set(files) == {"events.json"},
        "LEDGER_CONTRACT_MISMATCH",
    )
    events = json.loads(files["events.json"])
    require(isinstance(events, list) and len(events) <= EVENT_LIMIT, "LEDGER_SIZE_LIMIT")
    previous = None
    ids: set[str] = set()
    for event in events:
        require(
            set(event) == {"event_id", "body", "body_hash", "previous_hash", "proof"},
            "LEDGER_CHAIN_MISMATCH",
        )
        identity(event["event_id"])
        require(
            event["body_hash"] == sha(canonical(event["body"]))
            and event["previous_hash"] == previous
            and event["event_id"] not in ids,
            "LEDGER_CHAIN_MISMATCH",
        )
        previous = sha(canonical(event))
        ids.add(event["event_id"])
    return list(events)


class EvidenceLedger:
    """Replay authenticated facts, never trust a resettable status JSON."""

    def __init__(
        self,
        root: Path,
        protocol: Protocol,
        registry: SourceRegistry,
        authority: SyntheticAuthority,
    ) -> None:
        self.root = namespace(root)
        self.protocol = protocol
        self.registry = registry
        self.authority = authority

    def _events(self) -> list[dict[str, Any]]:
        events = read(self.root)
        runs = self.root / "runs"
        if runs.exists():
            generations = list(runs.iterdir())
            require(len(generations) <= EVENT_LIMIT, "LEDGER_SIZE_LIMIT")
            high_water = 0
            for generation in generations:
                identity(generation.name)
                require(generation.resolve() == generation, "PATH_ESCAPE_DENIED")
                leaf = generation / "manifest.json"
                require(leaf.resolve() == leaf and leaf.stat().st_size <= 8192, "LEDGER_SIZE_LIMIT")
                manifest = json.loads(leaf.read_bytes())
                checkpoint = self.authority.verify(
                    Proof.parse(manifest["checkpoint"]), "checkpoint"
                )
                require(
                    checkpoint["events_sha256"] == manifest["files"]["events.json"],
                    "LEDGER_CHAIN_MISMATCH",
                )
                high_water = max(high_water, checkpoint["event_count"])
            require(len(events) == high_water, "LEDGER_ROLLBACK_DENIED")
        return events

    def replay(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        state = "NOT_PREREGISTERED"
        first = None
        calendar = None
        last_at = None
        source_admitted = False
        observed: dict[str, tuple[Observation, Proof]] = {}
        finalized: dict[str, Observation] = {}
        quarantined: set[str] = set()
        issued: dict[str, dict[str, Any]] = {}
        consumed: set[str] = set()
        intervals: dict[str, set[str]] = {}
        ready_phase = None
        for event in events:
            body = event["body"]
            require(
                set(body)
                == {"kind", "protocol_hash", "source_digest", "event_at", "payload", "scope"}
                and body["protocol_hash"] == self.protocol.digest
                and body["source_digest"] == self.protocol.source_digest
                and body["scope"] == "SYNTHETIC_ONLY",
                "LEDGER_IDENTITY_MISMATCH",
            )
            require(
                self.authority.verify(Proof.parse(event["proof"]), "event")
                == {"body_hash": event["body_hash"]},
                "UNTRUSTED_EVIDENCE",
            )
            stamp = instant(body["event_at"])
            require(last_at is None or stamp >= last_at, "BACKDATED_EVENT_DENIED")
            last_at = stamp
            kind, payload = body["kind"], body["payload"]
            require(state != "CLOSED", "EVIDENCE_CLOSED")
            require(
                state != "BLOCKED" or kind == "EVIDENCE_QUARANTINED", "FACT_REVISION_QUARANTINED"
            )
            if kind == "PROTOCOL_REGISTERED":
                require(state == "NOT_PREREGISTERED", "INVALID_LIFECYCLE_TRANSITION")
                calendar = Proof.parse(payload["calendar"])
                require(
                    calendar.digest == self.protocol.calendar_proof_hash,
                    "CALENDAR_IDENTITY_MISMATCH",
                )
                state = "PREREGISTERED"
            elif kind == "SOURCE_ADMITTED":
                require(
                    state == "PREREGISTERED" and not source_admitted, "INVALID_LIFECYCLE_TRANSITION"
                )
                verify_source(self.protocol, self.registry)
                source_admitted = True
            elif kind == "ACTIVATION_BOUND":
                require(
                    state == "PREREGISTERED" and source_admitted and calendar,
                    "INVALID_LIFECYCLE_TRANSITION",
                )
                assert calendar is not None
                first = activation(
                    self.protocol, Proof.parse(payload["anchor"]), calendar, self.authority
                )
                require(payload["first_session"] == first, "PROSPECTIVE_ACTIVATION_NOT_VERIFIED")
                state = "ACTIVATED"
            elif kind == "FACT_SNAPSHOT_OBSERVED":
                require(
                    first
                    and state
                    in {
                        "ACTIVATED",
                        "COLLECTING_PROSPECTIVE_FACTS",
                        "WAITING_FOR_MATURITY",
                        "PHASE_CONSUMED",
                    },
                    "INVALID_LIFECYCLE_TRANSITION",
                )
                receipt = Observation(**payload["receipt"])
                proof = Proof.parse(payload["proof"])
                verify_observation(
                    receipt, proof, self.protocol, str(first), self.registry, self.authority
                )
                require(instant(receipt.observed_at) <= stamp, "BACKDATED_EVENT_DENIED")
                require(receipt.exchange_session not in observed, "FACT_SNAPSHOT_IMMUTABLE")
                observed[receipt.exchange_session] = (receipt, proof)
                state = "COLLECTING_PROSPECTIVE_FACTS"
            elif kind == "FACT_FINALIZED":
                day = payload["session"]
                require(day in observed and day not in finalized, "FACT_NOT_FINALIZED")
                receipt = observed[day][0]
                require(
                    payload["receipt_hash"] == receipt.digest
                    and instant(receipt.source_finalized_at) <= stamp,
                    "FACT_NOT_FINALIZED",
                )
                finalized[day] = receipt
                state = "WAITING_FOR_MATURITY"
            elif kind == "MATURITY_REACHED":
                require(
                    state in {"WAITING_FOR_MATURITY", "PHASE_CONSUMED"},
                    "INVALID_LIFECYCLE_TRANSITION",
                )
                phase = payload["phase"]
                require(phase not in consumed, "PHASE_ALREADY_CONSUMED")
                require(first, "PROSPECTIVE_ACTIVATION_NOT_VERIFIED")
                result = maturity(
                    self.protocol,
                    payload["signal"],
                    payload["horizon"],
                    finalized,
                    authorized_phase=phase,
                    quarantined=quarantined,
                    registry=self.registry,
                    authority=self.authority,
                    first_session=str(first),
                    fact_proofs={d: v[1] for d, v in observed.items()},
                )
                require(
                    result["status"] == "MATURED"
                    and payload["maturity_hash"] == sha(canonical(result)),
                    "PENDING_MATURITY",
                )
                outcomes = set(result["sessions"][1:])
                require(
                    not any(outcomes & dates for p, dates in intervals.items() if p != phase),
                    "PHASE_OUTCOME_OVERLAP",
                )
                intervals.setdefault(phase, set()).update(outcomes)
                ready_phase = phase
                state = "READY_FOR_AUTHORIZED_PHASE"
            elif kind == "ACCESS_VIEW_ISSUED":
                require(
                    state == "READY_FOR_AUTHORIZED_PHASE" and payload["phase"] == ready_phase,
                    "INVALID_LIFECYCLE_TRANSITION",
                )
                identity(payload["view_id"])
                require(payload["view_id"] not in issued, "IMMUTABLE_VIEW_REQUIRED")
                view = self.authority.verify(Proof.parse(payload["receipt"]), "view")
                require(
                    view["protocol_hash"] == self.protocol.digest and view["phase"] == ready_phase,
                    "PROTOCOL_HASH_MISMATCH",
                )
                require(
                    payload["view_id"] == view["view_id"]
                    and payload["content_hash"] == view["content_hash"],
                    "CONTENT_HASH_MISMATCH",
                )
                issued[payload["view_id"]] = payload
            elif kind == "ACCESS_VIEW_CONSUMED":
                require(
                    state == "READY_FOR_AUTHORIZED_PHASE" and payload["view_id"] in issued,
                    "INVALID_LIFECYCLE_TRANSITION",
                )
                view = issued[payload["view_id"]]
                require(
                    payload["content_hash"] == view["content_hash"]
                    and view["phase"] not in consumed,
                    "PHASE_ALREADY_CONSUMED",
                )
                consumed.add(view["phase"])
                state = "PHASE_CONSUMED"
            elif kind == "EVIDENCE_REVISION_DETECTED":
                require(first and payload["session"] in observed, "REVISION_IDENTITY_REQUIRED")
                require(
                    payload["category"]
                    in {
                        "membership",
                        "adjusted_close",
                        "delisting",
                        "calendar",
                        "symbol",
                        "coverage",
                    },
                    "REVISION_IDENTITY_REQUIRED",
                )
                require(
                    payload["original_hash"] == observed[payload["session"]][0].digest
                    and payload["new_hash"] != payload["original_hash"],
                    "REVISION_IDENTITY_REQUIRED",
                )
                quarantined.add(payload["session"])
                state = "BLOCKED"
            elif kind == "EVIDENCE_QUARANTINED":
                require(
                    state == "BLOCKED" and payload["session"] in quarantined,
                    "INVALID_LIFECYCLE_TRANSITION",
                )
            elif kind == "EVIDENCE_CLOSED":
                require(state == "PHASE_CONSUMED", "INVALID_LIFECYCLE_TRANSITION")
                state = "CLOSED"
            else:
                require(False, "EVENT_KIND_DENIED")
        return {
            "state": state,
            "first_session": first,
            "finalized": finalized,
            "quarantined": quarantined,
            "consumed": consumed,
        }

    def status(self) -> dict[str, Any]:
        with process_lock(self.root / ".evidence.guard"):
            recover_publication(self.root)
            return self.replay(self._events())

    def append(self, event_id: str, body: dict[str, Any], proof: Proof) -> str:
        identity(event_id)
        require(len(canonical(body)) <= 64 * 1024, "LEDGER_SIZE_LIMIT")
        with process_lock(self.root / ".evidence.guard"):
            recover_publication(self.root)
            events = self._events()
            existing = next((e for e in events if e["event_id"] == event_id), None)
            if existing:
                require(
                    existing["body"] == body and existing["proof"] == proof.as_dict(),
                    "DUPLICATE_EVENT_CONFLICT",
                )
                self.replay(events)
                return "NOOP_ALREADY_PUBLISHED"
            event = {
                "event_id": event_id,
                "body": body,
                "body_hash": sha(canonical(body)),
                "previous_hash": sha(canonical(events[-1])) if events else None,
                "proof": proof.as_dict(),
            }
            require(len(events) < EVENT_LIMIT, "LEDGER_SIZE_LIMIT")
            self.replay([*events, event])
            raw = canonical([*events, event])
            require(len(raw) <= LIMIT, "LEDGER_SIZE_LIMIT")
            objects = self.root / "objects"
            objects.mkdir(exist_ok=True)
            object_path = objects / (sha(canonical(event)) + ".json")
            if object_path.exists():
                require(object_path.read_bytes() == canonical(event), "IMMUTABLE_OBJECT_CONFLICT")
            else:
                atomic_bytes(object_path, canonical(event))
            publish_account_generation(
                self.root,
                "evidence_" + sha(raw)[:32],
                {"events.json": raw},
                {
                    "contract": "SYNTHETIC_PROSPECTIVE_EVIDENCE",
                    "checkpoint": self.authority.issue(
                        "checkpoint", {"events_sha256": sha(raw), "event_count": len(events) + 1}
                    ).as_dict(),
                },
            )
            return "PUBLISHED"

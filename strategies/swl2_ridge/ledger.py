"""Immutable forecast/evaluation events on the existing journaled storage primitives."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from strategies.etf_quant.runtime.storage import (
    atomic_bytes,
    contained,
    digest,
    external_root,
    json_bytes,
    process_lock,
    publish_account_generation,
    read_generation,
    recover_publication,
)
from strategies.swl2_ridge.registry import SWL2_RIDGE_V1, SWL2_RIDGE_V2

MAX_EVENTS = 10000
MAX_BODY = 16 * 1024 * 1024
MAX_EVENT_BODY = 512 * 1024


def checked_namespace(root: Path) -> Path:
    """Reject namespace/ancestor symlink aliases before any read, lock or mkdir."""
    if (
        not root.is_absolute()
        or root.name not in (SWL2_RIDGE_V1, SWL2_RIDGE_V2)
        or root.parent.name != "industry-forecast"
        or root.resolve() != root.absolute()
        or any((p / ".git").exists() for p in (root, *root.parents))
    ):
        raise ValueError("FORECAST_NAMESPACE_PATH_BLOCKER")
    return root


def event_hash(event: dict[str, Any]) -> str:
    return digest(json_bytes({k: event[k] for k in ("event_id", "body_hash", "previous_hash")}))


def recover(root: Path) -> None:
    """Recover before model/provider work on a genuine live retry, under the same mutex."""
    root = checked_namespace(root)
    if root.exists():
        with process_lock(root / ".forecast.guard"):
            recover_publication(root)


def initialize(root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    root = checked_namespace(root)
    if root.name != binding["family_id"] or root.parent.name != "industry-forecast":
        raise ValueError("INDEPENDENT_FORECAST_NAMESPACE_REQUIRED")
    root = external_root(root)
    with process_lock(root / ".forecast.guard"):
        recover_publication(root)
        state = read(root)
        if state:
            return state["binding"]
        publish_account_generation(
            root,
            "binding_" + uuid4().hex,
            {"events.json": json_bytes({"events": []}), "binding.json": json_bytes(binding)},
            {"contract": "FORWARD_INDUSTRY_FORECAST_LEDGER"},
        )
    return binding


def bounded_json(root: Path, name: str, limit: int = MAX_BODY) -> dict[str, Any]:
    with contained(root, name).open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("FORECAST_READ_SIZE_LIMIT")
    result: dict[str, Any] = json.loads(raw)
    return result


def read(root: Path) -> dict[str, Any] | None:
    root = checked_namespace(root)
    if not root.exists() or not (root / "latest.json").exists():
        return None
    pointer = bounded_json(root, "latest.json", 4096)
    # Bounded before calling the existing byte/hash verifier.
    run = contained(root, "runs/" + pointer["run_id"])
    manifest = bounded_json(run, "manifest.json", 4096)
    if set(manifest["files"]) != {"events.json", "binding.json"}:
        raise ValueError("CLOSED_FORECAST_GENERATION_REQUIRED")
    for name in manifest["files"]:
        bounded_json(run, name)
    _, bodies = read_generation(contained(root, "runs"), pointer)
    references = json.loads(bodies["events.json"])["events"]
    binding = json.loads(bodies["binding.json"])
    if not isinstance(references, list) or len(references) > MAX_EVENTS:
        raise ValueError("FORECAST_EVENT_COUNT_LIMIT")
    events = []
    for reference in references:
        if set(reference) != {"event_id", "body_hash", "previous_hash"}:
            raise ValueError("CLOSED_FORECAST_EVENT_REFERENCE_REQUIRED")
        body_hash = reference["body_hash"]
        if (
            not isinstance(body_hash, str)
            or len(body_hash) != 64
            or any(c not in "0123456789abcdef" for c in body_hash)
        ):
            raise ValueError("FORECAST_OBJECT_HASH_REQUIRED")
        with contained(root, "objects/" + body_hash + ".json").open("rb") as handle:
            raw = handle.read(MAX_EVENT_BODY + 1)
        if len(raw) > MAX_EVENT_BODY or digest(raw) != body_hash:
            raise ValueError("FORECAST_OBJECT_HASH_MISMATCH")
        events.append({**reference, "body": json.loads(raw), "body_json": raw.decode()})
    previous: str | None = None
    ids: set[str] = set()
    publications: dict[str, dict[str, Any]] = {}
    for event in events:
        body = event["body"]
        if (
            event["previous_hash"] != previous
            or digest(event["body_json"].encode()) != event["body_hash"]
            or json.loads(event["body_json"]) != body
            or event["event_id"] in ids
        ):
            raise ValueError("FORECAST_EVENT_CHAIN_MISMATCH")
        if (
            body["source_commit"] != binding["source_commit"]
            or body["family_id"] != binding["family_id"]
            or body["model_contract_hash"] != binding["model_contract_hash"]
        ):
            raise ValueError("FORECAST_BINDING_MISMATCH")
        if body["kind"] == "FORECAST":
            if body["signal_date"] in publications:
                raise ValueError("DUPLICATE_FORECAST_PUBLICATION")
            publications[body["signal_date"]] = body
        elif body["kind"] == "EVALUATION":
            forecast = publications.get(body["signal_date"])
            if not forecast or body["forecast_hash"] != digest(json_bytes(forecast)):
                raise ValueError("EVALUATION_FORECAST_HASH_MISMATCH")
        else:
            raise ValueError("UNKNOWN_FORECAST_EVENT")
        ids.add(event["event_id"])
        previous = event_hash(event)
    return {"binding": binding, "events": events, "pointer": pointer}


def append(
    root: Path,
    binding: dict[str, Any],
    event_id: str,
    body: dict[str, Any],
    *,
    after_publish: Callable[[], None] | None = None,
) -> str:
    root = checked_namespace(root)
    if root.name != binding["family_id"] or root.parent.name != "industry-forecast":
        raise ValueError("INDEPENDENT_FORECAST_NAMESPACE_REQUIRED")
    root = external_root(root)
    with process_lock(root / ".forecast.guard"):
        recover_publication(root)
        state = read(root)
        if state and state["binding"] != binding:
            raise ValueError("FORECAST_BINDING_MISMATCH")
        events = state["events"] if state else []
        existing = next((e for e in events if e["event_id"] == event_id), None)
        if existing:
            if existing["body_hash"] != digest(json_bytes(body)):
                raise ValueError("DUPLICATE_PUBLICATION_CONFLICT")
            return "NOOP_ALREADY_PUBLISHED"
        if any(
            body[k] != binding[k] for k in ("source_commit", "family_id", "model_contract_hash")
        ):
            raise ValueError("FORECAST_BINDING_MISMATCH")
        if body["kind"] == "EVALUATION" and not any(
            e["body"]["kind"] == "FORECAST"
            and e["body_hash"] == body["forecast_hash"]
            and e["body"]["signal_date"] == body["signal_date"]
            for e in events
        ):
            raise ValueError("EVALUATION_FORECAST_HASH_MISMATCH")
        if len(events) >= MAX_EVENTS:
            raise ValueError("FORECAST_EVENT_COUNT_LIMIT")
        event: dict[str, Any] = {
            "event_id": event_id,
            "body": body,
            "body_json": json_bytes(body).decode(),
            "body_hash": digest(json_bytes(body)),
            "previous_hash": event_hash(events[-1]) if events else None,
        }
        raw = event["body_json"].encode()
        if len(raw) > MAX_EVENT_BODY:
            raise ValueError("FORECAST_EVENT_SIZE_LIMIT")
        objects = contained(root, "objects", exists=False)
        objects.mkdir(exist_ok=True)
        target = contained(objects, event["body_hash"] + ".json", exists=False)
        if target.exists():
            with target.open("rb") as handle:
                existing_body = handle.read(MAX_EVENT_BODY + 1)
            if existing_body != raw:
                raise ValueError("FORECAST_OBJECT_HASH_MISMATCH")
        else:
            atomic_bytes(target, raw)
        payload = json_bytes(
            {
                "events": [
                    {k: e[k] for k in ("event_id", "body_hash", "previous_hash")}
                    for e in [*events, event]
                ]
            }
        )
        if len(payload) > MAX_BODY:
            raise ValueError("FORECAST_READ_SIZE_LIMIT")
        # This generic publisher's historical name does not introduce account state.
        publish_account_generation(
            root,
            "forecast_" + uuid4().hex,
            {"events.json": payload, "binding.json": json_bytes(binding)},
            {"contract": "FORWARD_INDUSTRY_FORECAST_LEDGER"},
        )
        if after_publish:
            after_publish()
        read(root)  # Verify the committed chain before returning success.
    return "APPENDED"

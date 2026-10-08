"""Run with the independent developer Docker; SYNTHETIC_ONLY throughout."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from research.evidence.contracts import Denied, canonical, sha
from research.evidence.ledger import EvidenceLedger
from research.evidence.numeric import Boundary, consume, grant_claims, materialize
from research.evidence.prospective import activation, maturity

from .fixture import event, observation, observed_payload, setup


def run(root: Path) -> dict[str, object]:
    authority, registry, protocol, calendar, anchor = setup()
    ledger = EvidenceLedger(root / "prospective" / "synthetic-demo", protocol, registry, authority)

    def append(event_id: str, kind: str, at: str, payload: dict) -> None:
        body = event(protocol, kind, at, payload)
        ledger.append(event_id, body, authority.issue("event", {"body_hash": sha(canonical(body))}))

    at = "2028-01-03T11:00:00+08:00"
    first = activation(protocol, anchor, calendar, authority)
    append("protocol", "PROTOCOL_REGISTERED", at, {"calendar": calendar.as_dict()})
    append("source", "SOURCE_ADMITTED", at, {})
    append(
        "activation", "ACTIVATION_BOUND", at, {"anchor": anchor.as_dict(), "first_session": first}
    )
    fact_proofs = {}
    for day in protocol.sessions[1:12]:
        receipt = observation(protocol, registry, day)
        fact_proofs[day] = authority.issue("fact", {"receipt_hash": receipt.digest})
        at = day + "T16:05:00+08:00"
        append(
            "observed-" + day, "FACT_SNAPSHOT_OBSERVED", at, observed_payload(receipt, authority)
        )
        append(
            "finalized-" + day,
            "FACT_FINALIZED",
            at,
            {"session": day, "receipt_hash": receipt.digest},
        )
    state = ledger.status()
    matured = maturity(
        protocol,
        first,
        10,
        state["finalized"],
        authorized_phase="development",
        quarantined=state["quarantined"],
        registry=registry,
        authority=authority,
        first_session=first,
        fact_proofs=fact_proofs,
    )
    append(
        "matured",
        "MATURITY_REACHED",
        at,
        {
            "phase": "development",
            "signal": first,
            "horizon": 10,
            "maturity_hash": sha(canonical(matured)),
        },
    )
    facts_hash = sha(canonical(matured["receipt_hashes"]))
    boundary = Boundary(
        "development",
        first,
        protocol.sessions[11],
        protocol.sessions[11],
        protocol.sessions[11],
        (10,),
        "2030-01-01T00:00:00Z",
    )
    n = len(protocol.sessions)
    features = np.arange(n * 3 * 2, dtype=float).reshape(n, 3, 2) / 1000
    returns = np.arange(n * 3, dtype=float).reshape(n, 3) / 100000
    returns[12:] = 9.9e99  # Forbidden sentinel never enters the worker view or output.
    mother = root / "synthetic-mother.npz"
    np.savez_compressed(
        mother,
        sessions=np.array(protocol.sessions),
        universe=np.array(protocol.model_universe),
        features=features,
        returns=returns,
    )
    view = root / "views" / "synthetic-view"
    grant = authority.issue("phase", grant_claims(protocol, boundary, facts_hash))
    manifest = materialize(
        mother,
        view,
        protocol,
        boundary,
        grant,
        registry,
        authority,
        now=at,
        facts_hash=facts_hash,
        activation_anchor=anchor,
        calendar=calendar,
    )
    source = registry.get(protocol.source_digest).source
    pin = sha(canonical(manifest))
    consumed = consume(
        view,
        pinned_manifest_hash=pin,
        protocol=protocol,
        boundary=boundary,
        source_hash=source.source_hash,
        data_contract_hash=source.data_contract_hash,
        now=at,
    )
    denied = False
    try:
        consume(
            mother.parent,
            pinned_manifest_hash=pin,
            protocol=protocol,
            boundary=boundary,
            source_hash=source.source_hash,
            data_contract_hash=source.data_contract_hash,
            now=at,
        )
    except Denied:
        denied = True
    append(
        "issued",
        "ACCESS_VIEW_ISSUED",
        at,
        {
            "phase": "development",
            "view_id": view.name,
            "content_hash": manifest["content_hash"],
            "receipt": manifest["authority_receipt"],
        },
    )
    append(
        "consumed",
        "ACCESS_VIEW_CONSUMED",
        at,
        {"view_id": view.name, "content_hash": manifest["content_hash"]},
    )
    return {
        "scope": "SYNTHETIC_ONLY",
        "source_admission": "SOURCE_ADMITTED",
        "activation_session": first,
        "maturity": matured["status"],
        "future_read_denied": denied,
        "physical_view": consumed,
        "ledger_state": ledger.status()["state"],
        "events": 28,
        "real_evidence_created": 0,
        "process_isolation": "NOT_TESTED_BY_IN_PROCESS_DEMO",
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="synthetic-evidence-") as directory:
        print(json.dumps(run(Path(directory)), sort_keys=True))

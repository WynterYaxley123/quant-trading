"""Isolated synthetic trust domain reused by the demo and adversarial tests."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from research.evidence.contracts import Proof, SyntheticAuthority, canonical, sha
from research.evidence.prospective import Observation, Protocol
from research.evidence.source_admission import Source, SourceRegistry


def setup() -> tuple[SyntheticAuthority, SourceRegistry, Protocol, Proof, Proof]:
    authority = SyntheticAuthority(synthetic_only=True)
    source = Source(
        "synthetic-source",
        sha(b"synthetic-provider"),
        sha(b"synthetic-contract"),
        "synthetic-taxonomy",
        "synthetic-membership",
        "RECONSTRUCTED_INDUSTRY_RETURN",
        "A",
        sha(b"revision-1"),
    )
    proofs = tuple(
        authority.issue(p, {"source_digest": source.digest, **claims})
        for p, claims in (
            ("metadata", {"identity_reference": "PUBLIC_SYNTHETIC_FIXTURE"}),
            (
                "rights",
                {
                    "research_use": "PERMITTED",
                    "redistribution": "PERMITTED",
                    "evidence_reference": "MIT_SYNTHETIC_FIXTURE",
                },
            ),
            ("pit", {"tier": "A", "availability_basis": "CONTEMPORANEOUS_RECEIPT"}),
        )
    )
    registry = SourceRegistry(authority)
    registry.register(source, proofs, required_tier="A")
    days: list[str] = []
    value = date(2028, 1, 3)
    while len(days) < 280:
        if value.weekday() < 5 and value != date(2028, 1, 6):
            days.append(value.isoformat())
        value += timedelta(days=1)
    calendar = authority.issue(
        "calendar", {"sessions_hash": sha(canonical(days)), "scope": "SYNTHETIC_EXCHANGE_SPINE"}
    )
    protocol = Protocol(
        "synthetic-research",
        1,
        source.digest,
        ("industry-a", "industry-b", "industry-c"),
        (10, 40, 120),
        ("development", "validation", "final_oos"),
        tuple(days),
        calendar.digest,
    )
    anchor = authority.issue(
        "anchor",
        {
            "protocol_hash": protocol.digest,
            "transport": "SYNTHETIC_GITHUB_FIXTURE",
            "main_ancestry": "VERIFIED",
            "exact_protocol_bytes": "VERIFIED",
            "result_history": "ABSENT",
            "merged": True,
            "merged_at": "2028-01-03T10:00:00+08:00",
            "author_date": "1900-01-01T00:00:00Z",
        },
    )
    return authority, registry, protocol, calendar, anchor


def observation(protocol: Protocol, registry: SourceRegistry, day: str) -> Observation:
    source = registry.get(protocol.source_digest).source
    return Observation(
        "fact-" + day,
        day + "T16:05:00+08:00",
        day + "T15:30:00+08:00",
        day + "T16:00:00+08:00",
        day,
        source.digest,
        source.taxonomy_identity,
        source.membership_identity,
        source.data_contract_hash,
        sha(canonical({"synthetic_day": day})),
        "PERMITTED",
        day,
        source.revision_identity,
        protocol.universe_hash,
        "COMPLETE",
        "VERIFIED",
        "VERIFIED",
    )


def event(protocol: Protocol, kind: str, at: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "protocol_hash": protocol.digest,
        "source_digest": protocol.source_digest,
        "event_at": at,
        "payload": payload,
        "scope": "SYNTHETIC_ONLY",
    }


def observed_payload(receipt: Observation, authority: SyntheticAuthority) -> dict[str, Any]:
    return {
        "receipt": asdict(receipt),
        "proof": authority.issue("fact", {"receipt_hash": receipt.digest}).as_dict(),
    }

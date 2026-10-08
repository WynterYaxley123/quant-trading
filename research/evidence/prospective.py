"""Activation, factual receipts and exact exchange-session maturity; no models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from zoneinfo import ZoneInfo

from .contracts import (
    Proof,
    SyntheticAuthority,
    canonical,
    hash_id,
    identity,
    instant,
    require,
    session,
    sha,
)
from .source_admission import Kind, Source, SourceRegistry, Tier


@dataclass(frozen=True)
class Protocol:
    family_id: str
    research_generation: int
    source_digest: str
    model_universe: tuple[str, ...]
    horizons: tuple[int, ...]
    phases: tuple[str, ...]
    sessions: tuple[str, ...]
    calendar_proof_hash: str
    synthetic_only: bool = True
    required_pit_tier: Tier = "A"
    required_series_kind: Kind = "RECONSTRUCTED_INDUSTRY_RETURN"

    def __post_init__(self) -> None:
        identity(self.family_id)
        require(self.synthetic_only is True, "PRODUCTION_PROTOCOL_NOT_AUTHORIZED")
        require(self.required_pit_tier in {"A", "B", "C"}, "PIT_TIER_INVALID")
        require(self.research_generation > 0, "GENERATION_INVALID")
        hash_id(self.source_digest)
        hash_id(self.calendar_proof_hash)
        require(
            self.model_universe
            and self.model_universe == tuple(sorted(set(self.model_universe)))
            and all(identity(v) for v in self.model_universe),
            "MODEL_UNIVERSE_DRIFT",
        )
        require(
            self.horizons
            and len(set(self.horizons)) == len(self.horizons)
            and all(type(h) is int and 0 < h <= 1000 for h in self.horizons),
            "HORIZON_NOT_REGISTERED",
        )
        require(self.phases and len(set(self.phases)) == len(self.phases), "PHASE_NOT_REGISTERED")
        for phase in self.phases:
            identity(phase)
        require(
            1 <= len(self.sessions) <= 20000 and self.sessions == tuple(sorted(set(self.sessions))),
            "EXCHANGE_CALENDAR_UNAVAILABLE",
        )
        for value in self.sessions:
            session(value)

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    @property
    def universe_hash(self) -> str:
        return sha(canonical(self.model_universe))


def verify_source(protocol: Protocol, registry: SourceRegistry) -> Source:
    source = registry.get(protocol.source_digest).source
    require(
        "ABCD".index(source.tier) <= "ABCD".index(protocol.required_pit_tier),
        "PIT_EVIDENCE_INSUFFICIENT",
    )
    require(source.kind == protocol.required_series_kind, "SOURCE_KIND_MISMATCH")
    return source


def activation(
    protocol: Protocol, anchor: Proof, calendar: Proof, authority: SyntheticAuthority
) -> str:
    """Author dates are ignored. An authenticated external merge witness is required."""
    claims = authority.verify(anchor, "anchor")
    spine = authority.verify(calendar, "calendar")
    require(calendar.digest == protocol.calendar_proof_hash, "CALENDAR_IDENTITY_MISMATCH")
    require(
        spine.get("sessions_hash") == sha(canonical(protocol.sessions)),
        "CALENDAR_IDENTITY_MISMATCH",
    )
    require(
        claims.get("protocol_hash") == protocol.digest
        and claims.get("transport") == "SYNTHETIC_GITHUB_FIXTURE"
        and claims.get("main_ancestry") == "VERIFIED"
        and claims.get("exact_protocol_bytes") == "VERIFIED"
        and claims.get("result_history") == "ABSENT"
        and claims.get("merged") is True,
        "PROSPECTIVE_ACTIVATION_NOT_VERIFIED",
    )
    merged = instant(claims["merged_at"]).astimezone(ZoneInfo("Asia/Shanghai"))
    eligible = [s for s in protocol.sessions if s > merged.date().isoformat()]
    require(eligible, "EXCHANGE_CALENDAR_UNAVAILABLE")
    return eligible[0]


@dataclass(frozen=True)
class Observation:
    observation_id: str
    observed_at: str
    source_published_at: str
    source_finalized_at: str
    exchange_session: str
    source_identity: str
    taxonomy_identity: str
    membership_identity: str
    data_contract_hash: str
    factual_snapshot_hash: str
    rights_status: str
    cutoff: str
    revision_identity: str
    model_universe_hash: str
    constituent_coverage: str
    suspension_status: str
    delisting_status: str

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))


def verify_observation(
    observation: Observation,
    proof: Proof,
    protocol: Protocol,
    first_session: str,
    registry: SourceRegistry,
    authority: SyntheticAuthority,
) -> None:
    source = verify_source(protocol, registry)
    require(
        authority.verify(proof, "fact").get("receipt_hash") == observation.digest,
        "UNTRUSTED_EVIDENCE",
    )
    identity(observation.observation_id)
    hash_id(observation.factual_snapshot_hash)
    require(
        observation.exchange_session in protocol.sessions
        and observation.exchange_session >= first_session
        and observation.cutoff == observation.exchange_session,
        "BACKDATED_OBSERVATION_DENIED",
    )
    seen = instant(observation.observed_at)
    published = instant(observation.source_published_at)
    finalized = instant(observation.source_finalized_at)
    require(published <= finalized <= seen, "AVAILABILITY_NOT_VERIFIED")
    local = seen.astimezone(ZoneInfo("Asia/Shanghai"))
    require(
        local.date().isoformat() == observation.exchange_session
        and local.hour >= 15
        and finalized.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        == observation.exchange_session,
        "AVAILABILITY_NOT_VERIFIED",
    )
    require(
        observation.source_identity == source.digest
        and observation.taxonomy_identity == source.taxonomy_identity
        and observation.membership_identity == source.membership_identity
        and observation.data_contract_hash == source.data_contract_hash
        and observation.revision_identity == source.revision_identity,
        "SOURCE_IDENTITY_MISMATCH",
    )
    require(observation.model_universe_hash == protocol.universe_hash, "MODEL_UNIVERSE_DRIFT")
    require(observation.rights_status == "PERMITTED", "SOURCE_RIGHTS_UNKNOWN")
    require(
        observation.constituent_coverage == "COMPLETE"
        and observation.suspension_status == "VERIFIED"
        and observation.delisting_status == "VERIFIED",
        "FACT_NOT_FINALIZED",
    )


def maturity(
    protocol: Protocol,
    signal: str,
    horizon: int,
    finalized: dict[str, Observation],
    *,
    authorized_phase: str,
    quarantined: set[str],
    registry: SourceRegistry,
    authority: SyntheticAuthority,
    first_session: str,
    fact_proofs: dict[str, Proof],
) -> dict[str, Any]:
    require(authorized_phase in protocol.phases, "PHASE_NOT_REGISTERED")
    require(horizon in protocol.horizons, "HORIZON_NOT_REGISTERED")
    require(signal in protocol.sessions, "EXCHANGE_CALENDAR_UNAVAILABLE")
    start = protocol.sessions.index(signal)
    interval = protocol.sessions[start : start + horizon + 1]
    for day in interval:
        if day in finalized:
            require(day in fact_proofs, "AVAILABILITY_NOT_VERIFIED")
            verify_observation(
                finalized[day], fact_proofs[day], protocol, first_session, registry, authority
            )
    ready = (
        len(interval) == horizon + 1
        and all(s in finalized and s not in quarantined for s in interval)
        and all(
            finalized[s].model_universe_hash == protocol.universe_hash
            and finalized[s].constituent_coverage == "COMPLETE"
            for s in interval
            if s in finalized
        )
    )
    return {
        "protocol_hash": protocol.digest,
        "source_digest": protocol.source_digest,
        "phase": authorized_phase,
        "status": "MATURED" if ready else "PENDING_MATURITY",
        "signal_session": signal,
        "horizon": horizon,
        "maturity_session": interval[-1] if len(interval) == horizon + 1 else None,
        "sessions": list(interval),
        "receipt_hashes": [finalized[s].digest for s in interval if s in finalized]
        if ready
        else [],
    }


def accounting(protocol: Protocol, signals: tuple[str, ...], horizon: int) -> dict[str, Any]:
    require(horizon in protocol.horizons, "HORIZON_NOT_REGISTERED")
    intervals = []
    for signal in signals:
        require(signal in protocol.sessions, "EXCHANGE_CALENDAR_UNAVAILABLE")
        i = protocol.sessions.index(signal)
        outcomes = set(protocol.sessions[i + 1 : i + horizon + 1])
        require(len(outcomes) == horizon, "PENDING_MATURITY")
        intervals.append(outcomes)
    overlap = any(a & b for i, a in enumerate(intervals) for b in intervals[i + 1 :])
    return {
        "signal_count": len(signals),
        "distinct_outcome_sessions": len(set().union(*intervals)),
        "overlapping_outcomes": overlap,
        "independent_experiments": None,
        "confidence": "DEPENDENT_OVERLAPPING_OBSERVATIONS"
        if overlap
        else "DISJOINT_OUTCOME_INTERVALS",
    }


def purge(protocol: Protocol, left: str, right: str, horizon: int) -> None:
    require(horizon in protocol.horizons, "HORIZON_NOT_REGISTERED")
    require(
        left in protocol.sessions and right in protocol.sessions, "EXCHANGE_CALENDAR_UNAVAILABLE"
    )
    require(
        protocol.sessions.index(right) > protocol.sessions.index(left) + horizon,
        "PHASE_OUTCOME_OVERLAP",
    )

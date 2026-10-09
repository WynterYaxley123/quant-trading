"""Synthetic inference adapter behind the existing authenticated prospective gates."""

from __future__ import annotations

from typing import Any

from research.evidence.contracts import Denied, Proof, canonical, hash_id, require, sha
from research.evidence.ledger import EvidenceLedger

from .model import CODES, Array, score, summarize_ranking


class ProspectiveAdapter:
    def __init__(self, ledger: EvidenceLedger, model_hash: str) -> None:
        protocol = ledger.protocol
        require(protocol.synthetic_only is True, "REAL_FORECAST_NOT_AUTHORIZED")
        require(protocol.family_id == "swl1_rev10_short_v1", "REV10_PROTOCOL_REQUIRED")
        require(
            protocol.model_universe == CODES and protocol.horizons == (10, 5),
            "REV10_PROTOCOL_REQUIRED",
        )
        hash_id(model_hash)
        self.ledger = ledger
        self.model_hash = model_hash

    @classmethod
    def production(cls) -> ProspectiveAdapter:
        raise Denied("SIGNATURE_AUTHORITY_NOT_ESTABLISHED")

    def infer(
        self, returns: Array, dates: tuple[str, ...], asof: str, view_proof: Proof
    ) -> dict[str, Any]:
        status = self.ledger.status()
        require(status["first_session"] is not None, "FORMAL_ACTIVATION_NOT_ESTABLISHED")
        require(
            status["state"] in {"WAITING_FOR_MATURITY", "COLLECTING_PROSPECTIVE_FACTS"},
            "SOURCE_OR_ACTIVATION_BLOCKED",
        )
        require(
            dates and dates[-1] == asof and dates[0] >= status["first_session"],
            "HISTORICAL_BACKFILL_DENIED",
        )
        protocol = self.ledger.protocol
        require(asof in protocol.sessions, "EXCHANGE_CALENDAR_UNAVAILABLE")
        i = protocol.sessions.index(asof)
        require(
            dates == protocol.sessions[i - len(dates) + 1 : i + 1],
            "EXACT_FINALIZED_SESSION_WINDOW_REQUIRED",
        )
        require(
            all(day in status["finalized"] and day not in status["quarantined"] for day in dates),
            "AUTHORIZED_FINALIZED_FACTS_REQUIRED",
        )
        claims = self.ledger.authority.verify(view_proof, "rev10_view")
        expected = {
            "scope": "SYNTHETIC_ONLY",
            "protocol_hash": protocol.digest,
            "model_hash": self.model_hash,
            "source_hash": protocol.source_digest,
            "asof": asof,
            "universe_hash": protocol.universe_hash,
            "dates_hash": sha(canonical(dates)),
            "payload_hash": sha(returns.tobytes()),
            "facts_hash": sha(canonical([status["finalized"][day].digest for day in dates])),
        }
        require(claims == expected, "AUTHORIZED_FINALIZED_VIEW_MISMATCH")
        values = score(returns, dates, CODES, asof=asof, cutoff=asof)
        output = summarize_ranking(
            values, names={}, asof=asof, source_generation=protocol.source_digest
        )
        return {
            **output,
            "status": "SYNTHETIC_PROSPECTIVE",
            "namespace": "SYNTHETIC_ONLY",
            "model_hash": self.model_hash,
            "source_hash": protocol.source_digest,
            "protocol_hash": protocol.digest,
            "formal_forecast": False,
        }

    def publish_real_forecast(self) -> None:
        raise Denied("REAL_FORECAST_NOT_AUTHORIZED")

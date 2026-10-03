"""Formal T0 strategy instance, distinct from the legacy T1 accounting epoch.

Documents live inside immutable, hash-verified run generations, not in Git.
No historical replay or network client is provided by this module.
"""

import json
from dataclasses import dataclass
from datetime import date, time, timedelta

from .exports import SHANGHAI, observed_time
from .storage import GateError, digest, json_bytes

SOURCE_PIN = "1650e384a3fd1f67a70144a489acc91432f1df27"
CANDIDATE_HASH = "e743bedb846a286c83870202c4514c80504c74409779b24f2968740914c2eb89"
PIT_REGISTRY_HASH = "81cf6d44831736c81966d3f5275bb0fd0c7d56c4652320821e4fc34143f172dc"
STRICT_REGISTRY_HASH = "37a9b81cbc07c3255d18b514eef733d4497f98cca19ba855f8626031a66afb37"
BOOK_HASH = "ac730d6475528d494515eec841b7c49f8be55d667449fc8208f534058a907b79"
# Historical readiness observation, never eligible for a retroactive formal signal.
HISTORICAL_READINESS_DATE = date(2026, 9, 24)


@dataclass(frozen=True)
class FormalContract:
    candidate_id: str
    candidate_hash: str
    pit_registry_id: str
    pit_registry_hash: str
    strict_registry_hash: str
    evidence_book_hash: str
    available_from: str
    source_commit: str

    def references(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_formal_contract(candidate_path, pit_registry_path, registry, book):
    """Authenticate the immutable certified inputs; never rewrite Candidate."""
    candidate_bytes, pit_bytes = candidate_path.read_bytes(), pit_registry_path.read_bytes()
    if (
        digest(candidate_bytes) != CANDIDATE_HASH
        or digest(pit_bytes) != PIT_REGISTRY_HASH
        or registry.sha256 != STRICT_REGISTRY_HASH
        or book.sha256 != BOOK_HASH
    ):
        raise GateError("FORMAL_CERTIFIED_INPUT_HASH_BLOCKER")
    candidate, pit = json.loads(candidate_bytes), json.loads(pit_bytes)
    if (
        candidate.get("candidate_status") != "READY_FOR_FUTURE_SHADOW"
        or candidate.get("execution_policy") != "B40_WITH_CASH"
        or candidate.get("policy_approved") is not True
        or candidate.get("production_pit_evidence_ready") is not True
        or pit.get("availability_semantics") != "FORWARD_ONLY"
        or pit.get("cneqity_pin") != SOURCE_PIN
    ):
        raise GateError("FORMAL_CERTIFIED_INPUT_CONTRACT_BLOCKER")
    available = max(
        observed_time(candidate["production_pit_evidence_available_from"]),
        observed_time(pit["production_available_from"]),
    )
    return FormalContract(
        candidate["candidate_id"],
        digest(candidate_bytes),
        pit["registry_id"],
        digest(pit_bytes),
        registry.sha256,
        book.sha256,
        available.isoformat(),
        SOURCE_PIN,
    )


def start_gate(provider, contract, now):
    """Structured WAIT is not an exception and creates no business records."""
    local = observed_time(now).astimezone(SHANGHAI)
    if provider.manifest.get("source_commit") != contract.source_commit:
        raise GateError("FORMAL_SOURCE_IDENTITY_BLOCKER")
    if local.date() not in provider.sessions:
        return "READY_NO_SIGNAL"
    if local.time() < time(15, 5):
        return "WAITING_FOR_MARKET_CLOSE"
    if provider.cutoff != local.date() or now < provider.created_at:
        return "WAITING_FOR_FINALIZED_DATA"
    available = observed_time(contract.available_from)
    if now < available:
        return "WAITING_FOR_PIT_EVIDENCE"
    # A first forward signal may not replay the observation day's past close.
    earliest = available.astimezone(SHANGHAI).date() + timedelta(days=1)
    if provider.cutoff < earliest or provider.cutoff == HISTORICAL_READINESS_DATE:
        raise GateError("FORMAL_HISTORICAL_BACKFILL_PROHIBITED")
    return "ELIGIBLE"


def record_signal(ledger, view, selected, contract, *, now, code_commit, strategy_hash):
    """Append by immutable generation, retaining exactly one T0 manifest."""
    refs = contract.references()
    existing = ledger.get("shadow_epoch")
    if existing and any(existing.get(k) != v for k, v in refs.items()):
        raise GateError("FORMAL_EPOCH_PROVENANCE_DRIFT_BLOCKER")
    signal_date = view["status"]["signal_date"]
    if ledger.get("formal_signal", {}).get("signal_date") == signal_date:
        raise GateError("DUPLICATE_FORMAL_SIGNAL_BLOCKER")
    epoch_id = existing["epoch_id"] if existing else "ETF_QUANT_V1_SHADOW_EPOCH_0001"
    signal_id = (
        "SIGNAL_"
        + digest(
            json_bytes(
                {
                    "candidate_hash": contract.candidate_hash,
                    "epoch_id": epoch_id,
                    "signal_date": signal_date,
                }
            )
        )[:24]
    )
    safety = {"simulation_only": True, "broker_enabled": False, "real_order_path": False}
    slots = selected["slots"]
    signal = {
        "schema_version": "1.0.0",
        "epoch_id": epoch_id,
        "signal_id": signal_id,
        "signal_date": signal_date,
        "decision_at": now.isoformat(),
        "code_sha": code_commit,
        **refs,
        **safety,
        "execution_policy": "B40_WITH_CASH",
        "strategy_hash": strategy_hash,
        "model_hashes": {str(m["horizon"]): m["model_hash"] for m in view["models"]},
        "snapshot_id": view["status"]["snapshot_id"],
        "top5": view["rankings"]["fusion"][:5],
        "slots": slots,
        "risk_asset_weight": selected["risk_asset_weight"],
        "cash_weight": selected["cash_weight"],
        "liquidity_window": selected["liquidity_window"],
        "t1_status": "AWAITING_T1_OPEN" if ledger["pending"] else "NO_ORDER",
    }
    if existing is None:
        ledger["shadow_epoch"] = {
            "schema_version": "1.0.0",
            "epoch_id": epoch_id,
            "created_at": now.isoformat(),
            "status": "FORMAL_T0_SIGNAL_ACCEPTED",
            **refs,
            **safety,
            "code_sha": code_commit,
            "execution_policy": "B40_WITH_CASH",
            "initial_capital": "10000",
            "strategy_hash": strategy_hash,
            "first_model_hashes": signal["model_hashes"],
            "initial_cash": "10000",
            "initial_positions": [],
            "first_signal_date": signal_date,
            "first_signal_id": signal_id,
            "decision_at": now.isoformat(),
            "risk_asset_weight": selected["risk_asset_weight"],
            "cash_weight": selected["cash_weight"],
            "top5_summary": signal["top5"],
            "mapping_summary": slots,
            "t1_status": signal["t1_status"],
            "source_licensing_status": "SOURCE_LICENSING_UNRESOLVED",
        }
    ledger["formal_signal"] = signal
    if ledger["pending"]:
        ledger["pending"].update(
            epoch_id=epoch_id, signal_id=signal_id, candidate_hash=contract.candidate_hash, **safety
        )
    view["status"].update(
        shadow_epoch=ledger["shadow_epoch"],
        formal_signal=signal,
        shadow_epoch_created=True,
        accounting_epoch=ledger["epoch"],
    )
    if ledger["epoch"] is None:
        view["status"]["phase"] = "AWAITING_T1_OPEN" if ledger["pending"] else "SHADOW_CASH_ONLY"

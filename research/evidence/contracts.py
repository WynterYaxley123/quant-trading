"""Closed identities and authority-authenticated factual proofs.

An ephemeral synthetic authority is not a production signing identity. Production
construction fails closed until a separately reviewed identity/transport exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


class Denied(ValueError):
    """Only a stable code crosses the boundary; never echo paths or numeric facts."""


def require(condition: object, code: str) -> None:
    if not condition:
        raise Denied(code)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(value: str) -> str:
    require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", value), "IDENTITY_INVALID")
    return value


def hash_id(value: str) -> str:
    require(re.fullmatch(r"[a-f0-9]{64}", value), "HASH_INVALID")
    return value


def instant(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(stamp.tzinfo is not None, "TIMESTAMP_PROOF_REQUIRED")
        return stamp
    except (TypeError, ValueError):
        raise Denied("TIMESTAMP_PROOF_REQUIRED") from None


def session(value: str) -> str:
    try:
        require(date.fromisoformat(value).isoformat() == value, "SESSION_INVALID")
    except (TypeError, ValueError):
        raise Denied("SESSION_INVALID") from None
    return value


@dataclass(frozen=True)
class Proof:
    issuer: str
    purpose: str
    claims_json: bytes
    signature: str

    @property
    def digest(self) -> str:
        return sha(canonical(self.as_dict()))

    def as_dict(self) -> dict[str, Any]:
        return dict(
            issuer=self.issuer,
            purpose=self.purpose,
            claims_json=self.claims_json.decode(),
            signature=self.signature,
        )

    @classmethod
    def parse(cls, value: dict[str, Any]) -> Proof:
        require(set(value) == {"issuer", "purpose", "claims_json", "signature"}, "PROOF_INVALID")
        require(all(isinstance(v, str) for v in value.values()), "PROOF_INVALID")
        return cls(
            value["issuer"], value["purpose"], value["claims_json"].encode(), value["signature"]
        )


class SyntheticAuthority:
    """Test-only secret stays with the authority, never in a worker manifest/mount."""

    def __init__(self, *, synthetic_only: bool) -> None:
        require(synthetic_only is True, "SIGNATURE_AUTHORITY_NOT_ESTABLISHED")
        self._key = secrets.token_bytes(32)
        self.issuer = "synthetic-authority"

    def issue(self, purpose: str, claims: dict[str, Any]) -> Proof:
        identity(purpose)
        body = canonical({"purpose": purpose, "claims": claims, "scope": "SYNTHETIC_ONLY"})
        return Proof(self.issuer, purpose, body, hmac.digest(self._key, body, "sha256").hex())

    def verify(self, proof: Proof, purpose: str) -> dict[str, Any]:
        require(len(proof.claims_json) <= 64 * 1024, "PROOF_INVALID")
        require(
            proof.issuer == self.issuer
            and proof.purpose == purpose
            and hmac.compare_digest(
                hmac.digest(self._key, proof.claims_json, "sha256").hex(), proof.signature
            ),
            "UNTRUSTED_EVIDENCE",
        )
        value = json.loads(proof.claims_json)
        require(
            set(value) == {"purpose", "claims", "scope"}
            and value["purpose"] == purpose
            and value["scope"] == "SYNTHETIC_ONLY"
            and isinstance(value["claims"], dict),
            "PROOF_INVALID",
        )
        return dict(value["claims"])

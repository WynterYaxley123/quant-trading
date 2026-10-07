"""Exclusive phase claims make research access irreversible and hash-bound."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import body, digest, immutable


class Lifecycle:
    def __init__(self, root: Path, protocol: Path, expected_hash: str) -> None:
        self.root, self.protocol, self.expected_hash = root, protocol, expected_hash
        root.mkdir(parents=True, exist_ok=True)

    def verify(self) -> dict[str, Any]:
        if not self.protocol.is_file() or digest(self.protocol.read_bytes()) != self.expected_hash:
            raise ValueError("PREREGISTRATION_REQUIRED_OR_MODIFIED")
        result: dict[str, Any] = json.loads(self.protocol.read_bytes())
        return result

    def freeze_candidate(self, candidate: dict[str, Any]) -> str:
        self.verify()
        if (self.root / "validation.claim.json").exists():
            raise ValueError("VALIDATION_INFORMED_REVISION_FORBIDDEN")
        return immutable(
            self.root / "candidate.json", {"protocol_hash": self.expected_hash, **candidate}
        )

    def claim(self, phase: str) -> dict[str, Any]:
        self.verify()
        if phase not in ("development", "validation", "final_oos"):
            raise ValueError("UNKNOWN_PHASE")
        lineage: dict[str, Any] = {"protocol_hash": self.expected_hash, "phase": phase}
        if phase != "development":
            candidate = self.root / "candidate.json"
            if not candidate.is_file():
                raise ValueError("FROZEN_CANDIDATE_REQUIRED")
            if json.loads(candidate.read_bytes())["protocol_hash"] != self.expected_hash:
                raise ValueError("CANDIDATE_PARENT_MISMATCH")
            lineage["candidate_hash"] = digest(candidate.read_bytes())
        if phase == "final_oos":
            validation = self.root / "validation.result.json"
            if (
                not validation.is_file()
                or json.loads(validation.read_bytes())["passed"] is not True
            ):
                raise ValueError("VALIDATION_PASS_REQUIRED")
            result = json.loads(validation.read_bytes())
            if (
                result["lineage"]["candidate_hash"] != lineage["candidate_hash"]
                or result["lineage"]["protocol_hash"] != self.expected_hash
            ):
                raise ValueError("VALIDATION_PARENT_MISMATCH")
            lineage["validation_hash"] = digest(validation.read_bytes())
            immutable(
                self.root / "final_oos_seal.json",
                {
                    **lineage,
                    "range": self.verify()["split"]["ranges"]["final_oos"],
                    **{
                        key: self.verify().get(key)
                        for key in ("data_panel_sha256", "model_universe_hash", "source_commit")
                    },
                },
            )
        path = self.root / f"{phase}.claim.json"
        try:
            with path.open("xb") as handle:
                handle.write(body({**lineage, "consumed": True}))
        except FileExistsError:
            raise ValueError("REJECT_ALREADY_CONSUMED") from None
        return lineage

    def complete(self, phase: str, lineage: dict[str, Any], result: dict[str, Any]) -> str:
        self.verify()
        claim = json.loads((self.root / f"{phase}.claim.json").read_bytes())
        if claim != {**lineage, "consumed": True}:
            raise ValueError("PHASE_LINEAGE_MISMATCH")
        if (
            "candidate_hash" in lineage
            and digest((self.root / "candidate.json").read_bytes()) != lineage["candidate_hash"]
        ):
            raise ValueError("CANDIDATE_BYTES_MODIFIED")
        return immutable(self.root / f"{phase}.result.json", {"lineage": lineage, **result})

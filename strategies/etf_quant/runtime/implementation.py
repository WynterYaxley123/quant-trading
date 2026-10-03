"""Current source verification with immutable historical-certificate provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PARENT_MANIFEST = "reports/engineering/repository-health.json"
ACTIVE_MANIFEST = "reports/engineering/v4-integrity.json"
PREVIOUS_MANIFEST = "reports/etf_quant/autonomous_code_integrity_v1.json"
PREVIOUS_TRANSITION = "docs/archive/engineering/public_repo_adversarial_remediation_v2.json"


class ImplementationIntegrityError(ValueError):
    """Active source or its recorded historical transition is inconsistent."""


def verify_implementation(root: Path) -> dict[str, str]:
    """Check source hashes; never read market data or sealed performance."""
    previous_bytes = (root / PREVIOUS_MANIFEST).read_bytes()
    previous = json.loads(previous_bytes)
    parent_bytes = (root / PARENT_MANIFEST).read_bytes()
    active = json.loads(parent_bytes)["implementation_integrity"]
    previous_transition = (root / PREVIOUS_TRANSITION).read_bytes()
    if (
        active["identifier"] != "PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V3"
        or active["previous_transition_sha256"] != hashlib.sha256(previous_transition).hexdigest()
        or active["previous_certificate_sha256"] != hashlib.sha256(previous_bytes).hexdigest()
        or active["previous_source_hashes"] != previous["files"]
        or active["candidate_sha256"] != previous["candidate_sha256"]
        or not set(previous["files"]).issubset(active["files"])
        or active["certificate_sha256"]
        != hashlib.sha256(
            json.dumps(active["files"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise ImplementationIntegrityError("IMPLEMENTATION_TRANSITION_BLOCKER")
    child = json.loads((root / ACTIVE_MANIFEST).read_bytes())["implementation_integrity"]
    immutable = (
        "previous_certificate_sha256",
        "previous_transition_sha256",
        "previous_source_hashes",
        "candidate_sha256",
    )
    if (
        child["identifier"] != "PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V4"
        or child["parent_manifest_sha256"] != hashlib.sha256(parent_bytes).hexdigest()
        or not set(active["files"]).issubset(child["files"])
        or any(child[key] != active[key] for key in immutable)
        or child["certificate_sha256"]
        != hashlib.sha256(
            json.dumps(child["files"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise ImplementationIntegrityError("IMPLEMENTATION_TRANSITION_BLOCKER")
    changes = {item["path"]: item for item in child["changes"]}
    for name, before in active["files"].items():
        if before != child["files"][name] and (
            name not in changes
            or changes[name]["before_sha256"] != before
            or changes[name]["after_sha256"] != child["files"][name]
        ):
            raise ImplementationIntegrityError("IMPLEMENTATION_CHANGE_LEDGER_BLOCKER")
    files: dict[str, str] = child["files"]
    for name, expected in files.items():
        target = (root / name).resolve(strict=True)
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ImplementationIntegrityError("IMPLEMENTATION_PATH_BLOCKER")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ImplementationIntegrityError("IMPLEMENTATION_SOURCE_HASH_BLOCKER:" + name)
    return files

"""Current source verification with immutable historical-certificate provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ACTIVE_MANIFEST = "reports/engineering/public_repo_adversarial_remediation_v2.json"
PREVIOUS_MANIFEST = "reports/etf_quant/autonomous_code_integrity_v1.json"


class ImplementationIntegrityError(ValueError):
    """Active source or its recorded historical transition is inconsistent."""


def verify_implementation(root: Path) -> dict[str, str]:
    """Check source hashes; never read market data or sealed performance."""
    previous_bytes = (root / PREVIOUS_MANIFEST).read_bytes()
    previous = json.loads(previous_bytes)
    active = json.loads((root / ACTIVE_MANIFEST).read_bytes())["implementation_integrity"]
    if (
        active["identifier"] != "PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V2"
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
    files: dict[str, str] = active["files"]
    for name, expected in files.items():
        target = (root / name).resolve(strict=True)
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ImplementationIntegrityError("IMPLEMENTATION_PATH_BLOCKER")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ImplementationIntegrityError("IMPLEMENTATION_SOURCE_HASH_BLOCKER:" + name)
    return files

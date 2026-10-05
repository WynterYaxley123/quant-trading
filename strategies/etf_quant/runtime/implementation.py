"""Current source verification with immutable historical-certificate provenance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

V3_MANIFEST = "reports/engineering/repository-health.json"
V4_MANIFEST = "reports/engineering/v4-integrity.json"
PARENT_MANIFEST = "reports/engineering/current-implementation-integrity.json"
HOTFIX_MANIFEST = "reports/engineering/release-hotfix-integrity.json"
V2_PREREQUISITE_MANIFEST = "reports/engineering/etf-quant-v2-integrity.json"
V2_BUILD_MANIFEST = "reports/engineering/etf-quant-v2-build-integrity.json"
V2_FINALIZATION_MANIFEST = "reports/engineering/etf-quant-v2-finalization-integrity.json"
V2_OBSERVATION_MANIFEST = "reports/engineering/etf-quant-v2-observation-integrity.json"
V2_FACTUAL_REFRESH_MANIFEST = "reports/engineering/etf-quant-v2-factual-refresh-integrity.json"
V2_FACTUAL_UNITS_MANIFEST = "reports/engineering/etf-quant-v2-factual-units-integrity.json"
V2_CONSOLE_MANIFEST = "reports/engineering/etf-quant-v2-console-integrity.json"
FORWARD_CLOSURE_MANIFEST = "reports/engineering/forward-shadow-closure-integrity.json"
ACTIVE_MANIFEST = "reports/engineering/shadow-operations-integrity.json"
PREVIOUS_MANIFEST = "reports/etf_quant/autonomous_code_integrity_v1.json"
PREVIOUS_TRANSITION = "docs/archive/engineering/public_repo_adversarial_remediation_v2.json"


class ImplementationIntegrityError(ValueError):
    """Active source or its recorded historical transition is inconsistent."""


def certificate_hash(integrity: Mapping[str, object]) -> str:
    """Bind every integrity field except its own digest; keys sort recursively.

    Compact UTF-8 JSON preserves array order and Unicode, without ASCII escaping.
    This is a repository-local consistency check, not externally signed provenance.
    """
    payload = {key: value for key, value in integrity.items() if key != "certificate_sha256"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def verify_implementation(root: Path) -> dict[str, str]:
    """Check source hashes; never read market data or sealed performance."""
    previous_bytes = (root / PREVIOUS_MANIFEST).read_bytes()
    previous = json.loads(previous_bytes)
    v3_bytes = (root / V3_MANIFEST).read_bytes()
    v3 = json.loads(v3_bytes)["implementation_integrity"]
    previous_transition = (root / PREVIOUS_TRANSITION).read_bytes()
    if (
        v3["identifier"] != "PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V3"
        or v3["previous_transition_sha256"] != hashlib.sha256(previous_transition).hexdigest()
        or v3["previous_certificate_sha256"] != hashlib.sha256(previous_bytes).hexdigest()
        or v3["previous_source_hashes"] != previous["files"]
        or v3["candidate_sha256"] != previous["candidate_sha256"]
        or not set(previous["files"]).issubset(v3["files"])
        or v3["certificate_sha256"]
        != hashlib.sha256(
            json.dumps(v3["files"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise ImplementationIntegrityError("IMPLEMENTATION_TRANSITION_BLOCKER")
    v4_bytes = (root / V4_MANIFEST).read_bytes()
    v4 = json.loads(v4_bytes)["implementation_integrity"]
    immutable = (
        "previous_certificate_sha256",
        "previous_transition_sha256",
        "previous_source_hashes",
        "candidate_sha256",
    )
    if (
        v4["identifier"] != "PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V4"
        or v4["parent_manifest_sha256"] != hashlib.sha256(v3_bytes).hexdigest()
        or not set(v3["files"]).issubset(v4["files"])
        or any(v4[key] != v3[key] for key in immutable)
        or v4["certificate_sha256"]
        != hashlib.sha256(
            json.dumps(v4["files"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise ImplementationIntegrityError("IMPLEMENTATION_TRANSITION_BLOCKER")
    changes = {item["path"]: item for item in v4["changes"]}
    for name, before in v3["files"].items():
        if before != v4["files"][name] and (
            name not in changes
            or changes[name]["before_sha256"] != before
            or changes[name]["after_sha256"] != v4["files"][name]
        ):
            raise ImplementationIntegrityError("IMPLEMENTATION_CHANGE_LEDGER_BLOCKER")
    parent, parent_bytes, parent_path = v4, v4_bytes, V4_MANIFEST
    for manifest_path in (
        PARENT_MANIFEST,
        HOTFIX_MANIFEST,
        V2_PREREQUISITE_MANIFEST,
        V2_BUILD_MANIFEST,
        V2_FINALIZATION_MANIFEST,
        V2_OBSERVATION_MANIFEST,
        V2_FACTUAL_REFRESH_MANIFEST,
        V2_FACTUAL_UNITS_MANIFEST,
        V2_CONSOLE_MANIFEST,
        FORWARD_CLOSURE_MANIFEST,
        ACTIVE_MANIFEST,
    ):
        current_bytes = (root / manifest_path).read_bytes()
        current = json.loads(current_bytes)["implementation_integrity"]
        if (
            current["identifier"] != "CURRENT_IMPLEMENTATION_INTEGRITY"
            or current["canonicalization"] != "JSON_SORTED_KEYS_COMPACT_UTF8_V1"
            or current["parent_manifest_path"] != parent_path
            or current["parent_manifest_sha256"] != hashlib.sha256(parent_bytes).hexdigest()
            or not set(parent["files"]).issubset(current["files"])
            or any(current[key] != parent[key] for key in immutable)
            or current["certificate_sha256"] != certificate_hash(current)
        ):
            raise ImplementationIntegrityError("IMPLEMENTATION_TRANSITION_BLOCKER")
        changes = {item["path"]: item for item in current["changes"]}
        for name, before in parent["files"].items():
            if before != current["files"][name] and (
                name not in changes
                or changes[name]["before_sha256"] != before
                or changes[name]["after_sha256"] != current["files"][name]
            ):
                raise ImplementationIntegrityError("IMPLEMENTATION_CHANGE_LEDGER_BLOCKER")
        parent, parent_bytes, parent_path = current, current_bytes, manifest_path
    files: dict[str, str] = current["files"]
    for name, expected in files.items():
        target = (root / name).resolve(strict=True)
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ImplementationIntegrityError("IMPLEMENTATION_PATH_BLOCKER")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ImplementationIntegrityError("IMPLEMENTATION_SOURCE_HASH_BLOCKER:" + name)
    return files

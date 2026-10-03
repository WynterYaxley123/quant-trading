"""Public configuration and certificate failures, without starting services."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from scripts.engineering.references import audit
from strategies.etf_quant.runtime.implementation import (
    ACTIVE_MANIFEST,
    PREVIOUS_MANIFEST,
    PREVIOUS_TRANSITION,
    ImplementationIntegrityError,
    certificate_hash,
    verify_implementation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_jupyter_requires_authentication_and_loopback():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    service = compose["services"]["jupyter"]
    assert service["ports"] == ["127.0.0.1:8888:8888"]
    assert (
        "JUPYTER_TOKEN=${JUPYTER_TOKEN:?Set a nonempty JUPYTER_TOKEN outside Git}"
        in service["environment"]
    )
    assert "JUPYTER_TOKEN:?" in service["command"]
    assert r"--IdentityProvider.token=\"$${JUPYTER_TOKEN}\"" in service["command"]


def test_document_aliases_and_archive_bytes_are_consistent():
    assert audit(ROOT)["status"] == "PASS"


def test_implementation_rejects_changed_source_and_forged_transition(tmp_path):
    files = verify_implementation(ROOT)
    for name in [*files, ACTIVE_MANIFEST, PREVIOUS_MANIFEST, PREVIOUS_TRANSITION]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    name = next(iter(files))
    source = tmp_path / name
    source.write_bytes(source.read_bytes() + b"\n# tampered\n")
    with pytest.raises(ImplementationIntegrityError, match="SOURCE_HASH_BLOCKER"):
        verify_implementation(tmp_path)
    manifest = tmp_path / ACTIVE_MANIFEST
    content = json.loads(manifest.read_text())
    content["implementation_integrity"]["files"][name] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    manifest.write_text(json.dumps(content))
    with pytest.raises(ImplementationIntegrityError, match="TRANSITION_BLOCKER"):
        verify_implementation(tmp_path)


@pytest.mark.parametrize("field", ["files", "changes", "parent_sha", "parent_manifest_path"])
def test_current_certificate_binds_source_ledger_and_transition_metadata(tmp_path, field):
    files = verify_implementation(ROOT)
    for name in [*files, ACTIVE_MANIFEST, PREVIOUS_MANIFEST, PREVIOUS_TRANSITION]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    manifest = tmp_path / ACTIVE_MANIFEST
    content = json.loads(manifest.read_text())
    integrity = content["implementation_integrity"]
    if field == "files":
        integrity[field][next(iter(files))] = "0" * 64
    elif field == "changes":
        integrity[field][0]["reason"] += " tampered"
    else:
        integrity[field] += "tampered"
    manifest.write_text(json.dumps(content))
    with pytest.raises(ImplementationIntegrityError, match="TRANSITION_BLOCKER"):
        verify_implementation(tmp_path)


def test_current_certificate_accepts_recursive_key_reordering_and_stable_payload(tmp_path):
    files = verify_implementation(ROOT)
    for name in [*files, ACTIVE_MANIFEST, PREVIOUS_MANIFEST, PREVIOUS_TRANSITION]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    manifest = tmp_path / ACTIVE_MANIFEST
    content = json.loads(manifest.read_text())

    def reordered(value):
        if isinstance(value, dict):
            return {key: reordered(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reordered(item) for item in value]
        return value

    integrity = content["implementation_integrity"]
    assert certificate_hash(integrity) == certificate_hash(reordered(integrity))
    assert certificate_hash(integrity) == integrity["certificate_sha256"]
    manifest.write_text(json.dumps(reordered(content), ensure_ascii=False))
    assert verify_implementation(tmp_path) == files

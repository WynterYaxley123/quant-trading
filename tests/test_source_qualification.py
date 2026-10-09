"""Adversarial qualification checks, synthetic evidence only, never provider data."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from research.evidence.acquisition import NoRedirect, response_receipt, target, verify_document
from research.evidence.contracts import Denied, SyntheticAuthority, sha
from research.evidence.qualification import (
    QUALITY_CHECKS,
    RIGHTS,
    real_registry_preflight,
    synthetic_preflight,
)
from research.evidence.source_admission import Source

NOW = "2026-01-15T09:00:00+08:00"


def fixture():
    authority = SyntheticAuthority(synthetic_only=True)
    source = Source(
        "qualification-fixture",
        sha(b"source"),
        sha(b"contract"),
        "SWCLASS2021",
        "synthetic-members",
        "RECONSTRUCTED_INDUSTRY_RETURN",
        "A",
        sha(b"revision"),
    )
    binding = {"source_digest": source.digest}
    claims = {
        "metadata": {
            **binding,
            "identity_reference": "synthetic-reference",
            "upstream_origin": "synthetic-origin-a",
        },
        "rights": {
            **binding,
            "research_use": "PERMITTED",
            "redistribution": "PROHIBITED",
            "evidence_reference": "synthetic-grant",
            "scope": dict.fromkeys(RIGHTS, "PERMITTED"),
            "basis": "DATASET_SPECIFIC_GRANT",
            "conflicts": [],
            "conditions_satisfied": True,
            "valid_from": "2026-01-01T00:00:00+08:00",
            "valid_until": "2027-01-01T00:00:00+08:00",
            "contract_hash": source.data_contract_hash,
        },
        "pit": {
            **binding,
            "tier": "A",
            "availability_basis": "CONTEMPORANEOUS_RECEIPT",
            "taxonomy_identity": source.taxonomy_identity,
            "membership_identity": source.membership_identity,
            "published_at": "2026-01-02T08:00:00+08:00",
            "observed_at": "2026-01-02T08:01:00+08:00",
            "ingested_at": "2026-01-02T08:02:00+08:00",
            "signal_at": "2026-01-02T15:00:00+08:00",
            "revised_at": "2026-01-02T08:00:00+08:00",
            "snapshot_hash": sha(b"snapshot"),
            "receipt_scope": "FULL_REQUIRED_UNIVERSE",
        },
        "quality": {
            **binding,
            "revision_identity": source.revision_identity,
            "assessment_scope": "AUTHORIZED_BLIND_NUMERIC_QA",
            "performance_fields": [],
            "checks": dict.fromkeys(QUALITY_CHECKS, "PASS"),
            "independent_origin": "synthetic-origin-b",
            "method_equivalence": "VERIFIED",
            "evidence_reference": "synthetic-quality",
        },
    }
    return source, authority, claims


def run(claims, source, authority):
    proofs = tuple(authority.issue(k, v) for k, v in claims.items())
    return synthetic_preflight(source, authority, proofs, now=NOW)


def test_synthetic_complete_review_never_promotes_production():
    source, authority, claims = fixture()
    claims["rights"]["scope"]["redistribution"] = "PROHIBITED"
    result = run(claims, source, authority)
    assert result.state == "QUALIFIED_SYNTHETIC_ONLY" and not result.production_admission
    assert real_registry_preflight(asdict(source))["real_sources_admitted"] == 0
    with pytest.raises(Denied, match="SIGNATURE_AUTHORITY_NOT_ESTABLISHED"):
        SyntheticAuthority(synthetic_only=False)


@pytest.mark.parametrize(
    "basis",
    ["SOFTWARE_LICENSE", "PUBLIC_WEBSITE", "verified=true", "APP_TERMS", "OTHER_DATASET_GRANT"],
)
def test_non_dataset_grant_is_not_rights(basis):
    source, authority, claims = fixture()
    claims["rights"]["basis"] = basis
    with pytest.raises(Denied, match="DATASET_GRANT_REQUIRED"):
        run(claims, source, authority)


@pytest.mark.parametrize(
    "field",
    [
        "dataset_access",
        "local_storage",
        "internal_research",
        "automated_processing",
        "derived_data",
        "retention",
        "revision_access",
    ],
)
def test_restricted_or_missing_required_right(field):
    source, authority, claims = fixture()
    claims["rights"]["scope"][field] = "CONDITIONAL"
    with pytest.raises(Denied, match="RIGHTS_SCOPE_BLOCKED"):
        run(claims, source, authority)


@pytest.mark.parametrize(
    ("purpose", "field", "value", "code"),
    [
        ("rights", "valid_until", "2026-01-03T00:00:00+08:00", "RIGHTS_EXPIRED"),
        ("rights", "conflicts", ["conflicting-contract"], "RIGHTS_CONFLICT"),
        ("rights", "conditions_satisfied", False, "RIGHTS_CONFLICT"),
        ("rights", "contract_hash", sha(b"different-contract"), "RIGHTS_CONTRACT_SCOPE"),
        ("pit", "published_at", "2026-01-03T08:00:00+08:00", "PIT_NOT_AVAILABLE"),
        ("pit", "observed_at", "2026-01-01T08:00:00+08:00", "PIT_NOT_AVAILABLE"),
        ("pit", "ingested_at", "2026-01-03T08:00:00+08:00", "PIT_NOT_AVAILABLE"),
        ("pit", "revised_at", "2026-01-04T08:00:00+08:00", "PIT_REVISION_AFTER"),
        ("pit", "taxonomy_identity", "STALE_HIERARCHY", "PIT_TAXONOMY"),
        ("pit", "membership_identity", "BACKFILLED_CURRENT_MEMBERS", "PIT_TAXONOMY"),
        ("pit", "snapshot_hash", "", "HASH_INVALID"),
        ("pit", "receipt_scope", "ONE_MEMBER_ONLY", "PIT_SNAPSHOT"),
        ("quality", "revision_identity", sha(b"other-generation"), "QUALITY_REVISION"),
        ("quality", "assessment_scope", "METADATA_ONLY", "QUALITY_SCOPE"),
        ("quality", "performance_fields", ["RankIC"], "QUALITY_SCOPE"),
        ("quality", "independent_origin", "synthetic-origin-a", "INDEPENDENT_SOURCE"),
        ("quality", "method_equivalence", "DIFFERENT_ADJUSTMENT_METHODS", "QUALITY_METHOD"),
    ],
)
def test_bound_scope_and_temporal_proofs(purpose, field, value, code):
    source, authority, claims = fixture()
    claims[purpose][field] = value
    with pytest.raises(Denied, match=code):
        run(claims, source, authority)


@pytest.mark.parametrize("check", sorted(QUALITY_CHECKS))
def test_quality_defect_prevents_qualification(check):
    source, authority, claims = fixture()
    claims["quality"]["checks"][check] = "DEFECT_OR_NOT_ESTABLISHED"
    with pytest.raises(Denied, match="QUALITY_INCOMPLETE"):
        run(claims, source, authority)


def test_forged_approval_and_another_generation_are_rejected():
    source, authority, claims = fixture()
    proofs = tuple(authority.issue(k, v) for k, v in claims.items())
    forged = replace(proofs[0], signature="0" * 64)
    with pytest.raises(Denied, match="UNTRUSTED_EVIDENCE"):
        synthetic_preflight(source, authority, (forged, *proofs[1:]), now=NOW)
    with pytest.raises(Denied, match="SOURCE_IDENTITY_MISMATCH"):
        synthetic_preflight(
            replace(source, revision_identity=sha(b"revision-two")), authority, proofs, now=NOW
        )


def test_absent_and_incomplete_proofs_do_not_promote():
    source, authority, claims = fixture()
    assert synthetic_preflight(source, authority, (), now=NOW).state == "SOURCE_BLOCKED"
    claims["rights"]["research_use"] = "UNKNOWN"
    assert run(claims, source, authority).reason == "BLOCKED_UNVERIFIED_RIGHTS"


def document_fixture():
    t = target("sse-legal")
    raw = b"<!doctype html><html>synthetic legal statement</html>"
    receipt = response_receipt(t, final_url=t.url, media=t.media, raw=raw, retrieved_at=NOW)
    return t, raw, receipt


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("content_sha256", "0" * 64, "DOCUMENT_HASH"),
        ("publisher", "untrusted-publisher", "DOCUMENT_IDENTITY"),
        ("source_url", "https://example.invalid/", "DOCUMENT_IDENTITY"),
        ("final_url", "https://example.invalid/", "DOCUMENT_REDIRECT"),
        ("retrieved_at", "2025-01-01T00:00:00+08:00", "DOCUMENT_REVIEW_STALE"),
        ("retrieved_at", "2027-01-01T00:00:00+08:00", "DOCUMENT_REVIEW_STALE"),
    ],
)
def test_document_forgeries_and_staleness(field, value, code):
    t, raw, receipt = document_fixture()
    receipt[field] = value
    with pytest.raises(Denied, match=code):
        verify_document(
            receipt, raw, document_id=t.document_id, markers=("synthetic legal",), now=NOW
        )


def test_exact_document_claim_is_not_dataset_permission():
    t, raw, receipt = document_fixture()
    assert "NOT_DATASET_AUTHORIZATION" in verify_document(
        receipt, raw, document_id=t.document_id, markers=("synthetic legal",), now=NOW
    )
    with pytest.raises(Denied, match="DOCUMENT_CLAIM_MISMATCH"):
        verify_document(
            receipt,
            raw,
            document_id=t.document_id,
            markers=("unconditional redistribution",),
            now=NOW,
        )


@pytest.mark.parametrize(
    "name",
    ["../data", "C:/private", "https://evil.invalid", "tdx-terms?url=private", "credentials"],
)
def test_no_arbitrary_network_or_path(name):
    with pytest.raises(Denied, match="DOCUMENT_NOT_ALLOWLISTED"):
        target(name)


@pytest.mark.parametrize(
    ("media", "raw"),
    [
        ("application/zip", b"PKpayload"),
        ("text/html", b"MZpayload"),
        ("application/octet-stream", b"binary"),
    ],
)
def test_unsafe_document_payload(media, raw):
    t = target("sse-legal")
    with pytest.raises(Denied):
        response_receipt(t, final_url=t.url, media=media, raw=raw, retrieved_at=NOW)


def test_redirect_is_rejected_before_destination_request():
    import urllib.error
    import urllib.request

    with pytest.raises(urllib.error.HTTPError, match="REDIRECT_REJECTED"):
        NoRedirect().redirect_request(
            urllib.request.Request(target("sse-legal").url),
            None,
            302,
            "redirect",
            {},
            "https://evil.invalid",
        )


def test_pdf_active_content_and_wrong_magic():
    t = target("baostock-adjustment")
    for raw in (b"<!doctype html>error", b"%PDF-1.7 /JavaScript evil", b"%PDF-1.7 /Launch evil"):
        with pytest.raises(Denied):
            response_receipt(t, final_url=t.url, media=t.media, raw=raw, retrieved_at=NOW)


def test_reviewed_gb2312_bytes_do_not_fail_claim_identity():
    t = target("sina-copyright")
    raw = '<html><meta charset="gb2312">合成许可声明</html>'.encode("gb2312")
    receipt = response_receipt(t, final_url=t.url, media=t.media, raw=raw, retrieved_at=NOW)
    assert "NOT_DATASET_AUTHORIZATION" in verify_document(
        receipt, raw, document_id=t.document_id, markers=("合成许可",), now=NOW
    )


def test_public_reports_reproduce_without_promotion_or_parallel_registry():
    import json
    from pathlib import Path

    from scripts.engineering.source_qualification import REPORT_DIR, build

    root = Path(__file__).resolve().parents[1]
    reports = build(root)
    assert len(reports) == 9
    for name, data in reports.items():
        assert json.loads((root / REPORT_DIR / f"{name}.json").read_bytes()) == data
    results = reports["admission-results"]
    assert results["real_sources_admitted"] == 0
    assert all(
        s["proofs_supplied"] == 0 and not s["production_admission"] for s in results["sources"]
    )
    assert sum(s["existing_registry_state"] == "SOURCE_UNREVIEWED" for s in results["sources"]) == 4
    assert reports["final-readiness"]["official_documents_verified"] == 15
    assert reports["final-readiness"]["current_sources_audited"] == 12


def test_pr34_admission_and_isolation_semantics_stay_byte_identical():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for name in (
        "contracts",
        "source_admission",
        "numeric",
        "prospective",
        "ledger",
        "anchor",
        "worker",
    ):
        relative = f"research/evidence/{name}.py"
        before = subprocess.check_output(
            ["git", "show", f"fb82ce96e278b032d9113b6ecfcef7d06dd4f187:{relative}"], cwd=root
        )
        assert sha(before) == sha((root / relative).read_bytes())

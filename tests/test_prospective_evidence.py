"""Synthetic source/PIT, numeric isolation and prospective adversarial acceptance."""

from __future__ import annotations

import multiprocessing
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from examples.prospective_evidence_demo.__main__ import run
from examples.prospective_evidence_demo.fixture import event, observation, observed_payload, setup
from research.evidence import anchor as anchors
from research.evidence.contracts import Denied, Proof, SyntheticAuthority, canonical, sha
from research.evidence.ledger import EvidenceLedger, read
from research.evidence.numeric import Boundary, consume, grant_claims, materialize, safe_read
from research.evidence.prospective import (
    accounting,
    activation,
    maturity,
    purge,
    verify_observation,
)
from research.evidence.source_admission import SourceRegistry, admit
from strategies.etf_quant.runtime import storage


@pytest.fixture
def domain():
    return setup()


def source_proofs(authority, source, *, rights="PERMITTED", basis="CONTEMPORANEOUS_RECEIPT"):
    return tuple(
        authority.issue(p, {"source_digest": source.digest, **claim})
        for p, claim in (
            ("metadata", {"identity_reference": "synthetic-provider"}),
            (
                "rights",
                {
                    "research_use": rights,
                    "redistribution": "UNKNOWN",
                    "evidence_reference": "synthetic-license",
                },
            ),
            ("pit", {"tier": source.tier, "availability_basis": basis}),
        )
    )


def test_production_authority_is_not_self_attested():
    with pytest.raises(Denied, match="SIGNATURE_AUTHORITY_NOT_ESTABLISHED"):
        SyntheticAuthority(synthetic_only=False)


@pytest.mark.parametrize("right", ["UNKNOWN", "PROHIBITED", None, True, "verified"])
def test_rights_fail_closed(domain, right):
    authority, registry, protocol, _, _ = domain
    source = registry.get(protocol.source_digest).source
    result = admit(
        source, authority, source_proofs(authority, source, rights=right), required_tier="A"
    )
    assert result.state == "SOURCE_BLOCKED"


def test_missing_source_missing_rights_missing_pit(domain):
    authority, registry, protocol, _, _ = domain
    source = registry.get(protocol.source_digest).source
    proofs = source_proofs(authority, source)
    assert admit(source, authority, (), required_tier="A").state == "SOURCE_UNREVIEWED"
    assert (
        admit(source, authority, proofs[:1], required_tier="A").reason
        == "BLOCKED_UNVERIFIED_RIGHTS"
    )
    assert admit(source, authority, proofs[:2], required_tier="A").state == "SOURCE_RIGHTS_VERIFIED"
    with pytest.raises(Denied, match="SOURCE_NOT_REGISTERED"):
        registry.get(sha(b"missing"))


def test_boolean_forgery_wrong_issuer_scope_source(domain):
    authority, registry, protocol, _, _ = domain
    source = registry.get(protocol.source_digest).source
    forged = Proof("user", "rights", canonical({"verified": True}), "a" * 64)
    with pytest.raises(Denied, match="UNTRUSTED_EVIDENCE"):
        admit(source, authority, (forged,), required_tier="A")
    with pytest.raises(Denied, match="SOURCE_IDENTITY_MISMATCH"):
        admit(
            source,
            authority,
            (authority.issue("metadata", {"source_digest": sha(b"wrong")}),),
            required_tier="A",
        )
    with pytest.raises(Denied, match="ADMISSION_PURPOSE_INVALID"):
        admit(
            source, authority, (authority.issue("performance", {"rank_ic": 1}),), required_tier="A"
        )


@pytest.mark.parametrize(
    "tier,basis,admitted",
    [
        ("A", "RECONSTRUCTED_PROVENANCE", False),
        ("B", "VERIFIED_EFFECTIVE_DATED_RECONSTRUCTION", False),
        ("C", "RECONSTRUCTED_PROVENANCE", False),
        ("D", "CURRENT_ONLY", False),
        ("A", "CONTEMPORANEOUS_RECEIPT", True),
    ],
)
def test_pit_tier_not_upgraded(domain, tier, basis, admitted):
    authority, registry, protocol, _, _ = domain
    source = replace(registry.get(protocol.source_digest).source, tier=tier)
    result = admit(
        source, authority, source_proofs(authority, source, basis=basis), required_tier="A"
    )
    assert (result.state == "SOURCE_ADMITTED") is admitted
    assert source.kind == "RECONSTRUCTED_INDUSTRY_RETURN"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("source_published_at", "2028-01-10T18:00:00+08:00", "AVAILABILITY_NOT_VERIFIED"),
        ("source_published_at", "2028-01-10", "TIMESTAMP_PROOF_REQUIRED"),
        ("source_finalized_at", "2028-01-11T16:00:00+08:00", "AVAILABILITY_NOT_VERIFIED"),
        ("exchange_session", "2028-01-03", "BACKDATED_OBSERVATION_DENIED"),
        ("observed_at", "2028-01-11T16:05:00+08:00", "AVAILABILITY_NOT_VERIFIED"),
        ("model_universe_hash", "a" * 64, "MODEL_UNIVERSE_DRIFT"),
        ("constituent_coverage", "MISSING", "FACT_NOT_FINALIZED"),
        ("suspension_status", "UNKNOWN", "FACT_NOT_FINALIZED"),
        ("delisting_status", "UNKNOWN", "FACT_NOT_FINALIZED"),
        ("revision_identity", "b" * 64, "SOURCE_IDENTITY_MISMATCH"),
    ],
)
def test_factual_receipts_fail_closed(domain, field, value, code):
    authority, registry, protocol, calendar, anchor = domain
    receipt = replace(observation(protocol, registry, "2028-01-10"), **{field: value})
    proof = authority.issue("fact", {"receipt_hash": receipt.digest})
    with pytest.raises(Denied, match=code):
        verify_observation(
            receipt,
            proof,
            protocol,
            activation(protocol, anchor, calendar, authority),
            registry,
            authority,
        )


def numeric_fixture(root, domain, layout="C", poison="none"):
    authority, registry, protocol, _, _ = domain
    features = np.arange(len(protocol.sessions) * 3 * 2, dtype=float).reshape(-1, 3, 2)
    returns = np.arange(len(protocol.sessions) * 3, dtype=float).reshape(-1, 3)
    if poison == "positive":
        returns[12:] = 1e200
    if poison == "negative":
        returns[12:] = -1e200
    if poison == "nan":
        returns[12:] = np.nan
    if poison == "reordered":
        returns[12:] = returns[12:, ::-1]
    if poison == "feature":
        features[16:] = -1e200
    if poison == "induced":
        returns[12:] = features[12:, :, 0] * 1e100
    if layout == "F":
        features, returns = np.asfortranarray(features), np.asfortranarray(returns)
    mother = root / "mother.npz"
    save = np.savez_compressed if layout == "compressed" else np.savez
    save(
        mother,
        sessions=np.array(protocol.sessions),
        universe=np.array(protocol.model_universe),
        features=features,
        returns=returns,
    )
    boundary = Boundary(
        "development",
        protocol.sessions[1],
        protocol.sessions[15],
        protocol.sessions[15],
        protocol.sessions[11],
        (10,),
        "2029-01-01T00:00:00Z",
    )
    facts_hash = sha(b"synthetic finalized receipt set")
    grant = authority.issue("phase", grant_claims(protocol, boundary, facts_hash))
    manifest = materialize(
        mother,
        root / "views" / "view",
        protocol,
        boundary,
        grant,
        registry,
        authority,
        now="2028-02-01T16:00:00+08:00",
        facts_hash=facts_hash,
        activation_anchor=domain[4],
        calendar=domain[3],
    )
    return mother, boundary, manifest


def consume_fixture(root, domain, permitted_boundary, manifest, **overrides):
    _, registry, protocol, _, _ = domain
    source = registry.get(protocol.source_digest).source
    kwargs = dict(
        pinned_manifest_hash=sha(canonical(manifest)),
        protocol=protocol,
        boundary=permitted_boundary,
        source_hash=source.source_hash,
        data_contract_hash=source.data_contract_hash,
        now="2028-02-01T16:00:00+08:00",
    )
    kwargs.update(overrides)
    return consume(root / "views" / "view", **kwargs)


@pytest.mark.parametrize("layout", ["C", "F", "compressed"])
@pytest.mark.parametrize(
    "poison", ["positive", "negative", "nan", "reordered", "feature", "induced"]
)
def test_future_poison_never_changes_permitted_bytes(tmp_path, domain, layout, poison):
    base = tmp_path / "base"
    poisoned = tmp_path / "poisoned"
    base.mkdir()
    poisoned.mkdir()
    _, boundary, manifest = numeric_fixture(base, domain, layout)
    _, changed_boundary, changed = numeric_fixture(poisoned, domain, layout, poison)
    assert manifest["content_hash"] == changed["content_hash"]
    before = consume_fixture(base, domain, boundary, manifest)
    after = consume_fixture(poisoned, domain, changed_boundary, changed)
    assert before["derived_hash"] == after["derived_hash"]
    assert before["feature_rows"] == 15 and before["return_rows"] == 11
    assert set((poisoned / "views" / "view").iterdir()) == {
        poisoned / "views" / "view" / n for n in ("manifest.json", "features.npy", "returns.npy")
    }
    if poison != "none":
        assert manifest["mother_snapshot_hash"] != changed["mother_snapshot_hash"]


@pytest.mark.parametrize(
    "name",
    [
        "../mother.npz",
        "features.npy/../returns.npy",
        "/mother.npz",
        r"D:\mother.npz",
        r"\\host\data",
        "mother.npz!returns.npy",
        "returns.npy:stream",
    ],
)
def test_path_escape_denied_before_open(tmp_path, domain, name):
    numeric_fixture(tmp_path, domain)
    with pytest.raises(Denied, match="PATH_ESCAPE_DENIED"):
        safe_read(tmp_path / "views" / "view", name)


def test_manifest_hash_source_phase_dates_stale_universe_before_decode(
    tmp_path, domain, monkeypatch
):
    _, boundary, manifest = numeric_fixture(tmp_path, domain)

    def no_decode(*args, **kwargs):
        raise AssertionError("numeric decode was reached")

    monkeypatch.setattr(np, "load", no_decode)
    for overrides, code in [
        ({"pinned_manifest_hash": ""}, "DATA_ACCESS_DENIED"),
        ({"pinned_manifest_hash": "f" * 64}, "MANIFEST_HASH_MISMATCH"),
        ({"source_hash": "e" * 64}, "SOURCE_IDENTITY_MISMATCH"),
        ({"now": "2030-01-01T00:00:00Z"}, "STALE_CAPABILITY"),
        ({"boundary": replace(boundary, phase="unregistered")}, "PHASE_NOT_REGISTERED"),
        (
            {"boundary": replace(boundary, realized_return_cutoff=domain[2].sessions[12])},
            "DATE_BOUNDARY_MISMATCH",
        ),
        ({"protocol": replace(domain[2], model_universe=("different",))}, "PROTOCOL_HASH_MISMATCH"),
    ]:
        with pytest.raises(Denied, match=code):
            consume_fixture(tmp_path, domain, boundary, manifest, **overrides)


def test_symlink_hardlink_unexpected_member_and_content_poison(tmp_path, domain):
    mother, boundary, manifest = numeric_fixture(tmp_path, domain)
    view = tmp_path / "views" / "view"
    view.chmod(0o755)
    leaf = view / "returns.npy"
    original = leaf.read_bytes()
    leaf.unlink()
    leaf.symlink_to(mother)
    with pytest.raises(Denied, match="PATH_ESCAPE_DENIED"):
        consume_fixture(tmp_path, domain, boundary, manifest)
    leaf.unlink()
    os.link(mother, leaf)
    with pytest.raises(Denied, match="PATH_ESCAPE_DENIED"):
        consume_fixture(tmp_path, domain, boundary, manifest)
    leaf.unlink()
    leaf.write_bytes(original + b"poison")
    with pytest.raises(Denied, match="CONTENT_HASH_MISMATCH"):
        consume_fixture(tmp_path, domain, boundary, manifest)
    (view / "unexpected.npz").write_bytes(b"forbidden")
    with pytest.raises(Denied, match="UNEXPECTED_VIEW_MEMBER"):
        consume_fixture(tmp_path, domain, boundary, manifest)


def test_toctou_descriptor_replacement(tmp_path, domain, monkeypatch):
    numeric_fixture(tmp_path, domain)
    view = tmp_path / "views" / "view"
    actual = os.open

    def replace_before_open(path, flags):
        view.chmod(0o755)
        replacement = view / "replacement"
        replacement.write_bytes(b"replacement")
        os.replace(replacement, path)
        return actual(path, flags)

    monkeypatch.setattr(os, "open", replace_before_open)
    with pytest.raises(Denied, match="TOCTOU_DENIED"):
        safe_read(view, "returns.npy")


def test_authority_denies_before_mother_decode(tmp_path, domain, monkeypatch):
    authority, registry, protocol, _, _ = domain
    boundary = Boundary(
        "unauthorized",
        protocol.sessions[1],
        protocol.sessions[15],
        protocol.sessions[15],
        protocol.sessions[11],
        (10,),
        "2029-01-01T00:00:00Z",
    )
    monkeypatch.setattr(np, "load", lambda *a, **k: pytest.fail("decoded full panel"))
    with pytest.raises(Denied, match="PHASE_NOT_REGISTERED"):
        materialize(
            tmp_path / "missing.npz",
            tmp_path / "views" / "view",
            protocol,
            boundary,
            authority.issue("phase", {}),
            registry,
            authority,
            now="2028-02-01T00:00:00Z",
            facts_hash=sha(b"facts"),
            activation_anchor=domain[4],
            calendar=domain[3],
        )


def test_logical_firewall_cannot_read_mother(tmp_path, domain):
    mother, boundary, manifest = numeric_fixture(tmp_path, domain)
    with pytest.raises(Denied):
        source = domain[1].get(domain[2].source_digest).source
        consume(
            mother.parent,
            pinned_manifest_hash=sha(canonical(manifest)),
            protocol=domain[2],
            boundary=boundary,
            source_hash=source.source_hash,
            data_contract_hash=source.data_contract_hash,
            now="2028-02-01T16:00:00+08:00",
        )
    with pytest.raises(Denied, match="DATA_ACCESS_DENIED"):
        authority, registry, protocol, _, _ = domain
        materialize(
            mother,
            tmp_path / "views" / "view",
            protocol,
            boundary,
            authority.issue("phase", {}),
            registry,
            authority,
            now="2028-02-01T00:00:00Z",
            facts_hash=sha(b"facts"),
            activation_anchor=domain[4],
            calendar=domain[3],
        )


def maturity_fixture(domain, horizon):
    authority, registry, protocol, calendar, anchor = domain
    first = activation(protocol, anchor, calendar, authority)
    receipts = {s: observation(protocol, registry, s) for s in protocol.sessions[1 : horizon + 2]}
    proofs = {
        s: authority.issue("fact", {"receipt_hash": receipt.digest})
        for s, receipt in receipts.items()
    }
    kwargs = dict(
        authorized_phase="validation",
        quarantined=set(),
        registry=registry,
        authority=authority,
        first_session=first,
        fact_proofs=proofs,
    )
    return protocol, first, receipts, kwargs


@pytest.mark.parametrize("horizon", [10, 40, 120])
def test_exact_exchange_maturity_complete_not_calendar_days(domain, horizon):
    protocol, first, receipts, kwargs = maturity_fixture(domain, horizon)
    result = maturity(protocol, first, horizon, receipts, **kwargs)
    assert result["status"] == "MATURED"
    assert result["maturity_session"] == protocol.sessions[horizon + 1]
    assert "2028-01-06" not in result["sessions"]  # Synthetic holiday.
    del receipts[protocol.sessions[horizon + 1]]
    assert maturity(protocol, first, horizon, receipts, **kwargs)["status"] == "PENDING_MATURITY"


def test_forged_finalized_receipt_cannot_mature(domain):
    protocol, first, receipts, kwargs = maturity_fixture(domain, 10)
    day = protocol.sessions[2]
    receipts[day] = replace(receipts[day], factual_snapshot_hash="f" * 64)
    with pytest.raises(Denied, match="UNTRUSTED_EVIDENCE"):
        maturity(protocol, first, 10, receipts, **kwargs)


def test_revision_quarantine_and_missing_sessions_block_maturity(domain):
    protocol, first, receipts, kwargs = maturity_fixture(domain, 10)
    kwargs["quarantined"] = {protocol.sessions[2]}
    assert maturity(protocol, first, 10, receipts, **kwargs)["status"] == "PENDING_MATURITY"
    registry = domain[1]
    source = registry.get(protocol.source_digest).source
    revised = replace(source, revision_identity="d" * 64)
    assert registry.revision(source, revised) == "SOURCE_TRANSITION_REQUIRED"
    with pytest.raises(Denied, match="FACT_REVISION_QUARANTINED"):
        registry.get(source.digest)


def test_126_h120_signals_are_dependent_and_need_245_outcome_sessions(domain):
    protocol = domain[2]
    result = accounting(protocol, protocol.sessions[1:127], 120)
    assert result["distinct_outcome_sessions"] == 245
    assert result["overlapping_outcomes"] is True
    assert result["independent_experiments"] is None
    with pytest.raises(Denied, match="PHASE_OUTCOME_OVERLAP"):
        purge(protocol, protocol.sessions[1], protocol.sessions[121], 120)
    purge(protocol, protocol.sessions[1], protocol.sessions[122], 120)


@pytest.mark.parametrize(
    "change",
    [
        {"merged": False},
        {"result_history": "PRESENT"},
        {"main_ancestry": "UNKNOWN"},
        {"protocol_hash": "a" * 64},
        {"transport": "user-reported"},
    ],
)
def test_anchor_forgery_unmerged_and_results_are_rejected(domain, change):
    authority, _, protocol, calendar, anchor = domain
    claims = authority.verify(anchor, "anchor")
    with pytest.raises(Denied, match="PROSPECTIVE_ACTIVATION_NOT_VERIFIED"):
        activation(protocol, authority.issue("anchor", {**claims, **change}), calendar, authority)


def test_author_time_has_no_effect_and_same_day_is_excluded(domain):
    authority, _, protocol, calendar, anchor = domain
    first = activation(protocol, anchor, calendar, authority)
    claims = authority.verify(anchor, "anchor")
    assert first == "2028-01-04"
    assert (
        activation(
            protocol,
            authority.issue("anchor", {**claims, "author_date": "2099-01-01T00:00:00Z"}),
            calendar,
            authority,
        )
        == first
    )


def append_event(ledger, authority, protocol, name, kind, at, payload):
    body = event(protocol, kind, at, payload)
    proof = authority.issue("event", {"body_hash": sha(canonical(body))})
    return ledger.append(name, body, proof)


def ledger_fixture(root, domain):
    authority, registry, protocol, calendar, anchor = domain
    ledger = EvidenceLedger(root / "prospective" / "synthetic-test", protocol, registry, authority)
    at = "2028-01-03T11:00:00+08:00"
    append_event(
        ledger,
        authority,
        protocol,
        "protocol",
        "PROTOCOL_REGISTERED",
        at,
        {"calendar": calendar.as_dict()},
    )
    append_event(ledger, authority, protocol, "source", "SOURCE_ADMITTED", at, {})
    append_event(
        ledger,
        authority,
        protocol,
        "activation",
        "ACTIVATION_BOUND",
        at,
        {"anchor": anchor.as_dict(), "first_session": "2028-01-04"},
    )
    return ledger


def test_demo_complete_and_phase_cannot_reopen(tmp_path, domain):
    result = run(tmp_path)
    assert result["scope"] == "SYNTHETIC_ONLY"
    assert result["ledger_state"] == "PHASE_CONSUMED"
    assert result["future_read_denied"] is True
    assert result["real_evidence_created"] == 0
    events = read(tmp_path / "prospective" / "synthetic-demo")
    assert len(events) == result["events"]
    assert events[-1]["body"]["kind"] == "ACCESS_VIEW_CONSUMED"


def test_ledger_idempotency_tamper_reset_forgery_backdate(tmp_path, domain):
    authority, registry, protocol, calendar, _ = domain
    ledger = ledger_fixture(tmp_path, domain)
    existing = read(ledger.root)[0]
    assert (
        ledger.append("protocol", existing["body"], Proof.parse(existing["proof"]))
        == "NOOP_ALREADY_PUBLISHED"
    )
    with pytest.raises(Denied, match="DUPLICATE_EVENT_CONFLICT"):
        ledger.append(
            "protocol", {**existing["body"], "kind": "RESET"}, Proof.parse(existing["proof"])
        )
    with pytest.raises(Denied, match="BACKDATED_EVENT_DENIED"):
        append_event(
            ledger, authority, protocol, "backdated", "FACT_FINALIZED", "2020-01-01T00:00:00Z", {}
        )
    with pytest.raises(Denied, match="UNTRUSTED_EVIDENCE"):
        ledger.append("forged", existing["body"], Proof("user", "event", b"{}", "f" * 64))
    with pytest.raises(Denied, match="INVALID_LIFECYCLE_TRANSITION"):
        append_event(
            ledger,
            authority,
            protocol,
            "reopen",
            "PROTOCOL_REGISTERED",
            "2028-01-04T11:00:00+08:00",
            {"calendar": calendar.as_dict()},
        )
    (ledger.root / "latest.json").unlink()
    with pytest.raises(Denied, match="LEDGER_RESET_DENIED"):
        ledger.status()


@pytest.mark.parametrize(
    "category", ["membership", "adjusted_close", "delisting", "calendar", "symbol", "coverage"]
)
def test_all_fact_revision_categories_preserve_original_and_block(tmp_path, domain, category):
    authority, _, protocol, _, _ = domain
    ledger = ledger_fixture(tmp_path, domain)
    day = protocol.sessions[1]
    receipt = observation(protocol, domain[1], day)
    at = day + "T16:05:00+08:00"
    append_event(
        ledger,
        authority,
        protocol,
        "observed",
        "FACT_SNAPSHOT_OBSERVED",
        at,
        observed_payload(receipt, authority),
    )
    append_event(
        ledger,
        authority,
        protocol,
        "revised",
        "EVIDENCE_REVISION_DETECTED",
        at,
        {
            "session": day,
            "category": category,
            "original_hash": receipt.digest,
            "new_hash": "f" * 64,
        },
    )
    append_event(
        ledger, authority, protocol, "quarantined", "EVIDENCE_QUARANTINED", at, {"session": day}
    )
    assert ledger.status()["state"] == "BLOCKED"
    assert (
        read(ledger.root)[3]["body"]["payload"]["receipt"]["factual_snapshot_hash"]
        == receipt.factual_snapshot_hash
    )
    with pytest.raises(Denied):
        append_event(
            ledger,
            authority,
            protocol,
            "new",
            "FACT_SNAPSHOT_OBSERVED",
            at,
            observed_payload(receipt, authority),
        )


def test_crash_recovery_retries_publication_without_reopening(tmp_path, domain, monkeypatch):
    authority, registry, protocol, calendar, _ = domain
    ledger = EvidenceLedger(
        tmp_path / "prospective" / "synthetic-crash", protocol, registry, authority
    )
    original = storage.atomic_bytes

    def crash_pointer(path, payload, **kwargs):
        if path.name == "latest.json":
            raise RuntimeError("synthetic crash")
        return original(path, payload, **kwargs)

    monkeypatch.setattr(storage, "atomic_bytes", crash_pointer)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        append_event(
            ledger,
            authority,
            protocol,
            "protocol",
            "PROTOCOL_REGISTERED",
            "2028-01-03T11:00:00+08:00",
            {"calendar": calendar.as_dict()},
        )
    monkeypatch.setattr(storage, "atomic_bytes", original)
    assert ledger.status()["state"] == "PREREGISTERED"
    assert (
        append_event(
            ledger,
            authority,
            protocol,
            "protocol",
            "PROTOCOL_REGISTERED",
            "2028-01-03T11:00:00+08:00",
            {"calendar": calendar.as_dict()},
        )
        == "NOOP_ALREADY_PUBLISHED"
    )


def _lock_child(path, connection):
    with storage.process_lock(Path(path)):
        connection.send("locked")
        connection.recv()


def test_real_process_mutex_denies_concurrent_publication(tmp_path, domain):
    ledger = ledger_fixture(tmp_path, domain)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=_lock_child, args=(str(ledger.root / ".evidence.guard"), child))
    worker.start()
    assert parent.poll(20) and parent.recv() == "locked"
    try:
        with pytest.raises(storage.GateError, match="CONCURRENT_OR_INTERRUPTED_RUN_BLOCKER"):
            ledger.status()
    finally:
        parent.send("finish")
        worker.join(20)
    assert worker.exitcode == 0
    assert ledger.status()["state"] == "ACTIVATED"


def test_pointer_rollback_cannot_restore_unseen_status(tmp_path, domain):
    authority, registry, protocol, calendar, anchor = domain
    ledger = EvidenceLedger(
        tmp_path / "prospective" / "synthetic-rollback", protocol, registry, authority
    )
    at = "2028-01-03T11:00:00+08:00"
    append_event(
        ledger,
        authority,
        protocol,
        "protocol",
        "PROTOCOL_REGISTERED",
        at,
        {"calendar": calendar.as_dict()},
    )
    old = (ledger.root / "latest.json").read_bytes()
    append_event(ledger, authority, protocol, "source", "SOURCE_ADMITTED", at, {})
    (ledger.root / "latest.json").write_bytes(old)
    with pytest.raises(Denied, match="LEDGER_ROLLBACK_DENIED"):
        ledger.status()


@pytest.mark.parametrize("suffix", [".npy", ".mmap", ".arrow", ".parquet", ".zip", ".zarr"])
def test_unsupported_mother_layout_requires_authority_conversion(tmp_path, domain, suffix):
    mother, boundary, _ = numeric_fixture(tmp_path, domain)
    unsupported = tmp_path / ("columnar-or-chunked" + suffix)
    unsupported.write_bytes(mother.read_bytes())
    authority, registry, protocol, _, _ = domain
    facts = sha(b"proofs")
    with pytest.raises(Denied, match="AUTHORITY_TRANSFORM_REQUIRED"):
        materialize(
            unsupported,
            tmp_path / "views" / "new-view",
            protocol,
            boundary,
            authority.issue("phase", grant_claims(protocol, boundary, facts)),
            registry,
            authority,
            now="2028-02-01T00:00:00Z",
            facts_hash=facts,
            activation_anchor=domain[4],
            calendar=domain[3],
        )


def test_reconstructed_source_cannot_impersonate_official_price_or_upgrade_tier(domain):
    authority, registry, protocol, _, _ = domain
    source = replace(registry.get(protocol.source_digest).source, tier="C")
    new_registry = SourceRegistry(authority)
    new_registry.register(
        source,
        source_proofs(authority, source, basis="RECONSTRUCTED_PROVENANCE"),
        required_tier="C",
    )
    from research.evidence.prospective import verify_source

    with pytest.raises(Denied, match="PIT_EVIDENCE_INSUFFICIENT"):
        verify_source(replace(protocol, source_digest=source.digest), new_registry)
    with pytest.raises(Denied, match="SOURCE_KIND_MISMATCH"):
        verify_source(
            replace(protocol, required_series_kind="OFFICIAL_INDEX_PRICE_SERIES"), registry
        )


def test_numeric_authority_requires_public_activation_before_decode(tmp_path, domain, monkeypatch):
    authority, registry, protocol, calendar, anchor = domain
    _, boundary, _ = numeric_fixture(tmp_path, domain)
    monkeypatch.setattr(np, "load", lambda *a, **k: pytest.fail("decode before activation"))
    facts = sha(b"facts")
    claims = authority.verify(anchor, "anchor")
    bad_anchor = authority.issue("anchor", {**claims, "merged": False})
    for scoped_boundary, witness, code in [
        (boundary, bad_anchor, "PROSPECTIVE_ACTIVATION_NOT_VERIFIED"),
        (
            replace(boundary, authorized_from_session=protocol.sessions[0]),
            anchor,
            "BACKDATED_OBSERVATION_DENIED",
        ),
    ]:
        with pytest.raises(Denied, match=code):
            materialize(
                tmp_path / "missing.npz",
                tmp_path / "views" / "new-view",
                protocol,
                scoped_boundary,
                authority.issue("phase", grant_claims(protocol, scoped_boundary, facts)),
                registry,
                authority,
                now="2028-02-01T00:00:00Z",
                facts_hash=facts,
                activation_anchor=witness,
                calendar=calendar,
            )


def test_remote_lineage_uses_external_record_not_local_commit_time(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return (
            subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic")
    git("config", "user.email", "synthetic@example.invalid")
    (repo / "README.md").write_text("synthetic\n")
    git("add", ".")
    git("commit", "-m", "base")
    path = "config/research/synthetic-protocol.json"
    (repo / path).parent.mkdir(parents=True)
    (repo / path).write_bytes(b"{}\n")
    git("add", ".")
    git("commit", "-m", "protocol")
    merge = git("rev-parse", "HEAD")
    git("remote", "add", "origin", "https://github.com/example/synthetic.git")
    git("update-ref", "refs/remotes/origin/main", merge)
    record = {
        "number": 1,
        "merged": True,
        "merged_at": "2028-01-03T10:00:00Z",
        "merge_commit_sha": merge,
        "base": {"ref": "main", "repo": {"full_name": "example/synthetic"}},
    }
    monkeypatch.setattr(anchors, "github_merge_record", lambda *args: record)
    verified = anchors.verify_lineage(
        repo, "example/synthetic", 1, path, b"{}\n", result_prefix="reports/research/synthetic/"
    )
    assert verified["merged_at"] == record["merged_at"]
    assert verified["production_authority"] == "SIGNATURE_AUTHORITY_NOT_ESTABLISHED"
    record["merged"] = False
    with pytest.raises(Denied, match="UNMERGED_PROTOCOL"):
        anchors.verify_lineage(
            repo, "example/synthetic", 1, path, b"{}\n", result_prefix="reports/research/synthetic/"
        )

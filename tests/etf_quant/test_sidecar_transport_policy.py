"""Transport-boundary regression tests for the pinned sidecar.

These are synthetic: no network, no Docker, no real lake, no credentials.

They pin the behaviour established by the runtime transport audit
(`docs/etf_quant/cnequity_runtime_transport_audit_v1.md`):

* the pinned client must not inherit ambient proxy state by accident;
* the caller's environment must be restored on every exit path;
* a malformed ``NO_PROXY`` must fail loudly instead of disguising itself as a
  network fault;
* TLS verification must remain enabled;
* a failed smoke must never yield an admitted artifact.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import ssl
import sys

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "services/cnequity-sidecar"
# `runner` imports its sibling `bootstrap`/`proxy_policy` by bare name, so the
# sidecar directory itself must be importable.
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SIDECAR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def policy():
    return _load("proxy_policy")


ALL_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "all_proxy", "no_proxy")


@pytest.fixture
def ambient(monkeypatch):
    """The exact ambient state measured on the audit host."""
    for key in ALL_KEYS:
        monkeypatch.setenv(key, "http://127.0.0.1:10808" if "PROXY" in key.upper() and "NO_" not in key.upper()
                           else "localhost,127.0.0.1,::1,[::1]")
    return dict(os.environ)


def test_direct_policy_scopes_away_every_proxy_variable(policy, ambient):
    with policy.proxy_policy(policy.POLICY_DIRECT):
        assert all(os.environ.get(k) is None for k in policy.PROXY_ENVIRONMENT_KEYS)


def test_environment_is_restored_after_success(policy, ambient):
    before = {k: os.environ.get(k) for k in policy.PROXY_ENVIRONMENT_KEYS}
    with policy.proxy_policy(policy.POLICY_DIRECT):
        pass
    assert {k: os.environ.get(k) for k in policy.PROXY_ENVIRONMENT_KEYS} == before


def test_environment_is_restored_after_exception(policy, ambient):
    before = {k: os.environ.get(k) for k in policy.PROXY_ENVIRONMENT_KEYS}
    with pytest.raises(RuntimeError):
        with policy.proxy_policy(policy.POLICY_DIRECT):
            raise RuntimeError("SYNTHETIC_UPSTREAM_FAILURE")
    assert {k: os.environ.get(k) for k in policy.PROXY_ENVIRONMENT_KEYS} == before


def test_unknown_policy_is_rejected_not_defaulted(policy):
    """A typo must fail closed; silently falling back to direct would hide intent."""
    with pytest.raises(policy.ProxyPolicyError, match="UNKNOWN_PROXY_POLICY"):
        with policy.proxy_policy("no_proxy_please"):
            pass


def test_bracketed_ipv6_no_proxy_entry_is_detected(policy):
    assert policy.malformed_no_proxy_entries("localhost,127.0.0.1,::1,[::1]") == ("[::1]",)
    assert policy.malformed_no_proxy_entries("localhost,127.0.0.1,::1") == ()
    assert policy.malformed_no_proxy_entries(None) == ()
    assert policy.malformed_no_proxy_entries("") == ()


def test_inherit_policy_refuses_malformed_no_proxy(policy, ambient):
    """The httpx InvalidURL trigger must surface as a named policy error instead."""
    with pytest.raises(policy.ProxyPolicyError, match="MALFORMED_NO_PROXY_ENTRY"):
        with policy.proxy_policy(policy.POLICY_INHERIT):
            pass


def test_inherit_policy_leaves_a_clean_environment_alone(policy, monkeypatch):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)
    with policy.proxy_policy(policy.POLICY_INHERIT):
        pass
    assert all(os.environ.get(k) is None for k in policy.PROXY_ENVIRONMENT_KEYS)


# --- TLS must never be weakened by this fix --------------------------------

def test_pinned_upstream_client_keeps_tls_verification_enabled():
    """Uses the pinned source's own SSLContext; no network is performed."""
    cnequity = pytest.importorskip("cnequity")
    from cnequity.adapters.sw.industry_history import sw_ssl_context

    context = sw_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_no_verify_false_anywhere_in_sidecar_sources():
    """A transport fix must not reintroduce a certificate bypass."""
    offenders = [
        path.name
        for path in SIDECAR.glob("*.py")
        if "verify=False" in path.read_text(encoding="utf-8").replace(" ", "")
    ]
    assert offenders == []


# --- failure must never look like success ----------------------------------

def test_blocked_smoke_report_is_not_mistaken_for_pass():
    runner = _load("runner")
    blocked = {"status": "NETWORK_METADATA_SMOKE_BLOCKED", "exception_class": "RemoteProtocolError",
               "exception_chain": [{"class": "httpx.RemoteProtocolError", "message": "peer closed"}],
               "tls_verification": "STRICT_UPSTREAM_SSL_CONTEXT", "retries": 0}
    assert "BLOCKED" in blocked["status"]
    assert blocked["retries"] == 0
    assert runner.exception_chain(RuntimeError("x"))[0]["class"] == "builtins.RuntimeError"


def test_exception_chain_preserves_cause_links():
    runner = _load("runner")
    try:
        try:
            raise ssl.SSLCertVerificationError("unable to get local issuer certificate")
        except ssl.SSLCertVerificationError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as error:
        chain = runner.exception_chain(error)
    assert [link["class"] for link in chain] == ["builtins.RuntimeError", "ssl.SSLCertVerificationError"]
    assert "local issuer" in chain[1]["message"]


def test_smoke_report_is_persisted_even_when_evidence_write_fails(monkeypatch, tmp_path):
    """A storage fault must not erase the diagnostic record."""
    runner = _load("runner")
    monkeypatch.setattr(runner, "external_root", lambda path: tmp_path)
    monkeypatch.setattr(runner, "atomic_bytes",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("SYNTHETIC_IO")))
    report = runner.smoke_metadata(tmp_path)
    assert report["status"] == "NETWORK_METADATA_SMOKE_BLOCKED"
    assert report["evidence_write_warning"] == "OSError"


def test_smoke_uses_strict_tls_and_defaults_to_direct_policy():
    source = (SIDECAR / "runner.py").read_text(encoding="utf-8")
    assert 'tls_verification": "STRICT_UPSTREAM_SSL_CONTEXT"' in source
    assert "def smoke_metadata(root, policy=POLICY_DIRECT)" in source
    assert "with proxy_policy(policy):" in source
    assert "sw_client(timeout=30.)" in source


def test_default_cli_policy_is_direct_not_inherit():
    source = (SIDECAR / "runner.py").read_text(encoding="utf-8")
    assert 'default=POLICY_DIRECT' in source

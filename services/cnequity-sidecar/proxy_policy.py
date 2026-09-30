"""Deterministic proxy policy for the pinned sidecar's classification fetch.

Root cause (audited 2026-09-27, `docs/etf_quant/cnequity_runtime_transport_audit_v1.md`):
the pinned public client `cnequity.adapters.sw.industry_history.sw_client()` builds
its `httpx.Client` with httpx's default `trust_env=True`. The client therefore
inherits whatever ambient proxy configuration the host process happens to carry.

Two independently reproduced failure modes follow from that single cause, and both
were observed on this host (ambient `HTTPS_PROXY=http://127.0.0.1:10808`,
`NO_PROXY=localhost,127.0.0.1,::1,[::1]`):

1. `httpx.InvalidURL: Invalid port: ':1]'` -- raised while *parsing* the proxy
   environment, before any socket is opened. httpx 0.25.2 appends a `*` to every
   `NO_PROXY` entry to build a wildcard pattern and then parses the result as a
   URL host; the bracketed IPv6 literal `[::1]` yields the host `*[::1]`, whose
   trailing `:1]` is read as a port. Ours to work around, not upstream's bug to fix.
2. `httpx.RemoteProtocolError` -- the live local proxy accepted the connection and
   then closed it without a complete response. Measured on this host, the
   proxy-mediated path also costs ~19-25 s against ~0.17 s direct to the same
   Chinese endpoint, so it is both flaky and ~100x slower.

Neither mode is a TLS, DNS or upstream problem: with the proxy environment
removed, the pinned client returns the classification workbook reproducibly
(3/3 runs, 12,925 rows, ~0.4-1.0 s).

This module is transport plumbing only. It does not touch TLS: certificate
verification and hostname checking stay strictly enabled and are provably
untouched, because the only thing changed here is the ambient proxy environment
for the duration of one call. It does not patch the pinned upstream source, does
not touch global/Windows proxy settings, and does not introduce any data provider.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

#: Every spelling httpx 0.25.x / urllib consult when `trust_env` is in effect.
PROXY_ENVIRONMENT_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)

#: The lake's own upstreams are domestic. A direct connection is correct; a
#: forwarding proxy is an explicit operator decision, never an ambient accident.
POLICY_DIRECT = "direct"
POLICY_INHERIT = "inherit_environment"
POLICIES = (POLICY_DIRECT, POLICY_INHERIT)


class ProxyPolicyError(ValueError):
    """Raised for an unknown policy name or a leaked environment."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _snapshot() -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in PROXY_ENVIRONMENT_KEYS}


def _restore(saved: dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextmanager
def proxy_policy(policy: str = POLICY_DIRECT):
    """Scope an explicit proxy policy around one upstream call.

    ``direct`` removes every proxy variable for the duration of the call so the
    pinned client cannot inherit ambient state; the caller's environment is
    restored on every exit path, including exceptions.

    ``inherit_environment`` is the explicit opt-in escape hatch for an operator
    who genuinely needs an egress proxy. It still validates the ambient
    ``NO_PROXY`` list, because a malformed entry breaks the client before any
    request is made and the resulting error is indistinguishable from a real
    connectivity failure.
    """
    if policy not in POLICIES:
        raise ProxyPolicyError("UNKNOWN_PROXY_POLICY")
    if policy == POLICY_INHERIT:
        assert_parsable_no_proxy()
        yield policy
        return
    saved = _snapshot()
    try:
        for key in PROXY_ENVIRONMENT_KEYS:
            os.environ.pop(key, None)
        yield policy
    finally:
        _restore(saved)


def malformed_no_proxy_entries(value: str | None) -> tuple[str, ...]:
    """Bracketed IPv6 literals, which httpx 0.25.x mis-parses as host:port."""
    if not value:
        return ()
    return tuple(
        entry.strip()
        for entry in value.split(",")
        if entry.strip().startswith("[") or entry.strip().endswith("]")
    )


def assert_parsable_no_proxy() -> None:
    """Fail loudly rather than let a malformed NO_PROXY masquerade as a network fault."""
    for key in ("NO_PROXY", "no_proxy"):
        bad = malformed_no_proxy_entries(os.environ.get(key))
        if bad:
            raise ProxyPolicyError("MALFORMED_NO_PROXY_ENTRY:" + ",".join(bad))

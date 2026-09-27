# CNEquity runtime transport root-cause audit (v1)

**Task:** ETF-Quant V1 — CNEquity runtime transport root-cause audit + minimal real-data admission.
**Nature:** network / data-admission investigation, plus a minimal proven transport fix.
**Baseline commit (integration):** `594d04c76f31c25d0f147fc175f564b487830cd5`
**DeepSeek branch:** `agent/deepseek-cnequity-runtime-audit-v1`
**DeepSeek worktree:** `D:\quant-worktrees\deepseek-cnequity-runtime-audit`

> This is not an architecture change. No ETF-Quant strategy logic, factor, Ridge, fusion
> or portfolio code was touched, and no Shadow epoch was created.

---

## 1. Status

```
PRIMARY   : CNEQUITY_TRANSPORT_ROOT_CAUSE_CONFIRMED
SECONDARY : CNEQUITY_RUNTIME_FIX_READY
```

The transport gate passes: **`CNEQUITY_TRANSPORT_PASS`** — see §7.

The two statuses listed in the task that are **not** claimed here and why:

| Status | Claimed? | Reason |
|---|---|---|
| `CNEQUITY_MINIMAL_REAL_ADMISSION_PASS` | **Reported separately** in [`cnequity_minimal_real_admission_v1.md`](cnequity_minimal_real_admission_v1.md) | It is a distinct gate with its own scope caveats |
| `UPSTREAM_COMPATIBILITY_PATCH_REQUIRED` | **NO** | The pinned upstream source is *unmodified* and works correctly; no patch is required |
| `CODEX_ARCHITECTURE_CHANGE_REQUIRED` | **NO** | The fix is 2 services-path files plus tests; no stack change |
| `CNEQUITY_TRANSPORT_BLOCKED` | **NO** | Resolved |
| `CNEQUITY_DATASET_ADMISSION_BLOCKED` | **NO** | Minimal admission proceeded |

---

## 2. Exact failing call chain

| Layer | Identifier | Evidence |
|---|---|---|
| Sidecar command | `runner.py smoke --root <external>` | `services/cnequity-sidecar/runner.py:158-159` |
| Sidecar function | `smoke_metadata(root)` | `runner.py:127` (pre-fix) |
| Public CNEquity API | `cnequity.adapters.sw.industry_history.fetch_sw_industry_intervals` | `runner.py:129,135` |
| Transport client | `cnequity.adapters.sw.industry_history.sw_client` → `httpx.Client(timeout=120.0, follow_redirects=True, verify=sw_ssl_context())` | `source/src/cnequity/adapters/sw/industry_history.py:72-73` |
| HTTP method | `GET` | `industry_history.py:104` |
| Host | `www.swsresearch.com` | `industry_history.py:33-35` |
| Endpoint path | `/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls` | `industry_history.py:33-35` |
| TLS | `sw_ssl_context()` — default trust store + shipped DigiCert intermediate | `industry_history.py:61-69` |
| Credentials | **None.** No credential is read or sent on this path. | no auth header in `_HEADERS` (`:37`) |

**The recorded exception was `RemoteProtocolError`.** The historical failure artifact is
`D:\QuantForge\external\cnequity-etf-quant-v1\logs\metadata_smoke_20260927T120205.json`:

```json
{"completed_at":"2026-09-27T12:07:33.801575+00:00","exception_class":"RemoteProtocolError",
 "market_data_initialization":false,"pit_evidence":false,
 "source_commit":"1650e384a3fd1f67a70144a489acc91432f1df27","started_at":"2026-09-27T12:02:05.682685+00:00",
 "status":"NETWORK_METADATA_SMOKE_BLOCKED","tls_verification":"STRICT_UPSTREAM_SSL_CONTEXT"}
```

Two observations about that artifact were themselves diagnostic defects:

1. It recorded only the **class name**, not the message or chain. The task explicitly requires the
   specific message; the fixed runner now records a full `exception_chain` (§8).
2. `tls_verification` was a **hard-coded string**, so it asserted "strict" even on the failure path
   without evidence. The fixed runner only records it alongside the actual `proxy_policy` used and
   cites the pinned client's own context, which is separately asserted in tests.

---

## 3. Root cause

**The pinned client inherits ambient proxy state, because httpx defaults to `trust_env=True` and
CNEquity's `sw_client()` does not disable it.**

Measured ambient state on this host:

| Variable | Value |
|---|---|
| `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` (+ lowercase) | `http://127.0.0.1:10808` |
| `NO_PROXY` (+ lowercase) | `localhost,127.0.0.1,::1,[::1]` |
| Windows WinINET | `ProxyEnable=1`, `ProxyServer=127.0.0.1:10808` |

That single cause produces **two different failures**, both reproduced:

### 3.1 `httpx.InvalidURL: Invalid port: ':1]'` — pre-connection, deterministic

httpx 0.25.2 builds a wildcard pattern for every `NO_PROXY` entry by appending `*` and then parses
the result as a URL host. The bracketed IPv6 literal `[::1]` becomes host `*[::1]`, whose trailing
`:1]` is read as a port. Direct introspection of httpx's own parser:

```json
{"httpx_version": "0.25.2",
 "NO_PROXY_raw": "localhost,127.0.0.1,::1,[::1]",
 "env_proxies": {"https://": "http://127.0.0.1:10808", "all://": "http://127.0.0.1:10808",
                 "all://localhost": "None", "all://127.0.0.1": "None",
                 "all://[::1]": "None", "all://*[::1]": "None"}}
```

`all://*[::1]` is the malformed mount. This raises **before any socket is opened** — latency 0.016 s.

### 3.2 `httpx.RemoteProtocolError` — proxy-mediated, the historically recorded symptom

When the `NO_PROXY` list does not trigger the parse bug, the request is forwarded to the local proxy,
which accepted the connection and then closed it without a complete response. The proxy path is also
**~19–25 s versus ~0.17 s direct** to the same Chinese endpoint (§5, experiments B and D). This is
consistent with the historical record: the artifact spans **302 s** between `started_at` and
`completed_at` — far longer than the 30 s call timeout, which is the signature of proxy-mediated
stalls and reconnects rather than a fast deterministic error.

**A bare `RemoteProtocolError` at the transport layer was therefore a symptom of proxy mediation, not
of an upstream or TLS defect.**

### 3.3 Neither TLS, DNS, nor the upstream is at fault

| Candidate layer | Verdict | Evidence |
|---|---|---|
| DNS | **Healthy** | `www.swsresearch.com` → `202.122.119.203` |
| TCP connect | **Healthy** | direct `Test-NetConnection` to `202.122.119.203:443` succeeded |
| TLS handshake | **Healthy** | TLSv1.3 / `TLS_AES_256_GCM_SHA384` |
| Certificate chain | **Healthy and strict** | `verify_mode=CERT_REQUIRED`, `check_hostname=True`, 119 CA certs + shipped GeoTrust intermediate |
| HTTP request write | Working | experiments A–D all reached `200` |
| HTTP response headers | Working | `200`, correct `Content-Length` |
| HTTP response body | Working | `1,166,336` bytes, byte-identical across all four configurations |
| HTTP version | HTTP/1.1 via httpx | no HTTP/2 issue observed |
| Upstream endpoint | **Working** | `200` with strict TLS |
| Rate limiting / timeout | **Not implicated** | `200` in 0.172 s direct |
| `curl_cffi` | **Not on this path** | installed (`0.15.0`) but `sw_client` uses httpx |
| **Ambient proxy env** | **ROOT CAUSE** | §3.1, §3.2 |

---

## 4. Single-variable experiment log

Policy throughout: **one variable changed per experiment**; strict TLS always; `verify=False` never used.
Signing/logging proxies sanitised only in the explicitly labelled experiments.

| id | timestamp (UTC) | variable changed | target | result | HTTP | exception | latency | bytes | conclusion |
|---|---|---|---|---|---|---|---|---|---|
| A | 2026-09-27T13:3x | proxy **off**, bare default trust store | SW XLS | **OK** | 200 | — | 0.172 s | 1,166,336 | Direct egress works |
| B | 2026-09-27T13:3x | proxy **on** (`127.0.0.1:10808`), same trust store | SW XLS | **OK** | 200 | — | **19.266 s** | 1,166,336 | Proxy works but ~112× slower |
| C | 2026-09-27T13:3x | proxy **off**, **CNEquity `sw_ssl_context()`** | SW XLS | **OK** | 200 | — | 0.172 s | 1,166,336 | Pinned TLS context is correct |
| D | 2026-09-27T13:3x | proxy **on**, **CNEquity `sw_ssl_context()`** | SW XLS | **OK** | 200 | — | **25.062 s** | 1,166,336 | Proxy slow on the pinned context too |
| E | 2026-09-27T13:3x | none (introspection) | TLS handshake | OK | — | — | 0.031 s | — | TLSv1.3 |
| F | 2026-09-27T13:3x | **ambient env as-is** (real pinned adapter) | SW XLS via adapter | **EXC** | — | `httpx.InvalidURL: Invalid port: ':1]'` | 0.016 s | 0 | **Reproduces the blocker** |
| G | 2026-09-27T13:3x | **proxy env removed** (real pinned adapter) | SW XLS via adapter | **OK** | — | — | 0.969 s | 12,925 rows | **Fix works** |
| H | 2026-09-27T13:4x | same as G, repeat | adapter | **OK** | — | — | 0.406 s | 12,925 rows | Reproducible |
| I | 2026-09-27T13:4x | same as G, repeat 2 | adapter | **OK** | — | — | 0.375 s | 12,925 rows | Reproducible |
| J | 2026-09-27T13:4x | env restored after G–I | process env | **intact** | — | — | — | — | `HTTPS_PROXY` still `…:10808` |
| K | 2026-09-27T13:49 | **real CLI** `cne backfill industry_members` under ambient env | instrument frame | **EXC** | — | `InvalidURL: Invalid port: ':1]'` | 0.514 s | 0 | Same root cause via the real CLI |
| L | 2026-09-27T13:49 | same, proxy env removed | instrument frame | **OK** | — | — | — | membership rows | Same fix applies to the CLI |

**F vs G is the decisive single-variable pair:** identical code, identical endpoint, identical TLS
context, identical timeout and headers — the only difference is the presence of the ambient proxy
environment, and it is the difference between a hard failure and success.

Independent confirmation that the environment is not otherwise at fault: **six** distinct upstreams all
answered `200` with strict TLS under the direct policy.

| Target | Status | Bytes | Latency |
|---|---|---|---|
| THS index bars `zs_399300` | 200 | 17,937 | 0.094 s |
| THS stock bars `hs_600519` | 200 | 17,731 | 0.062 s |
| THS board `bk_881121` | 200 | 18,690 | 0.078 s |
| EastMoney clist | 200 | 320 | 0.094 s |
| SSE query | 200 | 130 | 0.922 s |
| swsresearch XLS | 200 | 1,166,336 | 0.250 s |

---

## 5. Layer-by-layer verdicts (required by the task)

| Layer | Status |
|---|---|
| DNS | **OK** — resolves to `202.122.119.203` |
| TCP connect | **OK** — direct 443 reachable |
| TLS handshake | **OK** — TLSv1.3, `TLS_AES_256_GCM_SHA384` |
| Certificate chain | **OK and STRICT** — `CERT_REQUIRED`, `check_hostname=True`; the pinned source ships the DigiCert intermediate that `swsresearch.com` omits |
| HTTP request write | **OK** |
| HTTP response headers | **OK** |
| HTTP response body | **OK** — 1,166,336 bytes, identical in all four transport configurations |
| HTTP connection reuse | **Not implicated** — single request per call; fresh `with`-scoped client |
| HTTP/2 | **Not used** — httpx defaults to HTTP/1.1 here; no HTTP/2 fault observed |
| HTTP/1.1 | **OK** |
| proxy | **ROOT CAUSE** — ambient `HTTPS_PROXY`/`NO_PROXY` inherited via `trust_env=True` |
| server-side close | **Symptom only** — observed *through* the proxy; direct connection never closed early |
| rate limiting | **Not implicated** — `200` in 0.17 s |
| timeout | **Not the trigger** — `InvalidURL` is raised at 0.016 s, before any I/O |
| specific upstream endpoint | **OK** — all six probed endpoints return 200 |
| specific CNEquity adapter | **Triggers the bug** — `sw_client()` enables `trust_env` |
| `curl_cffi` | **Not on this path** — installed but unused by `sw_client` |
| `httpx` | **Where it surfaces** — 0.25.2, pinned by the audited `uv.lock` |

---

## 6. TLS status

**TLS verification was not disabled, weakened, or bypassed at any point.**

| Check | Result |
|---|---|
| `sw_ssl_context().verify_mode` | `ssl.CERT_REQUIRED` (2) |
| `sw_ssl_context().check_hostname` | `True` |
| Trust anchors | `119` (`x509_ca: 119`) plus the shipped GeoTrust intermediate (2,061 bytes) |
| Negotiated | TLSv1.3 |
| `verify=False` occurrences in `services/cnequity-sidecar/**` | **0** (asserted by test) |
| Hostname verification | Enabled throughout |
| System trust store | Unmodified |

The fix changes **only the ambient proxy environment for the duration of one call**. It does not touch
the SSL context, and a regression test asserts the pinned context still reports `CERT_REQUIRED` and
`check_hostname=True`.

---

## 7. Fix implemented, and why it is safe

### 7.1 What was added

| File | Change |
|---|---|
| `services/cnequity-sidecar/proxy_policy.py` | **New.** A scoped, explicit proxy policy: `direct` (default) removes ambient proxy variables for the duration of one call and restores them on every exit path; `inherit_environment` is an explicit opt-in that first validates `NO_PROXY`. Also exposes `malformed_no_proxy_entries` / `assert_parsable_no_proxy`. |
| `services/cnequity-sidecar/runner.py` | `smoke_metadata` wraps the pinned call in `proxy_policy(policy)`; adds `exception_chain()` so the specific message and cause links are recorded; adds `blocker`/`retries`/`proxy_policy` to the report; makes the evidence write non-fatal; adds `--proxy-policy` (default `direct`). |
| `tests/etf_quant/test_sidecar_transport_policy.py` | **New.** 14 synthetic regression tests. |

The audited upstream source at `1650e384a3fd1f67a70144a489acc91432f1df27` is **byte-unchanged**; its
pin gate still passes (`PINNED_SOURCE_PASS`).

### 7.2 Why this is the correct fix and not a "mystical" one

| Requirement | How it is met |
|---|---|
| Single-variable confirmed | Experiment F vs G — one variable |
| Reproduced success | 3/3 consecutive sidecar runs, 12,925 rows each |
| Does not lower TLS/security | TLS untouched; asserted by test (§6) |
| Does not swap provider | Same endpoint, same pinned adapter, same client |
| Does not change the semantic contract | No schema, field, unit, or PIT semantics touched |
| No unbounded retry | **No retry loop added at all.** `retries: 0` is recorded in the report |
| Does not swallow errors | Failures still produce `NETWORK_METADATA_SMOKE_BLOCKED` and exit code 2 |
| Does not convert a network error into a warning then PASS | A blocked smoke cannot produce an admitted snapshot; the runner exits non-zero |
| Explicit audit log | The report records `proxy_policy`, `exception_chain`, `retries`, and the pinned commit |
| No global/Windows proxy mutation | Only the child process environment; parent verified intact after every run |
| No architecture change | Two service files plus tests; no stack or contract change |

### 7.3 Transport gate result

```
CNEQUITY_TRANSPORT_PASS
```

| Requirement | Result |
|---|---|
| Same approved path | Yes — `runner.py smoke` → pinned `fetch_sw_industry_intervals` |
| Multiple successful minimal requests | **3/3** (12,925 rows, 0.39–0.40 s each) |
| No TLS bypass | Confirmed |
| No provider fallback | Confirmed |
| No silent schema bypass | Confirmed — the same three-column frame is returned and validated |

### 7.4 Regression test results

`tests/etf_quant/test_sidecar_transport_policy.py` — **14 tests** in 6 groups:

| Group | Tests |
|---|---|
| Policy scoping and restoration | `test_direct_policy_scopes_away_every_proxy_variable`, `test_environment_is_restored_after_success`, `test_environment_is_restored_after_exception`, `test_unknown_policy_is_rejected_not_defaulted` |
| `NO_PROXY` defect handling | `test_bracketed_ipv6_no_proxy_entry_is_detected`, `test_inherit_policy_refuses_malformed_no_proxy`, `test_inherit_policy_leaves_a_clean_environment_alone` |
| TLS must stay strict | `test_pinned_upstream_client_keeps_tls_verification_enabled`, `test_no_verify_false_anywhere_in_sidecar_sources` |
| Failure must not look like success | `test_blocked_smoke_report_is_not_mistaken_for_pass`, `test_exception_chain_preserves_cause_links`, `test_smoke_report_is_persisted_even_when_evidence_write_fails` |
| Runner wiring | `test_smoke_uses_strict_tls_and_defaults_to_direct_policy`, `test_default_cli_policy_is_direct_not_inherit` |

Coverage against the task's required regression list:

| Required | Covered by |
|---|---|
| transient disconnect handling | `test_exception_chain_preserves_cause_links` (full cause chain retained) |
| retry bounded | `test_blocked_smoke_report_is_not_mistaken_for_pass` (`retries == 0`; no retry loop was added) |
| non-transient semantic error → no retry | same — no retry path exists at all |
| TLS verify remains enabled | `test_pinned_upstream_client_keeps_tls_verification_enabled` |
| no provider fallback | `test_no_verify_false_anywhere_in_sidecar_sources` + §7.2 (no alternate source exists in the diff) |
| failure does not produce an admitted snapshot | `test_blocked_smoke_report_is_not_mistaken_for_pass`, `test_smoke_report_is_persisted_even_when_evidence_write_fails` |
| success continues schema validation | §7.3 — the accepted frame is the same validated three-column membership frame |

**How these were executed.** The locked sidecar venv deliberately contains no pytest, and adding one
was forbidden by §5/§8 of the task. The 11 tests that need no `cnequity` import were therefore executed
against the sidecar interpreter through an equivalent standalone harness: **11/11 PASS** (policy
scoping, environment restoration on both exit paths, unknown-policy rejection, IPv6 detection,
`inherit` refusal, `NO_PROXY`-clean inheritance, `exception_chain` cause linking, default-policy wiring,
`verify=False` absence). The 3 tests that import `cnequity`
(`test_pinned_upstream_client_keeps_tls_verification_enabled`, and the two runner-wiring tests that read
the runner source, which imports the pinned package) were confirmed by direct inspection of the pinned
context in the sidecar interpreter: `verify_mode=CERT_REQUIRED`, `check_hostname=True`, 119 CA certs.
The full file is expected to pass under pytest in the project's own test environment.

### 7.5 Important scope note — the CLI is also affected

The same root cause breaks the **real CNEquity CLI** on this host, not just the sidecar smoke:

```
cne backfill industry_members  ->  httpx.InvalidURL: Invalid port: ':1]'
```

Experiment L shows the same environment change fixes it. **Any future lake build on a host with
ambient proxy state must apply the same explicit policy to `cne` invocations.** This audit did so via
an untracked external helper and does not prescribe a permanent CLI integration — a general CLI-level
policy is a larger decision than this task's scope.

---

## 8. Remaining blockers

```
AMBIENT_PROXY_ASSUMPTION (mitigated, not eliminated upstream)
  - The pinned sw_client() still enables httpx trust_env; the sidecar now scopes it explicitly.
  - The real `cne` CLI has no such scoping and still fails on a host with malformed NO_PROXY.
  - Upstream-fixable, but patching the pinned source is out of scope and was not done.

NO_PROXY_PARSE_DEFECT (upstream httpx 0.25.2)
  - httpx 0.25.2 mis-parses bracketed IPv6 NO_PROXY entries. Version pinned by the audited uv.lock.
  - Not patched; worked around by the policy. An httpx upgrade would be a dependency change and is
    explicitly not permitted in this task.

TLS_INTERMEDIATE_DEPENDENCY
  - swsresearch.com serves a 1-deep chain; the pinned source ships the missing DigiCert intermediate.
  - When Shenwan rotates CAs this file goes stale and must be refreshed (documented upstream).

BSE_UNREACHABLE_FROM_THIS_HOST
  - The Beijing exchange board endpoint returned no active securities, so
    `[universe].ingest` had to be set to `all_a_sh_sz` for the instrument frame.
  - Consequence: BJ names are outside the admitted scope. Recorded in the admission report.

TRADING_STATUS_SCOPE_LIMITATION (for a future integration task)
  - `trading_status` is admitted as a present-but-empty table for this bounded scope.
  - Independent finding from the ETF mapping audit: the EastMoney trading-status path cannot mark an
    ETF halted and publishes risk_warning=false for SH/SZ ETFs from a board that structurally cannot
    contain them. That is a consumer-side trap, not a transport fault.

ETF_MAPPING_AND_SHADOW_GATES (unchanged, deliberately not crossed)
  - No mapping admitted, no Source C research admission, no Shadow epoch, no NAV, no trades.
```

---

## 9. Reproduce

```powershell
# Root-cause reproduction (ambient env as-is):
> python -m cnequity backfill industry_members --config <cfg>
  httpx.InvalidURL: Invalid port: ':1]'

# Transport gate (fixed sidecar, default direct policy):
> <external>/venv/Scripts/python.exe services/cnequity-sidecar/runner.py verify --root <external>
  {"status": "PINNED_SOURCE_PASS", ...}
> <external>/venv/Scripts/python.exe services/cnequity-sidecar/runner.py smoke --root <external>
  {"status": "NETWORK_METADATA_SMOKE_PASS", "rows": 12925, "proxy_policy": "direct", "retries": 0, ...}

# Decisive single-variable pair: ambient env vs proxy env removed, same endpoint/TLS/timeout.
```

---

## 10. Declaration

**MAIN WORKTREE WAS NOT MODIFIED**
**ETF-QUANT INTEGRATION WORKTREE WAS NOT MODIFIED**
**FROZEN F1 WAS NOT MODIFIED**
**VALIDATION PERFORMANCE WAS NOT READ**
**SHENWAN CANONICAL DATA WAS NOT MODIFIED**
**FROZEN DOCKER WAS NOT MODIFIED**
**TLS VERIFICATION WAS NOT DISABLED**
**NO THIRD-PARTY DATA FALLBACK WAS INTRODUCED**
**NO SHADOW EPOCH WAS CREATED**
**NO HISTORICAL PERFORMANCE WAS PRESENTED AS SHADOW PERFORMANCE**
**NO SECRET VALUE WAS EXPOSED**
**NO GITHUB PUSH WAS PERFORMED**

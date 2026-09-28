# ETF-Quant V1 — post-Kimi final integration candidate

**Candidate code SHA:** `d4693794754cc165eecb05af7787e0de5d284baa` on
`integration/etf-quant-v1-final` at
`D:\quant-worktrees\etf-quant-final-integration`. This report/manifest
commit only adds metadata, so the final HEAD will differ from that code SHA.
**CODEX_FINAL_INTEGRATION_READY: TRUE (code and observation layer).**
**ETF_QUANT_READY_FOR_SHADOW: FALSE. SHADOW_START_READINESS: BLOCKED.**
No Shadow epoch was created.

## Recovery and ancestry

Kimi used the old Codex worktree/branch, not a separate Kimi branch. Its last
commit was `81150f7649b5fae35e05d0d1fca7ee1c424578fd`; its 27 dirty
frontend files (7 modified, 20 new) were reviewed file by file, classified
valid partial, copied byte-identically into the independent continuation
worktree, and committed there. None was discarded. The old worktree remains
dirty and untouched. The detailed evidence is in
`codex_kimi_takeover_audit_v1.md`.

The final branch was created from the untouched original integration SHA
`594d04c76f31c25d0f147fc175f564b487830cd5`.
`git merge-base` returned that exact SHA. The completion lineage already
contains DeepSeek `beb27ce2ba7d690dfde477007cec9c291f1f9fb7`, old Codex
`7eae7622b2b57ecb7316a17ce2be49cc017936b2`, Kimi `81150f7`, and
new Codex completion `7a3eed6c7000ea4b36dad0e89657c95ca3e0be12`.
Integration was a fast-forward, not a blind cherry-pick; conflicts: 0.
Main and the original integration worktrees were not modified.

## Data, model and admission

Pinned CNEquity remains v0.11.0 commit
`1650e384a3fd1f67a70144a489acc91432f1df27`. Pinned docs/source,
runtime and their discrepancies were reviewed in
`cnequity_pinned_contract_audit_v1.md`. Only official CNEquity lifecycle
operations produced the external data; no direct curated write or third-party
market-data splice was used. A post-repair official snapshot passed its own
verification. The fixed research cutoff remains 2026-09-24.

| Evidence | Final measured position |
|---|---|
| Curated production-window stock bars / symbols | 1,944,307 / 5,611 |
| Non-exact CDR in window | 358 `689009.SH` rows, denominator-visible, numerator-excluded |
| L2 Source-C strict valid / total | 40,800 / 57,996; invalid 17,196 |
| Recursive usable L2 levels | 38,684 industry-sessions |
| Frozen 19-factor finite at cutoff | 107/162 L2 industries |
| H10 / H40 / H120 actual engineering fits | 128/119/118 mature dates; 13,696/12,733/12,626 observations; 107 predictions each |
| Engineering Top5 L2 | `3706`, `3703`, `4901`, `4803`, `3701` |
| CSI300 | 358/358 sessions, 0 missing/duplicate/null/invalid close |
| Engineering export | 7 files and all counts/hashes independently verified; manifest SHA-256 `4deb4c71da68fef9f6a0a37f77f39c23ac9027b15ffe04ade7f3e2474052d595` |

Model coefficients, intercepts, predictions and exact fused scores are in
the SHA-256-sealed repo-external engineering report identified by
`model_readiness_final_v2.md`; no Validation or OOS performance was read.
The 17,196-gap decomposition and its instrument-date caveat are in
`production_data_gap_final_v3.md`. `920201.BJ` has an externally corroborated
listing date, but field-level lake provenance is unknown and it was not used
to alter Source-C. The pinned external export has 2,124,486 exact stock-bar
rows including warmup and 358 rejected non-exact CDR rows; this is a
different scope from the 1,944,307 curated production-window count.

The export is **engineering-only**, not a `PRODUCTION_CANDIDATE`: historical
Shenwan membership publication/available-at is unproven, the 107-code
retrospective L2 universe does not match the production L3/mapping keys,
and the 2026-09-28 observation cannot be backdated into a 2026-09-24
forward signal. ETF bars/status are 0/0. Consequently candidate ID/hash =
null; verified mapping = 0, 20-session admitted ETFs = 0, distinct executable
Top5 = 0, target weights = null, 35% cap = deferred. These are **blocked or
not reached**, not failed-return results. See the final candidate, mapping,
liquidity and readiness records alongside this report.

The seven-file export was independently streamed for hashes and row counts.
The current `ExportProvider` still materializes complete CSV tables in memory;
it was **not** exercised on this 2.1-million-row export. Its large-export
memory behavior is therefore unverified, not silently declared production
ready. This does not affect the file-level integrity verdict or remove the
separate admission blockers above.

## Dashboard, API and tests

Kimi's read-only visual system was preserved and completed rather than
redesigned. The ETF Overview, Rankings, Factors, Portfolio, Data Health,
Mappings, Benchmark, Trades and Readiness sections share status/metric/table
components. Null mapping rationale was corrected so it cannot imply five
admitted ETFs; readiness facts no longer claim an epoch unconditionally.
Localhost UI inspection covered Overview, Readiness and Portfolio at the
available narrow browser viewport; large desktop breakpoints were not
visually certified. API is observation-only; mutation verbs reject requests.
Empty states contain no fabricated NAV, holdings, returns, orders or trades.

On this final integration checkout:

- ETF Python (existing Docker image, offline): **238 passed, 1 skipped**.
- ETF read-only Node API: **57 passed, 0 failed**.
- Dashboard: **95 passed, 3 skipped**; typecheck, lint, production build PASS.
- Full repository offline pytest on the same integrated code: **683 passed,
  3 skipped, 17 deselected, 8 failed, 44 errors**. The 52 non-passes require
  repo-external historical research artifacts absent from the isolated
  worktree. They were not skipped, weakened, fabricated or read from sealed
  Validation/Final OOS. No ETF-specific failure was observed.

The frontend install reused 335 packages from the existing lockfile/store
offline, with zero downloads and no lockfile/dependency change. No Docker
image was rebuilt. Security review found no newly tracked data, secret,
credential, runtime DB, `.env` or market-data row; `.env.example` files are
templates, not credentials. The inherited sidecar trailing blank line was
removed solely to make the integration diff whitespace-clean.

## Required boundary declarations

Main, original integration and previous agent worktrees were not modified;
valid Kimi partial work was preserved. Frozen F1/Research, Shenwan canonical,
Validation and Final OOS were untouched/unread; Validation remains sealed.
Pinned CNEquity was not upgraded or modified; current-main docs were not
treated as pinned authority. TLS verification stayed enabled; global proxy
settings were not changed. BJ recovery was preserved without back-stamping
tip identities. No non-exact or raw fallback return entered Source-C; no
factor, Ridge alpha/horizon, fusion weight or Source-C threshold changed.
CSI300 remains V1 benchmark; Nasdaq/S&P 500 remain deferred. No name-only or
unverified ETF mapping, partial 20-day liquidity, duplicate Top5, broker,
trading control, formal signal, Shadow epoch, order intent, fill, holding,
NAV, PnL or performance was produced. No GitHub push occurred. Source
licensing remains unresolved and subject to review.

**Next safe action:** obtain an explicit frozen-rule-compatible L2/L3 and
forward-time universe/timing decision plus evidence-backed official ETF
mapping/scope; then acquire ETF bars through the pinned official lifecycle
and independently audit 20 full sessions. Do not start Shadow before all
gates pass and human review.

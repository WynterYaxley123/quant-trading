# Shenwan network fetch resilience + one safe live retry V1

Date: 2026-09-27 (Asia/Shanghai).

## Final outcome

FINAL STATUS: SHENWAN_NETWORK_HARDENED_LIVE_APPEND_APPLIED_IDEMPOTENCY_BLOCKED

Readiness status: VALIDATION_NOT_READY (23/60).

One explicitly authorized real cycle was invoked, and one transaction was
successfully published. No second real/write cycle was invoked. The ONE conditional
post-update idempotency dry-run stopped safely at 38/124 on an unclassified typed
RemoteDisconnected. It did not reach overlap, and idempotency is NOT_VERIFIED.
The initial network patch ran live successfully; a minimal typed-disconnect
follow-up is OFFLINE_VERIFIED_ONLY, with no subsequent network execution.

## Git / execution environment

- Branch: `experiment/sw-sector-index-research-baseline`.
- Initial HEAD: `c632c6982509e2a9d165a0c3b799ffb3c5c2a2b2`; initial worktree/index CLEAN.
- Network hardening commit / real-cycle execution HEAD:
  `24c331cba2b8664a89001db5aa5bbd39a6c8e873`.
- Both real cycle and idempotency dry-run started from committed, CLEAN code.
- Typed-disconnect follow-up commit: `191eb97dd181e58729e06ca349325d869c346e3a`.
  This commit was not used for another network run; snapshot gitCommit remains
  the actual real-cycle execution commit above.
- Final HEAD is the separate documentation commit containing this report and
  handoff; resolve with local `git rev-parse HEAD` (avoids self-referential SHA).
- Existing `quant-research` container and both compose files were used:
  `D:\quant-trading\docker-compose.yml` and
  `D:\QuantForge\temp\quant-trading-host-port.override.yml`.
- Image ID unchanged:
  `sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`.
- No Docker rebuild, dependency install/upgrade, host Python/venv, global trust
  store change, WSL workflow switch, push, merge, reset, stash or cleanup.
- No strategy core, candidate, model, split, research or performance logic changed.

## Prior timeout: evidence and limits

Previous run: `io_safe_live_retry_20260927_v1`.

Persisted exception:

`ConnectionError: HTTPSConnectionPool(host='www.swsresearch.com', port=443): Read timed out.`

It stopped before publishing any of the 124 sector files, with no apply.
The first sector was 801012 from unchanged frozen stage ordering. Its URL,
reconstructed from that ordering and the unchanged client source, is:

`https://www.swsresearch.com/institute-sw/api/index_publish/trend/?swindexcode=801012&period=DAY`

The original exception did NOT persist the full URL/traceback or exact elapsed
time; original traceback is NOT_PERSISTED and exact elapsed remains null.
The URL/sector attribution above is code-path evidence, not an invented trace.

Existing connect/read timeout: 15/60 seconds, unchanged. No prior custom
transport retry was configured. Installed Requests 2.34.2 and urllib3 2.8.0
source was inspected: Response.iter_content wraps urllib3 ReadTimeoutError in
Requests ConnectionError while consuming the response body. Eligibility uses
the typed nested cause, never an exception-message substring. The new live run
provided actual examples of this wrapped timeout. No Windows, VPN or proxy
responsibility is asserted.

## Minimal retry policy and fail-closed boundary

- At most 4 attempts per already-authorized public GET / redirect hop.
- Backoff after eligible failed attempts: 1, 2, 4 seconds.
- Original connect/read timeout remains (15, 60).
- Only typed connect/read timeouts, including wrapped body read timeout, and
  typed reset/abort/broken-pipe/transport-timeout OS causes are eligible.
  The offline follow-up also recognizes typed built-in reset/abort/pipe without
  errno (including RemoteDisconnected); it does not infer from ProtocolError text.
- TLS and proxy errors override otherwise timeout-like nested causes.
- Unknown text-only ConnectionError, DNS/refused errors, arbitrary truncated
  payload, HTTP status, decoding/schema/source identity/frozen coverage/history
  revision errors are NOT retried.
- Existing strict TLS, public browser UA, exact source host/path/query/redirect
  checks, catalog/schema guards, staging I/O hardening, frozen U0, overlap,
  transaction preview, append-only gates, atomic publication and readiness
  semantics are unchanged.
- Requests' non-streaming GET must finish consuming the body before staging.
  Failed attempts cannot publish partial raw data or duplicate rows.
- All 124 sectors must finish successfully before overlap/audit/apply.
- Every eligible failure, including exhaustion, records timestamp, sector,
  request kind/page/URL, attempt/budget, exception class/message, typed reason,
  elapsed/total elapsed, HTTP status if available, timeout and backoff.
- Production audit log is independent ignored run metadata. Append, flush,
  fsync and close occur BEFORE another GET. Audit write failure stops immediately.
- Exhaustion raises NetworkFetchBlocker; no incomplete stage may be applied.
- Count-only progress is emitted from inside Docker. No Windows-side active
  staging payload polling occurred.

15/60 is the existing connect/read configuration, not a maximum whole-request
elapsed duration; the measured elapsed values are reported as observed.

## Tests and regression safeguards

38 synthetic cases were added in total: 27 initial cases and 11 typed-disconnect
follow-up cases. Coverage includes first timeout then success;
4-attempt exhaustion; wrapped body timeout/reset; durable audit before retry;
audit-write failure; no duplication; failure of the first OR second sector
blocks apply and preserves canonical hashes; malformed/schema/missing-sector/
untrusted-source errors and historical revision not retried; SSL/proxy/DNS/
unknown errors fail closed; cyclic nested exception graph terminates.

Follow-up regression additionally proves typed no-errno disconnect recovery,
finite exhaustion, TLS/proxy veto, no duplicate staging and canonical untouched
on first/second sector exhaustion. All 55 existing top-level updater test functions/fixtures were AST-identical to
the initial HEAD. AST comparison confirmed 17 critical source/schema/history/
transaction/readiness functions unchanged. No tests were removed, weakened or
newly skipped.

| Stage | Targeted | Full offline |
| --- | --- | --- |
| Baseline | 305 passed, 1 deselected (8.72s) | 865 passed, 2 existing skipped, 18 deselected, 2 warnings (226.06s) |
| Hardening before live | 332 passed, 1 deselected (9.36s) | 892 passed, 2 existing skipped, 18 deselected, 2 warnings (235.58s) |
| After real apply | 332 passed, 1 deselected (9.89s) | 892 passed, 2 existing skipped, 18 deselected, 2 warnings (240.15s) |
| Typed-disconnect follow-up (offline only) | 343 passed, 1 deselected (10.07s) | 903 passed, 2 existing skipped, 18 deselected, 2 warnings (235.72s); 0 failed |

All runs had 0 failed. Targeted includes data/updater, readiness and frozen
Validation preregistration/integrity tests. Default offline suite has no online
Shenwan dependency. Existing warnings are legacy target/missing ETF mapping.

## Actual real-cycle gates

Run ID: `net_safe_live_retry_20260927_v1`.

Native status: UPDATE_APPLIED; snapshot status: PUBLISHED_VERIFIED.

- Fresh strict TLS / catalog / representative trend / schema / source identity:
  PASS.
- Existing TLS mode: PROJECT_LOCAL_STRICT_CHAIN_COMPLETION. The server still
  sends leaf-only; existing pinned intermediate completion verifies hostname/
  server purpose against the unchanged trusted roots. No verify=False/global
  trust store change or newly trusted unknown certificate.
- Catalog: frozen 124 unchanged; no added/removed/renamed sectors.
- Representative 801012: 6,463 rows, latest source date 2026-09-24.
- Full fetch: **124/124 PASS**.
- Full historical overlap: **419,346 rows**, not a sample.
- Historical revision: **0**.
- Historical missing difference: **0**.
- Historical gap-fill difference: **0**.
- Transaction preview and historical prefix identity: PASS.
- Append: **496 rows**, 2026-09-21..2026-09-24, 4 dates x 124 sectors;
  every frozen sector contributed 4 rows.
- No unconfirmed same-day partial bar entered the append; new invalid OHLC: 0.
- Real apply attempted/applied: true/true, through existing transaction gates.
- Native retry log: 11 failed-attempt events, all recovered; 10 ConnectionError
  wrapping typed read timeout and 1 direct ReadTimeout. 9 distinct sectors;
  801081 and 801142 needed a third attempt, all other failed sectors recovered
  on their second. No exhaustion. Total actual scheduled backoff: 13 seconds.
- These failures had no attached HTTP response: status is null, not zero.
- No staging sharing failure was observed; previous I/O patch remains unchanged.

## Snapshot lineage and independently verified historical identity

Parent snapshot:

`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`

New / current snapshot:

`208207c7f85fc6236d7025d96fc61c56b27b049cf35b89bae77d80692b293782`

- Cutoff: 2026-09-18 -> 2026-09-24.
- Row count: 419,346 -> 419,842.
- Append-only historical prefix is byte-identical to original canonical.
- Prefix / golden CSV SHA256:
  `884c7dbaaacf6aa5652b63cde5153265ca383fe5bec18fa0a40c410a76b5a887`.
- New full CSV SHA256:
  `83e6d79e2e91ae27df85e0e3949e87beb9265d6f31e73d10e637935536a32a42`.
- Frozen U0 remains 124; hash:
  `f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a`.
- All 20 historical SOURCE_INVALID OHLC rows and invalid sidecar unchanged.
- 801193 historical missing sessions remain 336, last missing 2023-09-26;
  exact missing-date hash unchanged.
- Original `data/processed/shenwan/` remains unchanged and reproducible.
- Active generation is `data/processed/shenwan_snapshots/208207c7f85fc6236d7025d96fc61c56b27b049cf35b89bae77d80692b293782/`.
- Snapshot manifest records parentSnapshotId, parentManifestHash, appendManifest,
  code/raw/canonical fingerprints, execution gitCommit, cutoff/row counts and
  zero revisions. read_parent verifies the full lineage to the golden base.
- Independent post-apply audit compared all 10 raw fields on all 419,346
  historical rows with 0 changes and independently verified prefix/U0/anomalies/
  date/sector coverage. No hand-constructed returns or performance result.

Lineage paths:

- `data/manifests/shenwan_sector_snapshots/208207c7f85fc6236d7025d96fc61c56b27b049cf35b89bae77d80692b293782.json`
- `data/raw/shenwan/sector_history_append/net_safe_live_retry_20260927_v1/manifest.json`
- `data/manifests/shenwan_sector_snapshots/current.json`

| Evidence | SHA256 |
| --- | --- |
| New snapshot manifest | 46ca83f2930b5c6696c1115629599f34dfac0cb19fb0fba0802bb25096199921 |
| Parent manifest | 2f4e2888f3595b0f9fa8963d5f4c623d6b342ae18f617bffd0f62907c7dd8d2b |
| Append manifest | 1e7b43c06cffb03110c443cce2979ccc8265db9a603a7b15364974393cedfc4b |
| Native live result | 273fc72ee9cb0a4663dfe06f4afa72093230ac60694d68953cb5550b7dc2c3fd |
| Live retry audit | 216abbf4e19bdc1f749b2bac5bbe9eb4486d3770014fdd9592c81f94c134e68e |

## Readiness only; research remains sealed

Formal date/structural-only readiness: **19/60 -> 23/60, delta +4**.
fullValidationReadiness=false. Only calendar, dates, label-end maturity and
structural availability are used. Download/publication does NOT establish any
new classification/PIT/ETF-mapping admission evidence.

- validationOpened=false
- Validation performance read=false
- Validation results generated=false
- Final OOS read=false

## Production idempotency

Run ID: `net_idempotency_dryrun_20260927_v1`. Invoked ONCE with
`cycle --dry-run` from CLEAN execution commit
`24c331cba2b8664a89001db5aa5bbd39a6c8e873`.

- Fresh probe TLS/catalog/trend/schema/source identity: PASS.
- Full fetch: FAIL, 38/124; next sector 801103 inferred from unchanged frozen
  ordering/failure metadata (full terminal URL/traceback not persisted).
- Terminal persisted exception:
  `ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`.
- Native status: OFFICIAL_ENDPOINT_BLOCKED, stage status BLOCKED.
- Typed installed standard-library inheritance:
  RemoteDisconnected -> ConnectionResetError -> ConnectionError -> OSError,
  with errno=null. The initial classifier required a matching numeric errno,
  so this equivalent reset failed closed without retry.
- Seven prior eligible failed-attempt records were recovered during the dry-run:
  six ConnectionError and one ReadTimeout, no retry exhaustion. 801016 recovered
  on its fourth/last permitted attempt.
- The terminal disconnect was NOT included as an eligible retry event; it remains
  preserved in native result/failure evidence. Native logs were not rewritten.
- Overlap, revisions, gap fills, source append candidate: **NOT_RUN/null**, NOT
  zero and NOT PASS. Absence of new source rows was NOT established.
- Real apply attempted/applied: false/false; actual published extra rows: 0.
- Current snapshot, pointer, canonical CSV, snapshot manifest and golden CSV
  hashes exactly match the pre-dry-run observations. No new snapshot published.
- Readiness 23/60 -> 23/60, delta 0; all Validation/OOS seals remain false.
- Idempotency: **NOT_VERIFIED / BLOCKED**, not a successful 0-append result.
- Native dry-run result SHA256:
  `084853087882d1fec8e9b61e2e53d51b8ec846ae577cc85de65c2fd942279710`.
- Dry-run retry audit SHA256:
  `60cc4973e3fd2b974b31ee75249281207b03cd8015fdd0c9afdbc1a121297964`.
- No additional dry-run or real cycle was invoked. The exact typed-reset omission
  was corrected and tested offline only, within the original authorized
  equivalent-transient-transport scope. No gate was loosened.

The failed safe check does not undo or invalidate the previously hash-verified
publication, and must not be misreported as a failed/no-write real cycle.

## Reports / handoff / evidence

- Report: `docs/research/shenwan_network_fetch_resilience_live_retry_v1_report.md`.
- Handoff: `docs/research/handoff_shenwan_network_fetch_resilience_live_retry_v1.md`
  and corresponding JSON.
- Ignored native live result/retry log:
  `data/manifests/shenwan_official_runs/net_safe_live_retry_20260927_v1/`.
- Independent evidence outside repo:
  `D:\QuantForge\temp\shenwan-network-resilience-v1\` (pre-audit,
  full raw historical audit, post-cycle check, independent post-apply audit,
  report basis, idempotency check). Data/log files are not committed.
- Earlier UA/I/O failure reports are retained as historical records, not rewritten
  to claim they applied data.

## NEXT SAFE ACTION

Human review of the failed idempotency check, then a separately authorized safe
full dry-run of the typed-disconnect follow-up (no automatic second real cycle).

WAIT FOR MORE LEGALLY AVAILABLE SHENWAN OFFICIAL DATA.

This task stops here. Any further network cycle requires fresh authorization. Never
open Validation automatically; at 60/60 stop for human review first.

SHENWAN OFFICIAL REMAINS THE CANONICAL F1 DATA SOURCE
NO THIRD-PARTY MARKET DATA SOURCE WAS SPLICED INTO THE SERIES
NO THIRD-PARTY DATA SOURCE
VERIFY_FALSE NOT USED
NO HISTORICAL PREFIX REVISION
VALIDATION PERFORMANCE WAS NOT READ
NO VALIDATION RESULTS WERE GENERATED
VALIDATION REMAINS SEALED AND UNSEEN
FINAL OOS REMAINS SEALED

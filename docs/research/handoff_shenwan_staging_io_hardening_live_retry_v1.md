# Handoff: staging I/O hardening + one live retry V1

FINAL STATUS: SHENWAN_STAGING_IO_HARDENED_LIVE_RETRY_BLOCKED

Hardening commit: `4a607edcac3b9c5bc98c9b6537a6409d643503f9`.
Branch: `experiment/sw-sector-index-research-baseline`.

Original PermissionError was errno 13 at the staging stage.json atomic replace.
Existing writer already closed/fsynced its unique temp. No writer leak found;
external locking process UNKNOWN, no historical handle trace. New bounded
staging-only replace retries are durable-audited, fail closed and cannot alter
source/schema/overlap/prefix/publication gates. Progress comes from Docker, not
Windows live staging readers.

The ONE authorized new run `io_safe_live_retry_20260927_v1` has been consumed.
Fresh strict TLS/catalog/trend/schema probe PASS, then first full fetch suffered
an official HTTPS read timeout. Complete full fetch 0/124; overlap/revision/
preview NOT_RUN/null. No real apply attempted/applied. No PermissionError/retry
audit event in this live run. Hardening passed synthetic tests; live apply is
NOT verified. Do not run another probe, cycle or apply under this authorization.

Actual append 0, dates null; new snapshot/cutoff null. Parent/current unchanged:
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`,
cutoff 2026-09-18, rows 419346. Prefix SHA256 unchanged, 124 U0, 20 invalid OHLC,
801193's 336 missing sessions (last 2023-09-26) preserved. No new lineage/manifest.
Prior dry-run's 496 rows are candidate-only, not this run's fresh audit or append.

Readiness recalculated: 19/60 -> 19/60, delta 0; VALIDATION_NOT_READY.
fullValidationReadiness=false; validationOpened=false;
validationPerformanceRead=false; validationResultsGenerated=false;
finalOosRead=false. Production idempotency NOT_RUN (no apply); offline contracts
PASS. Tests before live: targeted 305 passed; full offline 865 passed, 2 existing
skipped, 18 deselected. Post-live targeted 305 passed; full offline 865 passed,
2 existing skipped, 18 deselected, 2 warnings (234.99s). Final failed count 0;
no existing test weakened/deleted, no new skip. Imports PASS.

Detailed evidence/tests: `shenwan_staging_io_hardening_live_retry_v1_report.md`.
Machine state: `handoff_shenwan_staging_io_hardening_live_retry_v1.json`.
Native ignored run evidence:
`data/manifests/shenwan_official_runs/io_safe_live_retry_20260927_v1/result.json`.
External evidence: `D:/QuantForge/temp/shenwan-staging-io-hardening-v1/`.
Final HEAD is the local documentation commit containing this handoff.

NEXT SAFE ACTION: STOP. Review official network availability; another network
probe/cycle requires fresh user authorization and a new run ID. Do not bypass via
apply or use cached prior dry-run data. Keep gates, stages and research seals.

NO THIRD-PARTY DATA SOURCE

VERIFY_FALSE NOT USED

NO HISTORICAL PREFIX REVISION

VALIDATION REMAINS SEALED AND UNSEEN

FINAL OOS REMAINS SEALED

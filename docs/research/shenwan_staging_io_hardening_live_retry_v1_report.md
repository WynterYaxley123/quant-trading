# Shenwan staging I/O hardening + one safe live retry V1

Date: 2026-09-27 (Asia/Shanghai). This is data infrastructure, not research,
backtesting, model tuning or Validation execution.

FINAL STATUS: **SHENWAN_STAGING_IO_HARDENED_LIVE_RETRY_BLOCKED**

The staging hardening passed synthetic/regression tests and was committed before
the ONE authorized live retry. That retry's fresh probe passed strict TLS,
catalog, representative trend and schema checks. The first full-sector fetch
then stopped on an official HTTPS read timeout, not PermissionError. No overlap,
transaction preview, append or snapshot publication occurred. Do not retry again
under this authorization.

## Git and execution boundary

Branch: `experiment/sw-sector-index-research-baseline`.

- Initial HEAD: `662533d206bf70486aafde705a0c15c91205e65d`; worktree/index clean.
- Hardening/execution commit: `4a607edcac3b9c5bc98c9b6537a6409d643503f9`.
- Commit subject: `fix: harden Shenwan staging atomic replace sharing failures`.
- Worktree/index were clean before the live cycle. Final HEAD is the local
  documentation commit containing this report; inspect `git rev-parse HEAD`.
- Only provider staging I/O, CLI progress/error labeling, associated tests and
  operations documentation changed. No strategy/model/candidate/split change.
- All Python/tests used the existing `quant-research` Docker container with BOTH
  `D:/quant-trading/docker-compose.yml` and
  `D:/QuantForge/temp/quant-trading-host-port.override.yml`.
- Docker image/dependencies, TLS configuration and public-browser-UA contract
  unchanged. No Windows quant execution, install, rebuild, push or merge.

## Original PermissionError: evidence, not process attribution

Prior run: `ua_live_append_20260927_v1`. Two raw responses had been saved when the
second sector's stage metadata update failed.

Code path:

```text
execute(cycle) -> stage(second sector) -> atomic_json
-> durable_bytes(unique xb/write/flush/fsync/context-manager close)
-> sync_dir(open/fsync/finally close) -> os.replace
```

Recorded exception: `PermissionError`, errno `13`, message `Permission denied`.

```text
/workspace/data/staging/shenwan_official/ua_live_append_20260927_v1/stage.json.1e413fd5f83040c481f3c07518908fb8.tmp
 ->
/workspace/data/staging/shenwan_official/ua_live_append_20260927_v1/stage.json
```

Original `winerror`, exact exception timestamp and full traceback were NOT
persisted. The replace path is corroborated by the recorded exception, retained
temp and source inspection; it is not a newly reconstructed traceback.

The failed temp is 8,715 bytes, mtime `2026-09-27T02:44:23.8097835+08:00`.
The subsequently written BLOCKED stage is 8,962 bytes, mtime
`2026-09-27T02:44:23.8307854+08:00`. These are filesystem observations, not precise
exception/recovery timestamps. Container/file UID 57439, mode 0644, and writable
file/directory checks do not indicate a permanent write-permission denial.

The original implementation already closed and fsynced the temp writer before
replace, and closed the directory descriptor in `finally`. No code-level writer
leak was found. New tests instrument close/fsync ordering, including closing the
retry audit writer before retry. Accessible current container descriptors showed
no matching old-stage handle; the failed process had exited, so this cannot
establish its historical handle state.

Windows handle tools were unavailable. Read-only `openfiles /query` reported
local-object tracking disabled and access denied. No tracking was enabled, tool
installed, ACL changed or process killed. A Windows bind-mount sharing conflict
is plausible, but the responsible process and precise external cause remain
**UNKNOWN**. Do not blame a reader, scanner or application without handle evidence.
The old temp/staging evidence remains intact.

## Minimal safe hardening

Only run-level `stage.json` / `audit.json` metadata receives bounded replace
retry. The canonical pointer retains its original one-shot publication path.

- Exclusive UUID temp, write/flush/fsync/fully close before replace; reuse the
  SAME closed durable temp on retry. No refetch, rewrite or duplicated rows.
- Maximum five replace attempts, backoff 0.1/0.25/0.5/1.0 seconds, total 1.85s.
- Eligible only for PermissionError/EACCES with winerror absent or 32/33, same
  parent directory, regular non-symlink files and confirmed writable paths.
  Bare EACCES through Docker is only an eligible transient candidate, NOT proof
  of an external process. Persistent denials still stop at the finite budget.
- EPERM, explicit winerror 5, missing write permissions and other I/O errors are
  not retried. No chmod/ACL/trust-store workarounds.
- Each denied attempt records paths, timestamp, errno/winerror/message, attempt,
  budget, eligibility and delay in `io_replace_audit.jsonl`. The audit is flushed,
  fsynced and closed BEFORE retry; inability to record it stops immediately.
- Exhaustion is a `StagingIOBlocker`; old target and failed temp are retained.
  In-loop failures record immutable `failure.json` without a second retry budget.
  Final STAGED-write failure leaves the previous FETCHING state, not an accepted
  partial stage. CLI labels I/O failures `STAGING_IO_BLOCKER` correctly.
- Count-only progress comes from the writer inside Docker on stderr. Stdout
  remains final JSON. No Windows-side live staging payload polling was used.

AST comparison with the initial committed implementation found 14 selected core
source/schema/parser/overlap/finalization/transaction/publication/readiness
functions/classes unchanged, including `OfficialClient`. All source, schema,
revision, historical-prefix, snapshot and sealed-research gates remain in force.

## One authorized live retry: actual outcome

Run ID: `io_safe_live_retry_20260927_v1`.

```text
python scripts/data/update_shenwan_official.py cycle --run-id io_safe_live_retry_20260927_v1
```

Exactly one invocation from clean committed code; no subsequent cycle/probe or
network retry. Source endpoint/GET/anonymous public access unchanged. No Cookie,
Referer, alternate provider or disabled TLS.

Fresh probe: PASS. Catalog exactly 124 with no code/name drift. Representative
trend 801012 returned 6,463 rows, latest finalized source date 2026-09-24; schema
compatible. Strict TLS used the existing project-local pinned intermediate-chain
completion against unchanged certifi roots, hostname and server-purpose checks.
The server still sends only its leaf: standard roots alone remain insufficient,
but the existing verified chain-completion mode passes; no global trust mutation.

The full fetch subsequently failed on its first sector:

```text
ConnectionError: HTTPSConnectionPool(host='www.swsresearch.com', port=443): Read timed out.
```

CLI exit 1 / `OFFICIAL_ENDPOINT_BLOCKED`; stage `BLOCKED`, zero complete raw
files, zero I/O retry events. This establishes a read timeout for this request,
not a renewed TLS failure, HTTP 508 diagnosis or proved persistent source outage.
The real filesystem retry path was not exercised by this network failure.

| Required item | This live run |
| --- | --- |
| Full frozen-U0 fetch | FAIL, 0/124 complete (probe sample is not full fetch) |
| Historical overlap rows / revision / missing / gap-fill | NOT_RUN / null |
| Transaction preview and fresh append candidate | NOT_RUN / null |
| Cycle invoked | true, exactly once |
| Real apply attempted / applied | false / false |
| Actual appended rows / dates | 0 / null |
| New snapshot / cutoff / published row count | null / null / null |
| Snapshot publication / append manifest / new lineage | none |

Prior dry-run `ua_full_dryrun_20260927_v1` verified 124/124, 419,346 overlap rows,
revision/missing/gap-fill differences zero and a 496-row candidate dated
2026-09-21..2026-09-24. That is **prior-run evidence only**, not this retry's fresh
overlap audit, and it does not authorize applying cached/partial data.

## Canonical identity, anomalies and readiness

Parent and current snapshot:
`872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.

Old/current cutoff: `2026-09-18`; old/current rows: `419346`.
No new generation/current pointer/lineage was published; original golden parent
remains reproducible.

- Prefix/full-parent CSV SHA256 unchanged:
  `884c7dbaaacf6aa5652b63cde5153265ca383fe5bec18fa0a40c410a76b5a887`.
- Frozen U0 unchanged, 124 sectors, SHA256:
  `f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a`.
- 20 SOURCE_INVALID OHLC preserved; row-key SHA256:
  `202043fbc25582502bfaa63d3f359fefb11ea75a82ebfce4973fd064f7d87755`.
  Invalid sidecar SHA256:
  `ddd5a362b5c68274ce6e3ea5c145fd65e03065b94fda0fe3cebb4a8378dde23d`.
- 801193 missing 336 common sessions, last 2023-09-26, unchanged;
  missing-date SHA256:
  `00c586669468962b70f1a01e31e8bd9378e17ef16d06d3f6fe9bc568e8aa1674`.

Formal readiness recalculated before and after using calendar, dates, label-end
maturity and structural availability only: **19/60 -> 19/60, delta 0**.
`fullValidationReadiness=false`, `validationOpened=false`,
`validationPerformanceRead=false`, `validationResultsGenerated=false`,
`finalOosRead=false`. No returns, label values, predictions, RankIC, Spread, Top5
or candidate performance was consumed for readiness. No Validation or Final OOS
execution occurred. Status remains `VALIDATION_NOT_READY`.

Production idempotency dry-run: **NOT_RUN**, because no apply occurred and this
single retry failed. It is not reported as a verified zero-append live run.
Synthetic idempotency/no-duplication contracts passed.

## Tests

Targeted command:
`pytest -q tests/data tests/test_f1_validation_readiness_v1.py tests/test_f1_independent_validation_v1.py`.
Full offline command: `pytest -q`.

| Phase | Targeted | Full offline |
| --- | --- | --- |
| Before edits | 290 passed, 1 deselected (9.00s) | 850 passed, 2 existing skipped, 18 deselected, 2 warnings (238.79s) |
| Hardening, before live | 305 passed, 1 deselected (9.24s) | 865 passed, 2 existing skipped, 18 deselected, 2 warnings (231.30s) |
| After failed live retry | 305 passed, 1 deselected (8.34s) | 865 passed, 2 existing skipped, 18 deselected, 2 warnings (234.99s) |

15 new synthetic cases cover first replace PermissionError then success,
persistent denial/fail-closed budget, durable audit failure, non-eligible I/O,
unique temp, fully closed/fsynced handles, partial-publication prohibition,
unchanged canonical/pointer on failures at each stage, no duplicate fetch/rows,
unchanged pointer semantics, progress and correct CLI blocker labeling.
Final failed count: 0. Existing tests were not weakened/deleted/skipped; no new
skips were introduced. Imports pass.

## Evidence and handoff

- Machine handoff: `docs/research/handoff_shenwan_staging_io_hardening_live_retry_v1.json`.
- Short handoff: `docs/research/handoff_shenwan_staging_io_hardening_live_retry_v1.md`.
- Ignored native run result:
  `data/manifests/shenwan_official_runs/io_safe_live_retry_20260927_v1/result.json`.
  SHA256: `bde5f2b7e8c8332733a6390a99eae58f6c7fed64337dfd64a38b04340a895eed`.
- Ignored blocked stage: `data/staging/shenwan_official/io_safe_live_retry_20260927_v1/`.
- Repo-external audit/check evidence:
  `D:/QuantForge/temp/shenwan-staging-io-hardening-v1/pre-audit.json` and
  `post-cycle-check.json`.
- Original UA/full-dry-run report remains unchanged:
  `docs/research/shenwan_official_ua_formalization_full_cycle_v1_report.md`.

NEXT SAFE ACTION: Stop. Review official network availability and obtain fresh user
authorization before another probe/cycle with a new run ID. Do not use apply to
bypass this failed full cycle, reuse prior dry-run data, alter timeouts/source
contracts without review, or open Validation. Preserve both failed stages and
the frozen historical prefix. Wait for more legally available Shenwan official
data; reaching 60/60 later still requires human review before opening Validation.

```text
NO THIRD-PARTY DATA SOURCE
VERIFY_FALSE NOT USED
NO HISTORICAL PREFIX REVISION
VALIDATION REMAINS SEALED AND UNSEEN
FINAL OOS REMAINS SEALED
```

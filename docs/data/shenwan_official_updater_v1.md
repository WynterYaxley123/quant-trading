# Shenwan official append-only updater v1

This is data infrastructure, not a strategy/backtest/Validation runner. Only the
original HTTPS `www.swsresearch.com/institute-sw/api/index_publish/current/`
(page, page_size=50, indextype=二级行业) and `trend/` (swindexcode, period=DAY)
are market-data sources. No AKShare calls or alternate-provider fallback.

## Operations (inside the existing quant-research container)

```text
python scripts/data/update_shenwan_official.py probe
python scripts/data/update_shenwan_official.py cycle --dry-run
python scripts/data/update_shenwan_official.py cycle
python scripts/data/update_shenwan_official.py readiness
python scripts/data/update_shenwan_official.py stage --run-id <unique_id>
python scripts/data/update_shenwan_official.py audit --run-id <staged_id>
python scripts/data/update_shenwan_official.py apply --run-id <staged_id> --dry-run
python scripts/data/update_shenwan_official.py apply --run-id <staged_id>
```

Use BOTH `docker-compose.yml` and the approved host-port override. A write-capable
run requires a clean committed checkout. `readiness` is offline and writes nothing.
`probe` writes only ignored health/run metadata; no raw/canonical publication.
`cycle --dry-run` stages and builds a private transaction preview, never a current
pointer. No scheduler is configured. A 60/60 gate requires human review; it never
opens Validation or Final OOS.

## Strict TLS

OpenSSL observes the server chain with certificate verification still enabled.
Only a verified missing-intermediate case enables the bundled public GeoTrust
intermediate. Its SHA/AIA, CA property, issuer equality, validity, root chain,
leaf hostname and server-auth purpose are rechecked. The temporary adapter bundle
is the unchanged certifi roots plus that intermediate; no partial-chain trust,
leaf trust, system/Conda/certifi/Windows mutation, or disabled TLS. Standard chains
use standard roots. The advertised catalog `next` may be HTTP `/api/...`; it is
recorded but NEVER followed. Authorized HTTPS pages are constructed directly.

## Transaction / lineage

1. Probe catalog and representative 801012, preserving HTTP/redirect evidence.
2. Fetch ALL frozen U0 into ignored `data/staging/shenwan_official/<run_id>/`.
3. Require exact schema, code/date uniqueness, source identity and response SHA.
4. Compare ALL historical rows through the dynamically read parent cutoff using
   exact Decimal numeric equality for OHLCVA. Any revision, deletion or backfill
   rejects the whole run, including repairs to known invalid bars/missing 801193.
5. Exclude the fetch-day natural date with `UNCONFIRMED_FINAL_SESSION`: there is
   no proved same-day finalization condition. Never invent weekday/calendar rows.
6. Build immutable delta raw, its manifest, a complete canonical generation and
   a versioned snapshot manifest in staging. New invalid source bars are retained
   with the existing quality rules; null volume/amount stay null.
7. Copy ALL historical CSV row bytes, including original provenance and precision.
   Filter the candidate through parent cutoff and require the parent file SHA.
8. Acquire an exclusive publish lock, recheck parent and candidate hashes, fsync,
   materialize immutable delta/generation/manifest, then atomically replace ONE
   `data/manifests/shenwan_sector_snapshots/current.json` pointer last.
9. Reverify complete lineage, raw/canonical hashes and prefix after publication.
   Recompute readiness with only date/quality columns under frozen rules.

`data/processed/shenwan/` remains the immutable golden original. New active
canonical generations are `data/processed/shenwan_snapshots/<snapshot_id>/`.
Framework loader default resolves current once per call; explicit legacy paths
continue selecting the golden base. Frozen strategy/research files are untouched.
Do not run old full-table importers against an active snapshot. The existing
`shenwan_sector.snapshot_id` algorithm is reused: original inputs still produce
the original ID; new immutable delta/manifest/code fingerprints extend its input.

The current pointer is the only authority, not directory modification times.
Crashes before pointer replacement leave a fully usable previous generation.
Immutable orphans/evidence are retained for human review; no automatic cleanup or
stale-lock breaking. A crash after replacement is a committed publication and
must be re-audited, not falsely reported as a rollback. Same accepted source data
returns `NO_NEW_CANONICAL_DATA` without publishing a meaningless snapshot.

## Limitations / seals

Download success does not establish strict PIT admission. Classification version,
publication timing, units, recalculation policy and ETF mapping remain unresolved
where the frozen admission says null/unknown. This updater neither upgrades them
nor reads predictions, label values, returns, research performance or OOS.

## Staging I/O hardening V1

The previous failed run (`ua_live_append_20260927_v1`) reached
`stage -> atomic_json -> os.replace` and got PermissionError errno 13 for
`stage.json.1e413fd5f83040c481f3c07518908fb8.tmp -> stage.json`.
The existing temp writer already used exclusive unique creation, flush/fsync,
context-manager close and directory sync BEFORE replace. No code-level leaked
writer was found. The old failed process has exited; present-day `/proc` checks
cannot prove past handles. Windows handle tooling was absent; `openfiles /query`
reported disabled local-object tracking and access denial. No tracking/settings
were enabled. The precise external locking process remains UNKNOWN.

Only run-level staging `stage.json` and `audit.json` opt into replacement retries.
The canonical current-pointer replacement, raw files, directory moves, locks and
all source/schema/overlap/history/publication gates are unchanged.

- Same unique, fully closed/fsynced temp is reused; no refetch or duplicate writes.
- At most five attempts; backoff 0.1, 0.25, 0.5, 1.0 seconds (1.85 seconds total).
- Only PermissionError/EACCES, with no explicit Windows denial (winerror must be
  absent or sharing/lock codes 32/33), same directory, regular non-symlink files
  and confirmed file/directory write access is eligible. Bare EACCES can be how
  Docker exposes a Windows sharing conflict; it does NOT establish a process's
  responsibility. Persistent eligible failures still stop at the finite limit.
- EPERM, winerror=5, absent write permissions and other I/O errors are not retried.
- Every retry is preceded by a flushed/fsynced `io_replace_audit.jsonl` record
  containing timestamp, paths, attempt/budget, errno/winerror/message and delay.
  Failure to record the audit stops immediately; there is no unaudited retry.
- Exhaustion raises `StagingIOBlocker`; the temp and old target remain intact.
  An in-loop staging failure writes immutable `failure.json`, not another retry
  budget against the blocked target. A final STAGED replacement failure leaves
  the old FETCHING record, never an accepted partial stage.
- CLI reports STAGING_IO_BLOCKER, not a false HTTP verdict, and reads immutable
  failure metadata where present. All errors still prohibit apply/publication.

Progress is count-only writer output to stderr from INSIDE Docker. Stdout retains
the final result JSON. Do not poll/read active staging files from Windows; do not
kill processes, change ACLs, delete evidence or bypass gates to release a handle.

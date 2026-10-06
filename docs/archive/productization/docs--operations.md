# Operations guide

[English](operations.md) | [简体中文](operations.zh-CN.md)

## Operational architecture and ownership

Git is the `SOURCE_OF_TRUTH_REPOSITORY`: source, tests, templates, dependency pins,
deployment logic and public knowledge. A `LOCAL_DEPLOYMENT_ROOT` owns facts,
accounts, private evidence, logs and local configuration. The maintainer reference
root `D:\QuantForge` is an implementation detail; users choose their own external
root. [Deployment](deployment.md) covers bootstrap and the reference directory layout.

An operational checkout is a deployed copy of canonical Git source, not a second
source authority. Keep it clean and independently owned. Its presence under a local
deployment root does not authorize committing that root. Provider source stays
external and pinned; mutable facts and all account/control roots stay separate.

## Canonical runner and daily lifecycle

Forward operation uses `services/etf-quant-runner/one_shot.py` for both versions.
Pass one external `--config` for compatibility, or repeat `--config` once for V1
and once for V2. The pair is checked for distinct versions and disjoint resolved
account/control paths before either runs. Calls execute sequentially; a failure
in one version returns a bounded receipt and still permits the other version's
independent invocation. An aggregate blocked result exits with code 2.

```powershell
& $TransportPython -B "$Checkout/services/etf-quant-runner/one_shot.py" `
  --config $V1Config --config $V2Config
```

Use an explicit Python interpreter for standard-library transport only. Numerical
code runs in Docker. Fetch remote metadata before an operational invocation and
use a clean committed checkout whose HEAD equals `origin/main`; never switch or
reset an occupied deployment merely to satisfy this gate. Supply absolute external
configuration paths and the pinned existing images/source. The V2 container config
must match the documented mounted paths exactly.

Invoke after the official session's finalized close (15:05 Shanghai or later).
The entry refreshes completed factual sessions, verifies certificates and exports,
then creates only a genuinely current post-freeze signal. A committed same-date
signal returns before provider refresh or model execution. Reinvoke on factual
waiting outcomes; at the next eligible T+1 close, the existing persisted intent
uses genuine raw opening evidence for delayed paper accounting and current NAV.
An unavailable provider or ETF never authorizes guessed prices or a retroactive
intent. Integrity blockers require diagnosis; waiting receipts remain visible
through the read-only API without replacing the last verified account/NAV.

## Scheduler

The Windows host owns scheduling through
`scripts/Install-ForwardShadowTask.ps1`. Its task wakes the standard-library
`services/etf-quant-runner/scheduled_wake.py`, which updates an exclusively owned
operational checkout by fetch and fast-forward, then invokes the exact canonical
command above. A dirty or divergent checkout blocks without discarding changes.
Use a permanent clean clone/worktree at merged main, separate from research and PR
worktrees. Copy `services/etf-quant-runner/scheduler.config.example.json` outside Git;
fill the checkout, existing transport Python/Git executables, two version configs
and an existing external log directory. The configs bind the existing independent
accounts; installation never resets them. Preflight and install from that checkout:

```powershell
& $TransportPython -B "$OperationalCheckout/services/etf-quant-runner/scheduled_wake.py" `
  --deployment $DeploymentConfig --dry-run
& "$OperationalCheckout/scripts/Install-ForwardShadowTask.ps1" -Deployment $DeploymentConfig
```

The non-admin task uses the current user's interactive token and stores no password.
It wakes daily every 15 minutes from 15:05 through the seven-hour Shanghai retry
window, converted to the host's local time, and five minutes after login. It allows
one task instance, catches missed schedules and retries failures three times.
The runner owns holidays, data maturity and both signal/fill decisions. On ordinary
reboot/login, Windows retains the task; Docker Desktop and its images must be
available in that user session. Logged-out, sleeping or unavailable hosts cannot
guarantee a signal. Missed dates remain blocked, with no backfill.

Each wake emits a compact UTC JSON receipt with code commit, per-version runner
decision, factual data date, state identity and available business counts. External
log files omit holdings, prices and child stderr. WAIT/NOOP exits 0; runner blockers,
Git, provider-process and logging failures exit 3 for task retry. The canonical
runner still exits 2 for integrity blockers. Dry-run verifies paths and clean
merged-main identity without invoking the runner or updating the checkout.
The scheduler CLI dry-run still writes a diagnostic receipt to its configured
external log root. It creates no signal, intent, fill or account generation.

## Idempotence and crash recovery

Host transport locks serialize invocations. Account publication and recovery both
run in Docker's Linux lock domain; Windows byte locks cannot coordinate with Linux
file locks on mounted paths. Account mutexes release on process death. A journal
written before immutable generation publication lets restart
complete only the exact hash-verified prior state and latest pointer, preserving
original timestamps. Incomplete stages publish nothing; corrupted journals and
ambiguous legacy locks require diagnosis. Same-date signals, intents, fills and NAV
are idempotent, including crashes before/after pointer publication.
On holidays the workflow arms without business records. The next eligible date
comes from the verified official calendar and release availability; a still-waiting
current trading date is retained, rather than silently skipped to tomorrow.

The 2026 exchange calendar closes October 1–7 and resumes October 8, as announced
by [SSE](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)
and [SZSE](https://investor.szse.cn/disclosure/notice/general/t20260917_622911.html).
This dated example never overrides the runtime calendar/time gates.

## Services, console and trust boundaries

The console starts dashboard and two read-only APIs without invoking a runner,
refreshing data or initializing a formal epoch. Supply machine-local configuration
outside Git via ETF_QUANT_CONSOLE_CONFIG or -Config. Runtime/control roots are absolute
paths outside the checkout. Legacy deployment defaults are compatibility examples,
not contributor requirements.
For a joint console, add absolute `v2_runtime_root` and `v2_control_root` to the
external console config (or explicitly set the matching `ETF_QUANT_V2_*` variables).
Supply both; all account/control roots must be disjoint. The launcher binds both
versions, includes both roots in process reuse identity, and checks V2 readiness.
The read-only Research workspace uses `RESEARCH_WORKSPACE_CONFIG` or the existing
external control's `research-workspace.json`; approved Development artifacts remain
in their existing external directory. Absence is an honest connected empty state.

The launcher supports configurable ports and shares DASHBOARD_ORIGINS with both APIs.
Standalone ETF API defaults to localhost/127.0.0.1 on 5173/4173. Configure
ETF_QUANT_DASHBOARD_PORT or comma-separated exact DASHBOARD_ORIGINS. Wildcards,
credentials, paths, queries and fragments are invalid. APIs bind locally.

Compose Jupyter requires a nonempty JUPYTER_TOKEN supplied in the process environment
or ignored local .env; both Compose and container shell reject absence. Its published
port remains loopback. Never commit the token. Config edits do not authorize a deployed
research-service restart or rebuild.

Runner keeps argv arrays and disables shell execution. Model reference names accept
bounded letters/digits/dot/underscore/hyphen, without traversal. Mount source values
reject Docker delimiter/quote grammar. A new implementation certificate does not
authorize a formal signal or relax historical branch guards.

## Decisions and missed T+1 recovery

WAIT means evidence/calendar maturity is insufficient; retrying may become legal
without changing the model. SIGNAL commits a current legal finalized-close decision.
FILL performs simulated accounting with verified actual raw T+1 opening evidence.
NOOP preserves an already handled date. A blocked integrity result is not WAIT and
must not be bypassed. All decisions preserve original chronology.

For `ABANDONED_MISSED_T1`, retain the terminal missed intent and its evidence.
Future legal epochs can proceed through the canonical runner. Never fabricate a
historical opening, move an old intent to another date, remove the terminal record
or replay an epoch to obtain a preferred outcome.

## Stale locks and process ownership

Distinguish active kernel mutexes from historical transport/legacy lock records.
Before considering recovery, establish process identity, start time, executable,
checkout and account ownership. A PID alone is insufficient because it can be reused.
Do not delete a lock just because its timestamp is old. Quiesce only an owned writer;
ambiguous ownership or corrupted journals require diagnosis. Let the canonical
hash-verified journal recovery complete the prior generation. Do not edit ledgers.

## Provider delay and networking

Keep unavailable/missing source data visible as a waiting or blocked receipt.
Never substitute a cache with unproven PIT time, fill gaps manually, weaken TLS or
upgrade CNEquity silently. Check pin, source/export configuration, publication
evidence and provider-specific diagnostics without dumping restricted rows.
Keep data acquisition separate from network-disabled numerical/accounting execution.

Windows port errors can come from HNS excluded ranges rather than listeners.
Use [host-ports.mjs](../scripts/operations/host-ports.mjs) for read-only diagnostics;
parameterize loopback publication with the
[Compose template](../config/deployment/compose.host-ports.example.yml).
Preserve internal ports/images/mounts. Never reset global DNS, locale, firewall or
install a remote-control product as routine project recovery.

## API, dashboard and runtime health

Check service ownership and loopback ports before restarting. ETF API health verifies
source/certificate and runtime admission; a reachable process is not proof of a
valid account. Research API serves only approved Development artifacts and keeps
its separate trust boundary. Verify the dashboard's version, account identity,
as-of date, integrity and honest empty/waiting state. Do not launch a runner as a
health check. Preserve the last verified account when a newer observation is blocked.

The [read-only deployment verifier](../scripts/operations/verify_deployment.py)
checks selected source/state roots and provider identity without parsing market or
ledger files. A successful boundary check is not a complete data/readiness certificate.
Use existing account generation/certificate checks for runtime integrity.

## Logs, backup and restore

Keep operational receipts, stdout/stderr, provider caches and private evidence
external. Public diagnostics should report identifiers/counts without token values,
paths, holdings, market rows or child stderr. Limit local log retention according to
your deployment policy; do not delete the only failure/recovery evidence.

Back up a coherent account/control generation, configuration and corresponding
source/image/provider pins while the owned writer is quiescent, or use a verified
immutable generation. Treat backups as private; source licensing grants no data
redistribution rights. Verify hashes and identity before restore. Restore is a
deliberate operator action, never an engineering fixture installation. Keep failed
state for diagnosis and preserve original event timestamps.

## Deployment update and safe restart

Review and merge a source PR with passing CI before any deployment switch. Back up
state and inspect ownership, dirty status, exact source transition and effective
Compose configuration. Fast-forward only a clean owned checkout; do not reset/stash
user work. A source update does not authorize image/provider upgrades or model changes.
Keep referenced local scripts/configs until a replacement is verified from merged
main. An operational clone remains legitimate local deployment source.

For an owned console restart, check its process receipt against executable, start
time and checkout; stop only that verified process. Start the observation launcher
with the same external configuration and inspect health. Do not kill arbitrary port
owners. For writer recovery, first preserve state and use the canonical recovery
protocol. Never force a formal cycle merely to verify restart.

## Troubleshooting and forbidden operator actions

| Symptom | Safe first check |
| --- | --- |
| Missing roots or provider mismatch | Read-only boundary verifier and exact external pin |
| Windows bind failure | Reservations plus TCP endpoint diagnostic; effective loopback override |
| Waiting source/calendar | Source publication time, official session and maturity gates |
| Dirty/divergent operational checkout | Preserve work; inspect fetch/fast-forward failure |
| Stale receipt or suspected lock | Process ownership and verified immutable generation/journal |
| Empty Research API | Approved Development root/config, without mounting sealed evidence |
| Failed runtime integrity | Source certificate, file hashes and published generation chain |

Never create retroactive fills, edit ledgers manually, bypass integrity checks,
replace accounts from historical fixtures, run model search through the production
runner, commit secrets/private evidence, enable a real broker or introduce real orders.
Readiness and API connectivity do not establish profitability. Recovery must keep
V1/V2 specifications, mapping policy, consumed OOS identity and namespace isolation.

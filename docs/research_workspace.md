# Approved Development research workspace

Run `& ./scripts/Start-EtfQuantConsole.ps1` to connect the configured machine's
existing approved Development workspace and open all six Research pages.
Research is read-only: it cannot train, backtest, create runs, refresh data,
change approval or invoke ETF Shadow. Validation and Final OOS remain **SEALED**.

## Identity and approval

The repository-safe [approval registry](../services/research-api/config/development-workspaces.v1.json)
contains logical ID `shenwan-iteration1-development`, collection
`shenwan_sector_index`, Development-only approval and two previously audited
Iteration-1 IDs. It contains no research payloads or machine paths. Each entry
pins the SHA256 of its original `metadata.json`, which pins all 29 content files.
Approval evidence is the [original artifact audit](../services/research-api/docs/artifact-audit.md)
and the owner's authorization to connect this existing Development workspace.

This is an explicit operator/repository approval contract, not a cryptographic
owner signature. Directory existence, names and filesystem mtime cannot confer
approval. The registry is checked before opening a run's metadata. Unregistered
runs are never opened; a configured catalog with only unapproved folders is
rejected. Legacy baseline folders and unrelated directories are not adapted.

Original metadata has no separate `created_at`. Its recorded `run_id` includes
UTC creation time. The registry makes that time explicit with
`timeSource=METADATA_RUN_ID_UTC`, validates it against the metadata identity and
orders approved runs by timestamp descending, then stable run ID descending.
Filesystem mtime has no role. Run selection changes only the URL's `run` query;
a valid deep link or refresh preserves it.

## Machine-local configuration

The launcher reads optional `control_root/research-workspace.json` outside Git:

```json
{
  "schemaVersion": "1.0.0",
  "artifactId": "shenwan-iteration1-development",
  "reportRoot": "<external-approved-research-report-root>"
}
```

`reportRoot` is the parent of `shenwan_sector_index`. Absolute paths are allowed
in this machine-local file; relative paths resolve from the file's directory.
Relocating approved immutable files requires updating this pointer, not source.

Resolution precedence:

1. Explicit launcher `-ResearchReportRoot`.
2. Caller `RESEARCH_REPORT_ROOT`.
3. Caller `RESEARCH_WORKSPACE_CONFIG`, pointing to the local JSON above.
4. Optional `control_root/research-workspace.json` found by the launcher.
5. Optional `<this checkout>/reports/research`.

The first configured source wins even if invalid; it never falls back to another
artifact. `RESEARCH_ARTIFACT_ID` overrides the local file's identity; otherwise
that identity or a sole registry workspace is selected. Multiple workspaces
without explicit selection are an error. Direct API startup supports these
environment variables; the unified launcher supplies the external control-root
pointer. Caller environment is restored after launching child services.

No local configuration and no optional report catalog is healthy
`NOT_CONFIGURED`. A missing explicit root, malformed config, unknown identity,
unapproved catalog, wrong phase, schema/hash failure or symlink escape is
**DEGRADED**, with a stable diagnostic code. Never point at an arbitrary directory.

## Integrity and UI states

Health is artifact-free. Status and capabilities return 200 for healthy empty
and invalid-artifact states. Invalid status carries `artifactError`,
`approvalState=REJECTED`, `integrityStatus=FAIL` and no active run; run/content
endpoints reject invalid data. An unreachable service is separately
**DISCONNECTED**. A valid workspace is **DEVELOPMENT_READY**.

Every workspace observation verifies approved metadata, frozen Development
schema/protocol, summary, realpath containment and hashes of all 29 declared
content files for each admitted run. JSON/CSV schemas and grids used in responses
are validated. The unused wide `per_date_predictions.csv` is hash-checked,
not projected or recalculated. Only schema parsing of verified immutable bytes
may be memoized; all hashes are rechecked on every observation. Changed content
cannot reuse a stale PASS.

Overview shows workspace identity, approved run count, selected run, availability
and integrity. Integrity shows approval, metadata SHA, manifest, content hashes
and API schema checks. Research `U0_FIXED_124` is distinct from ETF Quant's 107
admitted industries. Unknown values remain null/“—”. Retry re-queries only; it
never repairs files or generates results.

Correct the local pointer/identity or restore approved immutable bytes externally.
Restart verified owned services after configuration changes: the launcher
fingerprint includes local config and approval registry hashes and refuses to
reuse another configuration.

## Attaching another approved Development run

Obtain explicit owner approval first. Audit the Development phase, metadata and
protocol schema, complete manifest, hashes and containment with read-only tools.
Through normal review, add only its safe ID, recorded UTC creation identity and
metadata SHA256 to the JSON registry. Update the local pointer/identity if needed,
restart verified services, and check status/integrity. No application source edit
or API mutation is required. Never commit payloads. A new artifact schema or
research protocol needs a separately reviewed adapter; registry approval cannot
override frozen schema or sealed boundaries.

See [console operations](unified_console.md), [API contract](../services/research-api/docs/api-contract.md)
and [OpenAPI](../services/research-api/openapi/research-dashboard-api-v1.openapi.yaml).

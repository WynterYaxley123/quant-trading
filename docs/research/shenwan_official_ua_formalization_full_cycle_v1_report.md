# Shenwan official UA formalization and full cycle V1

FINAL STATUS: SHENWAN_OFFICIAL_LIVE_APPEND_BLOCKED

READINESS STATUS: VALIDATION_NOT_READY

## Result boundary

UA access restored and full dry-run accepted. The single real cycle failed in
staging atomic replacement before apply. No canonical generation, append manifest,
snapshot lineage or current pointer was published. The 496-row candidate is NOT
accepted/current data; preview snapshot 13d1cf47a653567837225ba02dd5c34e24f9be8710bc90a494e669783fd4fef7
is only a private transaction preview.

## Git and scope

- Initial HEAD: b8c1e2ced79b6fd89c5fe3a6cdee04253973ba54.
- Branch: experiment/sw-sector-index-research-baseline (unchanged).
- UA patch commit: 6f930557a00fc60ef5d18e2af33b0125cc3b113e.
- Clean execution HEAD: af4a2939053914d7db068a103f2959ce6595c983.
- Initial dirty audit found only the six-line UA patch and Hermes audit document.
- UA production diff remains six lines; no TLS/schema/endpoints/pipeline change.
- Two old Session doubles needed headers; three regression cases were added.
- Hermes audit was committed separately. No strategy/model/candidate/split change,
  Docker/dependency change, push, merge, stash, reset, restore or clean.
- Final HEAD is the documentation commit containing this report; local Git records it.

## Independent access audit

Hermes headers/bodies were inspected and their exact SHA256 verified. His evidence
directory has a matrix README but no per-request request-header/TLS transcript.
This turn therefore repeated the single-variable test independently in Docker:
same HTTPS URL and strict verified bundle, fresh Requests sessions, GET, with only
User-Agent varied. Both catalog and trend returned default-UA 508/empty body,
browser-UA 200/compatible JSON. No Cookie, Referer, Origin or Authorization was
sent; no Set-Cookie/Location/login/captcha/challenge was observed. Exact endpoints
remain /institute-sw/api/index_publish/current/ and trend/.

Strict TLS PASS uses the EXISTING project-local pinned intermediate completion.
The server still sends only a leaf; standard s_client reports missing issuer.
The unchanged roots plus verified GeoTrust intermediate pass hostname/server-auth
verification, and Requests verifies normally. No global trust store was modified.
The root bundle SHA remains 9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f.
Representative 801012: 6,459 historical rows match, 6,463 response rows, four new dates.
Regression cases inspect the real prepared GET and prohibit added browser headers,
implicit redirects, source-host changes and disabled TLS; TLS failure blocks creation.

## Formal probe and full dry-run

Both required compose files were used for all executions.
Probe ua_formal_probe_20260927_v1: TLS/catalog/trend/schema/source identity PASS.
Catalog count 124, no code additions/removals/renames.

Dry-run ua_full_dryrun_20260927_v1: 124/124 fetch and schema PASS.
All 419,346 historical rows compared; revision=0, deleted/missing old rows=0,
historical gap fills=0. Independent comparison of all ten raw bar fields also
found zero changes. Transaction preview and historical CSV prefix identity PASS.

Candidate: 496 rows, four actual dates 2026-09-21 through 2026-09-24,
each date 124/124, each frozen sector four rows. No current-day/partial session,
no new invalid OHLC. Parent cutoff is 2026-09-18.
Original 20 SOURCE_INVALID row keys and full sidecar hash unchanged.
801193 missing sessions remain 336; last missing 2023-09-26; missing-date SHA unchanged.
All these statements refer to the full dry-run and independent candidate inspection,
not to a successful real update.

## Real cycle failure (no publication)

Cycle ua_live_append_20260927_v1 was invoked ONCE. Fresh probe passed, two official
responses were saved, both byte-identical to the full dry-run. Atomic replacement
of stage.json failed:

```text
PermissionError: [Errno 13] Permission denied:
stage.json.1e413fd5f83040c481f3c07518908fb8.tmp -> stage.json
```

The failed temporary file and BLOCKED stage record are retained. Container uid and
file owner both 57439, file modes 0644, files/directory writable; a subsequent
BLOCKED stage record was successfully written. A transient Windows bind-mount
sharing conflict is plausible, and this turn's Windows-side progress reader may
have contributed. No handle trace was captured: this cause is not proven.

The existing CLI calls this pre-apply exception OFFICIAL_ENDPOINT_BLOCKED, but its
sourceHealth remains PASS. Do not misdiagnose this as another HTTP/TLS failure.
No permissions/environment/pipeline patch was made to hide the failure.

Real fetch FAIL (2/124); real overlap/preview/apply NOT_RUN.
realCycleInvoked=true; realApplyAttempted=false; updateApplied=false;
publicationOccurred=false; applied rows=0; new snapshot=null; new cutoff=null.
No second live cycle and no alternate apply command was used.
The user was asked whether to authorize a new-run-id retry; none has been executed.

Parent/current snapshot:
872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500

Current cutoff: 2026-09-18; rows: 419,346; frozen U0: 124.
Complete historical CSV SHA:
884c7dbaaacf6aa5652b63cde5153265ca383fe5bec18fa0a40c410a76b5a887

Current pointer absent; new lineage NOT_PUBLISHED; original snapshot reproducible.
Golden raw/canonical/code fingerprints, 20 invalid bars and 801193 missingness
were verified again by the official readiness inspector after the failed cycle.

## Readiness, tests and idempotency

Formal readiness entrypoint rerun: before 19/60, after 19/60, delta 0.
fullValidationReadiness=false; Validation SEALED/UNSEEN, Final OOS SEALED.
Only date/calendar/quality/label-end maturity/structural columns were used.
No Validation label values, predictions, returns, RankIC, Spread, Top5 or performance.

Before cycle: targeted data/readiness/prereg integrity 290 passed, 1 deselected;
full offline 850 passed, 2 existing skipped, 18 deselected, 2 warnings (232.35 s).
After failed cycle: targeted 290 passed, 1 deselected; full offline 850 passed,
2 existing skipped, 18 deselected, 2 warnings (236.12 s). Zero failed in both final suites.
No original tests were deleted/weakened/skipped to pass. Imports covered by suites.

Production post-update idempotency NOT_RUN because there was no update.
Synthetic transactional idempotency contracts PASS; they are not production evidence.
No zero-append live idempotency claim is made.

## Evidence and next safe action

- Hermes report: docs/research/shenwan_http508_root_cause_audit_v1.md.
- Hermes evidence: D:/QuantForge/temp/shenwan-http508-audit-v1/.
- Independent diagnostic/candidate/readiness: D:/QuantForge/temp/shenwan-ua-formalization-v1/.
- Immutable run results: data/manifests/shenwan_official_runs/<run_id>/result.json.
- Full per-sector audit: data/staging/shenwan_official/ua_full_dryrun_20260927_v1/audit.json.
- Failed stage: data/staging/shenwan_official/ua_live_append_20260927_v1/.
- Detailed machine handoff: docs/research/handoff_shenwan_official_ua_formalization_v1.json.

NEXT SAFE ACTION: review the staging atomic-replace conflict and obtain explicit
authorization for one new-run-id cycle retry. Monitor within Docker, not through
Windows stage.json readers; retain all source/history/transaction gates. No
Validation opening, bypass-apply, environment/dependency change or frozen research change.

SHENWAN OFFICIAL REMAINS THE CANONICAL F1 DATA SOURCE

NO THIRD-PARTY MARKET DATA SOURCE WAS SPLICED INTO THE SERIES

VERIFY_FALSE WAS NOT USED

THE FROZEN HISTORICAL PREFIX WAS NOT SILENTLY REVISED

VALIDATION PERFORMANCE WAS NOT READ

NO VALIDATION RESULTS WERE GENERATED

VALIDATION REMAINS SEALED AND UNSEEN

FINAL OOS REMAINS SEALED

WAIT FOR MORE LEGALLY AVAILABLE SHENWAN OFFICIAL DATA

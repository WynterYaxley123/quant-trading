# Handoff — Shenwan network resilience / live append / blocked idempotency

FINAL STATUS: SHENWAN_NETWORK_HARDENED_LIVE_APPEND_APPLIED_IDEMPOTENCY_BLOCKED

## Accepted current state

- Branch: `experiment/sw-sector-index-research-baseline`.
- Initial transport commit / real-cycle execution HEAD:
  `24c331cba2b8664a89001db5aa5bbd39a6c8e873`.
- Final network hardening (typed no-errno reset follow-up):
  `191eb97dd181e58729e06ca349325d869c346e3a`.
- Final HEAD is the separate documentation commit containing this handoff;
  resolve with local `git rev-parse HEAD`.
- ONE real cycle: `net_safe_live_retry_20260927_v1`, UPDATE_APPLIED.
- 124/124 fetch; 419,346 overlap; 0 revisions/missing difference/gap fills.
- Append 496 rows, 2026-09-21..2026-09-24; 124 sectors x 4 dates.
- Parent: `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
- Current: `208207c7f85fc6236d7025d96fc61c56b27b049cf35b89bae77d80692b293782`.
- Cutoff 2026-09-18 -> 2026-09-24; rows 419,346 -> 419,842.
- Parent prefix byte-identical; old golden remains reproducible.
- Frozen U0=124, 20 SOURCE_INVALID and 801193 missing 336 sessions unchanged.
- Snapshot lineage / raw append manifest verified.
- Readiness: 19/60 -> 23/60, delta +4; VALIDATION_NOT_READY.

## Failed safe idempotency check — do not misreport as PASS

ONE dry-run: `net_idempotency_dryrun_20260927_v1`, from CLEAN execution HEAD above.

Probe PASS, but fetch stopped at 38/124. Next frozen sector 801103 is inferred
from stage ordering/immutable failure metadata; original full terminal URL and
traceback were not recorded. Exception:

`ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`

Native OFFICIAL_ENDPOINT_BLOCKED / stage BLOCKED, no overlap/apply.
Idempotency NOT_VERIFIED. Source revisions/new-row candidate are null/NOT_RUN,
not zero. Actual extra publication=0. Snapshot/pointer/canonical/manifest/golden
hashes unchanged. Readiness remains 23/60.

RemoteDisconnected is a typed ConnectionResetError with errno=null. Initial
errno-only classification missed it and failed closed. The minimal follow-up
recognizes typed built-in reset/abort/pipe without errno, retaining TLS/proxy
veto, no text-only ProtocolError retry and max 4 attempts with 1/2/4 backoff.
This follow-up is OFFLINE_VERIFIED_ONLY: no later network execution occurred.

Tests: final targeted 343 passed, full offline 903 passed; 0 failed.
2 existing skips, 18 deselected, 2 existing warnings preserved.
38 new synthetic cases total; original 55 test functions/fixtures and 17
critical source/schema/history/transaction/readiness functions AST unchanged.

## Next safe action

Human review and separately authorize ONE safe full dry-run of the final typed
disconnect patch. Do NOT automatically launch another real cycle.
WAIT FOR MORE LEGALLY AVAILABLE SHENWAN OFFICIAL DATA.

Do not run Validation. At readiness 60/60 stop for human review first.

- validationOpened=false
- Validation performance read=false
- Validation results generated=false
- Final OOS read=false
- No Docker/dependency/global trust store/strategy/candidate/model/split changes.
- No third-party market data, verify=False, push or merge.

Detailed report:
`docs/research/shenwan_network_fetch_resilience_live_retry_v1_report.md`.

Native run evidence:
`data/manifests/shenwan_official_runs/<run_id>/` (ignored; retained).
Independent evidence:
`D:\QuantForge\temp\shenwan-network-resilience-v1\`.

SHENWAN OFFICIAL REMAINS THE CANONICAL F1 DATA SOURCE
NO THIRD-PARTY DATA SOURCE
VERIFY_FALSE NOT USED
NO HISTORICAL PREFIX REVISION
VALIDATION REMAINS SEALED AND UNSEEN
FINAL OOS REMAINS SEALED

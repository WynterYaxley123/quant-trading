# SWL1 Ridge V1 engineering acceptance

SWL1-Ridge-V1 closed as `FAILED_VALIDATION`. Its candidate, preregistered
implementation, protocol and scientific summaries are immutable. Final OOS was
not opened. Engineering tests use synthetic fixtures and do not rerun research.

## Local verification

- Independent developer Docker: full portable Python suite before the two final
  regression additions: 1315 passed, 2 skipped, 99 external tests deselected.
  The final SWL1 synthetic suite has 13 passing tests, including future-feature
  exclusion, complete-universe centering and missing-date rejection.
- Ruff lint and formatting passed. Staged Mypy has zero strict/new diagnostics;
  the 168 reviewed legacy diagnostics were not enlarged.
- Dashboard: 140 passed, 3 optional external skips; typecheck, lint and build passed.
- Research API: 63 passed, 7 optional external skips; typecheck and build passed.
- Industry forecast API: 22 passed; typecheck and build passed.
- Existing ETF API, security and operations tests: 144 passed before the final
  public-aggregate policy regression was added.
- Pre-commit all-file hooks, documentation references and naming checks passed.
  The reference audit found zero broken links and zero archive hash changes.
- Synthetic industry demo covers both frozen SWL2 generations and independent
  SWL1 fixtures, with zero formal publications and zero ETF events.

The hosted quality workflow verifies the final PR head separately. Fresh-clone,
hosted-CI, merge and post-merge results must be taken from the actual delivery
record, not inferred from these local results. No browser smoke is defined.

## Publication and dependency review

The six public research JSON files contain aggregate feasibility, factor audit,
preregistration, Development, Validation and closure evidence. They contain no
price panel, stock membership history, daily prediction ledger or private data.
The read-only publication scanner admits only their reviewed exact paths and
SHA-256 bytes, in the working tree and history. Altered bytes remain prohibited;
all admitted bytes still undergo the credential scan. Sealed performance payloads
remain unread by the scanner. Historical integrity certificates remain unchanged.

Dependency lockfiles are unchanged against base
`ef138f3a020fbd15f7e8f1beb55ccd0b0e02aa7b`; no new dependency advisories were
introduced. The observed existing dashboard audit has one high advisory
(`source-map-js`, GHSA-68fv-2mgg-jv7q). The research API audit has one critical,
one high and three moderate advisories, including Vitest GHSA-5xrq-8626-4rwp,
csv-parse GHSA-8cw4-87c7-c6xx, Vitest/mocker GHSA-82fw-gwwq-j7x9 and the same
source-map-js advisory. The industry API has no dependency advisories. These are
retained limitations, not a claim that the repository is vulnerability-free.

## Invariance and operating state

The SWL2 strategy packages and frozen scientific configuration are unchanged.
The new generic registry appends an independent level-one family; it does not
rename either level-two generation. Its read-only API reports the failed status
and empty formal ledgers without reading a runtime path. Forward eligibility is
false; scheduler, broker and live promotion remain disabled. Existing runtime
data and upstream CNEquity are read-only. Private research evidence remains under
`D:\QuantForge\research\swl1-ridge-v1`; temporary builds stay under QuantForge
or in task-owned developer containers.

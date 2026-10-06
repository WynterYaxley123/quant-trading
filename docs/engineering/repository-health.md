# Repository engineering health

This page describes the implementation based on official main
`b5ac584a7f6339e7ae089286fa6ec939b082ff33`, measured on 2026-10-05.
The [active integrity transition](../../reports/engineering/v8-integrity.json)
appends the immutable installation certificate as a compact delta. Earlier measurements in
[historical health metadata](../../reports/engineering/repository-health.json)
retain their original scope and dates; they are not current test counts or status.
Repository certificates establish local byte consistency, without an external signer.

## Product and operation

V1 remains the frozen baseline. V2 remains Ridge alpha 30, RAW features, a
12-calendar-month window, H10/H40/H120 and fusion 0.25/0.50/0.25. Its published
scientific status is PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE, with the original failed
Validation and overlapping Final-OOS observations disclosed in the
[V2 protocol](../etf-quant-v2-protocol.md). No research gate was reopened or model
retuned. Mapping admits 3 direct and 19 verified-proxy industries out of 124;
102 remain unmapped, retaining their original slot weights as CASH.
Both versions have independent CNY 10,000 accounts. Forward epochs remain zero
until a legitimate finalized post-freeze session; no profitability claim is made.

The [operations guide](../operations.md) defines the external Windows task,
canonical dual-version runner, permanent merged-main checkout, logs and retry
behavior. Synthetic crash tests cover T signals and T+1 accounting before/after
pointer publication. Recovery promotes only already-persisted, hash-verified
bytes with their original timestamps. Corrupt evidence fails closed. Missed T+1
retires the original intent/epoch without any fill and permits a new legal forward epoch.
Host operation requires the logged-in user's Docker Desktop runtime and provider
availability. The dashboard/API display factual waiting states and separate ledgers.

## Current measurements

`scripts/engineering/inventory.py` measures the Git path manifest and ASTs;
`scripts/engineering/references.py` measures rendered links, plain repository
paths, classification coverage and retained archive hashes. No historical alias
rescues a broken active path. The stdout ledger reviews exact calls, including
19 previously unclassified V2 report/CLI/transport outputs. URL paths are not
private filesystem paths; real paths beside URLs remain counted.

| Measure | Current run |
| --- | ---: |
| Python files / LOC including blanks and comments | 286 / 60719 |
| Functions / fully annotated signatures | 2318 / 744 |
| Function docstrings | 607 |
| Raw Mypy diagnostics / affected files | 168 / 22 |
| Active production/touched Mypy diagnostics | 0 |
| Tracked / active / historical Markdown | 74 / 57 / 17 |
| Broken active links and plain paths / unclassified Markdown | 0 / 0 |
| Private machine path lines in active docs / source | 0 / 0 |
| Active config private-path compatibility default | 1 |
| Debug / accidental / unclassified print calls | 0 / 0 / 0 |
| Active Python BOM / CRLF files | 0 / 0 |

Complete signatures count arguments and return annotations, excluding self/cls.
Annotations and docstrings remain partial. Mypy debt is unchanged and reviewed;
no baseline was enlarged. The single config path is the labelled legacy Windows
runtime fallback. `AGENTS.md` is the required repository instruction file; the
12 vendor-named historical provenance artifacts remain byte-pinned. No current
vendor handoff file exists. One concise V7 findings inventory was added.

## Validation

All numerical validation runs in the independent developer or unchanged frozen
Docker image, using synthetic inputs or permitted read-only evidence. The
[testing guide](../testing.md) defines the commands and explicit optional skips.
Current completed runs are recorded below; delivery and hosted CI authority are
GitHub PR/main metadata, not a fabricated self-referential merge SHA.

| Check | Result |
| --- | --- |
| Portable pytest | 1259 passed, 2 optional tests skipped, 99 external tests deselected |
| Full V1 frozen-image acceptance | 701 passed, 1 optional test skipped; network disabled, maintainer evidence read-only |
| Focused accounting/recovery/locks and canonical runner/scheduler | 105 passed |
| Ruff / format / staged Mypy / pre-commit | Passed; 168 unchanged legacy diagnostics, active production 0 |
| Dashboard | 132 passed, 3 optional live tests skipped; types/lint/build passed |
| Research API | 63 passed, 7 optional external tests skipped; types/build passed |
| ETF API/security | 140 passed on Linux and 140 passed on Windows |
| Windows launcher/task-definition | 6 passed, including actual cold task discovery |
| Synthetic performance regressions | 16 passed |

The [V7 inventory](v7-remediation.md) records corrected findings and compatibility
constraints. Final source-certificate verification runs separately after documentation
updates. Historical model/candidate/release/OOS bytes remain unchanged.

The built-in source/history scanner reports identifiers and counts, omits sealed
payloads and checks forbidden data paths and certificate bytes. Its result is
repository-native auditing, not dependency or external scientific certification.
No raw market data, private credentials, brokers or real-order implementation is
introduced. CNEquity remains external, clean and pinned; its upstream files and
the deployed research image are unchanged.

## Remaining limitations

Historical membership Tier A coverage is zero; dependence-aware uncertainty for
V2's 60 overlapping Final-OOS signals is unavailable. Executable mapping coverage
remains 22/124 and historical/source data rights are not inferred from MIT source
licensing. Optional external/live test tiers require separately configured evidence.
Legacy Mypy debt, partial annotations and larger cohesive modules remain. Host
sleep/logout, unavailable Docker or incomplete providers may prevent a legal
forward opportunity; retries never authorize retroactive signals or prices.
Full ledger snapshots retain cumulative archive growth and a bounded read ceiling;
future rollover needs a separately verified schema transition. Membership views
preserve latest dated row identities, cache unchanged membership and reduce in
canonical symbol order to prevent random floating mean bytes. No unsafe incremental
hash or changed historical membership selection was introduced.

# SWL1 failure-forensics engineering acceptance

This source transition adds independent, read-only forensic tooling and detailed
English/Chinese reports with seven static aggregate figures. It preserves the
four existing families, both SWL1 FAILED_VALIDATION states, closed lifecycle,
unopened Final OOS and all prior research/certificate bytes.

Exact selected replay: 2,427 fits, native metrics and V2 fit-trace hashes PASS;
maximum close-factor reconstruction error 7.247535904753022e-13. The union outcome
boundary is 2026-09-29. Only date/shape metadata for the last 2026-09-30 row was
admitted; its returns were never converted to numbers or included in targets.
Fortran layout skips 232 intervening opaque bytes, as distinct from numeric
decoding; adversarial synthetic tests cover this distinction. Private per-date
diagnostics remain outside Git.

Canonical gates use the independent pinned developer Docker image, with no live
runtime or private credentials for engineering. Python lint/format/staged Mypy,
portable/synthetic/regression/performance tests, demos, references, pre-commit,
industry/ETF/security/API tests, frontend and Research API frozen-install checks
are required before delivery. GitHub runs the same six quality jobs including the
Windows launcher/scheduler tests; all must pass before merge and on main.

Local acceptance completed in the public native Git clone (no private mounts):

| Gate | Result |
| --- | --- |
| Ruff / format / staged Mypy | PASS; 168 unchanged legacy diagnostics, new/touched code zero |
| Full portable pytest | 1,374 passed, 2 skipped, 99 deselected; 4 existing warnings |
| Forensic / SWL1 / SWL2 / registry regression | 28 / 32 / 30 / 10 passed; 100 total |
| Industry API / ETF API-security-operations | 32 / 145 passed |
| Dashboard | 145 passed, 3 skipped; frozen install, typecheck, lint, build PASS |
| Research API | 63 passed, 7 skipped; frozen install, typecheck, build PASS |
| Industry API typecheck/build | PASS |
| Actual Windows launcher/scheduler boundary tests | 11 passed, no service start or task enablement |
| Pre-commit | All 9 hooks PASS |
| References / archive byte integrity | 330 local links, 95 prose paths; broken links and changed archives zero |
| Developer image / demos / benchmark / performance | PASS; pinned independent image; synthetic-only demos; 16 performance tests |
| Source and full Git-history security | PASS; no forbidden payload, secret candidate or file over 500 KiB |

The first API fixture attempt inherited the science container's read-only Git
environment and failed synthetic `git init`; it made no original repository
mutation. All canonical API tests then passed in the independent native Git clone.
SVG whitespace was normalized in the deterministic exporter; no gate was relaxed.

Source authority is [the new cumulative delta](../../reports/engineering/swl1-failure-forensics-integrity.json),
with the unchanged installation full parent and V2 execution previous delta.
Reviewed public research exports use exact path-and-byte SHA256 exceptions;
one-byte mutations and unreviewed private payloads remain blocked. Lockfiles,
Docker bases and advisory baseline are unchanged; existing dashboard/Research
API advisories are disclosed, with zero introduced advisories.

Baseline comparison retains dashboard's one high advisory
`GHSA-68fv-2mgg-jv7q`; Research API's one critical, one high and three moderate
findings have four unique IDs: `GHSA-5xrq-8626-4rwp`, `GHSA-68fv-2mgg-jv7q`,
`GHSA-82fw-gwwq-j7x9`, `GHSA-8cw4-87c7-c6xx`. Industry API has zero.
Counts/IDs match the existing audited baseline; no lockfile or dependency change.

No scheduler enablement, deployment promotion, formal forecast, ETF event or order
is performed. Task-owned containers/checkouts are cleaned only after final public
delivery and private audit receipts are preserved. Other actor worktrees and
QuantForge originals are read-only. The main checkout's pre-existing two untracked
handoff/specification files are untouched.

See [English analysis](../research/swl1-v1-v2-failure-forensics.md),
[中文分析](../research/swl1-v1-v2-failure-forensics.zh-CN.md),
[design review](../research/swl1-next-generation-design-review.md).

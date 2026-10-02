# Research workspace usability acceptance — 2026-10-02

Local product acceptance passed on the isolated
`integration/research-workspace-full-usability-final` branch based on main
`aeadba668f08c565a4d7b649d13510cd2bd90ab5`. Implementation commits are
`fdc9d3b` (approved API), `b2ac9dc` (workspace UI), and `8960517` (launcher/docs).
Final GitHub merge and deployed source identities are recorded in the external
delivery certificate after ordinary PR review; this report does not invent a
future merge SHA.

## Product behavior

Normal `& ./scripts/Start-EtfQuantConsole.ps1` starts all three loopback services
and automatically resolves the configured machine's approved Development
workspace. Repeating it safely reuses all three verified processes. The normal
Research state is DEVELOPMENT_READY with two approved runs, four candidates per
run, read-only URL selection and preserved valid deep links.

The safe JSON registry pins both previously audited Iteration-1 IDs and their
original metadata SHA256; each metadata manifest anchors 29 content files.
The machine-local pointer is outside Git. Directories, names, filesystem mtime
and modified manifests cannot confer approval. All explicit overrides retain
precedence and fail closed. See [configuration and approval](research_workspace.md).

All six Research routes were checked in a real browser with actual approved data,
portable no-artifact configuration and an isolated corrupt metadata fixture.
Connected READY, connected NOT_CONFIGURED, connected DEGRADED and DISCONNECTED
remain distinct. Both empty/invalid retry controls only re-query observations.
Overview, candidates, Development, sectors, diagnostics and integrity show
existing evidence. U0_FIXED_124 remains separate from ETF's 107-industry scope.
All nine ETF pages still render their observational state. A compiled production
preview passed the six Research routes and ETF overview. No errors, warnings or
unexpected network failures were observed in these bounded browser sessions.

## Actual quality gates

| Gate | Result |
| --- | --- |
| Complete frontend suite, including three real-artifact adapter cases | 130 passed; 0 failed; 0 skipped |
| Frontend typecheck / lint / production build | PASS |
| Research API | 22 boundary/normalization + 14 approval/resolution + 7 actual Development integration = 43 passed |
| Research API typecheck / build | PASS |
| Full frozen Docker ETF suite | 612 passed; 1 existing optional-module skip; 0 failed |
| ETF API / security tests | 77 passed |
| Windows launcher lifecycle/configuration tests | 5 passed |
| Live HTTP schemas | 16 ETF GET routes + 11 Research GET routes passed |
| Live Research negatives | 18 rejected checks, plus valid CORS / HEAD / OPTIONS |
| Source smoke in network-none, read-only Docker | 197 Python, 48 JSON, 8 YAML, 1 TOML; 10 critical imports passed |
| Native tracked-tree / reachable-history security audit | PASS; no secret or forbidden payload candidates |

The full ETF suite used the existing frozen image
`sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5`,
network none, read-only source and read-only external runtime fixture. Its single
skip is the optional upstream sidecar package absent from that image; nothing
was installed to eliminate it. Existing dependency lockfiles and environment
pins are unchanged. An early concurrent frontend run encountered one cold lazy
import timeout; the completed full run passed all 130 after Docker's CPU-heavy
suite finished. JSDOM emits its pre-existing unsupported scrollTo notices;
actual browser error/warning observations were empty.

## Read-only and sealed evidence

Approval tests cover existing approved bytes, explicit overrides, absent optional
catalog, missing explicit root, corruption, metadata/content hash mismatch,
Validation, Final OOS, unapproved folders, symlink escape, deterministic ordering,
malformed metadata/config, ambiguity and unknown identity. Storage instrumentation
shows forbidden-phase metadata stops before content access and unapproved runs
are rejected before metadata access. The instrumented production storage boundary
with real Development files admits only registered Development IDs; sealed
requests perform no file reads. No Validation or Final OOS performance was opened.

Before/after byte hashes match for all 60 approved Development files and all six
Formal Shadow files. Epoch, Signal, Intent, Fill and NAV-history deltas are zero.
All 50 certified production-file hashes match, as do Candidate/PIT/Strict evidence
and F1/split/quantitative source. CNEquity remains the clean
`1650e384a3fd1f67a70144a489acc91432f1df27` checkout.

Every Research route remains observational; there are no artifact writes,
approval/run creation endpoints, job launchers, runner calls or broker hooks.
Bad Host, Origin, preflight Origin, mutation methods, force/bypass, malformed IDs,
traversal and sealed phase paths/queries are rejected. Broker-enabled and real-order
path remain false; no reachable real-order submission path was introduced.

The Shanghai calendar was inspected: 2026-10-02 is a holiday, latest finalized
market date is 2026-09-30 and next eligible date is 2026-10-08. Formal state has
no epoch; NAV remains null. No one-shot was run for this Research task and no
first operational cycle was consumed.

Full A–V final report, before/after hashes, browser captures, test logs, access
proof and exact GitHub delivery certificate are outside Git under the separate
`research-workspace-acceptance-20261002` external runtime audit directory.
No research payload, raw market/runtime/Shadow data, secrets, screenshots, logs,
node_modules, virtual environment or build output is committed. Owner license
and source-data redistribution decisions remain **REVIEW_REQUIRED**.

# SWL2 forecast closure evidence

Base: 840fc2ec0dc8d33d77c4fbf9d9198df16c18c430. Branch:
refactor/swl2-industry-forecast. All frozen pre-existing report/config/archive
bytes stay unchanged, including the preceding forecast integrity delta.

This closure adds dynamic pinned universe resolution and separates current
SWCLASS2021 taxonomy (134), legacy parsing inventory (63), model universes
(107/124), and actual published rows. V2's public identity-only projection
matches the original byte-pinned warmup metadata/panel references; it contains
no prices, private evidence or performance. Both model contract hashes stay
unchanged. Native targets remain exact h-session raw returns minus each family's
own complete frozen-universe mean. Common comparison verifies raw outcomes and
allows unequal centered targets; shared rank errors and overlap are descriptive.

Synthetic regressions cover all normalized model outputs, universe mismatch,
native centering, different-center compatibility, immutable evaluation recovery,
body/index hard limits, API metadata/tampering and complete UI rows. Quantitative
execution uses the independent Docker image without private facts. No market
backtest, sealed performance read, real forecast, ETF event, live promotion,
scheduler enabling or SWL1 training occurs.

## Executed engineering gates

- Portable Python: 1304 passed, 2 skipped, 99 external-runtime deselected.
- Forecast/runner/runtime regressions: 30 passed; full normalized frozen-model parity.
- Combined Node API/security/launcher: 167 passed, 6 Linux platform skips; industry API 21 passed.
- Frontend: 139 passed, 3 optional private-artifact integration skips; typecheck/lint/build PASS.
- Research API: 63 passed, 7 optional private integrations skipped; typecheck/build PASS.
- Ruff lint/format: PASS across 301 active Python files.
- Staged Mypy: PASS, 168 unchanged reviewed legacy diagnostics, strict/new code zero.
- All nine pre-commit hooks: PASS in a native Git clone inside the independent developer container.
- Docker developer build and fresh public-branch clone README demo/tests: PASS.
- References/naming: PASS, zero broken links or changed archived bytes.
- Built-in source/history security audit: PASS, no secrets or runtime/data tracked.

Node audit was run against both the base and current lockfiles. New advisory IDs: 0.
Existing dashboard baseline: 1 high (source-map-js, GHSA-68fv-2mgg-jv7q).
Existing Research API baseline: 3 moderate, 1 high, 1 critical
(vitest/@vitest/mocker/csv-parse/source-map-js; IDs 1139529, 1193670, 1193683,
1193684, 1241209). The dependency-free industry API reports zero advisories.
This is a baseline-aware audit result, not a claim of an advisory-free repository.
No package or lockfile upgrade is mixed into the forecast closure.

Windows-only tests run in hosted Windows CI. Optional skips/deselection are not
private-data acceptance. The existing frontend bundle-size warning remains.
The repository defines no production browser-smoke gate; UI verification uses
its complete synthetic frontend suite and build. No live browser/console starts.

The active certificate verifies 331 source paths and preserves the preceding
forecast certificate bytes. Runtime metadata baseline: 47,289 files,
SHA256 4DEAB97A4A9D4583D04D1A12F01717764808FB505F9700DE501D918914A214D0.
The legacy Shadow task remains Disabled. Source delivery promotes no live checkout.
GitHub and post-merge identities are reported separately after completion.

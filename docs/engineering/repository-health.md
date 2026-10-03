# Repository engineering health

V3 addresses the reproduced engineering findings against base `1e2ffbd4f75120df2511472662dcf7dcd308b0d6`. Detailed finding classifications, measurement locations, synthetic scales and source hashes are in the [health manifest](../../reports/engineering/repository-health.json). Status: IMPLEMENTATION_ACCEPTED_DELIVERY_VIA_PR_METADATA.

## Baseline and measured state

| Measure | Baseline | Current |
|---|---:|---:|
| Python files / LOC (comments and blanks included) | 222 / 49138 | 239 / 50999 |
| Functions / complete annotated signatures | 1963 / 572 (29.14%) | 2032 / 595 (29.28%) |
| Function docstrings | 550 (28.02%) | 561 (27.61%) |
| Raw Mypy diagnostics / affected files | 411 / 29 | 168 / 22 |
| Tracked / historical Markdown | 160 / 107 | 70 / 17 |
| Literal broken active links | 5 | 0 |
| Active docs / source / config private path lines | Earlier docs-only metric was incomplete | 0 / 0 / 1 |

Complete signatures include arguments, variadic arguments and return annotations, excluding `self`/`cls`; private and nested functions count. Annotation and docstring coverage remain partial. Mypy uses the unchanged configured scope; active `src`, ETF runtime and sidecar/runner scope has 0 diagnostics. Every touched production module has 0. The reviewed baseline only shrank. Ruff lint/format pass across active Python with 0 production format exclusions and 0 active Python BOM/CRLF files.

## Correctness, security and finding decisions

All 39 V2 claims have reproduced evidence, classifications, before/after decisions and test references in the JSON ledger. Liquidity selection now requires PASS plus a finite positive numeric amount, returns no candidate when admission empties the pool, and preserves strict precedence. PIT provenance binds the exact selected candidate even when an ETF has multiple benchmark records. T+1 selects the minimum later session. Partial research assignment now respects the documented exposure/margin priorities.

Fidelity remains **actual minus nominal**; the 35% cap still redistributes remaining capacity. Comments were corrected without changing either formula. Largest-non-target aliases clarify internal purity fields while preserving serialized names. The historical readiness date is named and retained. Dead parsing/weight collection and duplicate text checks were removed. The A40 naming claim is a false positive; its helper was already explicit. Weight parsers intentionally have different accepted input domains, now documented and tested.

The environment template uses mandatory external `JUPYTER_TOKEN`; missing/empty credentials fail closed, and a configured synthetic token passes Compose validation. Both APIs share adversarial Origin cases and enforce exact HTTP(S) origins, DNS/IP and port grammar without wildcard, userinfo, path, query or fragment. Pip TLS bypass was removed in source; only an independent developer image was built. Two confirmed security hardening findings are closed. Existing bounded-read, schema, method/host/path/mount and tamper tests remain. The built-in pattern/path audit reports no secret candidates, raw/runtime data, sealed paths, oversized blobs or credential-bearing remote URLs in the current tree or reachable history; it is not a third-party vulnerability certification.

## Synthetic performance evidence

Run `python -m benchmarks.core` in the independent Docker developer image. Three paired repetitions report medians; CI checks correctness and structural work, without machine-speed thresholds. No market data or performance periods are used. Full scales, asymptotic work and memory notes are in JSON.

| Hotspot / scale | Before seconds | After seconds | Observed ratio |
|---|---:|---:|---:|
| industry (days=50, industries=20, constituents=6) | 0.032044 | 0.024728 | 1.30x |
| industry (days=50, industries=100, constituents=6) | 0.191510 | 0.111363 | 1.72x |
| liquidity (etfs=8, bars=320, window=20) | 0.136636 | 0.003210 | 42.56x |
| liquidity (etfs=40, bars=1600, window=20) | 0.928394 | 0.014317 | 64.84x |
| prediction (days=420, sectors=8, horizons=3) | 0.640514 | 0.020304 | 31.55x |
| prediction (days=420, sectors=24, horizons=3) | 1.647258 | 0.050582 | 32.57x |
| research_rolling (sectors=6, signal_dates=20, visible_days=351) | 1.469354 | 0.822001 | 1.79x |
| shadow_prefix_cold (stock_rows=36000, total_rows=36600, industries=50, days=120) | 0.254095 | 0.309247 | 0.82x |
| shadow_prefix_warm (stock_rows=36000, total_rows=36600, industries=50, days=120) | 0.260581 | 0.201775 | 1.29x |
| training_dates (sectors=6, frame_days=600, train_days=121) | 0.005846 | 0.001101 | 5.31x |
| training_assembly (sectors=6, frame_days=600, train_days=121, features=19) | 0.009143 | 0.006383 | 1.43x |
| lake_fingerprint (files=12, bytes=3145728) | 0.002605 | 0.002480 | 1.05x |

Industry snapshots use industry membership indexes; liquidity uses one call-scoped symbol/date lookup; prediction shares immutable input arrays across horizons; Development rolling factors are precomputed only through the last visible signal and reinstate warmup/maturity masks; training uses eligible date/label projections and preserves the original Pandas matrix layout. Exact row identities, coefficients, order, duplicates, missing data, exclusions and tight factor equality are tested.

Shadow hashing still authenticates all economic bytes. Warm repeated calls reuse private, content-authenticated row hashes; cold/new-process calls remain O(rows) and have measured overhead. It does not claim cross-process or real formal-cycle acceleration. Lake hashing is **NO_CHANGE_WITH_REASON**: mutable files have no authenticated immutable child identity. Full byte checks are retained; the observed same-function timing ratio is noise, not an improvement. Same-size restored-mtime mutation, additions, deletion, ordering, caller poisoning and future/fetched metadata tests guard integrity.

## Architecture, metrics, docs and portability

Concrete strategy discovery now lives in `src/application/backtesting.py`; the old runner is an API compatibility facade. OHLC validation moved to neutral `src/data/ohlc.py`. Prefix hashing and causal research panels are cohesive extracted seams. ETF external root logic remains inside its self-contained configuration package, consumed by support-script facades; the ETF import firewall remains intact. Existing larger policy/evidence modules remain cohesive.

Every print call is reviewed by path, lexical context, normalized call AST and occurrence, with an explicit reason. Moving, changing or duplicating a call fails classification until reviewed. The old directory metric was invalid: one internal status helper was converted to logging. Current 112 calls classify as 20 CLI, 13 machine-readable, 59 report, 4 example and 16 test outputs; debug, accidental and unclassified counts are each 0. Literal links never use historical alias exemptions. Source/config/docs paths are separate, with test, historical and scanner-pattern scopes explicit; URL false positives are tested.

The current tree removes 91 redundant process Markdown records, retains 16 essential historical contracts/provenance plus archived V2, and has 53 active Markdown files. Recovery commit/path/SHA256 mappings remain in `config/engineering/documentation-map.json`; retained archives and previous certificates preserve bytes. The old `82e6f09` migration had **102 exact Git renames**, plus four copied originals (`AGENTS.md`, docs README, architecture, ETF README) whose active paths were rewritten; it was not 106 exact renames. Git history is unchanged. README now explains frozen model specification with causal coefficient refits, proves industry-first through code/tests and reconciles three layers with six components.

Public synthetic checks require no private drive, credentials or external framework. Environment root overrides and generic data-home defaults replace scattered private paths; Docker resolves through PATH. `config/legacy-runtime.json` contains the single labelled Windows fallback for existing maintainer deployments. KData integration remains a separate explicitly authorized maintainer capability, not engineering permission to run a market backtest.

## Review of 702e432

Qualified AST comparisons cover relocated methods and duplicate function names; whitespace-insensitive diffs also cover Compose, API and schema changes. The JSON lists every differing/new function reviewed. Actual behavior groups:

- Intended fixes: A40 admission/no-survivor handling while retaining dominance exemption and B40 cash; canonical NumPy boolean CSV encoding.
- Valid hardening: positive integer constituent-count validation; closed Docker mount/reference grammar; bounded regular-file artifact reads including concurrent growth; strict artifact hash keys; configurable explicit ETF Origin allowlist; mandatory Jupyter authentication; current source-certificate transition.
- Equivalent changes: lazy catalogue probing and per-symbol date collection; casts, renames, dictionary splits, valid-domain `or 0` sorting, `.eq`/`.ne`, list column projection, tuple serialization, invariant assertions and moved facades. The coverage None guard was already entailed by `is_valid`. Pinned JobEngine imports `steps.common`, which initializes registration, so removal of the redundant explicit steps import does not unregister steps.
- Engineering-only changes: measurement category/manifest overrides, typing/format/line-ending configuration, dependency locks and test adaptations. V3 corrects the unreliable prior measurement claims. No accidental supported-domain strategy behavior was found; prior history was not rewritten.

## Verification, Shadow and frozen strategy

| Check | Result |
|---|---|
| Docker portable suite | 1069 passed, 2 skipped, 99 excluded external/integration cases |
| Performance/correctness/measurement suite | 38 passed |
| Dashboard | 127 passed, 3 skipped; typecheck/lint/build pass |
| Research API | 63 passed, 7 skipped; typecheck/build pass |
| ETF API/security / Windows launcher | 117 / 2 passed |
| Synthetic demo / existing scale benchmark | pass |
| Ruff / staged Mypy / pre-commit / literal links | pass |
| Frozen image ETF acceptance | 659 passed, 1 skipped |
| GitHub Actions | Six checks passed for the validated implementation; final PR/main state is verified through GitHub metadata |

External Shadow comparison inspects filenames, sizes and SHA256 only: 6 files unchanged; epoch/signal/intent/fill deltas are all 0. The frozen image content ID is unchanged. Start-time samples refer to different container identities and cannot establish lifecycle stability; this task issued no lifecycle commands to deployed services. Frozen factors, model/Ridge specification, ranking, H10/H40/H120 fusion, sizing, B40 cash, PIT and T/T+1 contracts remain unchanged. CNEquity stays pinned; no upstream edits, formal one-shot, market-data backtest, broker, real order, leverage, short or sealed performance read occurred. Absent quantitative metrics remain null.

## Residual debt and GitHub identity

No known correctness/security blocker remains after local checks. Residual debt is the 168 reviewed legacy Mypy diagnostics across 22 files, partial signature/docstring coverage, larger cohesive legacy modules, warm-only process-local prefix reuse with cold overhead, mandatory full lake byte hashing and one labelled Windows path compatibility default. These are reported without claiming repository-wide strict typing or formal runtime speedups.

GitHub PR metadata is delivery authority. The tracked report records base and the explicitly validated implementation commit, plus PR number/URL when created. A metadata-only report commit can follow without changing validated source. The actual final main SHA is emitted after normal merge only in the console/untracked delivery state; this file cannot name its own containing merge commit.

Validated implementation: `88bb36f2867838e0e60a5c34a0d7f1be1de3231f`.

PR: [8](https://github.com/WynterYaxley123/quant-trading/pull/8).

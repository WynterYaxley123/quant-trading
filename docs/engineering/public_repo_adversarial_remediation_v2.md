# Public repository adversarial remediation V2

Engineering acceptance of the public quant-trading repository and ETF-Quant V1. No market-data backtest, sealed performance evaluation or formal Shadow cycle was run. Quantitative performance values remain absent.

## A–C. Revision and delivery identity

- Base SHA: `2de086421d1e2149faa8b987913ef14027f1c5a3` (fetched origin/main, public repository confirmed).
- Branch: `engineering/public-repo-adversarial-remediation-v2` in an isolated worktree.
- Final branch SHA: resolve `head.sha` from the [PR #7 delivery record](https://api.github.com/repos/WynterYaxley123/quant-trading/pulls/7).
- Merged main SHA: resolve `merge_commit_sha` from that same PR record after normal merge.
- Historical branches and deployed checkout are read-only. No force push, history rewrite, tag or release.

The [single metadata manifest](../../reports/engineering/public_repo_adversarial_remediation_v2.json) contains the full inventory, ledger, source certificate and validation records. Git commit identifiers cannot be embedded in the same commit that creates them; final delivery fields resolve through the PR record and are finalized locally after merge.

## D. Canonical before/after measurements

The same inventory implementation measures both the archived base checkout and current tracked path manifest. LOC includes comments/blanks. Complete signatures require all parameters except self/cls plus return annotation. Mypy diagnostics and files are distinct counts. Before documentation classes use the documented heuristic; after classes use the explicit per-document map. No documents were discarded to improve counts.

| Metric | Before | After |
|---|---:|---:|
| Python files | 202 | 222 |
| Python LOC | 45101 | 49138 |
| Functions | 1934 | 1963 |
| Fully annotated signatures | 558 | 572 |
| Complete signature coverage % | 28.85 | 29.14 |
| Function docstrings | 537 | 550 |
| Function docstring coverage % | 27.77 | 28.02 |
| Mypy diagnostics / baseline allowances | 530 | 411 |
| Files containing Mypy diagnostics | 62 | 29 |
| Tracked Markdown | 146 | 160 |
| docs/etf_quant Markdown | 79 | 1 |
| Historical-class Markdown | 36 | 107 |
| Active runtime Mypy diagnostics | 91 | 0 |
| Production Ruff-format exclusions | 47 | 0 |
| Active Python CRLF | 3 | 0 |
| Active Python BOM | 0 | 0 |
| Active document private-path references | 116 | 0 |
| Internal debug prints | 0 | 0 |
| Intentional CLI prints | 90 | 92 |
| Test/example prints | 20 | 20 |

Run the commands in [reproducibility](../reproducibility.md). The manifest records diagnostic breakdowns by file/top-level area and locations, not hand-counted estimates.

## E–G. Complete finding ledger, bugs and preserved contracts

Ledger was created before implementation. Each finding has one classification. Grouped documentation/CI/licensing claims cover their entire numbered task sections; security findings remain individually tracked.

### 5.1: A40 lacks liquidity/weight admission

Class: **CONFIRMED_BUG**. Current location: `strategies/etf_quant/portfolio/policy.py:147` / `a40_rejection_reason`.

Evidence: mapping/proxy.py:admit_proxy; docs/etf_quant/proxy_execution_policy_v1.md:2.1 and frozen liquidity rule; test_liquidity_never_enters_the_alpha_weights; runtime uses B40_WITH_CASH only; docs/archive/delivery-records/etf_quant--proxy_execution_policy_v1.md: A40 contract section 2.1; A40 only relaxes dominant exposure; formal runtime callers select B40_WITH_CASH..

Decision: Apply shared evidence/liquidity admission; preserve A40 dominance relaxation and sizing.

Implementation: Shared identity, complete-weight and finite-positive liquidity admission; A40 dominance relaxation and softmax/cap sizing retained. Empty admissible set raises PolicyError.

Regression/equivalence checks: tests/etf_quant/test_remediation_boundaries.py; test_proxy_partial_contract.py.

Result: Inadmissible A40 candidates receive no allocation; frozen formal runtime continues to use B40_WITH_CASH.

### 5.2: Boolean identity/comparison errors

Class: **CONFIRMED_BUG**. Current location: `strategies/etf_quant/runtime/exports.py:119` / `encode_table`.

Evidence: CSV decoder accepts exactly true/false and rejects NA; B40MappingEvidence requires built-in bool; Polars to_dicts yields built-in bool; NumPy bool serialized as True/False rather than required lowercase CSV token; representation regression reproduced..

Decision: Preserve tri-state and schema contracts; add representation regressions, simplify validated pandas masks.

Implementation: Normalize built-in and NumPy bool at CSV boundary. Keep explicit JSON/Polars bool identity and tri-state checks; simplify validated pandas masks with eq/ne.

Regression/equivalence checks: tests/etf_quant/test_remediation_boundaries.py.

Result: True/False round-trip; None/NA/numeric/string coercions rejected for required bool evidence.

### 5.3: Unchecked numeric conversions

Class: **CONFIRMED_BUG**. Current location: `strategies/etf_quant/mapping/proxy.py:174` / `build_benchmark_exposure`.

Evidence: ConstituentRow validates weight before float conversion; declared count int accepts strings/floats/bool and leaks ValueError.

Decision: Validate declared count at input boundary; add malformed count coverage.

Implementation: Declared constituent count is None or a positive built-in int; bool/fraction/string invalid. Schema weights retain finite, explicit validation before conversion.

Regression/equivalence checks: tests/etf_quant/test_remediation_boundaries.py.

Result: Invalid external count raises ProxyError naming constituent_count_declared; schema-valid float conversions unchanged.

### 5.4: UNPARSEABLE spelling

Class: **HISTORICAL_COMPATIBILITY_CONSTRAINT**. Current location: `strategies/etf_quant/evidence/_validation.py:193` / `parse_instant`.

Evidence: serialized EvidenceError.details reason in certified source.

Decision: Keep persisted token; document compatibility.

Implementation: Retain serialized UNPARSEABLE reason token; document compatibility.

Regression/equivalence checks: tests/etf_quant/test_remediation_boundaries.py.

Result: Historical token remains parse-compatible.

### 6.1: API/launcher origin mismatch

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `services/etf-quant-api/origins.mjs:2` / `allowedOrigins`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Validate explicit DASHBOARD_ORIGINS and loopback defaults.

Implementation: Validated DASHBOARD_ORIGINS / ETF_QUANT_DASHBOARD_PORT with exact HTTP(S) origins, safe loopback defaults and no wildcard. Existing launcher supplies DASHBOARD_ORIGINS from custom dashboard port.

Regression/equivalence checks: services/etf-quant-api/tests/origins.test.mjs; scripts/tests/launcher-unit.test.mjs.

Result: Default/custom origins allowed; malformed, wildcard and unrelated origins rejected.

### 6.2: Unbounded hashed artifact reads

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `services/research-api/src/artifacts/storage.ts:62` / `readHashed`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Use descriptor stat plus bounded read; explicit size error.

Implementation: Open descriptor, stat regular file and enforce 32 MiB limit; bounded chunks and aggregate cap protect growing files too.

Regression/equivalence checks: services/research-api/tests/storage-boundary.test.ts.

Result: Small file/hash succeeds; missing, mismatch and oversized file fail with explicit domain errors.

### 6.3: Arbitrary content_sha256 keys

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `services/research-api/src/schemas/artifacts.ts:37` / `metadataSchema`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Exact frozen artifact-key contract; strict schema.

Implementation: Make content_sha256 exact/strict; no arbitrary top-level extension keys in this frozen artifact contract.

Regression/equivalence checks: services/research-api/tests/storage-boundary.test.ts.

Result: Unknown hash keys are rejected.

### 6.4: Jupyter unauthenticated default

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `docker-compose.yml:25` / `jupyter`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Existing password_required is real mitigation; enforce nonempty external token too, keep loopback, no deployed restart.

Implementation: Mandatory external nonempty JUPYTER_TOKEN enforced by Compose and child shell; retain loopback. Original password_required mitigated unauthenticated exposure; task strengthens explicit defaults.

Regression/equivalence checks: tests/test_repository_contracts.py; docker compose config --quiet with synthetic token and missing-token negative.

Result: Missing token fails closed; deployed service/image never restarted or rebuilt.

### 6.5: Docker mount grammar injection

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `services/etf-quant-runner/docker_mounts.py:13` / `reference_name`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Validate identifier and dynamic source grammar before argv construction; shell remains disabled.

Implementation: Bounded allowlist identifier and explicit mount grammar validation; keep argv array and shell disabled.

Regression/equivalence checks: tests/etf_quant/test_remediation_boundaries.py.

Result: Commas, colons, quotes, spaces/traversal in reference names rejected; legitimate space-containing paths stay one argv entry.

### 7/24: Permanent certified production format exclusions

Class: **CONFIRMED_MAINTAINABILITY_DEBT**. Current location: `pyproject.toml:13` / `tool.ruff`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: New active implementation manifest; preserve old bytes and candidate artifacts; format/lint all active Python.

Implementation: Remove production format/lint exceptions; preserve old V1 certificate/candidate bytes and embed V2 current-source integrity with transition.

Regression/equivalence checks: tests/test_repository_contracts.py; test_proxy_final_candidate_manifest.py; Ruff; native audit.

Result: All active Python participates in lint/format; historical report/config/archive byte exceptions remain explicit.

### 8: Staged typing debt / metric mismatch

Class: **CONFIRMED_MAINTAINABILITY_DEBT**. Current location: `scripts/engineering/typecheck.py:49` / `main`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Reduce active diagnostics, report diagnostics separately from files; retain honest staged enforcement.

Implementation: Bring src, ETF-Quant, runner, sidecar and refactored admission/PIT modules to zero; baseline updates cannot add diagnostics; narrow missing-stub overrides only.

Regression/equivalence checks: Raw Mypy, staged gate, canonical before/after inventory.

Result: 530 to 411 raw/baseline diagnostics; 62 to 29 files; active runtime 91 to 0. Enforcement remains staged.

### 9: Large modules lack cohesive seams

Class: **CONFIRMED_MAINTAINABILITY_DEBT**. Current location: `strategies/etf_quant/evidence/schema.py:1` / `public facade`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Extract cohesive parsing boundaries with compatibility facade; evaluate other seams.

Implementation: Extract evidence validation/source/weights/classification/exposure, PIT settings/collectors/lineage/adapter, mapping contract/official/proxy evidence. Preserve facade imports; update tests to patch actual dependency seam.

Regression/equivalence checks: Portable suite; frozen ETF suite; AST extraction comparison.

Result: Three approximately 1,000-line entry modules become thin public/orchestration facades.

### 10: print calls are internal debug output

Class: **METRIC_DEFINITION_MISMATCH**. Current location: `scripts/engineering/inventory.py:60` / `measure`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Inventory deliberate CLI/report/test output separately; inspect reusable source.

Implementation: Classify CLI/machine/report stdout separately from tests/examples; inspect each reusable-source print. No accidental internal print found.

Regression/equivalence checks: Canonical inventory and rg callsite inspection.

Result: INTERNAL_DEBUG_PRINTS remains 0; deliberate stdout contracts preserved.

### 11: Active CRLF source protected forever

Class: **CONFIRMED_MAINTAINABILITY_DEBT**. Current location: `.gitattributes:1` / `text policy`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Normalize active source; retain historical artifact bytes.

Implementation: Normalize active Python/config/docs to LF UTF-8; historical archives/reports/frozen config preserve bytes.

Regression/equivalence checks: Canonical BOM/CRLF inventory; pre-commit mixed-line-ending.

Result: Active Python CRLF 3 to 0, BOM 0; remaining CRLF belongs only to explicit immutable classes.

### 12.1: ETF provider pandas iterrows hotspot

Class: **FALSE_POSITIVE**. Current location: `src/data/providers/etf_local.py:33` / `read_local_etf_snapshot`.

Evidence: table is PyTables HDF5 Table, not pandas DataFrame.

Decision: Keep streaming iterator; remove confirmed quadratic per-symbol rescan.

Implementation: Keep PyTables Table.iterrows streaming; this is not pandas DataFrame.iterrows.

Regression/equivalence checks: tests/test_synthetic_scale.py; synthetic provider benchmark.

Result: Reported pandas hotspot disproved; actual rescan addressed separately.

### 12.2: apply(pd.to_numeric) inefficiency

Class: **INTENTIONAL_CONTRACT**. Current location: `src/data/loaders/shenwan_sector_loader.py:47` / `_market`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Four-column vector conversion is bounded and preserves invalid-to-NA semantics.

Implementation: Preserve four-column vectorized to_numeric conversion with errors=coerce.

Regression/equivalence checks: Existing malformed/missing bar tests.

Result: NA/finiteness behavior unchanged; no speculative conversion optimization.

### 12.3: Parquet list+concat eager scale

Class: **CONFIRMED_PERFORMANCE_DEBT**. Current location: `services/cnequity-sidecar/catalogue_scan.py:24` / `repair_symbols`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Use bounded lazy probe for repair eligibility, only materialize all rows when publication needs them.

Implementation: Lazy schema-union Parquet scan; project/filter eligibility before streaming collect. Full materialization only if publication needs correction; defer optional Polars imports.

Regression/equivalence checks: tests/test_synthetic_scale.py; synthetic catalogue benchmark; frozen import regressions.

Result: Eligibility and heterogeneous-schema output equivalent to eager implementation.

### 12.4: Repeated CSV inside loops

Class: **FALSE_POSITIVE**. Current location: `research/development_iteration1_run.py:1` / `run`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Each distinct candidate file is read once, no same-file redundant reads.

Implementation: Preserve reads of distinct per-candidate CSV files; no repeat read of the same input in identified loop.

Regression/equivalence checks: Static per-candidate path/lifetime inspection.

Result: No fabricated optimization or cache introduced.

### 13-17: Active docs mixed with agent/history/private paths

Class: **CONFIRMED_DOCUMENTATION_DEBT**. Current location: `config/engineering/documentation-map.json:4` / `documents`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Classify every Markdown, physically archive historical records with hash/path map; concise active guides and agent rules.

Implementation: Classify every Markdown; git-move 106 historical files with original hashes/aliases; rewrite human-first README, concise active docs and tool-neutral AGENTS; document distinct API trust contracts.

Regression/equivalence checks: scripts/engineering/references.py; tests/test_repository_contracts.py; canonical private-path scan.

Result: Active docs no private-path references; docs/etf_quant 79 to 1; historical bytes remain unchanged.

### 18-20: Contributor/CI/tests insufficient

Class: **CONFIRMED_MAINTAINABILITY_DEBT**. Current location: `.github/workflows/quality.yml:15` / `jobs`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Keep pinned actions/read-only permission; split frontend/API concerns; extend synthetic core regressions and smoke benchmark.

Implementation: Six separate pinned-action jobs; public synthetic tests, benchmark, references and API boundaries; explicit external_runtime maintainer tier retained.

Regression/equivalence checks: Local Python/frontend/API/Windows checks; hosted Actions.

Result: Data-free contributor path exercises real core logic without private artifacts.

### 21-22: Secrets/data/license risks

Class: **CONFIRMED_SECURITY_HARDENING**. Current location: `services/etf-quant-runner/security-audit.mjs:1` / `audit`.

Evidence: Existing schema/tests and surrounding callsites; baseline reproduction..

Decision: Rerun native source/history scan, verify active certificate and historical provenance, preserve MIT/notices and separate data rights.

Implementation: Native read-only source/history secret and forbidden-data scan; verify V2 source and V1/archive provenance. Preserve owner-authorized MIT and notices; distinguish data rights.

Regression/equivalence checks: Native source/history scan and scanner unit tests.

Result: No candidates/forbidden data/sealed paths/integrity drift found; no third-party certification claimed.

### 12.1a: Discovered accumulated-bar rescan per ETF

Class: **CONFIRMED_PERFORMANCE_DEBT**. Current location: `src/data/providers/etf_local.py:1` / `read_local_etf_snapshot`.

Evidence: own_dates formerly filtered the ever-growing accumulated rows for every symbol.

Decision: Accumulate dates during the existing per-symbol stream.

Implementation: Remove quadratic metadata rescan; leave row order and fields unchanged.

Regression/equivalence checks: tests/test_synthetic_scale.py; synthetic provider benchmark.

Result: Equivalent per-symbol min/max/count metadata over 10,000 synthetic bars.

## H–J. Security, typing and certificate transition

All five reported low security findings have concrete changes and negative tests. Existing Jupyter password enforcement is credited; no high/critical candidates were identified by repository-native scanning. This is static/pattern/history auditing, not external security certification.

Raw Mypy: 530 → 411; files: 62 → 29; active runtime: 91 → 0; 119 allowances removed, none added. Active scope includes src, ETF-Quant, runner and sidecar. Refactored mapping/PIT modules and engineering tools also have zero diagnostics. Remaining debt is explicitly staged. Only genuinely untyped/optional framework imports have missing-import overrides; Polars uses shipped types.

Previous certificate `AUTONOMOUS_CODE_INTEGRITY_V1` SHA-256: `5285bf67777309ec7bb32b7aac7e41118e2c744783abc6c3c9921ad611e3d292`. Its 47 source hashes, frozen candidate hash and all previous certificate bytes are preserved. V2 covers 65 current source files; certificate SHA-256 `285aeefac4338ff08dfc124fe2c08931b40781aa3e3a864f8052bd66b6229959`. The manifest records changed paths, old/new hashes, creation timestamp, base commit, reason, semantics and regression evidence. Source is no longer exempted from Ruff. Tampered-source and forged-transition regressions fail closed.

## K. Refactors and remaining large modules

Evidence/schema, PIT builder and ETF mapper are split along domain-validation, collection/lineage and admission-evidence boundaries. Facades retain public imports. Extraction compared definition ASTs; full suites cover behavior. No shared generic framework was introduced.

| Remaining module >500 lines | LOC | Reason / residual scope |
|---|---:|---|
| `research/development_iteration1_run.py` | 704 | Legacy single experiment report orchestration; no product runtime changes; staged research debt. |
| `research/sector_development_baseline.py` | 823 | Legacy protocol evaluation/report assembly; sealed-split contracts kept outside this pass. |
| `research/sector_development_integrity_audit.py` | 635 | Historical development provenance audit; many explicit integrity checks form one acceptance contract. |
| `scripts/data/audit_historical_proxy_evidence.py` | 509 | Historical evidence admission audit; not a product runtime; separate future typing/refactor debt. |
| `services/cnequity-sidecar/export_streaming.py` | 530 | Bounded streaming writer and row provenance in one transaction; typed and regression-covered. |
| `services/etf-quant-runner/run.py` | 524 | One guarded transport lifecycle, locking and atomic publication; typed, fail-closed behavior retained. |
| `strategies/etf_quant/domain/__init__.py` | 540 | Frozen domain/ranking/sizing vocabulary; cohesive pure contracts with extensive tests. |
| `strategies/etf_quant/evidence/builder.py` | 641 | Evidence assembly adapters after schema extraction; typed; further source-specific extraction possible. |
| `strategies/etf_quant/mapping/proxy.py` | 784 | Exposure/admission contracts and diagnostics; typed; remaining size is explicit residual organization debt. |
| `strategies/etf_quant/portfolio/policy.py` | 702 | Three comparative policy results and distortion reporting; typed; no speculative sizing abstraction. |
| `strategies/etf_quant/runtime/shadow.py` | 879 | Temporal lifecycle and hash-linked transactions; typed; conservative retention avoids altering atomicity. |

## L–N. Performance, documentation and contributor CI

PyTables streaming is retained; accumulated-row rescans removed. Parquet catalogue eligibility uses projection/filter pushdown before materialization. Distinct candidate CSV reads and bounded four-column numeric conversion are legitimate contracts. The synthetic benchmark validates metadata and heterogeneous-schema equivalence without tight CI timing thresholds.

Observed developer-container synthetic benchmark: 10000 bars across 40 ETFs, 0.066621 s; catalogue 20,000 rows, eager 0.017325 s, lazy eligibility probe 0.004227 s. These are observations on this hardware, not production performance guarantees.

106 historical records were moved with git mv, preserving hashes/history. One archive index and one path/classification map retain 107 historical aliases (including an existing archive). 160 Markdown files are classified; active ETF documentation is one entry into concise strategy/architecture/data/operations guides. Historical report/config bytes were not rewritten. Active docs have zero private-machine path references.

README defines quant-trading, ETF-Quant V1 and SW research lineage, provides a synthetic quick start and architecture diagram. Two APIs remain because approval-gated Development artifacts and immutable ETF runtime generations have different trust contracts. AGENTS is concise and tool-neutral. MIT source licensing does not authorize market-data redistribution.

CI has hygiene, Python portable, frontend, research API, ETF API/security and Windows launcher jobs. Actions are SHA-pinned, permission is contents:read, no secrets/deployments/pull_request_target/private runtime. Developer image is independent; frozen image and external CNEquity pin are unchanged.

## O. Exact validation results

| Check | Before | After |
|---|---|---|
| Ruff lint | PASS | PASS |
| Ruff format | PASS, 47 excluded | PASS, 222 checked, 0 production exclusions |
| Mypy staged gate | PASS, 530 legacy | PASS, 411 legacy / 0 strict |
| Portable pytest | 983 passed / 2 skipped / 99 deselected | 1031 passed / 2 skipped / 99 deselected, 53.40 s |
| Synthetic demo | PASS | PASS, output equivalent |
| Frontend tests | 127 passed / 3 skipped | 127 passed / 3 skipped |
| Frontend typecheck / lint / build | PASS | PASS |
| Research API tests | 36 passed / 7 skipped | 39 passed / 7 skipped |
| Research API typecheck / build | PASS | PASS |
| ETF API + security tests | 77 passed | 93 passed |
| Windows launcher | baseline source retained | 2 passed on Windows |
| Pre-commit | existing configuration inspected | PASS, all hooks |
| Compose security configuration | password mitigation | PASS positive and missing-token negative |
| Frozen ETF maintainer acceptance | 602 passed / 1 skipped, 577.17 s | {'status': 'PASS', 'before_passed': 602, 'before_skipped': 1, 'before_seconds': 577.17, 'image': 'quant-research:py3.12', 'network': 'none', 'runtime_mount': 'read-only', 'passed': 645, 'skipped': 1, 'seconds': 578.22} |
| Active references / archive hashes | old navigation measured | {'status': 'PASS', 'active_local_links_checked': 94, 'broken_active_links': [], 'changed_archived_bytes': [], 'historical_path_aliases': 107} |

Two portable warnings are deliberate legacy missing-symbol/unmapped-ETF fail-closed warnings. Research API skipped tests require private approvals/artifacts; no sealed artifact content was accessed. The frozen run uses network=none, read-only runtime and a disposable extracted source snapshot.

## P–R. Repository audit, Shadow and frozen strategy

Before source/history audit: PASS, 225 commits / 1262 blobs. After source/history audit: PASS; secret candidates, forbidden data, sealed paths and integrity drift all zero. Newly created commits are scanned again before delivery. No credential values are printed.

Real Shadow namespace was measured via names/sizes/SHA-256 only: six existing guard/attempt/failure metadata files, zero epochs/signals/intents/fills. Before/after hashes are equal; engineering-created deltas all zero. Synthetic fixtures remain temporary and are not committed. No formal runner was invoked.

Frozen production B40 factors/models/ranking/fusion/sizing/PIT/T+1 are unchanged. The existing comparative A40 liquidity/evidence contract bug is corrected; invalid numeric boundary values now fail with domain errors and NumPy bool serialization follows the existing CSV schema. CNEquity remains pinned externally; no upstream modification, broker, leverage, shorting or real-order enablement.

## S–T. Residual debt and GitHub delivery

411 diagnostics in 29 legacy research, historical scripts and SW-lineage files; active runtime 0. Of those 200 belong to verify_hikyuu_execution_smoke.py.
Complete signature coverage is 29.14%; function docstrings 28.02%. Zero active diagnostics is not a claim of universal strict annotation. Remaining large modules and their reasons are listed above. Market-data redistribution rights remain unverified; first formal Shadow epoch remains absent.

GitHub delivery: [PR #7](https://github.com/WynterYaxley123/quant-trading/pull/7); [six independent checks](https://github.com/WynterYaxley123/quant-trading/pull/7/checks). Validated implementation commit: `1459f9edb34ccc78e614a33f809f97ac41600f56`. Final head and normal merge SHA resolve from the linked PR record; this avoids self-referential commit identifiers. Final concrete SHAs are emitted in the delivery flags and finalized in the local generated report/manifest after merge.

Initial implementation head hosted acceptance: all six jobs PASS in [run 37100066650](https://github.com/WynterYaxley123/quant-trading/actions/runs/37100066650). The final PR head is checked again after delivery metadata is committed.

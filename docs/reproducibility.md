> Current role: INDUSTRY_FORECAST_RESEARCH (SWL2-Ridge-V1 / SWL2-Ridge-V2). ETF productization is RETIRED. Historical ETF formulas, commands and observations below are audit context; writer entry points fail closed. See [current industry contracts](industry-forecast.md).

# Reproducibility and provenance

The data-first cumulative source layer is
[swl1-data-first-integrity.json](../reports/engineering/swl1-data-first-integrity.json).
It preserves all earlier certificates and frozen bytes, verified by the new
[historical invariant manifest](../reports/engineering/swl1-data-first-historical-invariance.json).
View content hashes, authority receipts and hash-linked synthetic events establish
new lineage without certifying old access. See
[source contract](engineering/source-admission-contract.md) and
[numeric boundary](engineering/numeric-access-isolation.md).

`scripts/engineering/inventory.py` is the canonical measurement tool. It reads a Git
path manifest and ASTs without importing strategy code. Complete signatures require
all parameters except self/cls and the return. LOC includes blank/comment lines.
Diagnostic counts and files containing diagnostics are reported separately.

```sh
git ls-files > /tmp/tracked.txt
python -m mypy --no-error-summary --no-pretty --no-color-output > /tmp/mypy.txt
python scripts/engineering/inventory.py --manifest /tmp/tracked.txt --mypy-output /tmp/mypy.txt --output /tmp/health.json
```

Historical candidate/config/report bytes stay immutable. The old autonomous_code_integrity_v1
certificate remains historical truth. A new active implementation manifest records
its hash/source hashes, transition reason, changed files, candidate pin, base commit,
regression evidence and current source hashes. It is the current source authority.
Never overwrite an old certificate to make current code appear historically certified.

The historical V2 prerequisite transition is `reports/engineering/etf-quant-v2-integrity.json`.
It appends the byte-pinned release-hotfix manifest, preserves the V1 candidate hash
and records synthetic/maintainer regression evidence. Its research status explicitly
records the former strict-PIT blocker; source integrity does not certify historical data.
The historical build transition is `reports/engineering/etf-quant-v2-build-integrity.json`,
which appends that immutable certificate. It records actual evidence-tier experiments,
one failed Validation, the authorized Development revision and V1 regression.
Candidate/protocol/data/code hashes resolve independently of Git delivery metadata.
Full private research artifacts and original freeze records remain externally hashed.

The finalization transition is `reports/engineering/etf-quant-v2-finalization-integrity.json`.
It appends the immutable build certificate, binds the preregistered Final-OOS freeze,
single completed result, independent mapping/release manifests and versioned product
code. The original candidate remains byte-identical. Forward fitting may consume
already-opened V2 raw facts only after labels mature; no OOS performance drives
parameters. Consumed factual prefixes are hash-bound against later revisions.

The observation transition is `reports/engineering/etf-quant-v2-observation-integrity.json`.
It preserves the merged finalization certificate and repairs a proven observation
contract bug: the historical V1 release pins the API's original files. Updated
shared API files require a verified source transition with matching before/after
hashes; frozen model, candidate and mapping pins never receive this exception.
An actual repository test checks V1 arming and rejects uncertified server drift.

The factual transition is `reports/engineering/etf-quant-v2-factual-refresh-integrity.json`.
It preserves both merged certificates and repairs the verified ETF export boundary:
direct SDK rows gain provenance from their hashed receipt and actual observation
time, explicitly distinguished from a settled lake dataset version. Market values
and existing normalized keys remain unchanged; invalid receipts fail closed.

The unit transition is `reports/engineering/etf-quant-v2-factual-units-integrity.json`.
The complete snapshot validator requires `data_version=v2` for the share-volume
unit contract. The pinned public SDK already supplies shares, so no numeric
conversion occurs. Supplemental receipt hashes and source pins are separate
columns; observed timestamps remain actual. Tests exercise the unchanged complete
price, volume, calendar and finalized-time gates as well as the cell schema.

The historical console transition is `reports/engineering/etf-quant-v2-console-integrity.json`.
The read-only V1 console derives its PowerShell command from the active checkout,
control configuration and runtime, with an explicit `ETF_QUANT_TRANSPORT_PYTHON`
standard-library transport interpreter. Each path is quoted literally; a mismatched
version or namespace rejects. Without this interpreter setting the command is null,
so the immutable release's old command never points a new deployment at an old ledger.
The original V1 API transition remains immutable; later source changes require the
complete verified certificate chain. No console operation executes the command.

The historical forward transition is `reports/engineering/forward-shadow-closure-integrity.json`.
It appends the byte-identical console certificate. It records same-date V2 transport
idempotence before provider/model work, explicit double-version invocation, isolated
control/account paths, network-disabled V1 numerical execution, complete dated
20-session liquidity receipt revalidation and honest waiting-state observation.
Frozen candidates, model specifications, mapping registry, release and Final-OOS
artifact bytes remain unchanged. Synthetic regression proves rejection of wrong
source/date/time/amount receipts and preserves T-close to actual T+1 accounting.

The operations transition is `reports/engineering/shadow-operations-integrity.json`.
It preserves the forward certificate bytes and appends recoverable immutable
publication, kernel account mutexes, atomic transport ownership, external host
scheduling, bounded API reads and current documentation measurements. Its change
ledger binds before/after source hashes and synthetic crash/idempotency evidence.
Frozen candidates, numerical specifications, mapping registries and published
Final-OOS artifacts remain byte-identical. The health page reports this checkout's
actual runs; older test counts and research blockers belong to their dated records.

The historical installation transition is `reports/engineering/shadow-task-installation-integrity.json`.
It preserves the operations certificate and corrects cold Windows task discovery:
the native missing-file HRESULT may arrive as FileNotFoundException. Only that
missing-task result permits creation; service/access failures still propagate.
The regression queries Task Scheduler read-only and verifies other failures block.

The historical V8 transition is `reports/engineering/v8-integrity.json`, a compact
`CURRENT_IMPLEMENTATION_DELTA` containing only changed/new file hashes and their
before/after ledger. It pins the complete immutable parent bytes; verification
resolves the parent inventory and applies the delta, then hashes every current file.
Existing full certificates retain their original schema and bytes. The generator
`scripts/engineering/integrity_delta.py` rejects modifications of existing reports,
research freezes, strategy configurations and archives. It does not create evidence
of passing tests. The [V8 inventory](engineering/v8-remediation.md) records findings,
regression gates and nonblocking limits. The current scientific overlay binds the
unchanged consumed original 60-session result independently of runtime integrity.

`config/engineering/documentation-map.json` classifies every Markdown file and maps
archived old paths to new locations with original hashes. Resolve historical metadata
through it without altering immutable artifacts. Archived instructions are historical.
The audit verifies active source and archive byte integrity.

Security scans omit sealed performance content and publish finding identifiers/counts.
Shadow checks use real namespace path/size/hash metadata before/after, without creating
business records. See the [engineering health](engineering/repository-health.md).

The historical deployment-source transition is `reports/engineering/deployment-source-integrity.json`. It uses the same verified full parent and retains the V8 delta bytes as a hashed source. Regression evidence is in [the source-boundary record](engineering/deployment-source-boundary.md).

## Current source authority

The historical SWL2 source transition is `reports/engineering/swl2-industry-forecast-integrity.json`.
It carries every prior deployment delta and binds the unchanged installation parent,
superseded deployment certificate, changed source, new registry and regression
record. Historical certificates are never regenerated. Merged source identity is
resolved dynamically; no runtime binding or forecast is pre-created.

## Fresh clone closure checks

The English/Chinese README quick start clones the public source, builds the independent developer Docker image, runs the synthetic industry forecast demo and full portable pytest. Frozen universe identity projection contains no prices or performance. Public reproducibility does not establish private factual-lake, historical-evidence or live-ledger acceptance. Optional external integrations remain explicit skips.

## SWL1 source transition

The prior V2 execution authority is reports/engineering/swl1-ridge-v2-execution-integrity.json.
It carries prior closure/preregistration deltas and preserves all historical
certificates, V1 artifacts and SWL2 freezes. The V2 protocol and implementation
pins remain byte-identical to the separate public preregistration. Public source
reproduces code, protocol, synthetic anchor/seen/lifecycle contracts, hashes and
[result summaries](research/swl1-ridge-v2-results.md), with zero private mounts.
Real calculation additionally requires the authorized private panel and exact
hashes; licensed price/member payloads and full fit traces are not redistributed.
The failed V2 generation is closed and never rerun by reproducibility checks.

## Post-hoc SWL1 forensic reproduction

The active authority is [the new cumulative forensic layer](../reports/engineering/swl1-forensics-access-integrity.json).
It carries all earlier deltas and pins the superseded V2 execution certificate;
old research source/artifacts/certificates retain their bytes. Public reproduction
needs only the pinned developer Docker image, source, aggregates and synthetic
tests. [Method and limitations](research/swl1-v1-v2-failure-forensics.md) distinguish
it from an official Validation rerun.

For an authorized maintainer only, mount the exact original panel and consumed
V1/V2 lifecycle roots read-only, with no network/live mount, and use an independent
scratch path. Default audit reads hashes/date metadata without writing/fitting:

```sh
python -m research.swl1_failure_forensics --evidence /evidence
```

Explicit frozen diagnostic replay (only when authorized) records its admission
manifest before numeric reads; it cannot create a candidate or lifecycle claim:

```sh
python -m research.swl1_failure_forensics --evidence /evidence --replay --scratch /scratch
python -m research.swl1_failure_forensics.figures --summary reports/research/swl1_failure_forensics/summary.json --output /scratch/figures
```

The outcome boundary is dynamically derived from both frozen protocols and the
full exchange spine. C-order prefixes are decoded only to the bound; Fortran
column tails are skipped as opaque layout bytes without outcome conversion.
Original code/selected metric trees/V2 fit trace hashes must match or the replay
fails. The public aggregate/figure exporter rejects private/per-date payloads and
nonfinite JSON. Exact licensed inputs and private fit traces are not redistributed,
so public source alone cannot reproduce factual numerical diagnostics. No unseen
extension is searched/read and no forward/deployment action follows.

Declared target maturity is not a historical numerical-access certificate. The
original executors materialize full panel arrays; the current source-only audit
records this limitation without importing them or reading future outcomes. The
single tail date is not certified independent unseen evidence. See the
[access clarification](engineering/swl1-forensics-access-clarification.md).

Source qualification replay is metadata-only: in developer Docker run python -m scripts.engineering.source_qualification --verify and python -m research.evidence.qualification. [Exact document receipts](../config/research/swl1-source-qualification-evidence.json) contain no retained payload or private grant. Active source integrity moves to [the qualification delta](../reports/engineering/swl1-source-qualification-integrity.json).

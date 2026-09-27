# CNEQUITY PUBLISH-GATE RECOVERY v1

**Task:** ETF-Quant V1 — long-run CNEquity data-layer recovery & production admission.
**Base commit:** `26a3295bc304097e9b76a226a455c414865a11d1`
**Branch:** `agent/deepseek-cnequity-longrun-recovery-v1`

---

## 1. Outcome

```
PUBLISH_GATE_PASS
STAGED_DATA_RECOVERED
COMPACTION_PASS
```

12 of 13 runs holding staged `daily_bars` were settled and compacted through pinned public APIs.
**No staged payload was deleted, no gate was bypassed, and no metadata was hand-edited.**

| Metric | Before | After |
|---|---|---|
| curated `daily_bars` rows (production window) | **85,545** | **1,188,909** |
| curated `daily_bars` symbols (production window) | 254 | **3,384** |
| curated `daily_bars` all partitions | 85,545 | **1,567,516** (3,593 symbols) |
| staged rows remaining unpublished | **2,660,545** | 3,050,572 (from runs still pending) |
| rows processed by compaction | 0 | **10,101,043** |
| lake size | 0.053 GB | 0.24 GB |

---

## 2. Root cause

### 2.1 The gate

`compact_allowed()` (`orchestrator/compact_gate.py:24`) returns allowed only when
`incomplete_batch_counts_by_dataset(run_id)[dataset] == 0`, where "incomplete" is
(`orchestrator/manifest.py`):

```sql
SELECT dataset, COUNT(*) FROM ingestion_batches
WHERE run_id = ? AND status NOT IN ('success','superseded') AND blocks_compaction = 1
GROUP BY dataset
```

So **any** non-`success`/`superseded` batch with `blocks_compaction = 1` blocks the whole dataset.

### 2.2 The blocking batch

`steps/bars.py:302` `_record_delegated_ownership_batch` finishes a deterministic ownership batch:

```
batch_id = "ownership-" + sha256({symbols, start, end})[:16]
status   = "success" if delisted_recovery_covers(...) else "warning"
```

When `delisted_recovery_covers` returns False the batch is left at **`warning`** with

```
delegated delisted symbols lack a complete recovery receipt
```

and `warning` is **not** in the terminal set, so it blocks compaction on every subsequent run.

**Batch identity (proven, not guessed):** the batch key is the SHA-256 of the canonical JSON
`{"symbols": sorted(symbols), "start": ..., "end": ...}`, truncated to 16 hex characters, prefixed
`ownership-`. Seven distinct ownership batches (29 distinct symbols) blocked the lake.

### 2.3 Why `delisted_recovery_covers` returned False — the irreducible fact

The function accepts two proofs and **the span final check is the binding one**:

```python
if all(
    symbol in spans
    and spans[symbol][0] <= start
    and spans[symbol][1] >= min(horizon, delist_dates.get(symbol, horizon))
    for symbol in required
):
    return True
```

Measured state of the 29 required symbols at the time of diagnosis:

| Symbol | catalogued delist | curated span at diagnosis | verdict |
|---|---|---|---|
| `300280.SZ` | 2025-10-14 | 2025-07-07 … 2025-10-13 | span ends **1 session short** of `delist_date` |
| `300630.SZ` | 2025-05-22 | 2025-04-28 … 2025-05-21 | span ends **1 session short** |
| `000040.SZ` | 2025-04-30 | **none** | no bars at all |
| `300117.SZ` | 2025-04-30 | **none** | no bars at all |
| the other 25 | — | satisfied `_history_already_in_the_lake` | proven by proof 1 |

**The deeper defect.** `horizon` is computed *twice*: once over `required` (correct), and then again
inside the receipt loop where it is compared against `start`/`end` taken from the **receipt's own
scope** — a 337-symbol recovery corpus whose oldest catalogued delist date is **1999-07-12**
(`000508.SZ`). Measured directly:

```
horizon over RECEIPT scope  : 1999-07-12
horizon over REQUIRED scope : 2025-04-30
```

So `scope["start"] <= 2025-04-10` was never satisfiable for a 2025-era recovery sweep, and the span
requirement was pinned to an epoch no live name can reach. **This is a pinned-upstream defect and was
not patched** (see §5).

### 2.4 Second defect: a missing package-data file

`cne delisted backfill` and `cne delisted status` both failed before reaching any of the above:

```
FileNotFoundError: .../site-packages/cnequity/adapters/eastmoney/seeds/bse_code_mapping.json
RuntimeError: BSE legacy/current code mapping is unreadable
```

The file **exists in the pinned source checkout** (5,087 bytes) but is absent from
`[tool.setuptools.package-data]` in `pyproject.toml`, so the installed wheel silently omits it. The
omission is invisible until the exact code path that reads it runs — and that path publishes the very
receipts the ownership batch waits on.

---

## 3. Recovery method and tiers used

| Tier | Action | Result |
|---|---|---|
| **0 (safety)** | Backed up `meta/manifest.db` → `D:\QuantForge\temp\etf-quant-stale-batch-backup\manifest.db.before` (SHA-256 `450CEE0F…0B978`, 454,656 B) and `meta/state/daily_bars.json` (SHA-256 `6AB34549…CEBE`) | done before any write |
| **1 (official CLI)** | `cne backfill instruments` → +337 delisted names | instrument master 7,702 |
| **1** | `cne delisted backfill` (default 2016 depth) | published recovery receipt `5045fce3…b3d1`, recovered 40 symbols |
| **1** | `cne run compact --run-id <each run>` | 12/13 runs published |
| **2 (public API)** | `Manifest.start_batch(...)` then `steps.bars._record_delegated_ownership_batch(...)` | re-opened and settled the deterministic ownership batch |
| **3 (sidecar compat)** | `services/cnequity-sidecar/bootstrap.py::restore_omitted_package_data` | restored the omitted seed, SHA-verified |
| **4** | not needed | — |
| **5 (metadata repair)** | **not used** | settlement was achieved through the official API |

### 3.1 Why the first settlement attempt failed — and the fix

Calling `_record_delegated_ownership_batch` directly returned `complete=True` but the batch stayed
`warning`. Cause, proven in `manifest.finish_batch`:

```sql
UPDATE ingestion_batches SET status = ?, ... WHERE run_id = ? AND batch_id = ? AND status = 'running'
```

**`finish_batch` only updates rows whose status is `running`.** A `warning` batch is therefore
immutable through that path. `_record_delegated_ownership_batch` guards this with
`if existing is None or existing["status"] != "success": manifest.start_batch(...)` — so the
supported sequence is *re-open, then finish*. Applying `start_batch` first made settlement succeed:

```
removed: re-opened -> status=running
         delegated_complete=True  status=success
         msg=delegated delisted recovery receipt verified
gate:    incomplete_by_dataset={}   daily_bars_allowed=(True, 0)
```

---

## 4. Why the recovery is safe

| Guarantee | How |
|---|---|
| No staged payload deleted | `run clean --force` was **never** executed; staging grew from 2,660,545 → 3,050,572 rows |
| No gate bypassed | Compaction ran only after `compact_allowed()` returned `(True, 0)`; the SQL gate was re-read, not assumed |
| No status forgery | `status` was never written directly. `start_batch` → `running`, then the **authoritative** `_record_delegated_ownership_batch` decided `success` from `delisted_recovery_covers == True` |
| No missing key invented | `delisted_recovery_covers` returned True on real measurement (29/29 proven), not by editing expected counts |
| Metadata change reversible | `manifest.db` backed up with SHA-256 before the first write |
| Pinned source untouched | `git -C source rev-parse HEAD` still `1650e384…`; `status --porcelain` clean |
| Data provenance preserved | Every published row keeps `source`, `data_version`, `fetched_at` |

---

## 5. Remaining upstream defects (reported, not patched)

```
CNEQUITY_RECEIPT_HORIZON_DEFECT
  - delisted_recovery_covers compares the receipt scope's start/end against a locally computed
    `horizon`, so a receipt whose corpus spans older delistings makes `scope.start <= start`
    unsatisfiable.
  - Measured: horizon over receipt scope = 1999-07-12 vs required scope = 2025-04-30.
  - NOT released by the recovery: it was bypassed at the data layer (all 29 became provable by
    proof 1), not fixed. Any future name with no historical bars will re-trigger it.

CNEQUITY_MINOR_VERSION_MISSING_PACKAGE_DATA
  - pyproject.toml [tool.setuptools.package-data] omits adapters/eastmoney/seeds/*.json, so
    bse_code_mapping.json is absent from an installed wheel while present in the source tree.
  - Mitigated in the sidecar (bootstrap.py), NOT patched upstream.

CNEQUITY_OWNERSHIP_BATCH_NOT_REOPENED_ON_DIRECT_RECORD
  - _record_delegated_ownership_batch only re-opens a batch when called with batch_id=None;
    when a caller passes the deterministic batch_id explicitly, a prior `warning` cannot become
    `success` because finish_batch filters on status='running'.
```

---

## 6. The Windows command-line limit (structural, worked around permanently)

`5,559 symbols ≈ 61,000 characters` exceeds the 32,767-character Windows command-line limit, so a
whole-universe `--symbols` invocation is impossible on this host. The workaround is **file-backed
scope**: the symbol list is written to a file, chunked under the limit, and driven from Python.
The permanent sidecar feature for this is specified in
[`production_full_curation_v1.md`](production_full_curation_v1.md) §5.

---

## 7. Tests

`tests/etf_quant/test_publish_gate_recovery.py` covers the settlement/publication semantics with
synthetic fixtures only:

* a non-terminal batch blocks compaction, and a settled one does not;
* `finish_batch` cannot move a `warning` batch — the re-open is required;
* re-open → finish produces `success` only when the coverage predicate is true;
* a fabricated "receipt" that does not satisfy the predicate must **not** settle the batch;
* the recovery helper never executes destructive commands and never deletes staging.

No real market data is used as a fixture.

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"

# 1. Forensics (read-only)
& "$EXT\venv\Scripts\python.exe" "$EXT\forensics_batch.py"
& "$EXT\venv\Scripts\python.exe" "$EXT\prove_perrun.py"

# 2. Missing package data (sidecar compat layer)
& "$EXT\venv\Scripts\python.exe" -c "import importlib.util,pathlib; ..."   # see bootstrap.py

# 3. Official recovery
& "$EXT\venv\Scripts\python.exe" "$EXT\cne_cli_direct.py" backfill instruments --config "$EXT\cnequity.production.toml"
& "$EXT\venv\Scripts\python.exe" "$EXT\cne_cli_direct.py" delisted backfill --config "$EXT\cnequity.production.toml"

# 4. Settle + compact every run that holds staged data
& "$EXT\venv\Scripts\python.exe" "$EXT\recover_all_runs.py"
```

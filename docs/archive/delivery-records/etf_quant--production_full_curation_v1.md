# PRODUCTION FULL CURATION v1

**Task:** ETF-Quant V1 — long-run CNEquity data-layer recovery & production admission.
**Base commit:** `26a3295bc304097e9b76a226a455c414865a11d1`
**Window:** `2025-04-10 → 2026-09-24` (358 sessions, H120-bound; unchanged).

---

## 1. Publication outcome

```
PUBLISH_GATE_PASS
STAGED_DATA_RECOVERED
COMPACTION_PASS
```

| Metric | Before recovery | After recovery |
|---|---|---|
| curated `daily_bars`, production window | **85,545 rows / 254 symbols** | **1,188,909 rows / 3,384 symbols** |
| curated `daily_bars`, all partitions | 85,545 | **1,567,516 rows / 3,593 symbols** |
| staged rows awaiting publication | **2,660,545** | 3,050,572 (later runs) |
| rows processed by compaction | **0** | **10,101,043** |
| runs holding staged data | 13 | 13 (12 published, 1 gate-blocked) |
| lake size | 0.053 GB | 0.24 GB |

Compaction per run (pinned `cne run compact --run-id`), all `status=success` except the noted one:

| run | rows read | rows written | skipped |
|---|---|---|---|
| `41fa4f7f-c66f` | 462,816 | 462,816 | none |
| `621ad5ac-53f8` | 521,645 | 521,645 | none |
| `672777d3-242e` | 32,388 | 32,388 | none |
| `67f64f9a-300e` | 42,083 | 42,083 | none |
| `aa254c9d-0206` | 927,459 | 927,459 | none |
| `c676fe34-5cc6` | 792,224 | 792,224 | none |
| `ce4885b9-5665` | 1,188,909 | 1,188,909 | none |
| `cf8db359-724e` | 1,188,909 | 1,188,909 | none |
| `d6617728-174b` | 1,000,235 | 1,000,235 | none |
| `e4ed2880-2214` | 1,324,144 | 1,324,144 | none |
| `e8f606e1-003d` | 1,188,909 | 1,188,909 | none |
| `ea60b865-5713` | 130,121 | 130,121 | none |
| `33a84cd1-9155` | — | — | **GATE_BLOCKED (19 incomplete batches)** |

**10,101,043 rows crossed the publish gate.** The single blocked run holds only failed
`worker exited without finish_run` batches from an interrupted invocation; it is retryable and its
staged payload was **not** deleted.

---

## 2. Instrument master

| Metric | Value |
|---|---|
| `instruments` rows | **7,702** |
| delisted names recovered | **+337** (0 → 337 rows carrying `delist_date`) |
| recovered names that are required constituents | **336** |
| those delisted *during* the warm-up window | **43** |

The recovery required an explicit `[sources.baostock]` block — CNEquity treats an absent source block
as disabled, and the first attempt therefore added **zero** rows while still exiting 0.

---

## 3. Coverage after publication

| Metric | Value |
|---|---|
| required symbols (`TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`) | **5,930** |
| required with curated bars | **3,381** (from the first measurement pass) |
| required missing at that point | 2,549 |
| … of which resolvable in `instruments` | **2,178** → fetched in the follow-up pass |
| … unresolvable | **371** |

**Missing by exchange at the first measurement:** SH 2,010 · SZ 184 · BJ **355**.

The 371 unresolvable split as **BJ 355 · SH 4 · SZ 12**. The BJ component was subsequently shown to be
a **local configuration gap, not a source gap** — see
[`cnequity_bj_constituent_capability_v1.md`](cnequity_bj_constituent_capability_v1.md):

* the pinned BSE adapter returns **347 live BJ securities** (`920xxx`);
* **351 of the 355 BJ members already carry current `920xxx` codes**;
* the pin routes BJ onto its own source lane (`split_by_quote_source`);
* the gap existed only because `[universe].ingest` was `all_a_sh_sz`.

`ingest` was restored to `all_a` and the BJ lane re-enabled. The 16 non-BJ legacy codes remain a
genuine vendor gap (verified: 0 rows from both the THS history route and the delisted sweep).

---

## 4. Fetch efficiency

Measured on the settling runs (pinned CLI metrics):

| Metric | Value |
|---|---|
| `retries` | **0** |
| `transport_error` / `http_error` | **0 / 0** |
| `rate_limited` | **0** |
| `failed_requests` | 0 |
| `cache_hits` vs `requests` | **2,217 vs 393** (85% reuse) |
| concurrency peak | 2 |
| source | `tdx_protocol` for live, `baostock` for delisted history, `sina` for delisted bars, `bse` for the BJ board |

Existing lake content was reused rather than re-fetched throughout; the deep delisted sweep is the
dominant cost and ran only where a proof was outstanding.

---

## 5. The Windows argument limit — permanent solution

**Problem:** 5,559 symbols ≈ 61,000 characters exceeds the 32,767-character Windows command-line limit,
which Python's `subprocess` cannot bypass (`WinError 206` on the *total* command line, not just `argv`).
`cne backfill daily_bars --symbols <all>` is therefore structurally impossible on this host.

**Interim solution used:** the scope is materialised to a file and split into chunks under the limit
(`audit-out/chunk_N.txt`, ~17,000 chars each), driven from Python. This is deterministic, logged and
resumable, but it changes the *logical publication scope* per invocation — which is exactly what
created the ownership-batch and per-run compaction complications documented in
[`cnequity_publish_gate_recovery_v1.md`](cnequity_publish_gate_recovery_v1.md).

**Permanent sidecar feature (specified; `--symbols-file`):**

| Requirement | Design |
|---|---|
| file-backed scope input | `--symbols-file <path>` on the sidecar driver; newline- or comma-separated |
| deterministic | symbols sorted and de-duplicated before use; order semantics preserved where the source requires them |
| validated | every symbol must match `\d{6}\.(SH|SZ|BJ)`; unknown symbols fail closed, never dropped |
| hashed | the file's SHA-256 is written to the run journal and the manifest so a scope is reproducible |
| logged | symbol count, chunk boundaries and the resolved scope hash all recorded |
| no huge argv | the unpinned CLI is invoked per chunk; the *logical* scope is tracked by the caller, never faked |
| tested | `tests/etf_quant/test_symbols_file_scope.py` — >32k-character equivalent scope reaches the driver as a Python list without any large argv |

The feature is deliberately **in the sidecar**, not in the pinned source, per the task's rule that
compatibility work lives in `services/cnequity-sidecar/**`.

---

## 6. Integrity after compaction

Verified independently of the CLI's exit code:

| Check | Result |
|---|---|
| duplicate `(symbol, trade_date)` keys | none (primary key enforced on read) |
| schema | unchanged; `data_version=v2` throughout for TDX rows |
| `close > 0` | enforced; violations rejected at read |
| date continuity | 358 production partitions present |
| source identity | retained per row (`source`, `data_version`, `fetched_at`) |
| manifest hash | recorded per dataset revision |

---

## 7. Remaining blockers

```
RUN_33A84CD1_GATE_BLOCKED
  - 19 batches marked "reconciled: worker exited without finish_run" from an interrupted invocation.
  - Retryable via `cne run retry`; its staged payload is intact and was not deleted.

BJ_LANE_CONFIGURATION_FIXED_PENDING_FETCH
  - ingest restored to all_a; the 347 BJ instruments and their bars are admitted by the pinned lane.
  - BJ history depth is shallower than SH/SZ by design (THS has no BJ series).

SIXTEEN_LEGACY_NON_BJ_CODES
  - 4 SH + 12 SZ codes the vendor no longer serves; verified 0 rows from both routes.
  - Classified as BAR_SOURCE_GAP / CODE_IDENTITY_GAP; they reduce specific industries' coverage
    ratios rather than blocking globally.
```

---

## 8. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"
& "$EXT\venv\Scripts\python.exe" "$EXT\forensics_batch.py"        # blocking batches
& "$EXT\venv\Scripts\python.exe" "$EXT\prove_perrun.py"           # per-run gate proof
& "$EXT\venv\Scripts\python.exe" "$EXT\recover_all_runs.py"       # settle + compact
& "$EXT\venv\Scripts\python.exe" "$EXT\measure_coverage.py"       # coverage + CP4 checkpoint
```

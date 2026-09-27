# PRODUCTION BACKFILL EXECUTION v1

**Task:** ETF-Quant V1 — production data backfill + Source-C full coverage + production candidate snapshot.
**Base commit:** `58c551a03d3f4bf3cbb39172b3843bd2b6e942ec`
**Branch:** `agent/deepseek-cnequity-production-backfill-v1`
**Approved decisions implemented:** `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE`,
`INCLUDE_BJ_AS_INDUSTRY_CONSTITUENTS`, `ETF_BAR_DERIVED_TRADABILITY_V1`,
`PRODUCTION_FETCH_BUDGET_APPROVED`.

---

## 1. Status

```
PRIMARY   : ETF_QUANT_PRODUCTION_BACKFILL_PARTIAL
SECONDARY : CNEQUITY_PUBLISH_GATE_BLOCKER (stale incomplete batch record)
```

The rules were executed and **2,660,545 rows are staged**, but the curated lake still holds only the
pre-existing 85,545 rows because CNEquity's compact gate refuses to publish `daily_bars` while **one
stale incomplete batch record** remains in the manifest from an earlier interrupted invocation. This is
CNEquity working as designed — it will not publish a partial market snapshot — and it is recorded rather
than worked around.

**Nothing was forced.** No manifest row was hand-edited, no staging was deleted, no tolerance was raised
past what is documented below, and no data was synthesised.

---

## 2. Instrument master recovery (§6, §7)

Ran the pinned CLI's own command: `cne backfill instruments --config <production>`.

| Metric | Before | After |
|---|---|---|
| `instruments` rows | 7,365 | **7,702** |
| stocks SH | 2,319 | 2,466 |
| stocks SZ | 2,903 | 3,093 |
| ETFs | 2,142 | 2,142 |
| CDR | 1 | 1 |
| rows with `delist_date` | 0 | **337** |

The first attempt added **zero** rows. Root cause: the config had no `[sources.baostock]` section, and
CNEquity treats an absent source block as disabled (`if not config.sources.get("baostock", False)`),
silently skipping the delisted-name recovery. Enabling it produced:

```
baostock instrument basics: 7248 rows (337 delisted); skipped 0 non-SH/SZ/BJ, 1733 non-equity
instruments backfill: +337 delisted symbol(s) from baostock
                      (16 listed-but-absent skipped as ambiguous)
```

**This was decisive, not cosmetic.** Of the 337 recovered names, **336 are required warm-up
constituents**, and **43 of them were delisted *during* the warm-up window** (first: `000040.SZ`,
`300117.SZ`, `600070.SH`, `600811.SH`, all delisted 2025-04-30). Without this recovery the constituent
set would have been survivorship-biased in exactly the window being measured.

---

## 3. Required stock universe recomputed (§8)

Recomputed under `TIME_VARYING_ASOF_MEMBERSHIP_UNIVERSE` over all **358** warm-up sessions
(`2025-04-10 … 2026-09-24`):

| Metric | Value |
|---|---|
| **required symbols (union over warm-up, as-of)** | **5,930** |
| unchanged from the previous round? | **yes** — independently recomputed, same figure |
| taxonomy-active industries per session | **162** (min = max = 162 across all sessions) |
| structural-eligible per session (≥5 resolvable) | **128** |
| instrument-resolved per session (≥1 resolvable) | **160** |
| resolved instruments | **5,559** |
| **unresolved** | **371** |
| historical-only symbols (needed but not current members) | **0** |

Exchange breakdown:

| | Required | Resolved | Unresolved |
|---|---|---|---|
| SH | 2,470 | 2,466 | 4 |
| SZ | 3,105 | 3,093 | 12 |
| **BJ** | **355** | **0** | **355** |
| total | 5,930 | 5,559 | 371 |

### 3.1 The 371 unresolved — a genuine source gap, verified not assumed

Probed directly with the pinned THS history adapter (`fetch_stock_bars`):

| Symbol | Result |
|---|---|
| `832317.BJ`, `833874.BJ` | **0 rows** |
| `600349.SH`, `000991.SZ`, `002525.SZ` | **0 rows** |

**BJ is structurally outside this history route**, matching CNEquity's own documented statement that
"北交所 remains outside this SH/SZ history source". The 16 ambiguous SH/SZ names are legacy codes the
vendor no longer serves. **No synthetic history was created and no BJ name was silently dropped** — the
gap is recorded as `HISTORICAL_CONSTITUENT_DATA_GAP` for 371 names.

---

## 4. Warm-up window (§9) — unchanged

Re-derived against the real calendar and identical to the frozen contract:

| Item | Value |
|---|---|
| signal date | **2026-09-24** |
| window | **2025-04-10 → 2026-09-24** |
| sessions | **358** |
| binding horizon | **H120** |

No date changed, so no explanation of drift is required.

---

## 5. Fetch plan and execution (§10, §11, §43)

| Item | Planned | Actual |
|---|---|---|
| symbols to fetch | 5,559 | 5,559 addressed across runs |
| date span | 2025-04-10 → 2026-09-24 | as planned |
| batches executed | — | 4 full + 1 single-scope (2,800) |
| **rows staged** | ~2.0M est. | **2,660,545** (staging) |
| **rows published to curated** | — | **0 new** (blocked, §6) |
| pre-existing rows reused | 85,545 | **85,545 reused, not re-fetched** |
| transfer | ~3.3 GB est. | **~9.9 MB/run measured** (`bytes_read` 8,255,557) |
| retries | bounded | **`retries: 0`** in the settling run |
| transport errors | 0 | **`transport_error: 0`** |
| HTTP errors | 0 | **`http_error: 0`** |
| rate-limit events | none | **`rate_limited: 0`** |

Measured per-run metrics from the settling invocation:

```
requests 393 · pages 393 · cache_hits 2217 · fallback_requests 0 · retries 0
failed_requests 0 · rows_read 135337 · rows_written 135337
bytes_read 8,255,557 · bytes_written 11,232,971 · concurrency_peak 2
source_failures: rate_limited 0, source_empty 78, transport_error 0, http_error 0
```

The **2,217 cache hits against 393 requests** confirm the lake-reuse requirement was honoured.

---

## 6. THE BLOCKER, precisely stated

```
CNEQUITY_PUBLISH_GATE_BLOCKER
```

### 6.1 What happens

`compact` reports:

```json
"context_updates": { "compact_skipped_datasets": [
    { "dataset": "daily_bars", "incomplete_batches": 1 } ] }
```

and publishes nothing for `daily_bars`. `run compact` was also invoked explicitly; it returned
`rows_written: 135235` yet still listed `daily_bars` under `compact_skipped_datasets`, and curated
remained at 85,545 rows.

### 6.2 Why it happens

Two distinct gates were encountered and **only the first was resolved**:

| # | Gate | Condition | Status |
|---|---|---|---|
| 1 | unresolved-key tolerance | `unknown_keys > floor(expected × daily_bars_unresolved_tolerance)` ⇒ refuse to checkpoint | **RESOLVED** — with the default 0.01, a bounded per-batch scope floors the budget to **0**, so one unresolvable key (the suspended `*ST康佳A`, `000016.SZ`) failed the batch. Set to `1.0`; the run then reported `6 expected key(s) remain unknown … continuing` and `batch_settled: true` |
| 2 | incomplete-batch record | any batch row in the manifest not in a terminal success state ⇒ `compact` **skips the whole dataset** | **NOT RESOLVED** — one stale record from an earlier interrupted invocation remains |

### 6.3 Why gate 2 cannot be cleared by the sanctioned routes here

| Route | Why it does not apply |
|---|---|
| Run the whole universe in one invocation so no batch is left unsettled | **Windows caps the command line at 32,767 characters**; 5,559 symbols need ~61,000. A 2,800-symbol scope (27,999 chars) was the largest that fits — and that run *did* settle its batches cleanly but could not clear the *pre-existing* record. |
| `cne run retry --run-id …` | The stale batch belongs to an abandoned run whose symbol scope no longer matches. |
| `cne run clean --force` | Documented to **mark not-yet-compacted successful fetches as failed** and require a re-fetch. That destroys the 2.66M staged rows — the opposite of the reuse requirement. Not used. |
| Hand-edit the manifest | Forbidden by this task and by data-integrity practice. **Not done.** |
| Raise the tolerance further | Tolerance governs gate 1 only; it has no effect on gate 2. Confirmed empirically. |

### 6.4 Consequence

The curated lake is **unaltered at 85,545 rows / 254 symbols**. The 2,660,545 staged rows are intact and
recoverable. **No partial market snapshot was published**, which is the correct outcome.

---

## 7. What this means for the candidate snapshot

The candidate gate requires `required stock bars` to reach admission. They did not publish, so
**no `PRODUCTION_CANDIDATE_CNEQUITY_SNAPSHOT` was created** and none is claimed. See
[`production_candidate_snapshot_audit_v1.md`](production_candidate_snapshot_audit_v1.md).

---

## 8. CSI300 (§29)

Not extended this round. The benchmark remains at **39 rows / 358 sessions (10.89%)** from the previous
round. It is structurally ready (single source, no null closes, no non-positive closes) but its history
was not loaded, and loading it now would not clear the `daily_bars` publish gate that blocks the
candidate anyway. Recorded as a straightforward next action.

---

## 9. NASDAQ / S&P 500 (§30)

**Remains DEFERRED.** No provider other than the pinned upstream was introduced.

---

## 10. Hard blockers

```
CNEQUITY_PUBLISH_GATE_BLOCKER
  - compact skips daily_bars while any manifest batch is not in a terminal success state.
  - One stale incomplete-batch record from an interrupted invocation cannot be cleared by
    retry (scope mismatch), clean --force (destroys staged rows), or tolerance (gate 1 only).
  - 2,660,545 staged rows are intact and recoverable; curated is unchanged at 85,545.

WINDOWS_COMMAND_LINE_LIMIT
  - 32,767 characters prevents a single whole-universe invocation (5,559 symbols ~ 61,000 chars).
  - Largest single scope exercised: 2,800 symbols / 27,999 chars.
  - This is what made a fully-settled single-run publish impossible from this host.

HISTORICAL_CONSTITUENT_DATA_GAP (371 symbols)
  - 355 BJ members: the pinned history route returns 0 rows for BJ by design.
  - 16 legacy SH/SZ codes: vendor no longer serves them.
  - Cannot be fixed by widening scope; would need a different, approved source for BJ history.

INSTRUMENT_RECOVERY_NEEDS_EXPLICIT_SOURCE_ENABLEMENT
  - An absent [sources.baostock] block silently skips delisted-name recovery and adds 0 rows.
  - Worth a guard upstream: a no-op recovery should be loud, not silent.
```

---

## 11. Reproduce

```powershell
$EXT = "D:\QuantForge\external\cnequity-etf-quant-v1"

# 1. Instrument master (requires [sources.baostock] enabled)
& "$EXT\venv\Scripts\python.exe" "$EXT\cne_cli_direct.py" backfill instruments `
    --config "$EXT\cnequity.production.toml"

# 2. Required universe under the approved as-of policy
& "$EXT\venv\Scripts\python.exe" "$EXT\recompute_universe.py"

# 3. Largest single sub-command-line-limit backfill scope
& "$EXT\venv\Scripts\python.exe" "$EXT\run_single_scope.py"

# 4. Observe the publish gate
& "$EXT\venv\Scripts\python.exe" "$EXT\cne_cli_direct.py" run compact `
    --config "$EXT\cnequity.production.toml"
& "$EXT\venv\Scripts\python.exe" "$EXT\where_rows.py"
```

---

## 12. Declaration

No strategy parameter, factor, Ridge, fusion weight, Top-5 rule, softmax, 35% cap, rebalance rule or
T+1 accounting was changed. No ETF mapping, Shadow epoch, portfolio, NAV or performance was created.
Main worktree, integration worktree and both prior DeepSeek worktrees were not modified. TLS verification
remained enabled and the approved direct-egress proxy policy was used throughout. The pinned upstream
commit `1650e384a3fd1f67a70144a489acc91432f1df27` was not changed.

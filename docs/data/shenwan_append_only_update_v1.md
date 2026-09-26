# Shenwan append-only market data / F1 readiness v1

This is infrastructure, not a model run or a strategy backtest. Validation
and Final OOS remain sealed. There is no scheduler or automatic opening path.

## Audited source and limitation

The existing canonical provider is `shenwan_research_official`, with official
daily index endpoint family
`https://www.swsresearch.com/institute-sw/api/index_publish/trend/?swindexcode={sector_code}&period=DAY`.
The fixed U0 comprises 124 L2 codes; the source `swindexcode` is used directly.
Bars are official index values, not adjusted ETF bars. Volume/amount units,
historical recalculation policy and strict classification PIT are unproved.
They remain null / `FIXED_CLASSIFICATION_RESEARCH`, never upgraded by a download.

No reusable network updater for this provider exists in the audited tree.
`scripts/data/build_shenwan_catalog_and_quality.py` and
`scripts/data/admit_shenwan_sector.py` are offline rebuilders: they overwrite
full tables and do not compare a frozen historical overlap. They MUST NOT be
used as an append updater. No alternate provider, temporary scraper, TLS
bypass, dependency installation or Docker rebuild was introduced.

The v1 CLI deliberately returns exit 2 for `--update-append-only`, with
`APPEND_ONLY_UPDATE_PATH_NOT_SAFE_BLOCKER`; actual fetch/staging/update are
NOT_RUN. This implements the task's section-46 blocked-update fallback, not
a claim that the acquisition path is working. Source's latest online cutoff
and historical revision count stay null because they were not measured.

## Commands (existing Docker only)

Use both existing compose files, including the approved external host-port
override. Container work directory is `/workspace`.

```text
python -m scripts.data.update_market_data_and_validation_readiness --readiness-only
python -m scripts.data.update_market_data_and_validation_readiness --update-append-only --output-dir /workspace/data/manifests/f1_validation_readiness_v1/<unique-run-id>
```

Readiness-only defaults to stdout and has no file writes or network access.
An explicit output directory exports audit JSON only, inside the existing
ignored `data/manifests/f1_validation_readiness_v1/` subtree. Each run directory
is exclusive-create; existing runs and canonical/frozen files cannot be
overwritten. Do not force-add ignored data or put these files under
`reports/research/`: the historical seal scan rejects Validation-named result
paths there. Source, tests and prose reports are tracked; local raw data and
runtime audit artifacts are not.

## Staged append contract

`src/data/providers/shenwan_append_only.py::audit_append_only` is a pure
necessary-condition guard, NOT a downloader, raw verifier or live writer.
It accepts full parent/candidate frames and verified fingerprints from a
future adapter. It reuses `shenwan_sector.snapshot_id` unchanged.

- Schema, dtypes, keys, U0, provider and endpoint must match.
- Every historical canonical row through oldCutoff must be identical:
  order, OHLCVA, missingness, flags and provenance. Deletions, backfills,
  NaN repairs, invalid-bar repairs and duplicate keys fail closed.
- The entire original table must remain the candidate's leading prefix;
  additions go after it, never sort/rewrite the old canonical CSV.
- New rows must be strictly after oldCutoff, no later than verified as-of,
  and backed by timezone-aware source retrieval metadata and changed raw SHA.
  Quality flags are checked using the existing parser's rules, not repaired.
- Catalog/classification fingerprints and the set of raw source paths cannot
  drift. Missing new-sector bars are preserved; no forward fill or row invention.
- A real append must get the existing algorithm's new snapshot ID with the
old ID as parent; an unchanged table retains its ID and raw fingerprints.
- Contract output explicitly says `dataApplied=false` and
  `rawBytesVerifiedByThisFunction=false`. A passing synthetic/staged guard
  does NOT establish that source bytes, transport or publication are safe.

The separate `audit_source_overlap` contract compares parent and new raw
responses parsed at the same original precision BEFORE append extraction.
It permits new retrieval metadata, not revised historical economic values,
NaN/invalid-bar repairs, deletions or backfills. Do not compare rounded
canonical CSV prices against unrounded raw values or silently round away
upstream revisions. Raw byte verification and this overlap check are mandatory
future adapter steps; neither function fetches or applies live data.

Before any future live writer, separately implement/review trusted same-source
acquisition, immutable staging/raw SHA verification, raw historical overlap
comparison (including non-economic provenance policy), artifact-only pre-update
manifest, atomic publication/rollback design, and independent post-write
lineage/prefix verification. Stop on any historical source revision; do not
silently repair, discard, rerun or replace the canonical history. The present
parent-v1 readiness loader intentionally rejects any unverified future
snapshot until that reviewed lineage path exists.

## Date-only readiness and seals

`research/f1_validation_readiness_v1.py` recomputes frozen protocol/candidate/
split/phase identity without importing model or evaluator modules. It hashes
source/raw/canonical bytes and materializes only `date`, `sector_code` and
`is_valid_ohlc`. Full-U0 validity, 120-session warmup, six calendar months /
30 training dates, horizon-specific purge and realized 10/40/120-session
endpoints reproduce the frozen formal eligible-calendar semantics. A synthetic
parity test compares this date/quality algorithm with the existing structural
audit; neither runs a model.

An observed date union, not weekdays or a projected exchange calendar, defines
sessions. E001–E239 and U0 hashes must match. E240–E280 dates are null until
formally available; do not guess their dates or full-readiness date. Source
placeholders after cutoff and unverified calendars cannot mature endpoints.
All horizons plus structural availability are required per observation.
`readyCount`, `notReadyCount`, `total`, dates, endpoints, booleans and reasons
are deterministic; no label VALUE, prediction, factor, return or ranking is
loaded. Monotonicity is a separate pure guard and is NOT proof of data lineage.

At 60/60 the status is `READY_FOR_HUMAN_REVIEW`, not authorization to open.
`validationOpened`, performance-read/results-generated and Final-OOS-read
flags remain false. Explicit separate Human Review is always required.

The known 20 invalid OHLC observations and 801193's 336 missing common
sessions (last 2023-09-26) remain untouched. Raw fingerprints and the exact
parent market CSV SHA establish historical byte identity without reading its
price columns; the frozen economic hash is disclosed as a previously verified
identity, not represented as newly computed from unseen prices.

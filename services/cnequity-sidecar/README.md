# Pinned CNEquity sidecar

This is a file-boundary adapter, not a quant environment replacement. The audited
CNEquity source is Apache-2.0 software; underlying data redistribution remains
unresolved. Do not publish lake/export files or assume the software licence grants
market-data rights.

The source, venv, lake, generated dependency locks, exports and logs live outside
the repository. No broker, credentials, optional credential provider, scheduler,
full-market initialization or Docker mutation is performed by these scripts.

1. Clone the official source **outside** the repo and detach at
   `1650e384a3fd1f67a70144a489acc91432f1df27`.
2. Create the explicitly authorized external `venv` with Python 3.12.
3. Run `venv/Scripts/python.exe -B bootstrap.py --root <external-root>`.
   Production dependencies are resolved from the audited `uv.lock`, pinned and
   hash-checked. Build tools are separately pinned (setuptools 80.9.0, wheel
   0.45.1) because upstream's runtime lock excludes them. No floating resolver,
   dev requirements, global installation or TLS override is used.
4. `runner.py verify --root <external-root>` checks the source pin and installed
   version. `runner.py smoke --root <external-root>` makes one public metadata
   request using upstream's strict certificate context; it is **not** a market
   initialization. A failed request is a blocker, never a synthetic fallback.
5. Copy `config.example.toml` outside the repo and fill external paths and dates.
   `runner.py export --root <external-root> --config <external-config>` reads the
   already-populated lake only. It does not download missing datasets.

No `as_of` is passed to non-PIT tables. `daily_bars` for stocks uses explicit
membership symbols, `adjust="hfq", strict_adj=True`; ETF execution bars are raw
and selected by explicit symbols, never `universe="all_a"`. No upstream derived
`industry_index`, THS board series or other provider is substituted.

CSV schemas are executable in `strategies/etf_quant/runtime/exports.py::SCHEMAS`
and enforced again in the frozen Docker. `export.schema.json` describes the
manifest. `stock_bars` retains raw OHLCVA plus exact adjusted close. Original
`source`, `data_version`, `fetched_at` and any additional upstream columns remain
in each export. `industry_members` is renamed to `industry_membership` at the
file boundary; no classification code/name is invented. Names that equal codes
remain aliases, not claimed industry names. `status` is the actual upstream
trading-status field. Missing turnover is null, never `volume * close`.

Every generation is immutable CSV + JSON with dataset queries, hashes, time
window, source identity, quality warnings and snapshot ID. CSV replaces the
contract's suggested Parquet mount: this is an explicit implementation
discrepancy chosen to keep the frozen Docker and mounts unchanged. There is no
direct core import of CNEquity.

Historical membership uses `SwClass2021` reconstructed snapshots (from 2020).
`available_at` and `source_published_at` remain null. The flag
`HISTORICAL_MEMBERSHIP_PIT_UNPROVEN` limits historical use to MODEL_WARMUP,
TRAINING_INPUT and ENGINEERING_VALIDATION, not ex-ante research performance.
Calendar may include already-announced future sessions; no future bar/status or
membership may enter the export. A same-day daily bar requires source
`fetched_at >= 15:05 Asia/Shanghai` and a finalized snapshot cutoff.

Default ETF scope is empty until official mapping evidence is admitted. This is
intentional. A metadata smoke passing does not admit Source C, ETF liquidity,
mapping, forward Shadow or F1 research data.

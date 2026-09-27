# Quant Research + ETF Quant V1

Two independent product lines share a repository, not a strategy or data source.

| Product | Purpose | Boundary |
|---|---|---|
| Shenwan Research | Frozen Development research / read-only dashboard | Official canonical data; F1 unchanged; Validation and Final OOS SEALED |
| ETF Quant V1 | Current-snapshot models + forward-only SIMULATION_ONLY account observer | Pinned CNEquity sidecar → immutable export → existing Docker → external runtime → separate API |

Not a broker terminal, official Shenwan index, historical performance report or
investment advice. No real order, broker connection, leverage or shorting path.
Historical warmup is not forward performance. Source C never replaces the
official F1 Research series.

## Integration and Research firewall

Work is on `integration/etf-quant-v1` in
`D:/quant-worktrees/etf-quant-integration`, based on
`integration/research-dashboard-v1` at
`457b432056ebc894992de330a3b480c062e90bcc`. It includes the committed Research
API and Dashboard heads, intentionally not later main Research changes.
Main `D:/quant-trading` remains read-only at
`bd13d278b25eace66a7eae287307413f930effd9`.

`strategies/sw_sector_rotation/`, `research/`, F1 protocols/seals, the official
updater and canonical/raw data/snapshots are unchanged. F1 readiness 23/60 is
user-provided context, not recalculated here. Validation performance and Final
OOS are never read. `AGENTS.md` remains the historical policy; the explicit
ETF task permits only this independent simulation product, external sidecar,
read-only UI/API and conditional integration-branch sync. It does not authorize
general research execution, global quant installation or Docker changes.

## Frozen ETF model

`ETF_QUANT_V1`: CNY10,000 configured budget, **not current account equity**.
Three independent Ridge models, alpha .01, raw X without scaling, six calendar
months anchored at each horizon's label cutoff, minimum 30 valid training dates.
Target: same-date full-universe cross-sectional excess forward return.

- H10: `d10, p5, align, vc, dd20`.
- H40/H120 ordered: `d5, d10, d20, d60, d120, p5, p10, p20, p60, p120, align, v5, v20, vc, rev5, rev10, dd20, dd60, rsi`.
- Per-date/horizon population z-score (ddof=0) **before** .25/.50/.25 fusion;
  score descending, code ascending ties; Top5.
- Capped softmax, 35% target cap, redistribution only to uncapped names.
  Infeasible/insufficient sets block; no hidden capacity change.
- Rebalance only when the **executable ETF member set changes**, not score/
  weight changes inside the same set. Initial build is allowed.

Core is self-contained under `strategies/etf_quant/`, independent of existing
Research and any vendor SDK/client. Actual close formulas, named coefficients,
training cutoffs and model hashes are available in the ETF namespace.

## Isolated CNEquity and Source C

Official software: [CNEquity](https://github.com/rootSunc/CNEquity), pinned
`1650e384a3fd1f67a70144a489acc91432f1df27`, 0.11.0.
Source/venv/lake/locks/exports/logs are repo-external. The explicitly authorized
sidecar venv is an exception, not a global quant environment. Existing
`quant-research:py3.12` image/dependencies/compose/mounts are unchanged.
See [sidecar](services/cnequity-sidecar/README.md).

Seven immutable CSV+JSON tables: calendar, exact-HFQ stock bars, reconstructed
SW membership, raw ETF bars, instruments, trading status, CSI300.
CSV rather than a new Parquet mount is an explicit implementation discrepancy
to preserve Docker. Source/version/fetched time, queries, hashes, counts,
cutoff and pin are retained. Missing amount stays null, never volume×close.
Stock `strict_adj=True` / `adj_is_exact=true` are mandatory. Non-PIT `as_of`
is not historical availability proof.

Source C: `INTERNAL_SHENWAN_INDUSTRY_SERIES_V1`, construction
`INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1`: equal-weight exact-adjusted
constituent returns, recursive base1000. Minimum five valid constituents and
80% coverage against **all** eligible members. No ffill, interpolation, fake
zero returns, synthetic OHLC, hidden repair/rebase. A broken recursive prefix
blocks that series. Original six-digit codes are preserved, alias names not
claimed as verified names or guessed official index identities. Membership
PIT is **UNPROVEN**; source available_at/published_at stay null. Historical
uses: MODEL_WARMUP / TRAINING_INPUT / ENGINEERING_VALIDATION only.
No upstream derived industry_index, THS or other-provider fallback.

**Actual admission is blocked:** strict upstream metadata smoke on 2026-09-27
failed with RemoteProtocolError. No real lake/export/model/epoch/account was
admitted. Passing synthetic offline tests does not change that fact.

## Evidence mapping and forward accounting

Default VERIFIED_MAPPING_REGISTRY_V1 is empty. VERIFIED requires official
tracking-index evidence, original external file/SHA256, provider/URL and real
retrieval/verification/availability/effective timing. No fuzzy names, invented
ETF codes or backfilled effective dates. Only A_SHARE_INDUSTRY_OR_THEME_ETF.
Twenty explicit complete sessions require valid listing/raw OHLC, genuine
nonzero volume and amount≥1 CNY. Highest true mean amount wins, code ASC ties;
duplicate ETFs try next candidates; exactly five distinct executable ETFs.
EastMoney default booleans are not proof; credible exchange halt overrides bars.
See [mapping contract](docs/etf_quant/industry_etf_mapping_contract_v1.md).

T0 close intent persists first. User-authorized **delayed T+1 EOD accounting**
uses the genuine finalized T+1 raw OPEN. market_execution_at=09:30 market time;
processed_at and fill executed_at retain actual processing time. Missed T+1
blocks, never retrospective replay. Epoch starts at actual first all-gates-PASS
processing time; **no pre-epoch NAV**.

Commission3bps/slippage5bps per side, duty0/minimum0 explicitly modeled and
configurable. Lot100 configurable; floor quantities, SELL before BUY, costs
cash-aware, leftovers kept, cash never negative. Slippage affects price and
is not charged twice. EOD needs current finalized raw close; missing close
blocks, no carry-forward fallback. Turnover=cumulative absolute slipped
notional / initial cash. First daily return and insufficient Sharpe are null.

## Manual runner — no scheduler

Copy [external config/profile templates](services/etf-quant-runner/README.md)
outside Git; fill absolute external paths and an authorized existing lake.
The transport refuses dirty/uncommitted integration code and downloads no
missing market data.

```powershell
# Host file transport only; numerical execution is in existing Docker.
python -B services/etf-quant-runner/run.py cycle --config <external-config.json>
```

Only ETF code, hash-verified snapshot/profile/evidence and last committed state/
prefix go to a unique Docker temp workspace, never the main /workspace bind.
Docker verifies export → Source C → models → ranking → mapping → legal pending
T+1 fills → valuation → state/NAV. A hidden external bridge verifies all outputs
before immutable publication and advances latest pointer **last**. Failures
preserve the successful account. No new mounts/dependencies/rebuilds, automatic
Validation, source init or market scheduler.

## Read-only API and Dashboard

ETF API: built-in Node only, loopback3312, `/api/etf-quant/v1/`,
GET/HEAD/OPTIONS; writes405. Explicit external runtime, realpath containment,
pointer/manifest/all-file hashes, public DTOs only; no paths/secrets/stack leaks.
[API instructions](services/etf-quant-api/README.md).

```powershell
$env:ETF_QUANT_RUNTIME_ROOT='<external-runtime-root>'
node services/etf-quant-api/server.mjs
# Separate shell, integration checkout:
cd dashboard
pnpm install --frozen-lockfile --ignore-scripts
pnpm dev --host 127.0.0.1
```

Eight `/etf-quant/` routes: overview, portfolio, rankings, factors, mappings,
trades, benchmarks, health. Independent capability/data contracts: Research API
disconnect does not block ETF pages. Original Research contracts/nav/seals stay.
Every page shows SIMULATION_ONLY, snapshot/cutoff/hashes/processing/epoch state.
Not-started means null metrics, empty holdings/trades and no NAV graph, never
fake CNY10,000 equity. No automatic mock fallback. Rankings Top20/show-all/Top5;
factors signed named coefficients; mapping explicit blockers.
[Dashboard instructions](dashboard/README.md).

CSI300 uses only sidecar `000300.SH`, same forward epoch normalization,
display-only, never model input. NASDAQ Composite / S&P500 **DEFERRED**.
No Yahoo/FRED/AKShare fallback or fake US curves.

## Verification and safe sync

Python tests run only in existing Docker against a copied integration source
workspace, never the main bind. [Handoff](docs/etf_quant/integration_v1_handoff.md)
records commands/counts and distinguishes engineering tests from real admission.
Never say the full frozen-data-dependent suite passed without its exact external
fixtures. Failed tests are not removed/skipped to pass.

```text
Docker: pytest tests/etf_quant -q
ETF API: node --test
Research API: pnpm test:unit && pnpm typecheck
Dashboard: pnpm typecheck && pnpm lint && pnpm exec vitest run --maxWorkers=1 && pnpm build
```

Origin already exists; earlier “no remote configured” claims were obsolete.
Only integration/etf-quant-v1 sync is authorized after required tests, clean
committed code, firewall, secret and data-leak gates. No main merge/push,
force-push, agent-branch push or credential changes.

Never commit .env, market data/caches/databases, runtime state/NAV/trades/logs,
accounts/tokens/cookies. Templates contain no secrets. Software licensing is
not data redistribution permission; no CNEquity market data is in Git.
[Third-party notices](THIRD_PARTY_NOTICES.md) and
[historical safety audit](docs/etf_quant/etf_quant_public_github_security_baseline_v1.md).
No repository-wide license grant is invented; ownership/licensing needs human
review before reuse. Research/engineering observation, not investment advice.

Directory roles: strategies=self-contained; src=existing framework;
tests=framework/integration/ETF; scripts=data/automation; research=frozen;
services=separate APIs/sidecar/transport; dashboard=observer; docs=contracts.
Docker Python3.12.11/Hikyuu2.8.2/RQAlpha6.4.0/AKShare1.18.88/NumPy2.3.5/
Pandas2.3.3/SciPy1.16.3 remain unchanged.

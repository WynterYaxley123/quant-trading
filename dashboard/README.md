# Quant Trading / ETF-Quant Dashboard

## ETF-Quant V1 current operations console

`/etf-quant/overview` and `/etf-quant/readiness` read the independent
CURRENT_ETF_QUANT_STATUS_V1 API: usability, model readiness/as_of, latest finalized
cutoff, dynamic next session, armed/start gate, Formal T0 epoch, T+1 state and
provenance. Zero epochs is normal; Cash slots show CASH / FAIL-CLOSED.
Superseded failures are HISTORICAL; new failures are not hidden.

From the checkout root run `& ./scripts/Start-EtfQuantConsole.ps1` in PowerShell and open
http://127.0.0.1:5173/etf-quant/overview. Existing dependencies/lockfile are reused.
No runner trigger, runtime edit or broker control exists. ETF routes do not open
Research artifacts; only their artifact-free Research health request is enabled.
The launcher now includes Research API 8787 as well as ETF API 3312 and Dashboard
5173. All pages show service connectivity. Missing approved Research artifacts
produce a connected empty state; network and integrity errors remain visible.
See [unified console](../docs/operations.md).

**Sector Index Research** — a read-only, modern React research dashboard for the Shenwan
sector-index rotation research programme.

> **RESEARCH DASHBOARD — NOT A TRADING TERMINAL.**
> Research phase: DEVELOPMENT ONLY · Validation: SEALED · Final OOS: SEALED ·
> executable=false · tradable=false.
> This dashboard **does not control research execution**, cannot trade, and shows no
> portfolio/backtest metrics in the Research namespace. Independent ETF pages
> below never convert Research results into account performance.

## Purpose

Give researchers and non-specialist stakeholders a clear, honest view of the development
iteration results (candidates D0–D3) for the Shenwan secondary-industry index research:

- what research phase everything is in (always shown first),
- how candidates compare on weighted RankIC (unitless) and weighted spread (return),
- per-candidate development series (E001–E100) across metrics and horizons,
- per-date sector predictions with realized labels clearly separated from predictions,
- diagnostics of the training/label pipeline,
- the immutable integrity record (protocol constants and artifact hashes).

## Architecture

```
Quant Research (Hikyuu / Docker)  →  Research Artifacts  →  Research Data API (read-only)  →  React Dashboard
                                                                        ▲
                                                   (mock adapter, dev only) ▲
```

**Research artifacts are the source of truth.** The dashboard renders what the API reports;
it never re-derives metrics, promotion status, or protocol facts, and it never reads
research files directly. See [dashboard architecture](docs/architecture.md) for the full design and
[reference review](docs/reference-review.md) for the upstream-project study behind it.

## Technology

| Layer | Choice |
|-------|--------|
| UI | React 19 + TypeScript + Vite |
| Styling | Tailwind CSS v4 + shadcn/ui-style components (Radix primitives, CVA) |
| Routing | TanStack Router (explorer state lives in URL search params) |
| Tables | TanStack Table v8 (headless, sorting + local scroll) |
| Charts | recharts (Tremor composition patterns) |
| Validation | zod (all API payloads are untrusted input) |
| Tests | Vitest + React Testing Library |

## Installation

Node.js ≥ 24 and pnpm 11.25 are required for the unified console. The dashboard
is an independent Node project and does not touch the frozen quant Docker environment.

```bash
cd dashboard
pnpm install --frozen-lockfile --ignore-scripts
```

## Development

```bash
npm run dev          # Vite dev server on http://127.0.0.1:5173
```

## Build

```bash
npm run build        # typecheck + production build into dist/
npm run preview      # production build, loopback 127.0.0.1:5173; dev server must be stopped
```

## Test

```bash
npm test             # Vitest: unit + component tests (jsdom)
npm run typecheck    # tsc --noEmit
npm run lint         # ESLint
```

## Environment variables

Copy `.env.example` to `.env.local`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `VITE_DATA_MODE` | `api` | `api` = real Research Data API; `mock` = synthetic fixtures (explicit opt-in) |
| `VITE_RESEARCH_API_BASE_URL` | `http://127.0.0.1:8787/api/v1` | Base URL of the read-only Research Data API v1 |
| `VITE_ETF_QUANT_API_BASE_URL` | `http://127.0.0.1:3312` | Independent read-only ETF observer |

### API mode (normal default)

With `VITE_DATA_MODE=api` the dashboard talks to the read-only Research Data API. If the API
is not running, pages show **“研究数据接口未连接”** with a retry button. The
dashboard **never silently falls back to mock data**.

### Mock mode (development only)

`VITE_DATA_MODE=mock` serves small **synthetic** fixtures (invented numbers — not real
research results). A **模拟数据 / MOCK DATA** banner is shown on Research pages in this mode.

## Research safety statement

- This dashboard **does not control research execution** and cannot start/stop research runs.
- All data access is read-only through the Research Data API abstraction; the UI never opens
  research artifacts, Docker, Hikyuu or AKShare directly.
- Sealed phases (Validation / Final OOS) are displayed as `SEALED` with **no** unlock,
  preview, or override affordances.
- Promotion status is displayed exactly as reported by the official results — never
  re-derived in the UI.
- Prediction values are model outputs, **not** realized returns, and carry no buy/sell
  meaning anywhere in the product.
- No portfolio / trading / account / ETF / P&L features exist in Research.
- No broker or real-order path exists in either namespace.

## Independent ETF Quant V1

Nine /etf-quant/ routes: overview, readiness, portfolio, rankings, factors,
mappings, trades, benchmarks, health. Separate EtfQuantDataPort and schemas use
/api/etf-quant/v1/ on loopback3312, never ResearchDataPort. Its capability is
independent: Research disconnect does not block an ETF route. Optional local-only
VITE_ETF_QUANT_API_BASE_URL defaults to http://127.0.0.1:3312 when empty.
No automatic mock fallback. All envelope generations must match; a mid-refresh
pointer change requests manual refresh, not mixed state.

Every page says SIMULATION_ONLY, shows cutoff/source/code/mapping/strategy
hashes and epoch/processing time. Unknowns are “—”; before a genuine forward
epoch account metrics are null and holdings/trades/NAV empty. Test fixtures never
populate production models or assets. Rankings have four tabs, Top20/show-all/
Top5; factors have frozen5/19/19 names and signed coefficients. Mapping needs
official evidence and20 real-amount sessions, no guessed ETFs. Portfolio/trades
show lot-rounded simulated fills/costs/cash impact and actual processing time
separate from T+1 market open. Historical warmup is not account performance.

CSI300 only CNEquity000300.SH, same forward epoch, display-only. NASDAQ and
S&P500 DEFERRED. No ETF reads of Research performance, sealed Validation or
Final OOS. Existing Research adapter tests remain intact. ETF fixtures are
explicitly synthetic and never published to actual runtime.

Verification: pnpm typecheck / pnpm lint / pnpm exec vitest run --maxWorkers=1 /
pnpm build. pnpm-lock.yaml was converted from existing npm lock; direct versions
and existing package-lock.json were unchanged. Quant Docker is untouched.
For current product status and admission contracts, see the [project README](../README.md)
and [strategy contract](../docs/strategy.md).

## Documentation

| File | Content |
|------|---------|
| [dashboard architecture](docs/architecture.md) | Architecture, data flow, future extensions |
| [API integration](docs/api-integration.md) | API v1 contract usage, adapters, env switching |
| [Repository health](../docs/engineering/repository-health.md) | Synthetic validation and engineering integrity evidence |
| [reference review](docs/reference-review.md) | GitHub reference-project study and decisions |
| `THIRD_PARTY_NOTICES.md` | Licenses and adapted upstream code |

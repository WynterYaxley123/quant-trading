# Shenwan Research Dashboard

**Sector Index Research** — a read-only, modern React research dashboard for the Shenwan
sector-index rotation research programme.

> **RESEARCH DASHBOARD — NOT A TRADING TERMINAL.**
> Research phase: DEVELOPMENT ONLY · Validation: SEALED · Final OOS: SEALED ·
> executable=false · tradable=false.
> This dashboard **does not control research execution**, cannot trade, and shows no
> portfolio/backtest metrics (no equity curve, Sharpe, drawdown, win rate, P&L).

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
research files directly. See `docs/architecture.md` for the full design and
`docs/reference-review.md` for the upstream-project study behind it.

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

Node.js ≥ 20 and npm are required (the dashboard is an independent Node project; it does not
touch the frozen quant Docker environment).

```bash
cd dashboard
npm install
```

## Development

```bash
npm run dev          # Vite dev server on http://localhost:5173
```

## Build

```bash
npm run build        # typecheck + production build into dist/
npm run preview      # serve the production build
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

### API mode (normal default)

With `VITE_DATA_MODE=api` the dashboard talks to the read-only Research Data API. If the API
is not running, pages show a clear **“API disconnected”** state with a retry button. The
dashboard **never silently falls back to mock data**.

### Mock mode (development only)

`VITE_DATA_MODE=mock` serves small **synthetic** fixtures (invented numbers — not real
research results). A global **MOCK DATA** banner is shown on every page in this mode.

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
- No portfolio / orders / trading / execution / account / broker / ETF / P&L features exist.

## Documentation

| File | Content |
|------|---------|
| `docs/architecture.md` | Architecture, data flow, future extensions |
| `docs/api-integration.md` | API v1 contract usage, adapters, env switching |
| `docs/reference-review.md` | GitHub reference-project study and decisions |
| `THIRD_PARTY_NOTICES.md` | Licenses and adapted upstream code |

# Architecture — Shenwan Research Dashboard V1

## 1. Data flow

```
Quant Research (Hikyuu / RQAlpha, Docker)
        │  produces
        ▼
Research Artifacts  ←—— SOURCE OF TRUTH (files under reports/, immutable for the dashboard)
        │  read by
        ▼
READ-ONLY Research Data API v1 (separately developed, HTTP on 127.0.0.1:8787)
        │  consumed by
        ▼
ResearchDataPort (src/api/contracts.ts interface)
        ├── real-api adapter (src/api/adapters/real-api.ts)   ← VITE_DATA_MODE=api  (default)
        └── mock-api adapter (src/api/adapters/mock-api.ts)   ← VITE_DATA_MODE=mock (explicit only)
        │
        ▼
React UI (features/ pages) — render-only: no metric recomputation, no artifact access
```

**Rules encoded in the structure:**

- The React app never opens `reports/`, Docker, Hikyuu, or AKShare. Everything passes through
  `ResearchDataPort`; swapping the adapter is the only integration point.
- Research artifacts are the source of truth; the dashboard renders API values verbatim
  (including `promotionStatus` — never re-derived).
- Mock mode is opt-in and visibly marked; there is no silent fallback from a dead API.

## 2. Directory layout

```
dashboard/
├─ src/
│  ├─ app/            app shell: RootLayout, Sidebar, Header, AppDataProvider, router, nav
│  ├─ routes/         TanStack Router route definitions + URL search-param parsing
│  ├─ features/       one folder per page (overview, candidates, development, sectors,
│  │                  diagnostics, integrity) — domain UI lives here
│  ├─ components/
│  │  ├─ ui/          shadcn-style primitives (button, card, badge, table, select, dialog,
│  │  │               tooltip, collapsible, skeleton, states)
│  │  ├─ charts/      ChartFrame + recharts wrappers (GroupedBarChart, TimeSeriesChart)
│  │  ├─ tables/      DataTable (TanStack Table thin wrapper)
│  │  └─ research/    domain widgets (ResearchStatusBanner, MockDataBanner, PromotionBadge,
│  │                  SealedBadge, HashText, UnitHint, CandidateCard, FilterBar, StatusCard…)
│  ├─ api/            contracts (zod + types), errors, client, adapter selection
│  │  └─ adapters/    real-api.ts / mock-api.ts
│  ├─ mocks/          synthetic fixtures (clearly labelled, never real values)
│  ├─ hooks/          useResource (async + abort + retry), useTheme
│  ├─ lib/            env, format, hash, cn
│  └─ styles/         Tailwind v4 tokens (light + dark)
├─ tests/             Vitest + Testing Library suites
├─ docs/              this file, api-integration.md, reference-review.md
└─ (configs)          package.json, vite.config.ts, vitest.config.ts, tsconfig.json,
                      eslint.config.js, .env.example, THIRD_PARTY_NOTICES.md
```

## 3. Key design decisions

| Concern | Decision | Why |
|---------|----------|-----|
| Explorer state | URL search params (`run`, `candidate`, `date`, `metric`, `horizon`) | refresh / back / forward / bookmark restore the view (product requirement) |
| Server state | small `useResource` hook (loading/error/data + AbortController + retry) | the app is read-only with ~10 endpoints; a full server-state library is over-engineering |
| Global state | none (shell context only for capabilities/status/runs) | avoid global-state over-design |
| Runtime validation | zod schemas in `contracts.ts` mirror the API | API payloads are untrusted; typed errors instead of crashes |
| Sorting | TanStack Table with `sortUndefined: 'last'` + `sortDescFirst` policy | nulls sort last in **both** directions; numeric columns sort descending first |
| Unit discipline | `format.ts` — IC/RankIC as unitless decimals, returns as percentages | prevents the classic unit mix-up; conversion documented in tooltips |
| Hash display | abbreviated 8–12 chars, click to expand | no clipboard permission APIs |
| Accessibility | semantic tables/buttons, aria-sort, chart text summaries, live regions, focus rings, never colour-alone status | charts and status must be readable without vision or colour |
| Responsive | sidebar → drawer on mobile; cards reflow; wide tables scroll locally only | no page-level horizontal overflow at 1440 / 1024 / 390 |

## 4. Page → data mapping

| Page | Endpoints |
|------|-----------|
| Overview | `/research/status`, `/capabilities`, `/runs`, `/runs/:id/candidates`, `/runs/:id/integrity` |
| Candidate Comparison | `/runs/:id/candidates`, `/runs/:id/candidates/:cid/metrics` |
| Development Explorer | `/runs/:id/candidates/:cid/daily-metrics` |
| Sector Explorer | `/runs/:id/candidates/:cid/daily-metrics` (date options), `/predictions?date=` |
| Diagnostics | `/runs/:id/candidates/:cid/diagnostics` |
| Research Integrity | `/runs/:id`, `/runs/:id/integrity` |

## 5. Future extensions (notes only — not implemented)

The following are intentionally **absent** from the UI today (no fake pages, no disabled
look-alikes). When the corresponding research phase unseals and the API grows, each becomes a
new `features/<name>/` module plus routes:

- **Validation pages** — unlocked only when `validationAvailable` capability is true.
- **Final OOS pages** — same, gated on `finalOosAvailable`.
- **Portfolio pages / Execution pages** — only after an official portfolio contract exists;
  until then no portfolio/execution semantics are shown anywhere.
- **API v2 / new endpoints** — add schemas to `contracts.ts`, methods to `ResearchDataPort`,
  implementations in both adapters, and UI in a feature module. No core changes needed.
- **Large-data exploration** — re-evaluate Perspective (or TanStack virtualizer as the lighter
  first step) if a single table exceeds ~50k rows, or if cross-chart cross-filtering or
  streaming updates become requirements (current tables are ≤ ~124 rows by design).

## 6. What this dashboard is NOT

- Not a trading terminal: no orders, execution, broker, account, ETF, or P&L concepts.
- Not a BI platform: no SQL, no databases, no chart builder.
- Not an authority on research results: artifacts + API are.

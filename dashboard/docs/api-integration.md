# API Integration — Research Data API v1

## 1. Switching between mock and real API

Everything is controlled by environment variables (never hard-coded in components):

```bash
# .env.local
VITE_DATA_MODE=api                                  # default; use "mock" only for development
VITE_RESEARCH_API_BASE_URL=http://127.0.0.1:8787/api/v1
```

| `VITE_DATA_MODE` | Behaviour |
|------------------|-----------|
| `api` (default) | `real-api.ts` adapter calls the Research Data API. If unreachable → **“API disconnected”** state with retry. **No silent fallback to mock.** |
| `mock` (explicit) | `mock-api.ts` adapter serves synthetic fixtures; a global **MOCK DATA** banner marks every page. |

When Codex's API branch merges, **no component changes are required**: set the two env vars
above and the dashboard connects. The real-api adapter is fully implemented and tested today
against contract-shaped HTTP fixtures (`tests/real-api.test.ts`).

## 2. Envelope

Success:

```json
{ "schemaVersion": "1.0.0", "data": ... }
```

Error:

```json
{ "schemaVersion": "1.0.0", "error": { "code": "RUN_NOT_FOUND", "message": "..." } }
```

The client (`src/api/client.ts`) unwraps the envelope, validates `data` with zod schemas
declared in `src/api/contracts.ts`, and throws typed `ResearchApiError`s. The UI never shows
stack traces — only `userMessage` (human-readable) plus the error code.

## 3. Endpoints used

| Method | Path | Client method | Notes |
|--------|------|---------------|-------|
| GET | `/health` | `getHealth()` | `{ status, readOnly, sourceOfTruth }` |
| GET | `/capabilities` | `getCapabilities()` | UI respects feature flags (nav visibility, page gating) |
| GET | `/research/status` | `getResearchStatus()` | phase / validation / finalOos / executable / tradable … |
| GET | `/runs` | `getRuns()` | run list |
| GET | `/runs/:runId` | `getRun()` | run detail incl. hashes |
| GET | `/runs/:runId/candidates` | `getCandidates()` | D0–D3 summaries incl. `promotionStatus` |
| GET | `/runs/:runId/candidates/:cid/metrics` | `getMetrics()` | weighted metrics + 3 horizons of `MetricStats` |
| GET | `/runs/:runId/candidates/:cid/daily-metrics` | `getDailyMetrics()` | `?horizon=10\|40\|120` optional |
| GET | `/runs/:runId/candidates/:cid/predictions` | `getPredictions()` | **required** `?date=YYYY-MM-DD`; optional `top5`, `limit`, `offset` |
| GET | `/runs/:runId/candidates/:cid/diagnostics` | `getDiagnostics()` | date counters + per-horizon blocks |
| GET | `/runs/:runId/integrity` | `getIntegrity()` | protocol constants + artifact hashes |

### Request behaviour

- Timeout: 10 s per request (AbortController; caller aborts are honoured).
- Query encoding: booleans/numbers stringified; null/undefined omitted.
- Path segments URL-encoded (`encodeURIComponent`).

## 4. Error codes

Server-reported (frozen contract): `BAD_QUERY`, `RUN_NOT_FOUND`, `CANDIDATE_NOT_FOUND`,
`SEALED_PHASE`, `ARTIFACT_SCHEMA_ERROR`, `ARTIFACT_IO_ERROR`, `PATH_TRAVERSAL_BLOCKED`,
`METHOD_NOT_ALLOWED`.

Client-side: `NETWORK_UNREACHABLE` (→ “API disconnected”), `TIMEOUT`, `INVALID_RESPONSE`
(envelope/shape mismatch), `UNKNOWN`.

## 5. Contract notes / interpretations

These points follow the frozen v1 contract; where the contract text groups fields loosely,
this dashboard's `contracts.ts` encodes the interpretation below so both sides can align:

1. **`Diagnostics` shape** — `attemptedDates` / `successfulDates` / `skippedDates` are
   top-level; the training-observation, valid-date/sector counts **and** the exclusion /
   failure / zero-std / scaler / demean-residual fields are grouped **per horizon**
   (`horizons: [{ horizon, ... }]`), because labels and scalers are horizon-specific. All
   numerics are `number | null` ("nullable where unavailable").
2. **Horizon literals** — only `10 | 40 | 120` are accepted (zod literal union).
3. **Return units** — `weightedSpread`, `top5ForwardReturn`, `universeForwardReturn`,
   `top5MinusUniverse`, `pred*`, `realizedForwardReturn*` are decimal returns; the UI shows
   percentages (0.0181 → 1.81%) and documents the conversion in tooltips.
4. **Ordinals / dates** — ordinals match `E###`, dates are ISO `YYYY-MM-DD`.
5. **Date selection in Sector Explorer** — available dates come from the candidate's
   `daily-metrics` signal dates; the dashboard never invents dates.

## 6. What the dashboard guarantees to the API side

- Only GET requests; no mutations are ever attempted (`readOnly` respected).
- `capabilities` flags are respected: `portfolio` / `execution` / `etf` are false today and
  have no UI; `validationAvailable` / `finalOosAvailable` gate nothing yet because sealed
  phases display `SEALED` with no access affordances at all.
- `promotionStatus` is rendered verbatim (never recomputed client-side).
- No direct artifact/Docker/Hikyuu/AKShare access from the UI layer.

## 7. Testing the integration

- `tests/real-api.test.ts` — mocked `fetch` covering every endpoint's parsing, envelope
  errors, network failure → “API disconnected”, invalid shapes → `INVALID_RESPONSE`, and
  query encoding. This is the "real API readiness" suite.
- `tests/mock-adapter.test.ts` — validates mock fixtures against the same zod schemas
  (contract regression + synthetic-data guard).

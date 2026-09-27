# ETF Quant read-only Data API V1

Independent of `services/research-api`; no Research artifact loader, seal,
performance or data-provider path is reused. Requires Node >=22, with **zero
external dependencies**. Bind is always `127.0.0.1` (default port 3312).

Set `ETF_QUANT_RUNTIME_ROOT` to a repo-external runtime. The environment template
contains variable names and empty values only. Do not put credentials or absolute
runtime paths into tracked configuration. Run `node server.mjs` manually.

The fixed prefix is `/api/etf-quant/v1/`. All responses use:

```json
{"schemaVersion":"1.0.0","data":null,"error":null,"meta":{"runId":null,"manifestSha256":null,"etfQuant":true}}
```

`data` types: status/strategy/summary/mappings/benchmark/health are objects;
models/rankings/holdings/nav/trades are arrays. Executable DTO validation lives in
`server.mjs`; the independently validated TypeScript schema is
`dashboard/src/etf-quant/contracts.ts`. Financial decimals remain strings;
nullable results remain null, never fabricated zeros or current capital.

Endpoints (GET / HEAD / OPTIONS only):

- `status`, `strategy`, `models`, `health`
- `rankings/10d`, `rankings/40d`, `rankings/120d`, `rankings/fusion`
- `portfolio/summary`, `portfolio/holdings`, `portfolio/nav`, `trades`, `mappings`
- `benchmark/csi300` (display only; US benchmarks DEFERRED)

POST/PUT/PATCH/DELETE return 405. No query/file parameter or order endpoint exists.
Origin allowlist is exactly local Vite 5173 and preview 4173 (localhost/127.0.0.1).
No wildcard CORS, credentials, broker service, tick streaming or websocket.
The raw URL is checked before parsing; encoded paths, traversal, query strings,
non-local Host and external Origin fail closed.

The observer resolves symlinks and rejects repo-contained roots, verifies the
latest pointer, manifest and **all** committed files before returning public
`view.json`. Private state/prefix are hashed, never exposed. Missing committed
files are corruption, not fallback. Errors expose only a fixed blocker code,
never filesystem paths, environment, credentials or stack traces. Valid failure
manifests degrade the health of the last-success observation without replacing
its portfolio. Snapshots older than 48 hours show STALE; this is an observation
freshness warning, not an inferred market-calendar judgment.

No runtime or no successful generation means NOT_STARTED with empty arrays and
null current account metrics. The frozen budget is configuration, not a claim
that a simulation account exists. `strategy.json` is a tested mirror of the pure
Python public configuration for this no-runtime case.

Run `node --test tests/*.test.mjs`. All fixtures are synthetic and temporary;
they are never published into the user's real runtime. Clients must verify that
all endpoint envelopes refer to the same generation; the dashboard rejects a
mid-refresh pointer change and offers manual refresh, not mixed generations.

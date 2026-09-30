# Research Dashboard Data API v1 contract

Version `1.0.0`; prefix `/api/v1`. Formal JSON/CSV research artifacts are the only data source. This service is an adapter, not a research, backtest, portfolio, execution or trading service. It does not import Python or run Hikyuu/RQAlpha. Its source files and project dependencies live only in `services/research-api/`.

All successful responses use `{ "schemaVersion": "1.0.0", "data": ... }`. Errors use `{ "schemaVersion": "1.0.0", "error": { "code": "...", "message": "..." } }`. No request-time timestamp or random field is emitted. See the [OpenAPI contract](../openapi/research-dashboard-api-v1.openapi.yaml) for exact fields.

The catalog admits only `iteration1_*` runs with validated `DEVELOPMENT` metadata and the exact D0–D3 family. It sorts newest ID first. Legacy baseline outputs are deliberately excluded rather than coerced. Candidate metric means, other aggregate statistics, weighted comparison values, promotion status, predictions, realized labels and Top5 are copied from official artifacts. The only aggregation performed in this service is descriptive min/median/max or counts over already-recorded training diagnostics. No IC, RankIC, return, spread, promotion, model or candidate is recalculated.

IC, RankIC and weighted RankIC are unitless. Top5 and universe forward labels, their spread and weighted spread are decimal returns; `0.0123` means 1.23%. They describe sector-index prediction research, **not portfolio return, strategy PnL, tradable performance or an equity curve**. Null means missing/unavailable, not zero.

`Validation` and `Final OOS` remain `SEALED`. The API's route middleware returns `SEALED_PHASE` (403) for attempts to address them. Storage enumerates only one allowed research collection and only formal Iteration-1 Development run names. It never scans, indexes, logs or returns sealed-phase performance. Any mutation method under `/api/v1/*` returns 405. HEAD and OPTIONS are the only non-GET methods allowed, with OPTIONS used for CORS.

The configured `RESEARCH_REPORT_ROOT` is the sole filesystem authority. The Node HTTP entry point rejects traversal in the raw incoming URL before Node/Hono can normalize literal dot segments. Each path segment is checked against traversal/encoded separators and each resolved file is checked against the real root, including symlink escape attempts. Candidate IDs and run IDs have closed formats. Read files are checked against `metadata.content_sha256` before parsing. Schema failures log run/candidate/file and field context server-side, while clients receive stable codes without absolute filesystem paths. No cache is used in v1: each request reads current bytes and verifies the hash, avoiding stale content identity.

Default binding is `127.0.0.1:8787`; default CORS origins are exactly `http://127.0.0.1:5173` and `http://localhost:5173`. `DASHBOARD_ORIGINS` may override them with exact http(s) origins, never `*`.

Artifact schema and API schema are separate. Future artifact changes may be handled inside adapters while keeping `/api/v1` stable. Adding an endpoint or changing semantics requires a reviewed OpenAPI change and tests. New research phases, candidates or execution capabilities require their own explicit authorization and must not be inferred from files present on disk.

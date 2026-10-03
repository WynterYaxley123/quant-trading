# Research Dashboard Data API v1 contract

Normal console startup includes this service. Optional absent roots/collections
return an empty catalog; capabilities/status explicitly identify NOT_CONFIGURED.
This is an observation policy state, not fabricated Development metadata or
performance. Existing corrupt/unauthorized artifacts retain their errors.
Public listen addresses are rejected; the unified launcher pins local CORS origins.
Unsupported/duplicate query parameters are rejected, including force/bypass flags.

Version `1.0.0`; prefix `/api/v1`. Formal JSON/CSV research artifacts are the only data source. This service is an adapter, not a research, backtest, portfolio, execution or trading service. It does not import Python or run Hikyuu/RQAlpha. Its source files and project dependencies live only in `services/research-api/`.

All successful responses use `{ "schemaVersion": "1.0.0", "data": ... }`. Errors use `{ "schemaVersion": "1.0.0", "error": { "code": "...", "message": "..." } }`. No request-time timestamp or random field is emitted. See the [OpenAPI contract](../openapi/research-dashboard-api-v1.openapi.yaml) for exact fields.

The catalog admits only registry-approved `iteration1_*` runs with pinned metadata SHA256, validated `DEVELOPMENT` metadata and the exact D0–D3 family. It sorts explicit recorded metadata UTC creation time descending, then stable run ID descending; filesystem mtime has no role. Legacy outputs are excluded. Candidate metrics, weighted values, promotion, predictions, labels and Top5 are copied from artifacts. Only descriptive min/median/max or counts over recorded diagnostics are aggregated. No IC, RankIC, return, spread, promotion, model or candidate is recalculated.

IC, RankIC and weighted RankIC are unitless. Top5 and universe forward labels, their spread and weighted spread are decimal returns; `0.0123` means 1.23%. They describe sector-index prediction research, **not portfolio return, strategy PnL, tradable performance or an equity curve**. Null means missing/unavailable, not zero.

`Validation` and `Final OOS` remain `SEALED`. The API's route middleware returns `SEALED_PHASE` (403) for attempts to address them. Storage enumerates only one allowed research collection and only formal Iteration-1 Development run names. It never scans, indexes, logs or returns sealed-phase performance. Any mutation method under `/api/v1/*` returns 405. HEAD and OPTIONS are the only non-GET methods allowed, with OPTIONS used for CORS.

The resolved root is the sole filesystem authority; [workspace configuration](../../../docs/research-status.md) defines precedence and approval. Registry checks precede metadata access. The Node entry guards traversal before URL normalization; storage checks safe segments and realpath containment, including links. Metadata SHA anchors its content manifest. Every workspace observation hashes all declared content files; only parsing of previously verified immutable bytes may be memoized. Content endpoints recheck their file hashes. Clients receive stable codes without host paths. Malformed local configuration, missing explicit roots, unknown approval, wrong phase, schema/hash errors and escapes fail closed as DEGRADED. Healthy empty/invalid status is distinct from an unreachable service. Host and Origin are actively restricted, including preflight.

Default binding is `127.0.0.1:8787`; default CORS origins are exactly `http://127.0.0.1:5173` and `http://localhost:5173`. `DASHBOARD_ORIGINS` may override them with exact http(s) origins, never `*`.

Artifact schema and API schema are separate. Future artifact changes may be handled inside adapters while keeping `/api/v1` stable. Adding an endpoint or changing semantics requires a reviewed OpenAPI change and tests. New research phases, candidates or execution capabilities require their own explicit authorization and must not be inferred from files present on disk.

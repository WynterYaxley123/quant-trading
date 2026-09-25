# Research Dashboard v1 — integration / contract audit

This integration is read-only and Development-only. The formal artifact root used for
local verification is `D:\quant-trading\reports\research`; neither the API nor the
dashboard writes there. The current formal run is
`shenwan_sector_index/iteration1_20260924_163607_787266_utc` (D0–D3).
The earlier formal repeat `iteration1_20260924_163106_040404_utc` is also cataloged;
the older baseline control is not a formal Iteration-1 run.

## Git and artifact provenance

- Integration branch: `integration/research-dashboard-v1`, created at main
  `a1f7ff967aa882f90283b54f8f6140f2832d50bc` in its own worktree.
- Merged source commits without squash or conflict: API `ae92a2a1e49bc322bf4961f5115e24b0ba24ec46`
  and Dashboard `a4b549ca2114060d156ce7ee60f436d9e1aad35a`.
- The feature branches share research base `9c16c787eb3d638ee8683f2644ad01c0cfa21e39`;
  that base's research history is preserved, not changed by integration.
- Formal metadata records `git_head=9c16c787eb3d638ee8683f2644ad01c0cfa21e39`,
  protocol hash `f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125`,
  sector snapshot ID `872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500`.
- `metadata.json` contains phase, seals, research flags, identity and content SHA256.
  `candidate_summary.json` contains D0–D3 comparison and aggregate records.
  Each candidate directory contains aggregate JSON, per-date metrics CSV,
  predictions CSV, training diagnostics CSV, data-quality diagnostics JSON and
  transformation diagnostics JSON. All were consumed only by read-only tests/API.

## Frozen contract ↔ OpenAPI ↔ implementation ↔ Dashboard

| Endpoint / field | Frozen expectation | OpenAPI + API implementation | Dashboard before → after | Resolution |
| --- | --- | --- | --- | --- |
| Envelope | `schemaVersion=1.0.0` | Exact | Error version accepted any string → exact literal | Contract validation tightened |
| `/research/status.classification` | `FIXED_CLASSIFICATION_RESEARCH` | Missing → additive alias of `classificationAdmission` | Required field already expected | Added without removing old field |
| `/runs/:id.syntheticPortfolioConfigHash` | Null if not configured | Null | String → nullable | Null preserved; no invented portfolio |
| `/candidates` comparison | Exact artifact `Weighted_RankIC`, `Weighted_Spread`, promotion | Exact normalized values | No recomputation | D0–D3 checked against official summary |
| `/daily-metrics` | Date × horizon actual metrics | Exact pivot from CSV | Zod 10/40/120; return formatting only | Three dates × two candidates × two horizons checked against CSV |
| `/predictions` | Date × sector; pred/fusion/Top5 from artifact | Exact pivot from CSV | Predictions wrongly displayed as returns → decimal scores | Three dates × two candidates × ten rows × three horizons checked against CSV; 124 rows/date |
| `/diagnostics` | Only recorded counters/ranges | Per-horizon `{min,median,max}`; transforms top-level | Expected scalars/per-horizon transforms → actual shape | UI shows ranges; absent values remain `—` |
| `/integrity` | Git/protocol/snapshot/config hashes; flags | Missing git/protocol/classification/tradable/synthetic hash → additive official metadata mapping | Schemas/UI aligned | Full hash accessible; absent synthetic hash remains null |
| Errors/methods | Stable codes, read-only | 405 mutation, 403 sealed/path | Chinese safe text + unchanged error code | No API machine-field localization |

OpenAPI and TypeScript names remain English machine fields. UI translates only user-facing
labels. `pred*` and `fusedScore` are model scores; realized forward returns alone are
formatted as percentages. No score, rank, Top5 or promotion is recomputed in the UI.

## Local integration verification

Start the API with `RESEARCH_REPORT_ROOT` pointing at the existing formal artifact root;
start Vite with `VITE_DATA_MODE=api` and
`VITE_RESEARCH_API_BASE_URL=http://127.0.0.1:8787/api/v1`.
The API allows only `http://127.0.0.1:5173` and `http://localhost:5173` as browser origins.
Both origins returned the respective CORS header; an unrelated origin returned none.
Live HTTP mutation returned 405 `METHOD_NOT_ALLOWED`, sealed query returned 403
`SEALED_PHASE`, and literal traversal returned 403 `PATH_TRAVERSAL_BLOCKED`.
After stopping the local API, the Dashboard displayed `研究数据接口未连接` and no mock
content; restarting and using `重试连接` restored the real integrity page.

Browser checks covered all six pages and light/dark layout at 390 px, plus overview
layout at 1024 px and 1440 px. The mobile sector table scrolls horizontally so
prediction and realized-return columns remain distinct. No portfolio/trading result
is displayed. Validation and Final OOS remain sealed and were not opened.
The Development URL parser was corrected to accept a numeric `horizon=120` after a hard
reload; the bookmarked 120-day view now restores with its 100-date table. Browser
checks also covered six sector views (three Development dates × D0/D3), all with 124
rows, and the detail drawer's recorded label-end dates.

Run tests from the two Node directories. The API package has no lint script; it uses
TypeScript typecheck, tests and build. The Dashboard has typecheck, lint, tests and build.
The optional live Dashboard adapter suite is enabled only when both
`RESEARCH_DASHBOARD_REAL_API_BASE_URL` and `RESEARCH_REPORT_ROOT` are provided.

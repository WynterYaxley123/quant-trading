# Research Dashboard Data API v1

Read-only Hono/TypeScript adapter for formal Shenwan sector-index Development artifacts. It is independent of the frozen `quant-research` Docker/Python environment. It does not run research or expose Validation/OOS, portfolios, ETFs or execution.

## Requirements and setup

Use an existing Node.js 24+ and pnpm installation; do not install a global package manager. From `services/research-api/`:

```powershell
pnpm install --frozen-lockfile
$env:RESEARCH_REPORT_ROOT = 'D:\quant-trading\reports\research'
pnpm dev
```

The default report root resolves to `<this worktree>/reports/research`. In the isolated API worktree that directory is normally absent because formal reports are Git-ignored; set `RESEARCH_REPORT_ROOT` to the original project's formal report root for local development. The API never writes to it. Default URL: `http://127.0.0.1:8787/api/v1`.

## Commands

```powershell
pnpm typecheck
pnpm test:unit
pnpm test:integration   # requires RESEARCH_REPORT_ROOT with formal Iteration-1 artifacts
pnpm test
pnpm build
pnpm start              # starts the built dist/index.js
```

No lint script is configured; `pnpm typecheck`, tests and the production build are required gates. Tests use isolated temporary fixtures and, when `RESEARCH_REPORT_ROOT` is set, real read-only artifacts.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `RESEARCH_REPORT_ROOT` | `<repo>/reports/research` | Only filesystem root the API may read. |
| `HOST` | `127.0.0.1` | Listen address; not public by default. |
| `PORT` | `8787` | Listen port. |
| `DASHBOARD_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Exact allowed browser origins, comma-separated; wildcard rejected. |

See [artifact audit](docs/artifact-audit.md), [contract and security rules](docs/api-contract.md), [reference review](docs/reference-review.md) and [OpenAPI 3.1](openapi/research-dashboard-api-v1.openapi.yaml).

# Research Dashboard Data API v1

Read-only Hono/TypeScript adapter for formal Shenwan sector-index Development artifacts. It is independent of the frozen `quant-research` Docker/Python environment. It does not run research or expose Validation/OOS, portfolios, ETFs or execution.

## Requirements and setup

Normal operation starts this API with ETF Quant API and Dashboard using
`scripts/Start-EtfQuantConsole.ps1` from the repository root. See the
[unified console guide](../../docs/unified_console.md). No separate terminal is
needed. The launcher uses the existing `node --import tsx src/index.ts` entry
point without installing or upgrading dependencies. Manual commands below are
for component development.

Use an existing Node.js 24+ and pnpm installation; do not install a global package manager. From `services/research-api/`:

```powershell
pnpm install --frozen-lockfile
$env:RESEARCH_REPORT_ROOT = 'D:\quant-trading\reports\research'
pnpm dev
```

The default report root is `<this worktree>/reports/research`. An absent root,
collection or approved run is a valid empty deployment: health, capabilities,
status and runs return 200; capabilities/status say `artifactState=NOT_CONFIGURED`
and runs contains an empty items array. The API never creates or writes the root.
Configured corrupt artifacts still return integrity/IO errors. Select an existing
approved Development root with `RESEARCH_REPORT_ROOT` or `-ResearchReportRoot`.
Default URL: `http://127.0.0.1:8787/api/v1`.

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
| `HOST` | `127.0.0.1` | Loopback only: 127.0.0.1, localhost or ::1; public addresses rejected. |
| `PORT` | `8787` | Listen port. |
| `DASHBOARD_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Exact allowed browser origins, comma-separated; wildcard rejected. |

See [artifact audit](docs/artifact-audit.md), [contract and security rules](docs/api-contract.md), [reference review](docs/reference-review.md) and [OpenAPI 3.1](openapi/research-dashboard-api-v1.openapi.yaml).

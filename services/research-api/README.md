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

The normal console supplies the optional machine-local approved workspace.
An explicit registry anchors metadata SHA256 and its complete content manifest.
See [workspace configuration](../../docs/research_workspace.md). Without any local
configuration, the optional default is `<this worktree>/reports/research`; absent
root/catalog is `NOT_CONFIGURED`. Invalid explicit configuration is `DEGRADED`,
never an empty fallback. Health remains artifact-free; status/capabilities explain
admission while run/content routes reject invalid or unapproved data. No artifact
root is created or written.
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
| `RESEARCH_WORKSPACE_CONFIG` | Unset | Machine-local JSON pointer; root override wins. |
| `RESEARCH_ARTIFACT_ID` | Local config ID or sole registry workspace | Explicit approval identity; unknown/ambiguous IDs fail closed. |
| `HOST` | `127.0.0.1` | Loopback only: 127.0.0.1, localhost or ::1; public addresses rejected. |
| `PORT` | `8787` | Listen port. |
| `DASHBOARD_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Exact allowed browser origins, comma-separated; wildcard rejected. |

See [artifact audit](docs/artifact-audit.md), [contract and security rules](docs/api-contract.md), [reference review](docs/reference-review.md) and [OpenAPI 3.1](openapi/research-dashboard-api-v1.openapi.yaml).

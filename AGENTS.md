# Repository engineering rules

Read this file before repository work. ETF-Quant V1 has completed engineering preparation;
its first formal Shadow epoch has not been created.

- Preserve frozen factors, models, ranking, fusion, sizing, PIT and T/T+1 contracts.
  Change a strategy behavior only when existing evidence proves a contract bug.
- Do not create strategies, run market-data backtests, invoke formal one-shot,
  fabricate historical epochs, read sealed Validation/Final-OOS performance,
  enable brokers, real orders, leverage or shorting. Synthetic tests/demo are permitted.
- Execute quantitative code in Docker. Use the independent developer image for
  portable checks; never alter the deployed image or install quant dependencies
  into host Python. No host virtual environment or unrequested WSL tool switch.
- Keep CNEquity external and pinned. Never edit upstream or use private credentials
  for engineering tests. Mount permitted maintainer evidence read-only.
- Isolate work. Other worktrees/deployed services are read-only. Never reset, stash
  or clean another actor's changes; never force-push or rewrite history.
  GitHub delivery is permitted when requested by the user.
- Never commit secrets, .env, market/runtime data, Shadow payloads, sealed results,
  databases, dependency trees or build outputs. MIT source licensing grants no data rights.
- Keep strategy packages self-contained. Add shared abstractions for an actual need.
  Coordinate before concurrent writes to the same files; no standing agent ownership.
- Target zero Mypy diagnostics in touched active production modules. Wider typing
  enforcement is staged. Do not enlarge baselines, add broad ignores or exclude production.
- Ruff lint/format cover active Python. Historical certificates/evidence stay immutable;
  source changes need a new integrity manifest and explicit transition/regression evidence.
- Archive historical records under docs/archive with preserved hashes and path mapping.
  Keep active docs concise. Absent quantitative metrics are null, never invented numbers.

See [development](docs/development.md), [testing](docs/testing.md),
[strategy](docs/strategy.md) and [reproducibility](docs/reproducibility.md).

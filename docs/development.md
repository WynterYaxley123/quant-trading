> Current role: INDUSTRY_FORECAST_RESEARCH (SWL2-Ridge-V1 / SWL2-Ridge-V2). ETF productization is RETIRED. Historical ETF formulas, commands and observations below are audit context; writer entry points fail closed. See [current industry contracts](industry-forecast.md).

# Development

Tested toolchain: Python 3.12.11, Node 24.19.0, pnpm 11.25.0. The developer image pins
bases and requirements in `.devcontainer/Dockerfile` / `requirements-dev.lock.txt`.
Developer Polars matches the existing external source runtime for synthetic tests.

```sh
docker build -f .devcontainer/Dockerfile -t quant-trading-dev:local .
docker run --rm -it -v "${PWD}:/workspace" quant-trading-dev:local bash
```

Inside the independent container:

```sh
python -m examples.minimal_demo
python -m pytest -q -m "not external_runtime"
python -m pytest -q tests/performance
python -m benchmarks.core
ruff check .
ruff format --check .
python scripts/engineering/typecheck.py
pnpm --dir dashboard install --frozen-lockfile
pnpm --dir dashboard test --maxWorkers=1
pnpm --dir dashboard typecheck
pnpm --dir dashboard lint
pnpm --dir dashboard build
pnpm --dir services/research-api install --frozen-lockfile
pnpm --dir services/research-api test
pnpm --dir services/research-api typecheck
pnpm --dir services/research-api build
node --test services/etf-quant-api/tests/*.test.mjs services/etf-quant-runner/security-audit.test.mjs
pre-commit run --all-files
node services/etf-quant-runner/security-audit.mjs
```

Use a regular clone/devcontainer with accessible Git metadata for Git-aware checks.
A Windows managed worktree .git pointer names a host path: an independent Linux
container needs the Git common directory mounted read-only and GIT_DIR/GIT_WORK_TREE
pointing to its corresponding worktree metadata/checkout. Portable checks require
no runtime mounts or private data. [Testing](testing.md) describes maintainer acceptance.

For forward factual refresh, build the separate operational developer image:
`docker build -f .devcontainer/Dockerfile.forward -t quant-trading-forward:local .`.
It adds pinned public-SDK dependencies from `requirements-forward.lock.txt` and
uses externally mounted read-only CNEquity source. No host quantitative environment,
upstream edit or deployed-image modification is needed. Configure the shared
[runner](../services/etf-quant-runner/README.md) with independent external roots.

Copy `.env.example` to a private `.env` and set a nonempty `JUPYTER_TOKEN`
before `docker compose config --quiet`. The empty template deliberately fails
closed. Configuration validation does not start Jupyter.

On Docker Desktop, keeping installed Node dependencies inside the container avoids
slow Windows bind-mount I/O. Run the same lockfile and commands against a complete
source copy; dashboard fixtures also read `services/etf-quant-api/strategy.json`.

## Current industry gates

```sh
python -m examples.industry_forecast_demo
python -m pytest -q tests/test_swl2_forecast.py
node --test services/industry-forecast-api/tests/*.test.mjs
pnpm --dir services/industry-forecast-api install --frozen-lockfile
pnpm --dir services/industry-forecast-api typecheck
pnpm --dir services/industry-forecast-api build
```

Legacy writer tests use an explicit pytest temporary replay namespace. Production
entry points never inherit that gate. No real runtime is mounted for these checks.

## Read-only and dependency verification

Only current ETF state writers are retired; historical read-only inspection and explicitly isolated synthetic regression remain. The forward runner is services/industry-forecast-runner/run_forecast.py. Run pnpm audit --json in dashboard, services/research-api and services/industry-forecast-api, compare against the base lockfiles, and introduce no new advisories. Existing advisories are reported separately.

## SWL1 development directory boundary

On this maintainer workstation the primary project is D:/quant-trading; isolated checkouts belong under D:/QuantForge/worktrees, private task research under D:/QuantForge/research, and temporary logs/clones under a dedicated D:/QuantForge/temp subdirectory. Never scatter files at the drive root. SWL1 V1 research is closed after failed Validation; ordinary commands must not reopen it. The public demo uses only synthetic Level-1 data.

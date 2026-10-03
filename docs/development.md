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

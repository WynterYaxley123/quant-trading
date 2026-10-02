# Contributing

Use an isolated checkout. ETF-Quant V1 semantics, data provenance, scientific
dependencies and the certified Shadow implementation are frozen. Do not access
sealed Validation/Final OOS performance, connect a broker, download market data,
or run an operational Shadow cycle as a development test.

## Portable environment

The default `.devcontainer` provides Python 3.12.11, Node 24.19.0, pnpm 11.25.0
and pinned developer dependencies. It is independent of `quant-research` and
requires no runtime data. Windows contributors can also use Docker directly:

```sh
docker build -t quant-trading-dev -f .devcontainer/Dockerfile .
docker run --rm --network none --mount "type=bind,source=<absolute-checkout>,target=/workspace" quant-trading-dev python -m pytest -m "not external_runtime"
docker run --rm --network none --mount "type=bind,source=<absolute-checkout>,target=/workspace" quant-trading-dev python -m examples.minimal_demo
```

Replace `<absolute-checkout>` with your checkout path. Building only the
developer image is permitted; never rebuild or install tooling in the frozen
production image. No Windows global scientific installation or host `.venv` is
needed. On Linux/CI, a separate Python 3.12 environment may install
`python -m pip install -r requirements-dev.lock.txt`.

## Quality gates

Inside the developer container, from repository root:

```sh
ruff check .
ruff format --check .
python scripts/engineering/typecheck.py
python -m pytest -m "not external_runtime"
python -m examples.minimal_demo
pre-commit install
pre-commit run --all-files
```

Use a regular clone in the devcontainer for Git hooks. Linked Windows worktrees
contain host Git paths; open a normal clone if its Git metadata cannot be resolved
inside the container. Hooks may require network access on first installation.
Tests and the demo run with networking disabled and no external runtime mount.

Mypy checks all configured source directories. The reviewed legacy baseline is
explicit in `config/engineering/mypy-baseline.json`; new or stale diagnostics
fail. Strict checks apply to new tooling/demo, schema/calendar and notification
boundaries. The staged gate passing does **not** mean that legacy typing debt is
zero. Never update the baseline merely to make a regression green.

Checksum-bound files are listed individually in `pyproject.toml` and the text
hook configuration. Their bytes must continue to match
`reports/etf_quant/autonomous_code_integrity_v1.json`. They remain Mypy-checked;
Ruff exempts only their existing named diagnostics and defers their formatting.
Changes to these files require a separately reviewed implementation certificate.

## JavaScript checks

Node 24.19.0 / pnpm 11.25.0 are the tested versions. Requirements have not been
lowered without a Node 22 compatibility test. Lockfiles remain authoritative.

```sh
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
node --test scripts/tests/launcher-unit.test.mjs
node services/etf-quant-runner/security-audit.mjs
```

The Windows syntax test parses the launcher without starting processes. The
original console integration test still requires its explicit local configuration.
Research API real-artifact integration tests remain opt-in; synthetic tests run
in public CI.

## Maintainer integration tier

`external_runtime` identifies verified-data, pinned-framework and private-evidence
tests. Framework/integration directories are not imported during portable-only
collection; they remain available in full maintainer runs. Assertions have not
been relaxed. Run these tests only in the existing frozen environment, with
read-only source/runtime mounts and `--network none`. The exact ETF command is in
the [README testing section](README.md#testing).

Never upload datasets, runtime databases, Shadow state, logs, account payloads,
credentials or real `.env` files. The demo generates artificial feature vectors
and labels; it is not a backtest or evidence admission pipeline.

## Review and documentation

Preserve historical certificates and hashes. Use
[the active documentation index](docs/README.md) for current guidance and
[the logical archive](docs/archive/README.md) for historical paths. Keep CLI output
on stdout where it is the interface; use `logging.getLogger(__name__)` for new
internal status/debug messages, without configuring logging at import time.

Use logical commits and normal PR merges; never force-push or rewrite history.
Describe validation and remaining staged debt accurately. Repository-owned code
and documentation use [MIT](LICENSE); retain all third-party notices. Software
licensing does not grant market-data redistribution rights.

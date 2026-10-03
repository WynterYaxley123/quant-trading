# Contributing

Start with [development](docs/development.md) and [testing](docs/testing.md). Use the
independent developer Docker image, Python 3.12.11, Node 24.19.0 and pnpm 11.25.0.
Do not install quant dependencies into host Python or alter the deployed frozen runtime.

Use focused branches and logical commits. Run portable tests/demo, Ruff lint/format,
the staged Mypy gate, pre-commit, frontend checks and both API suites. Every confirmed
bug needs a synthetic regression. Keep touched active production modules type-clean;
do not enlarge the legacy baseline or add broad ignores. Explain compatibility changes.

Preserve frozen strategy semantics, external pins, sealed phases and forward Shadow
history. No broker, real orders, retrospective epochs or market-data backtests belong
in cleanup. Keep secrets, market/runtime data and generated dependency/build trees out
of Git. Historical evidence is immutable; follow [reproducibility](docs/reproducibility.md)
for certificates, measurements and archived path resolution. Preserve third-party notices.

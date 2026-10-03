# Project documentation

Current product entry points are the [project overview](../README.md) and
[unified console guide](unified_console.md). Quantitative V1 contracts remain
frozen; dated audit reports preserve the state they actually observed.

| Area | Documentation |
| --- | --- |
| Portable setup, quality checks and contribution | [Contributor guide](../CONTRIBUTING.md) |
| Python tooling, typing stages and portable configuration | [Engineering workflow](engineering/README.md) |
| Synthetic reusable-model example | [Minimal demo](../examples/minimal_demo/README.md) |
| Console startup, health and ownership | [Unified console](unified_console.md) |
| ETF V1 specifications and audit history | [ETF document index](etf_quant/README.md) |
| ETF observer | [ETF API](../services/etf-quant-api/README.md) |
| Development artifact firewall | [Research API](../services/research-api/README.md) |
| Formal Shadow operation | [One-shot runner](../services/etf-quant-runner/README.md) |
| User interface | [Dashboard](../dashboard/README.md) |
| Frozen dependency history | [Dependency conflicts](dependency_conflicts.md) |
| Third-party software and data rights | [Notices](../THIRD_PARTY_NOTICES.md) |

Historical audit/handoff records are organized through a
[logical archive](archive/README.md); original paths and bytes are retained.

The original environment-foundation documents describe their historical setup
scope. For current console topology, use loopback ports 3312 / 8787 / 5173 and
the existing external runtime configuration. The deployed research-service host
mappings remain 19200 → 9200 and 19201 → 9201; do not recreate host 9200/9201 from
an old setup example. No console action changes this environment.

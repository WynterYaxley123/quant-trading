# SWL1-Ridge-V2 execution engineering acceptance

The [scientific record](../research/swl1-ridge-v2-results.md) closes V2 as
FAILED_VALIDATION. This engineering transition changes registry/API/UI/docs
and exact public-aggregate publication hashes; no preregistered numerical
research module, V1 artifact, SWL2 model or historical certificate is modified.

The active certificate is
`reports/engineering/swl1-ridge-v2-execution-integrity.json`. It carries all
earlier delta sources and preserves the preregistration certificate bytes,
on the unchanged installation parent. It records source integrity rather than
claiming an external scientific or security certification.

Verification uses the independent developer Docker image and a complete public
clone without private factual/runtime mounts. Canonical gates cover Ruff lint
and format, staged Mypy with zero new/touched-module diagnostics, all pre-commit
hooks, full portable pytest, V2 synthetic anchor/seen/penalty/calendar/drop/
lifecycle tests, V1/SWL2 regression, all three APIs, Dashboard tests/types/lint/
build, reference/archive verification, secret/data/history audit, developer
image build and README synthetic flow. Test skips/deselections are reported
separately. Browser smoke has no defined project gate.

Integration tests cover four independent families, actual universes, optional
absent candidate/Validation, all legal closed/pending states, hash lineage and
tampering, forward=false even after passing Validation, null forward metrics
and zero runtime reads for inactive families. Dashboard rejects inactive
forecasts and exposes Development/Validation only as historical diagnostics.

Security permits only the three reviewed V2 aggregate paths with their exact
hashes; altered bytes, arbitrary research paths, raw market data and predictions
remain blocked in current/history scans. No dependency lockfile changes are
needed. Existing dependency advisories are compared against the starting main
lockfiles and disclosed separately; no new advisory is introduced.

Live checkout, scheduler, CNEquity, broker configuration and runtime remain
untouched. Own worktrees/containers are removed after merged-main acceptance;
necessary immutable research witnesses stay under QuantForge/research. The
primary user project stays under D:/quant-trading; auxiliary files belong under
D:/QuantForge. Exact test counts and GitHub commit/CI identities are recorded
in the PR and final delivery report after the actual checks finish.

# Real-source qualification acceptance

Base: fb82ce96e278b032d9113b6ecfcef7d06dd4f187. This transition qualifies public
document evidence, not new models, source production admission or numerical QA.

## Reproduction

In the pinned independent developer Docker, without runtime/provider mounts:

```sh
python -m scripts.engineering.source_qualification --verify
python -m research.evidence.qualification
python -m pytest -q tests/test_source_qualification.py tests/test_prospective_evidence.py tests/test_evidence_invariance.py
```

The report verifier has no network path. Qualification reuses the PR34 registry
with empty authenticating proof sets for real metadata candidates. Unsupported raw
component kinds remain outside direct industry admission. No source metadata hash
is represented as a numeric snapshot. No data-source generation is promoted.

The document CLI requests exactly one reviewed public document endpoint by ID;
it has no arbitrary URL, credentials, redirect following, payload persistence,
payment, consent or provider-refresh facility. BaoStock's documented POST endpoints
are read-only Markdown retrieval APIs; they do not log in or request financial data.
The TDX legal static asset is read as text and never executed. PDF input accepts
no active JavaScript/Launch payload. Hash/identity/age/claim checks cannot confer
dataset permission. Public acquisition is not run in CI.

The synthetic suite checks software/public-page grants, required rights,
expiry/conflicts, contract/generation binding, forged approval, temporal PIT,
stale/backfilled hierarchy, revision after signal, incomplete snapshots and each
quality-receipt defect. It rejects same upstream origin through different wrappers,
method mismatch, forged hashes/publishers, redirects, stale documents, exact-claim
mismatch, unsafe payloads and path/URL escape. Passing synthetic qualification
always yields SYNTHETIC_ONLY, never production authority.

The nine reports reproduce the actual reviewed snapshot. Backend responses bind
their bytes to the cumulative integrity certificate and remain exact-route
read-only. Dashboard validation rejects source promotion, false identity/readiness,
private fields, inconsistent inventory counts and escaped request-packet paths.

Canonical regression includes Ruff, format, staged Mypy, all pre-commit hooks,
portable pytest, existing source/PIT/numeric/ledger tests, SWL1/SWL2, API security,
Research API and dashboard gates, pinned Docker workers, fresh clone, references,
full-history secrets, integrity and baseline dependency audits. Actual counts,
CI/PR/main hashes and post-merge evidence are recorded in delivery/GitHub after run;
skips or blocked real data capabilities are never represented as passes.

Current cumulative source certificate is
[swl1-source-qualification-integrity.json](../../reports/engineering/swl1-source-qualification-integrity.json),
carrying PR34's full prior delta on the original full parent. The historical PR34
source-admission, contracts, numeric views, prospective ledger/anchor and reports
stay unchanged. Generic active integrity pointers move to this source transition.

## Production identity plan

Production authority remains SIGNATURE_AUTHORITY_NOT_ESTABLISHED. Before any
production implementation, owner governance must approve a named admission
authority, approved credential store, independently verifiable public-key trust,
key custody and separation from workers, rotation/revocation, approval audit roles
and durable independently retained receipts. Existing application access secrets,
GitHub permissions or ephemeral test HMAC do not prove those approvals. No private
credential inventory was read and no production keys were generated.

Real rights/PIT/quality remain blocked. Old research failure states and unseen
certification stay unchanged. Scheduler/live services are untouched. Previously
rejected legacy cleanup is retained without retries or alternate deletion methods.

[Acquisition plan](../research/swl1-source-acquisition-plan.md) ·
[Readiness](../../reports/research/swl1_source_qualification/final-readiness.json)

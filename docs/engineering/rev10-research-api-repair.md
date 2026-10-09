# REV10 Research API repair and prospective readiness

Base main: fd873ce4bc52f4bb0e29db628c02a28e949420bd. PR38 initial head:
e221d99c5a8436342d948d4e0a49fa791b78da99. Continue PR38 normally; no new PR.

## Root causes

| Symptom | Root cause | Component / evidence | Repair | Verification |
| --- | --- | --- | --- | --- |
| Windows verified offline fallback | Initial PR38 changed certified source without a new delta; REV10 health rejects it before Research startup | Run 37937893130, windows-launcher; original public head health returns 503 / REV10_INTEGRITY_BLOCKER | Append cumulative source delta from real main and retain PR37 bytes | Source/API gates and cold Windows launch |
| V2_RESEARCH_INTEGRITY_BLOCKER and Python failures | The same unregistered workflow/viewer/launcher/test hashes invalidate the shared current implementation inventory | etf-api-security and python-portable in that run; IMPLEMENTATION_SOURCE_HASH_BLOCKER:.github/workflows/quality.yml | Move active pointers to the new certificate; retain all earlier certificates | ETF regression, portable tests, immutable byte comparison |
| security audit BLOCKED | Four initial PR38 protected files differ from the active certificate | hygiene in that run, firewall_changes | Existing verifier with only its current-certificate pointer updated | Full-history audit, zero firewall changes |
| Research missing from prior launch / CSP | PR37 starts two services; static CSP disallows the separate loopback API | PR37 launcher/viewer and default frontend endpoint | Start/reuse Research on fixed 8787; exact CSP and actual viewer origins | Three-service cold/reuse tests, HTTP CORS and browser requests |
| Direct /research returns 404 | Static viewer recognizes only the industry SPA entry routes | Actual viewer regression returns 404 | Closed allowlist of existing Research page entry routes | GET /research = 200, unknown routes remain 404 |
| Reuse exceeds test deadline on the maintainer Windows host | Repeated full Windows TCP-provider enumeration; one measured read takes 5413 ms | Local second-run timeout with no service crash | One initial selection snapshot and fresh ownership snapshots at service readiness, retaining OS bind probes | Actual repeat timing and ownership/conflict tests; deadlines unchanged |
| Cold test waits until pipe timeout despite launcher exit | Windows long-lived children can inherit anonymous output handles | Local cold invocation exits 0 at the exact spawnSync deadline | Capture launcher stdout/stderr in fixture files and assert spawn errors as well as exit status | Actual parent exit and receipts; same 60-second per-invocation limit |
| Weak reuse and misleading service state | Preliminary reuse lacks a boot source/configuration identity; shell health can be conflated with artifact errors | Research health and ConsoleServiceStatus | PID + exact command + loopback + boot source/config hashes; independent CONNECTED/workspace states | Reject unknown/spoofed listeners, changed configuration and stale source; UI disconnection/empty/degraded tests |

## Connection and integrity boundary

Research starts the existing services/research-api/src/index.ts with locked tsx dependencies, IPv4
loopback 8787, exact selected viewer origins and the default unconfigured workspace.
This launcher clears inherited report/workspace/artifact overrides for its private
REV10 session, then restores the caller environment. It never creates artifacts.
Use the separate existing workspace configuration flow for approved Development
artifacts. A differently configured existing Research instance is preserved and
rejected, with a verified offline fallback. Research port is fixed because the
existing compiled client targets 127.0.0.1:8787/api/v1.

All three services require the actual Node executable and exact entry command at
the listener, IPv4 loopback, and the corresponding health identity. Research also
binds boot-time source inventory, lockfile, registry and resolved configuration;
health contains hashes and PID without exposing private paths or reading artifacts.
Capabilities and status confirm no mutations, sealed phases, non-executable and
non-tradable NOT_CONFIGURED state. Existing unknown processes are never stopped.
Only Process objects created by the failing invocation are cleaned up.

Industry rendering observes Research health/workspace without requesting runs or
candidate artifacts and remains available when Research disconnects. The Research
page independently displays its actual workspace status. CONNECTED is not a
scientific admission or an available artifact. The CSP permits only self and the
fixed IPv4 loopback Research address; CORS uses exact selected Dashboard origins.

The new reports/engineering/rev10-research-api-integrity.json is generated with
the existing integrity_delta tool, parent shadow-task-installation-integrity.json,
previous swl1-rev10-delivery-integrity.json and real base main above. It carries all
previous delta changes and pins the previous certificate bytes. Generic current
pointers move; verifier algorithms, protected-data rules and frozen references do
not change. Private web builds use the existing locked build and rev10-bundle tool;
prior private web, review and preview evidence is retained separately. No historical
metric, ranking, six plots, frozen model, source/data acquisition or lifecycle changes.

## Required acceptance

Portable Python including REV10/prospective/frozen regressions, Ruff/format/staged
typing, pre-commit, metadata verification, all APIs, frontend tests/types/lint/build,
actual Windows cold/reuse/conflict/fallback/ownership tests, full-history audit and
public fresh clone are required. Dependency findings compare unchanged lockfiles.
Normal PR merge follows successful hosted checks, then main CI and local/browser
acceptance. Actual identifiers, counts, hashes and screenshots belong in the private
repair receipt; this document does not substitute for execution evidence.

## Shortest prospective route — read-only assessment

ACTIVATION_READY=FALSE. Existing registry, rights qualification, PIT/session spine,
immutable signed receipts, exact maturity, revision quarantine/revocation and
synthetic REV10 adapter are sufficient foundations. Do not build another ledger.

1. Independently decide H10 primary / H5 secondary statistical design: minimum
   meaningful effect, dependence-aware uncertainty method and block rule, precision
   planning, fixed observation endpoint/stopping rule, missing/revision treatment,
   and success/failure/blocker criteria. Known historical +0.055633 cannot set the
   threshold. Lock these before any future observation.
2. Reuse pinned CNEquity 1650e384a3fd1f67a70144a489acc91432f1df27. Obtain owner/vendor
   evidence for use, automated processing, display/retention, historical and future
   classification/member PIT, calendar, corporate actions/suspension/delisting,
   final confirmation and auditable receive times. Current public qualification
   remains DATA_SOURCE_NOT_READY with zero admitted real sources. No duplicate
   AKShare ingestion or assumed purchase.
3. Establish reviewed production authority/public-key trust and approved key store;
   configure source generation, signed factual receipts and append-only predictions.
   Current production authority is deliberately refused; implementing its reviewed
   binding and one synthetic preactivation acceptance is necessary, not optional
   configuration or a fabricated signature. Keep keys and real data external.
4. Once those gates pass, obtain separate owner activation authorization and a
   protocol-only independent public anchor. Start only at the first eligible
   exchange session strictly after real lock/activation with ten legally received
   complete input sessions. No activation date or lawful first session is currently
   established. Preserve T+1…T+10 compounding and exact session/final-fact maturity;
   signed future H10 records evaluate the unchanged model only at the locked endpoint.

OWNER_APPROVAL_REQUIRED=SOURCE_RIGHTS_AND_PRODUCTION_AUTHORITY_AND_FORMAL_ACTIVATION.
STATISTICAL_DESIGN=PENDING; PIT_READINESS=NOT_ADMITTED;
SIGNATURE_AUTHORITY=NOT_ESTABLISHED; FORMAL_PREREGISTRATION_ACTIVE=FALSE;
REAL_PROSPECTIVE_OBSERVATIONS=0; LIVE_SCHEDULER_ENABLED=FALSE;
LIVE_DEPLOYMENT_PROMOTED=FALSE; REAL_ORDERS_CREATED=0; ETF_EVENTS_CREATED=0.

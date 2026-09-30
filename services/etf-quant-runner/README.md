# Manual ETF transport V1

Current deployment authority: root README and
`reports/etf_quant/etf_quant_v1_final_release_v1.json`. The certified one_shot.py
below is the unique formal entry; older run.py cycle examples are legacy
engineering transport documentation. COMMON_MODEL_UNIVERSE_V1/reference seed
binding is verified and mounted read-only automatically; no model repair step
is required. The console helper starts observation services only.

## Certified autonomous one-shot entry (no daemon)

The current formal branch is `integration/etf-quant-v1-shadow-autonomous-final`.
Use `one_shot.py --config <external-one-shot-config.json>` with the **existing
isolated CNEquity interpreter**, not Windows global Python. The separate
`one_shot.config.example.json` enumerates required paths; the deployment config
is outside Git at `D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json`.
Only file transport / calendar metadata execute on the host. Model, allocation,
PIT admission and accounting run inside the existing frozen Docker image.

The one-shot refreshes only already completed official sessions via the pinned
upstream job engine, preserving stage / batch / compact / revision / audit gates.
It exports the real lake with the existing streaming exporter. No direct curated
write, provider fallback, SDK upgrade or historical formal replay is used.
Refresh receipts live in the separate metadata-only control root. No formal
`shadow/` records are created for WAIT. Successful exports are reused by pinned
manifest hash. A same-T committed signal returns `ALREADY_PROCESSED` **before**
refresh, so it cannot generate another Epoch/signal/intent. The control lock
serializes the entire operation; the account lock remains exclusive.

On Windows the external export configuration may supply `paths.lake_io_root`,
a human/audit-visible short physical path to the **same** existing lake. The
runner proves `samefile` against the pinned source and export roots, and verifies
both lexical and resolved Windows raw-archive paths fit the pinned writer.
The physical directory was recoverably renamed on the same volume to
`D:/QuantForge/etf-lake`; the prior access path
`D:/QuantForge/external/cnequity-etf-quant-v1/lake-minimal` remains a junction to it.
The former short-to-long junction is retained as `etf-lake-link-before-relocation`.
File identities and published Parquet byte fingerprints are verified before/after;
no file is deleted, copied or rewritten by this relocation, and no SDK/global
settings change is made. A short junction TO a long physical root is insufficient:
long leaf resolve() may add an extended prefix and trip the unchanged containment
check. Extended `\\?\` paths are not used because native DuckDB glob
does not support them. Prior exact-plan jobs in this entry's own
`etf_quant_forward` namespace are reused only if successful; terminal failed
jobs are recovered through public SDK `retry_failed_only`, which re-runs the
finalization chain. Unknown plans and active jobs are never adopted or stolen.
Each invocation makes at most one recovery call per session.
If an old logical receipt is degraded but its physical batches are all settled,
the next invocation makes one fresh normal observation instead of endlessly
retrying no failed batches. Any non-success logical status still returns
`WAITING_FOR_DATA` without export/model/Epoch, recording safe stage identifiers.

Structured outcomes: `STARTED`, `ALREADY_PROCESSED`, `WAITING_FOR_MARKET_CLOSE`,
`WAITING_FOR_FINALIZED_DATA`, `WAITING_FOR_PIT_EVIDENCE`, `WAITING_FOR_DATA`,
`READY_NO_SIGNAL`, `BLOCKED_INTEGRITY`. Waiting is factual, not authorization to
invent prices or evidence. No clock override is exposed by either CLI.

Formal T0 `shadow_epoch` and `formal_signal` are stored in each immutable
hash-verified `state.json` generation; `view.status` exposes their compact
provenance. The first epoch object remains byte-equivalent in later states.
`state.epoch` / `view.status.epoch` remain the **legacy T1 accounting epoch**:
not renamed, not claimed as T0. At T0 no accounting NAV/fill/holding is invented.
T0 manifest records the real CNY10,000 initial cash and zero positions separately.
Even all-Cash creates a formal strategy epoch and signal, with no order/intent.
T1 accounting references the formal epoch, prior signal and immutable Candidate.

The Candidate retains its original SHA256. Its runtime-contract hash describes
the certified **baseline**. Authorized additive lifecycle code is separately
pinned in `reports/etf_quant/autonomous_code_integrity_v1.json`; that document
pins every strategy source and transport/API source used here. Both layers are
checked instead of rewriting the Candidate to pretend its old hash is current.

Production evidence remains forward-only. First legal T is strictly after the
Shanghai date when certified evidence first became available; the historical
reference 2026-09-24 can never initialize a formal epoch. Current finalized
same-day export, frozen models, listing, 20/20 liquidity and Strict > B40 > Cash
gates are enforced inside Docker. Missing evidence -> Cash; no coverage quota.

The following legacy strict-only transport is retained for compatibility; it
is **not** the certified B40 formal initialization entry.

`run.py` is stdlib-only host infrastructure. Only the standalone storage/hash
helper is imported, not a quant package. Numerical models and accounting execute
solely in existing quant-research. No scheduler, source downloader or credentials.

Copy config.example.json/profile.example.json outside every Git checkout. Fill
absolute external sidecar/config/export/runtime/profile/evidence paths. Registry
may be the tracked empty strategies/etf_quant/config/verified_mappings_v1.json
or an external manually verified registry. Only explicit VERIFIED evidence is
copied, after SHA256 checks. Profile must match source-policy.json exactly.
Coverage cannot fall below five constituents/0.8; core repeats every gate.
Sidecar must be pinned, tracked-clean and version0.11.0 in its dedicated venv.

```
python -B services/etf-quant-runner/run.py cycle --config <external-config.json>
```

Requires clean committed integration/etf-quant-v1, a real existing lake, current
finalized cutoff and next-session calendar. It exports the lake read-only and
does not fix missing data. Non-trading days/missed T+1 block, no backdated signals,
historical replay, automatic Validation or invented market prices.

Exclusive external transport lock is never stolen. Only ETF code, one immutable
seven-table export, profile, registry/evidence and last consumed account/prefix
enter unique Docker /tmp/etf-quant-v1.*. No Research copy, main /workspace writes,
mounts/dependency/compose/image changes. Hidden external .bridge_* receives output
first. All manifests/files/plans validate before immutable publication; API latest
pointer updates last. Generation collisions require exact identity. Failure
manifest is separate, preserving account. Unique closed/fsynced temp files use
bounded sharing-error retries. Hidden bridge/container directories remain for
diagnosis, never served/committed. Interrupted locks require human review.

To disclose a genuinely failed earlier metadata smoke without fake market data:

```
python -B services/etf-quant-runner/run.py record-smoke-blocker --runtime <external-root> --report <external-smoke-report.json>
```

This verifies pinned source, strict upstream TLS, blocked status, exception and
actual time. Only failure metadata is published, no model/portfolio/NAV/latest
success. Sanitized JSON output, no child stderr, paths or secrets. No broker,
real order, leverage, shorting, Validation or Final OOS path exists.

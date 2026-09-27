# Manual ETF transport V1

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

# Industry forecast runner

`run_forecast.py` is a one-shot Docker-only invocation for SWL2-Ridge-V1 and
SWL2-Ridge-V2. It reads finalized factual snapshots and byte-pinned model reference
data from external read-only mounts, then publishes/evaluates into a separate
external `industry-forecast/<family_id>` namespace. It performs no refresh, search,
ETF mapping or account operation. Data unavailable and partial maturity remain
explicit waits; there is no historical publication backfill.

```sh
python services/industry-forecast-runner/run_forecast.py --all-swl2 --config /control/industry-forecast.json --read-only-preflight
python services/industry-forecast-runner/run_forecast.py --family swl2-ridge-v1 --config /control/industry-forecast.json --dry-run
```

The [configuration](config.example.json) is a template; factual mount identities
must match existing admission contracts. First activation freezes an immutable
binding and waits for a genuinely future finalized session. Dry-run/preflight do
not create directories, locks, bindings or events. Source commit, frozen model and
published factual revisions fail closed. Existing storage's recoverable journal
and OS mutex supply crash recovery without refitting the original publication.

The [scheduler template](scheduler.template.json) is disabled and installs nothing.
No live scheduler is enabled by this task. See the [canonical lifecycle](../../docs/industry-forecast.md).

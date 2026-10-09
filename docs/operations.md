# Industry forecast operations

[Evidence operations](engineering/prospective-evidence-operations.md) expose five
read-only research-evidence resources under the industry API. They read reviewed
public aggregate metadata, never runtime facts, and create no event or data view.
Rights/PIT gaps, NOT_CREATED future protocol and zero formal observations remain
visible separately from successful synthetic engineering checks.

ETF productization is RETIRED. Historical ETF task/runner/config documents in the
[archive](archive/README.md) are audit records, not current launch instructions.
This engineering delivery does not promote deployed source, enable tasks or create
forecast/ETF events. Leave existing QuantForge state and disabled tasks unchanged.

## Read-only observation

The default dashboard reads `/api/industry-forecast/`; an unset runtime root yields
`No forward forecasts yet` and null aggregates. Set `INDUSTRY_FORECAST_RUNTIME_ROOT`
only to an existing external `industry-forecast` directory. API reads never create
folders, freeze bindings, fit models, import sources or publish events.
Historical ETF pages/API remain read-only and label HISTORICAL_PRODUCTIZATION_RESULT
and RETIRED. Current source's old ETF write commands fail closed.

## Separately authorized future activation

The independent Windows [industry console launcher](../scripts/Start-IndustryForecastConsole.ps1)
starts only the read-only industry API and dashboard, with an explicit external
log root and optional runtime root. It installs no packages, preserves occupied
ports, and invokes neither a forecast runner nor an ETF service. The historical
ETF console launcher remains an audit capability. Launching these services is a
separate operator action, not part of this source delivery.

Use a clean merged checkout, independent Docker image, pinned external CNEquity
and explicit source facts mounted read-only. Configure the
[runner template](../services/industry-forecast-runner/config.example.json) outside
Git with independent writable `industry-forecast/<family_id>` namespaces.

```sh
python services/industry-forecast-runner/run_forecast.py --all-swl2 --config /external/config.json --read-only-preflight
python services/industry-forecast-runner/run_forecast.py --all-swl2 --config /external/config.json --dry-run
```

These are Docker-container commands, require merged source, and are read-only.
An actual invocation without either flag requires separate operational activation.
Its first use freezes source/model/time but cannot publish that day's signal.
The next genuinely current eligible finalized session may publish. No unattended
task is installed by the engineering workflow. The
[scheduler template](../services/industry-forecast-runner/scheduler.template.json)
is disabled and includes no private path or credential.

## Retry and recovery

A repeated signal is NOOP_ALREADY_PUBLISHED and skips Ridge fitting. Recover only
verified journal generations under the same source/model binding; never regenerate
old predictions or edit published payloads. A changed binding or factual prefix
blocks. Investigate changed source/facts in a separately reviewed transition.
Missing/future/provisional/gapped outcomes stay PENDING. H10/H40/H120 use exact
exchange sessions. No task modifies old ETF namespace or migrates its ledger.

Keep Jupyter authenticated and loopback-bound as specified by existing compose.
No broker, real order, leverage, shorting or external message path exists here.
See [deployment](deployment.md), [industry contracts](industry-forecast.md),
[testing](testing.md) and [source evidence](engineering/swl2-industry-forecast-transition.md).

## Industry Forecast closure runbook

Read-only preflight/dry-run never initialize or write. Genuine retries return NOOP without fitting; mature checks append evaluations only after exact finalized exchange sessions. DATA_UNAVAILABLE/CALENDAR_UNAVAILABLE stay blocked or pending. Under the runner mutex, journals recover byte-identical publications; stale OS locks do not authorize overlap. Hash/source/model mismatch blocks and requires an independently reviewed source transition. Back up complete objects, generations, pointers and journals together; restore to an isolated external namespace and verify before any separately authorized activation. Legacy read-only inspection remains permitted; state-mutating ETF commands are retired.

[Source acquisition packets](research/swl1-source-acquisition-plan.md) remain unsent. No new provider refresh, credentials, real admission, key creation, scheduler enablement or live deployment is authorized by public readiness inspection. Real-source status is read-only at the existing evidence observer.

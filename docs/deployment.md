# Industry forecast deployment boundary

Engineering delivery is source-only. Live deployment promotion, runtime activation
and scheduler enabling require a separate operational instruction. Historical ETF
deployment guides retain original bytes under [archive](archive/README.md).

## Fresh checkout and independent image

```sh
git clone https://github.com/WynterYaxley123/quant-trading.git
cd quant-trading
docker build -f .devcontainer/Dockerfile -t quant-trading-dev:local .
docker run --rm -v "${PWD}:/workspace" quant-trading-dev:local python -m examples.industry_forecast_demo
```

Run portable Python and Node/frontend gates from [development](development.md).
No quantitative dependencies go into host Python. Never change the deployed image.
Fresh data-free API startup needs no CNEquity credentials and reports empty state.

For future authorized forecast operation, use clean merged main and pinned external
CNEquity. Existing exports/warmup facts are mounted read-only; the runner imports no
network source. The forward image remains independently built from pinned public
dependencies, never an edit to CNEquity or deployed services. Source, private
configuration, facts and writable runtime roots must remain separate outside Git.

Use the [runner config template](../services/industry-forecast-runner/config.example.json),
[runner guide](../services/industry-forecast-runner/README.md),
[API guide](../services/industry-forecast-api/README.md) and
[disabled scheduler template](../services/industry-forecast-runner/scheduler.template.json).
No legacy ETF namespace is re-used or migrated. Do not commit market rows, arrays,
SQLite/HDF5, credentials, environment files, ledgers, Shadow payloads or build outputs.

Preflight verifies current facts without writing. Actual initialization freezes
merged source/model identity and time; publication begins strictly after merge and
freeze dates with genuinely current finalized facts. No historical result is loaded
as new forward history. Model/source mismatch requires reviewed reactivation, not
rewriting a binding. Publication semantics are in [industry forecast](industry-forecast.md).

Dashboard uses `VITE_INDUSTRY_FORECAST_API_BASE_URL`; API defaults to loopback 3313.
The historical Research/ETF APIs remain separate read-only boundaries. An absent
runtime reports empty; integrity failures report blocked. No simulated account or
fake forecast demo is injected into production UI. [Operations](operations.md)
describes future authorized retries and [testing](testing.md) covers crash injection.

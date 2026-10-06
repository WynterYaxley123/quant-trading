# Industry forecast API

Run `node services/industry-forecast-api/server.mjs` for the local read-only service
on port 3313. `INDUSTRY_FORECAST_RUNTIME_ROOT` optionally selects the operator-owned
external `industry-forecast` root; absent runtime returns honest empty views.
`INDUSTRY_FORECAST_API_PORT` selects a local nonprivileged port. No GET creates state.

Closed GET/HEAD routes under `/api/industry-forecast/`:

- `families`
- `swl2-ridge-v1/current`, `history`, `evaluation`, `status`
- `swl2-ridge-v2/current`, `history`, `evaluation`, `status`
- `swl2-ridge/compare`

Sources, generations, event hashes, model/source bindings, full cross-sections and
provenance are validated. Reads are bounded; path escapes, arbitrary query paths,
unapproved origins, mutation methods, future results and account/secret fields fail
closed. Metrics come from matured forward events only. Historical source files
are hash-verified without interpreting performance records.

This service needs no third-party Node dependency. Test with
`node --test services/industry-forecast-api/tests/*.test.mjs`; build/type syntax
validation uses `node --check services/industry-forecast-api/server.mjs`.
See [the canonical research contract](../../docs/industry-forecast.md).

# Local observation and development

Forward operation uses `services/etf-quant-runner/one_shot.py` for both versions.
Pass one external `--config` for compatibility, or repeat `--config` once for V1
and once for V2. The pair is checked for distinct versions and disjoint resolved
account/control paths before either runs. Calls execute sequentially; a failure
in one version returns a bounded receipt and still permits the other version's
independent invocation. An aggregate blocked result exits with code 2.

```powershell
& $TransportPython -B "$Checkout/services/etf-quant-runner/one_shot.py" `
  --config $V1Config --config $V2Config
```

Use an explicit Python interpreter for standard-library transport only. Numerical
code runs in Docker. Fetch remote metadata before an operational invocation and
use a clean committed checkout whose HEAD equals `origin/main`; never switch or
reset an occupied deployment merely to satisfy this gate. Supply absolute external
configuration paths and the pinned existing images/source. The V2 container config
must match the documented mounted paths exactly.

Invoke after the official session's finalized close (15:05 Shanghai or later).
The entry refreshes completed factual sessions, verifies certificates and exports,
then creates only a genuinely current post-freeze signal. A committed same-date
signal returns before provider refresh or model execution. Reinvoke on factual
waiting outcomes; at the next eligible T+1 close, the existing persisted intent
uses genuine raw opening evidence for delayed paper accounting and current NAV.
An unavailable provider or ETF never authorizes guessed prices or a retroactive
intent. Integrity blockers require diagnosis; waiting receipts remain visible
through the read-only API without replacing the last verified account/NAV.

An external scheduler can repeat this exact command, serially, after the close
and during provider retry windows. There is no second scheduler/model/accounting
entry. Locks prevent concurrent work and same-date signals are idempotent.
On holidays the workflow arms without business records. The next eligible date
comes from the verified official calendar and release availability; a still-waiting
current trading date is retained, rather than silently skipped to tomorrow.

The 2026 exchange calendar closes October 1–7 and resumes October 8, as announced
by [SSE](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)
and [SZSE](https://investor.szse.cn/disclosure/notice/general/t20260917_622911.html).
This dated example never overrides the runtime calendar/time gates.

The console starts dashboard and two read-only APIs without invoking a runner,
refreshing data or initializing a formal epoch. Supply machine-local configuration
outside Git via ETF_QUANT_CONSOLE_CONFIG or -Config. Runtime/control roots are absolute
paths outside the checkout. Legacy deployment defaults are compatibility examples,
not contributor requirements.

The launcher supports configurable ports and shares DASHBOARD_ORIGINS with both APIs.
Standalone ETF API defaults to localhost/127.0.0.1 on 5173/4173. Configure
ETF_QUANT_DASHBOARD_PORT or comma-separated exact DASHBOARD_ORIGINS. Wildcards,
credentials, paths, queries and fragments are invalid. APIs bind locally.

Compose Jupyter requires a nonempty JUPYTER_TOKEN supplied in the process environment
or ignored local .env; both Compose and container shell reject absence. Its published
port remains loopback. Never commit the token. Config edits do not authorize a deployed
research-service restart or rebuild.

Runner keeps argv arrays and disables shell execution. Model reference names accept
bounded letters/digits/dot/underscore/hyphen, without traversal. Mount source values
reject Docker delimiter/quote grammar. A new implementation certificate does not
authorize a formal signal or relax historical branch guards.

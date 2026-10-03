# Local observation and development

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

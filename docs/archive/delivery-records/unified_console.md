# Unified operations console

The normal entry point is `scripts/Start-EtfQuantConsole.ps1`. It manages ETF Quant API (127.0.0.1:3312), Research API (127.0.0.1:8787) and Dashboard (127.0.0.1:5173). It observes existing data; it never invokes one-shot, research, training or market-data refresh.

## Start and configuration

Use the existing Node 24+ / locked pnpm dependency environment. The launcher resolves the checkout from its own script path, so an absolute script invocation works from another current directory.

The default `-Config` is `D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json`. It reads only `runtime_root` and `control_root` from that existing external configuration for the ETF observer. See the [runner configuration template](../services/etf-quant-runner/one_shot.config.example.json) for the separately managed full runtime deployment.

The launcher automatically connects an approved local workspace through optional `control_root/research-workspace.json`. Explicit `-ResearchReportRoot`, `RESEARCH_REPORT_ROOT` and `RESEARCH_WORKSPACE_CONFIG` overrides take precedence; without local configuration the optional default is this checkout's `reports/research`. All roots must pass the explicit approval registry and Development integrity checks. See [Research workspace configuration](research_workspace.md). No report folders or research results are created or copied.

The three API/client addresses, Research CORS origins and real-data mode are explicitly set for child processes. Caller environment variables are restored in a finally block. The services inherit the rest of the existing environment. Vite dev and preview defaults bind to loopback; production preview is a separate developer workflow, not the unified launcher's ownership/reuse contract. Both frontend API addresses are build-time variables in a production bundle.

## Readiness and ownership

The launcher uses bounded retries, a per-service timeout (default 30 seconds), HTTP responses and contract checks. ETF health and current must succeed; Research health and read-only capabilities must succeed; Dashboard must serve its actual app HTML. READY means those checks passed. Research process health is separate from admission: the launcher also prints DEVELOPMENT_READY, NOT_CONFIGURED or DEGRADED with its artifact diagnostic. Invalid artifacts leave the API connected so the UI can explain and retry that state.

A receipt under `control_root/console-logs` records the checkout/configuration fingerprint, PID, process start time and log paths. Reuse requires the same configuration, executable, exact checkout entry point, start time, listener PID, loopback address and successful health check. A stale owned process is reported explicitly for deliberate restart; it is not silently replaced. Ownership is never inferred from a port number alone.

Port conflicts are checked for all components before starting any component. Unknown listeners and different checkouts/configurations cause a clear conflict. The launcher never kills them. An exclusive launch lock prevents overlapping launches of the same stack. A failed startup rolls back only verified processes created during that invocation and preserves previously running services.

`-EtfApiPort`, `-ResearchApiPort` and `-DashboardPort` support isolated launcher tests. The documented production stack uses the defaults. ETF CORS has its existing fixed local origin allowlist, so arbitrary Dashboard test ports are not a supported production browser origin.

## Empty data versus failure

| Observation | Presentation |
| --- | --- |
| Research HTTP health + approved workspace | Connected / DEVELOPMENT_READY; approved selector and content |
| Research HTTP health + absent optional configuration/catalog | Connected / NOT_CONFIGURED; explicit empty state |
| Research HTTP cannot be reached | DISCONNECTED with unified launcher guidance |
| Research artifacts fail schema/hash/IO checks | DEGRADED / typed error, never an empty-data fallback |
| ETF HTTP is unreachable | Independent DISCONNECTED state |
| ETF evidence fails integrity checks | DEGRADED; formal gates remain closed |

On ETF pages, the only Research request is the artifact-free health endpoint. Research metadata/performance loaders remain disabled there. On Research pages, the shell waits for health, capabilities, status and catalog before opening a run page. An empty catalog prevents any run/performance requests. The service strip appears on all pages, including Operations/Health.

## Logs and failure recovery

Logs are outside Git under `control_root/console-logs/run-<timestamp>-<launcher-pid>/`. Failure output names the component, port, exact Node command and stderr log. A dependency preflight error names the missing installed component; no automatic installation occurs.

If a verified owned process is stale, inspect its receipt and stderr log, then stop only that instance and invoke the launcher again. If the port belongs to another application, resolve the conflict separately. Never stop an arbitrary Node/Python process by port or process name.

Changing an artifact root or runtime config requires stopping the previously verified console instances first. A still-running stack with another configuration is intentionally not reused. This preserves the identity of the approved data sources.

## Tests and boundaries

[Launcher tests](../scripts/tests/console.test.mjs) use existing PowerShell 7 on Windows, copying only four approved control/calendar metadata files into disposable external fixtures. They cover portable start from another cwd, environment preservation, healthy reuse, unrelated port conflict, connected invalid-artifact state, startup rollback and approved local auto-configuration. `CONSOLE_TEST_CONFIG` selects the external certified config; `CONSOLE_APPROVED_RESEARCH_ROOT` enables the read-only actual workspace case. No system policy, networking or Docker configuration is changed.

Research tests cover absent roots, empty catalogs, corrupt metadata, sealed paths, malformed queries, read-only methods and containment. Frontend tests cover every Research empty route, disconnected/degraded states, retry and the ETF/Research observation boundary.

The frozen Docker image, CNEquity pin, quantitative modules, Candidate/PIT/Strict evidence, Dependency lockfiles and formal runner branch guard remain outside this integration's change scope. Historical audit reports preserve their original statements.

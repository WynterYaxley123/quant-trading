# Deployment guide

The Git repository is the `SOURCE_OF_TRUTH_REPOSITORY`. A separate
`LOCAL_DEPLOYMENT_ROOT` holds mutable facts, accounts, control metadata and private
configuration. Users choose their own root. The maintainer's `D:\QuantForge` is a
reference implementation detail, not a required path or distributed dataset.

## Prerequisites and developer setup

Use Git and Docker; Docker Desktop is the reference Windows transport. Start with
the verified [data-free workflow](../README.md#data-free-quick-start).
The independent developer image pins Python, Node, pnpm and requirements. It does
not rebuild or modify a deployed research image. Do not install quantitative
dependencies into host Python or create a host virtual environment. An existing
explicit host Python may run standard-library transport only.

Frontend and Research API installation, tests and builds are in
[development](development.md). Their frozen dependency lockfiles are reproducibility
source, unlike generated runtime locks.

## Select external roots

Separate the source checkout from mutable state. A possible layout is:

```text
<deployment-root>/
  etf-lake/                    authorized factual/market data
  external/cnequity/source/     exact pinned upstream checkout
  operations/                  clean operational source checkout
  runtime/accounts/v1/         independent V1 paper account
  runtime/accounts/v2/         independent V2 paper account
  runtime/control/v1/          V1 control/transport metadata
  runtime/control/v2/          V2 control/transport metadata
  logs/                        private operational receipts
  backups/                     private recovery copies
```

Empty directories do not constitute an admitted account. Account/control roots
must be disjoint after realpath resolution. Actual releases can require additional
external factual/warmup roots. Keep runtime UUIDs, pointers, logs, provider cache,
local `.env`, credentials and private evidence outside the source repository.

## Provider identity and bootstrap

[CNEquity metadata](../config/deployment/cnequity.pin.json) pins upstream
`rootSunc/CNEquity`, version 0.11.0, commit
`1650e384a3fd1f67a70144a489acc91432f1df27`, Apache-2.0. Clone upstream separately
into the provider source root and check out that exact commit. Verify HEAD and
clean source status before mounting it read-only. Preserve upstream notices.
Do not vendor its checkout/environment or upgrade implicitly. Software identity
grants no market-data rights.

Use the existing [sidecar](../services/cnequity-sidecar/README.md) export boundary,
not a direct write into curated tables. Configure its source/export templates for
container mounts. Authorized calendar, instruments, history, membership, adjustment
and publication evidence must pass existing admission contracts. Read
[data/PIT](data-and-pit.md) before importing data. Missing evidence remains blocked;
never replace it with synthetic production data.

## Configuration and read-only verification

[runtime.example.json](../config/deployment/runtime.example.json) is a boundary-check
template, not a one-shot configuration. Copy it outside Git; supply
`${SOURCE_REPOSITORY}` and `${DEPLOYMENT_ROOT}` through environment variables or
literal absolute paths. Create only roots you own. It does not initialize an account.

The verifier checks existing directories, containment, disjoint roots, source identity
and exact clean provider pin. It prints role results and public commit identities,
not private paths, secret values or data. Run in the developer container with
external roots mounted read-only at the paths used by the config. An existing host
transport interpreter may also run this standard-library-only check:

```sh
python scripts/operations/verify_deployment.py --help
python scripts/operations/verify_deployment.py --config /external/deployment-check.json
```

Operational transport uses the existing
[one-shot example](../services/etf-quant-runner/one_shot.config.example.json).
Keep both version configs external and follow the [runner guide](../services/etf-quant-runner/README.md),
including exact mount names, owned forward-source lake and independent namespaces.
Do not replace model/mapping/release files to make configuration pass.

## Docker and host networking

Compose requires a nonempty private `JUPYTER_TOKEN`; the empty `.env.example` fails
closed. Supply it through the environment or ignored local environment file.
`docker compose config --quiet` validates without starting services. Keep published
Jupyter/observation ports on loopback. Engineering verification never recreates a
deployed service or changes its image.

Windows HNS may reserve a host port even with no listener. Inspect candidates:

```sh
node scripts/operations/host-ports.mjs --help
node scripts/operations/host-ports.mjs --port 19500 --port 19501
```

The diagnostic reads IPv4/IPv6 reservations and TCP endpoints without changing DNS,
locale, firewall or services. It observes availability; it does not reserve ports.
The [host-port template](../config/deployment/compose.host-ports.example.yml) requires
`QUANT_SERVICE_HOST_PORT` and `QUANT_AUX_HOST_PORT`. Compose `!override` replaces
host publication only, keeping internal ports 9200/9201 unchanged. Validate base
and external override together with `config --quiet` before separately authorized
recreation. Keep the effective local override. Never run a global network/locale
reset or install remote-control software as project bootstrap.

## API and dashboard

The [console launcher](../scripts/Start-EtfQuantConsole.ps1) starts observation
services without a formal cycle. Supply external configuration, runtime/control
roots and approved Development artifacts. V2 needs both corresponding roots.
Absence of an approved Research workspace is an honest empty state. See
[operations](operations.md) for origins, health and restart.

## Scheduler installation and first safe preflight

Use a permanent clean operational checkout separate from PR/research worktrees.
[Install-ForwardShadowTask.ps1](../scripts/Install-ForwardShadowTask.ps1) installs
the action pointing at [scheduled_wake.py](../services/etf-quant-runner/scheduled_wake.py).
Copy the [scheduler template](../services/etf-quant-runner/scheduler.config.example.json)
outside Git, with explicit transport Python, Git, checkout, both configs and an
existing log directory. Follow [preflight](operations.md#scheduler).
Dry-run validates paths and checkout identity without updating or invoking one-shot.
Installation is a separate operator action; testing a guide does not authorize
installing, enabling or waking a task.

## Update, rollback and uninstall

Merge reviewed source changes with green CI through a normal PR. Before a deployment
update, back up state/configuration and record source/image/provider pins. Only a
clean exclusively owned operational checkout may fast-forward. Preserve dirty or
divergent work; never reset another actor's checkout. Retain live referenced files
until replacements have been verified.

For rollback, quiesce the owned writer and preserve failed-state evidence. Restore
a coherent verified backup under the same account identity, then check certificate
and generation chains before resuming. Source rollback never authorizes historical
signals, missed fills or manual ledger edits. Uninstall only owned tasks/services;
retain accounts, data and backups. Recovery rules are in [operations](operations.md).

# Shenwan official append-only updater v1 — final report

## Final outcome

FINAL STATUS: SHENWAN_OFFICIAL_UPDATER_V1_IMPLEMENTED  
UPDATE STATUS: OFFICIAL_ENDPOINT_BLOCKED  
READINESS STATUS: VALIDATION_NOT_READY — 19/60 READY, 41/60 NOT READY.

Strict project-local TLS verification was recovered and verified against unchanged
trusted roots. Both original official endpoints returned empty HTTP 508 responses.
The live cycle stopped at source health: no 124-series fetch, staging, overlap,
append, canonical publication or new snapshot. This is allowed outcome C, NOT a
successful real append and NOT a strategy/Validation/backtest result.

## Git / environment

| Item | Actual evidence |
|---|---|
| Branch | experiment/sw-sector-index-research-baseline |
| Initial HEAD | 23d77ba5816bea85f31c4c5626564bbac3ee3e4c |
| Implementation commit | c9f95c4771c9f0b81e8a538cd5990109a7e96112 |
| Runtime-entry fix / clean live execution HEAD | d257c18be4dd3fb8681282eb5263173875fcff14 |
| Result / handoff commit | Same final docs-only creation commit; resolve with the command below |
| Initial and live-run worktree/index | Clean |
| Docker | quant-research and quant-jupyter running; no recreate/rebuild/pull |
| Frozen research image | sha256:57858238189364c652cf673d64917d365afd5508ee464ed9c142d5d4e1b002e5 |
| RESEARCH_ENVIRONMENT_CHANGED | false |
| HOST_PORT_PUBLICATION_CHANGED | true — prior approved exception, not a new change this task |
| Host publication | 127.0.0.1:19200 → 9200; 127.0.0.1:19201 → 9201 |
| Python / Hikyuu / RQAlpha / AKShare | 3.12.11 / 2.8.2 / 6.4.0 / 1.18.88 |
| NumPy / Pandas / SciPy | 2.3.5 / 2.3.3 / 1.16.3 |
| Push / merge / scheduler / dependency changes | None |

The first committed CLI probe stopped BEFORE network because Docker bind-mount
ownership triggered Git's safe-directory protection. A separately tested fix uses
only `git -c safe.directory=/workspace` for each known-repository invocation.
No global Git configuration was written; no amend/rebase was used. The two real
network entries below ran from clean committed d257c18be4dd3fb8681282eb5263173875fcff14.

The final commit cannot literally contain its own SHA. Its exact full SHA is
reported in chat and reproducibly resolved from the local Git creation record:

```text
git log --diff-filter=A -1 --format=%H -- docs/research/handoff_shenwan_official_updater_v1.json
```

The previous bc97fb..23d77ba difference was inspected and was docs-only expected
handoff cleanup. Frozen strategy/research/protocol/model/split files were unchanged.
`git ls-files data` was empty, and generated health/run/staging/snapshot paths are
ignored. Only code, tests, public intermediate certificate and docs were committed.

## Recomputed frozen identities

| Identity | SHA256 |
|---|---|
| Protocol | 2344cc685201476de957109b9fccc2681923e2c4591b5ed91740a56baf128410 |
| Candidate | 6c2b16555b6dfd5d848ea451b09e7b75f53da67747fc76fd052d93afd3ea156b |
| Split | 3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038 |
| Phase | 28d3980e28b41b37d2a327aad6081e8312cf66d66762c13e33cc8ba814c8fa7f |

The existing golden inspector reverified the frozen config/source identities,
42 Development source artifacts by hash and 14 result-seal metadata files.
No Development/Validation/OOS performance payload was deserialized by this updater.

## Original source acquisition chain / authority

Provider remains `shenwan_research_official`. Existing offline importers and
historical raw manifest identify the original public catalog and DAY trend APIs;
the updater wraps exactly those endpoints, not AKShare or a replacement provider.

- Catalog: https://www.swsresearch.com/institute-sw/api/index_publish/current/
  with page={page}, page_size=50, indextype=二级行业.
- Trend: https://www.swsresearch.com/institute-sw/api/index_publish/trend/
  with swindexcode={frozen_code}, period=DAY.

Scheme, exact host/path/query and redirect target semantics are checked on every
request. No redirect was observed during the actual probe/dry-run. Historical
catalog pagination advertises an HTTP `/api/...` next link; it is recorded but
never followed. The client constructs authorized HTTPS pages itself.

Frozen U0 is 124 (hash f24e61c51f48e1b4ca8ded83eaf24bdd71be35711f3eb0ed88d7627f332d026a).
The current OFFICIAL catalog count, additions/removals/renames and full frozen
source coverage are UNKNOWN/null because both endpoints returned HTTP 508.
No latest-catalog row can change frozen U0.

## TLS diagnosis and strict recovery

DNS resolved 202.122.119.203; TCP 443 succeeded; no Docker proxy environment keys
were present. The observed peer leaf is the official wildcard certificate, not
an observed unknown inspection/proxy issuer. Host VPN state was not inferred.

| Diagnostic | Result |
|---|---|
| curl with /etc/ssl/certs/ca-certificates.crt | FAIL, curl 60: unable to get local issuer certificate |
| OpenSSL s_client, verification enabled | FAIL, verify code 20; server sent one leaf only |
| Explicit certifi / system requests before completion | SSLError issuer-chain failure |
| One early default request | Empty HTTP 508; recorded as intermittent behavior, not successful data access |
| Intermediate against existing certifi roots | OpenSSL verify PASS |
| Leaf + intermediate + existing roots + hostname/server purpose | OpenSSL verify PASS |
| Final project-local strict requests, catalog / 801012 trend | TLS verified; HTTP 508 / HTTP 508 |

Leaf: C=CN, ST=上海市, O=上海申银万国证券研究所有限公司, CN=*.swsresearch.com.  
Leaf issuer: C=US, O=DigiCert, Inc., CN=GeoTrust G2 TLS CN RSA4096 SHA256 2022 CA1.  
Leaf serial: 0A93E8B6F9263473C9401874508C5370; valid May 12–Nov 26, 2026.

Intermediate: C=US, O=DigiCert, Inc., CN=GeoTrust G2 TLS CN RSA4096 SHA256 2022 CA1.  
Issuer: C=US, O=DigiCert Inc, OU=www.digicert.com, CN=DigiCert Global Root G2.  
Serial: 0F06BB09306148267FCA1B71C1DB807D.  
Validity: Dec 15, 2022–Dec 14, 2032.  
Pinned PEM SHA256: 2182efcbf5b27c34ba8901fae4715a6c6bdc54d9e186adc7b43523ce2e9176c1.  
AIA acquisition: http://cacerts.digicert.cn/GeoTrustG2TLSCNRSA4096SHA2562022CA1.crt.  
Retrieved: 2026-09-27, DATE_ONLY precision (exact initial acquisition clock was not
captured; no midnight timestamp was invented).

The AIA DER was converted to public PEM and verified cryptographically before
use. Each probe rechecks pin SHA/AIA, issuer equality, CA property, validity,
original-root chain, leaf hostname and sslserver purpose. Verification includes:

```text
openssl verify -CAfile <original-certifi-roots> <intermediate.pem>
openssl verify -CAfile <original-certifi-roots> -untrusted <intermediate.pem> -verify_hostname www.swsresearch.com -purpose sslserver <leaf.pem>
```

Python default CA: /opt/conda/ssl/cert.pem.  
Requests/certifi CA: /opt/conda/lib/python3.12/site-packages/certifi/cacert.pem.  
Both unchanged SHA256: 9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f.  
System CA unchanged SHA256: 9481fcd95f41b221f02f14d896535fe500bec539bc563c4cdca1acee483a8bdd.

The temporary adapter-only bundle adds this verified intermediate to original
roots. No new root, leaf trust, global CA/Conda/certifi/Windows change,
hostname-disable, verify=False, warning-disable or AKShare patch was used.
HTTP 508's underlying site/network cause remains UNKNOWN. No cookie/account,
browser impersonation or site restriction bypass was attempted.

## Schema / frozen parent / quality facts

Historical wrapper: code/message/data. Historical trend keys:
swindexcode, bargaindate, openindex, maxindex, minindex, closeindex, hike, markup,
bargainamount, bargainsum. All 124 original files parsed under the new Decimal
schema: 419,346 rows and the same 20 invalid bars. This is HISTORICAL compatibility,
not a live schema/overlap PASS. Live schema is NOT_RUN; schemaCompatible=null.

| Parent fact | Verified value |
|---|---|
| Snapshot | 872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500 |
| Cutoff | 2026-09-18 |
| Rows | 419346 |
| Initial / final readiness | 19/60 / 19/60 |
| Market CSV SHA256 | 884c7dbaaacf6aa5652b63cde5153265ca383fe5bec18fa0a40c410a76b5a887 |
| Known SOURCE_INVALID OHLC | 20, preserved |
| Invalid row-key SHA256 | 202043fbc25582502bfaa63d3f359fefb11ea75a82ebfce4973fd064f7d87755 |
| Invalid sidecar SHA256 | ddd5a362b5c68274ce6e3ea5c145fd65e03065b94fda0fe3cebb4a8378dde23d |
| 801193 missing historical common sessions | 336, preserved |
| Last missing session | 2023-09-26 |
| Missing-session SHA256 | 00c586669468962b70f1a01e31e8bd9378e17ef16d06d3f6fe9bc568e8aa1674 |

Classification version, publication timing, volume/amount units and historical
index recalculation policy remain UNKNOWN/null; strictPit remains false.
Download/TLS success would not establish independent formal data admission.

## Implementation / transaction / lineage

See `docs/data/shenwan_official_updater_v1.md` for operations and recovery rules.

The additive updater provides probe/stage/audit/apply/readiness/cycle and dry-run.
It fetches ALL frozen sectors into ignored staging, verifies schema and response
SHA, compares the FULL parent historical key set/OHLCVA using Decimal (numeric
formatting/JSON ordering are not revisions), and rejects the ENTIRE cycle for
any true change, deletion or backfill—including known anomaly repairs.

Parent cutoff is dynamic. New source rows retain missingness/invalid OHLC under
existing rules. The current Shanghai natural day is excluded with
UNCONFIRMED_FINAL_SESSION because no same-day finalization evidence was established.
Future/duplicate dates are rejected; calendars or missing rows are never invented.

Original BASE raw and `data/processed/shenwan/` remain immutable. Accepted DELTA
raw would go to `data/raw/shenwan/sector_history_append/<run_id>/`, preserving
response provenance. A full candidate copies every old CSV row byte unchanged
and appends genuine newer rows per sector. Prefix SHA is checked before/after.

New canonical generations use `data/processed/shenwan_snapshots/<snapshot_id>/`.
Immutable versioned manifests use `data/manifests/shenwan_sector_snapshots/`.
An exclusive lock, fresh parent checks, candidate hash/path/golden-manifest checks,
fsync and immutable materialization precede ONE atomic `current.json` replacement.
This pointer is the sole publication boundary. Pre-pointer crashes leave the
old generation usable; orphans/stale locks require human review, not auto deletion.
Post-pointer failure is treated as committed and critically re-audited.

Framework default reads resolve/verify one current generation; explicit legacy
paths still select the golden original. Frozen strategy loaders/code were not
changed. Existing snapshot_id is reused with versioned delta/manifest/code input
fingerprints; original inputs still exactly reproduce 872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500.

Readiness uses the existing frozen date/quality-only rules, verified lineage,
fixed ordinal prefix and monotonicity against baseline/prior accepted snapshots.
It has no model/evaluator import and never reads labels/returns/predictions.
Even 60/60 only yields human-review readiness, never automatic Validation.

## Actual live run and non-executed gates

| Item | Actual result |
|---|---|
| Probe run | official_probe_20260927_v1_retry, OFFICIAL_ENDPOINT_BLOCKED |
| Dry-run | official_cycle_20260927_v1_dryrun, OFFICIAL_ENDPOINT_BLOCKED |
| Catalog / representative trend HTTP | 508 / 508, empty bodies |
| 124-series fetch / staging | NOT_RUN; 0 accepted full-fetch series |
| Staging directory | Not created |
| Full live overlap / revisions / deletions / gap fills | NOT_RUN / null / null / null |
| Append candidate rows / range | null / null (not audited) |
| Real apply attempted / applied | false / false |
| New snapshot / cutoff / rows | null / null / null |
| Current rows | 419,346 |
| Historical prefix identity | PASS, actual golden SHA unchanged |
| Live snapshot lineage / append manifest / current pointer | NOT_RUN / absent / absent |
| Synthetic publish/lineage/idempotency/crash tests | PASS |
| Live rerun idempotency | NOT_RUN — no successful apply to rerun |
| Readiness before / after / delta | 19 / 19 / 0 |
| fullValidationReadiness | false |

This is NOT a 124/124 fetch or live overlap PASS. The source gate correctly withheld
publication; there was no reason to invoke a real apply.

## Tests / determinism

| Checkpoint | Actual outcome |
|---|---|
| Pre-network targeted baseline | 186 passed |
| Pre-network full offline baseline | 788 passed, 2 skipped, 17 deselected, 2 warnings |
| Final implementation/runtime-fix targeted | 245 passed, 1 deselected |
| Final implementation/runtime-fix full offline | 847 passed, 2 skipped, 18 deselected, 2 warnings |
| Post-cycle targeted, including readiness/prereg integrity | 245 passed, 1 deselected |
| Post-cycle full offline | 847 passed, 2 skipped, 18 deselected, 2 warnings; 234.12s |
| Golden snapshot integration identity | 1 passed, 59 deselected |
| Imports / diff whitespace | PASS |
| Failed tests | 0 |
| New offline safety contracts | 59 |
| Readiness repeats | Two exact equal byte outputs |
| Readiness SHA256 | f4e252fbb2a5781a0847c80f3865195ac1332908a81f1820087ebd0828aecdc0 |

The original two skipped tests and two warning locations were unchanged. The new
real-local golden fixture is marked integration and was explicitly executed; all
59 new default tests are synthetic/offline. No existing test was weakened/deleted.
Safety coverage includes strict/wrong/expired/hostname TLS, source/redirect drift,
schema/missingness/duplicates, Decimal revisions/deletions/backfills/repairs,
catalog/U0 isolation, incomplete staging, final-session exclusion, prefix/lineage,
multiple crash checkpoints, atomic commit, rerun idempotency, dynamic second
parent, malformed paths/manifests, scoped Git trust, monotone readiness and seals.

## Evidence / handoff / future commands

- Health: `data/manifests/shenwan_official_source_status.json`
  SHA256 66ec69cce7012f7f752b2a9773ee19d93a689995c98e14a20149281f20c05d21.
- Cycle: `data/manifests/shenwan_official_runs/official_cycle_20260927_v1_dryrun/result.json`
  SHA256 06c4b0199304d799d57b62a1952c3b29499c439e5c4ebdf1923b90673f260112.
- Probe: `data/manifests/shenwan_official_runs/official_probe_20260927_v1_retry/result.json`.
- Handoff: `docs/research/handoff_shenwan_official_updater_v1.md` and `.json`.
- Actual new snapshot/append manifest paths: null — never published.

Windows PowerShell, existing Docker only, always BOTH compose files:

```powershell
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose -f 'D:\quant-trading\docker-compose.yml' -f 'D:\QuantForge\temp\quant-trading-host-port.override.yml' exec -T quant-research python scripts/data/update_shenwan_official.py probe
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose -f 'D:\quant-trading\docker-compose.yml' -f 'D:\QuantForge\temp\quant-trading-host-port.override.yml' exec -T quant-research python scripts/data/update_shenwan_official.py cycle --dry-run
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose -f 'D:\quant-trading\docker-compose.yml' -f 'D:\QuantForge\temp\quant-trading-host-port.override.yml' exec -T quant-research python scripts/data/update_shenwan_official.py cycle
& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose -f 'D:\quant-trading\docker-compose.yml' -f 'D:\QuantForge\temp\quant-trading-host-port.override.yml' exec -T quant-research python scripts/data/update_shenwan_official.py readiness
```

Future update is gated, not an instruction to run it now. Readiness-only has no
network and writes no file. Retry probe/dry-run only when original official endpoint
availability recovers. No fallback provider, scheduler or parameter optimization.

## Final seals / next safe action

validationOpened=false; Validation SEALED / UNSEEN; validationPerformanceRead=false;
validationResultsGenerated=false; Final OOS SEALED; finalOosRead=false.
Four frozen identities, old raw/canonical/research/strategy files remained intact.

SHENWAN OFFICIAL REMAINS THE CANONICAL F1 DATA SOURCE  
NO THIRD-PARTY MARKET DATA SOURCE WAS SPLICED INTO THE FROZEN SERIES  
VERIFY_FALSE WAS NOT USED  
THE FROZEN HISTORICAL PREFIX WAS NOT SILENTLY REVISED  
VALIDATION PERFORMANCE WAS NOT READ  
NO VALIDATION RESULTS WERE GENERATED  
VALIDATION REMAINS SEALED AND UNSEEN  
FINAL OOS REMAINS SEALED  
WAIT FOR MORE LEGALLY AVAILABLE SHENWAN OFFICIAL DATA

Stop. No Validation, Final OOS or LEVEL B execution.

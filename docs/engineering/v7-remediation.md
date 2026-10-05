# V7 remediation

Base: `b5ac584a7f6339e7ae089286fa6ec939b082ff33`. Inventory comes from the
user's listed findings; no separate review was supplied. All numerical checks use
independent Docker images and synthetic fixtures or permitted read-only evidence.

| ID | Finding | Verified classification and resolution |
| --- | --- | --- |
| 01 | Strong scientific umbrella | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. Separately certified current overlay labels the candidate provisional, direction STRONG_POSITIVE, statistics LIMITED, membership RECONSTRUCTED, historical ETF execution NOT_ESTABLISHED. |
| 02 | 120 versus 80/60 split | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. Strict-PIT proposal and actual evidence-tiered chronology are distinct explicit contracts; the latter shares 80/60 constants. Deviation documented; consumed original 60 sessions remain immutable. |
| 03 | V1 source freeze claim | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. Strategy economic/model contracts are frozen; verified runtime maintenance is permitted. No infrastructure rollback. |
| 04 | Missed T+1 deadlock | CONFIRMED_BUG. Authenticated pending intent becomes ABANDONED_MISSED_T1, old epoch loses fill authority, current forward epoch continues with preserved account and original evidence. |
| 05 | Stale account lock | FALSE_POSITIVE on current main. Kernel mutex already releases on death and publication journal already recovers atomically. Unowned legacy lock remains an INTENTIONAL_COMPATIBILITY_CONSTRAINT: ownership cannot be proved, so no automatic unlink. |
| 06 | Fixed 20-month history | CONFIRMED_BUG. Actual maturity cutoff plus configured calendar-month training window, 120-session factor warmup and 20-session margin; all supported 6/9/12/18/24 windows checked, unsupported/truncated inputs reject. Frozen production remains 12. |
| 07 | Duplicate fractional accounting | CONFIRMED_BUG in test-only compatibility helper. Wrapper now calls the production 100-lot, cost-aware primitive; production execution economics stay unchanged. |
| 08 | V2 importing V1 primitives | INTENTIONAL_COMPATIBILITY_CONSTRAINT. One-way dependency onto frozen domain/numerical/execution and shared storage primitives is documented; V1 has no V2 import. |
| 09 | Calendar linear searches | CONFIRMED_ARCHITECTURE_DEBT. Per-signal session index replaces per-observation scans; exact model outputs preserved. |
| 10 | Repeated ledger serialization | CONFIRMED_ARCHITECTURE_DEBT. Reuse exact canonical state bytes for identifier and publication. Full-ledger verification remains bounded and linear per cycle; cumulative archive storage remains quadratic. |
| 11 | Full row-list materialization | CONFIRMED_ARCHITECTURE_DEBT. Stream rows into the same lookup, removing the full intermediate list. Timings remain observational. |
| 12 | Membership filter/sort/unique | CONFIRMED_BUG and architecture debt. Unordered unique output produced nine mean hashes from identical synthetic inputs across 30 runs. Canonical symbol order repairs deterministic reduction; one cached view rebuilds only when dated membership changes. Latest effective row identities and per-day listing eligibility remain unchanged. |
| 13 | Serial JS source hashing | CONFIRMED_ARCHITECTURE_DEBT. Eight bounded concurrent reads; every complete file still hashes and verifies, without caches or skipped evidence. |
| 14 | Growing certificate ceremony | CONFIRMED_ARCHITECTURE_DEBT. New compact delta binds parent bytes and only changed/new files; legacy chains remain supported and immutable. |
| 15 | Forecast versus ETF backtest | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. Public docs and UI separate industry forecasts from unvalidated historical ETF execution and current 22/124 forward mapping. |
| 16 | Empty signals index | CONFIRMED_BUG. Empty committed V2 signal state rejects explicitly before any last-signal access. |
| 17 | Zero Development IC | CONFIRMED_BUG. Nonpositive/nonfinite reference yields null ratio and cannot pass the retention gate. Published original decision is unchanged. |
| 18 | Symbols used as paths | CONFIRMED_BUG. Strict six-digit SH/SZ identity checked before path construction, including nonexecuting receipt rows. |
| 19 | JS existence containment | CONFIRMED_BUG. Resolve contained parent and regular leaf before existence succeeds; symlink escapes reject. |
| 20 | Minor documentation/legacy symbols | CONFIRMED_ARCHITECTURE_DEBT. All three strategies listed, dashboard spacing corrected, frozen cneqity_pin spelling explained, live parity reference marked test-only. |

Current scientific authority is [the overlay](../../config/research/etf-quant-v2-scientific-status.json).
The original freeze, candidate, release and Final-OOS reports remain historical
byte truth. No extension is created: untouched chronology was not established,
and this task authorizes no further data access or model search.

Missed-session recovery is automatic in the canonical runner's next genuinely
current finalized cycle, under the account lock and atomic journal. No replay,
retroactive fill, manual ledger edit or backdated intent is supported. Failed
publication recovers its original bytes before any new work. A future signal can
only reference the new epoch; terminal targets are never pending again.

The `e69c6d7` infrastructure transition preserves economic primitives while
allowing storage/lock/isolation maintenance. Independent fixtures cover Ridge
coefficients, ranking, mapping/cash, sizing, legal T+1, costs, lots and NAV;
the full unchanged frozen-image V1 acceptance gate passed 701 tests, with one
optional skip, using network-disabled read-only maintainer evidence.

Canonical verification: Python `verify_implementation` and the read-only security
audit verify the complete historical chain, resolve the compact delta and hash all
current files. Generating a delta never certifies testing by itself. Synthetic
profile timings are observations, not CI thresholds or market performance.

Completed validation: portable 1,259 passed / 2 skipped / 99 external deselected;
focused accounting/recovery/locks/runner/scheduler 105 passed; API/security 140 passed;
dashboard 132 passed / 3 optional skipped with types/lint/build; Research API 63
passed / 7 optional skipped with types/build; Windows launcher/task definition 6
passed. Ruff/format/pre-commit pass; active production Mypy is zero and the legacy
168-diagnostic baseline is unchanged. Frozen-image V1 acceptance passed 701 tests
with one optional skip. Linux and Windows API/security each passed all 140 tests.

Synthetic profiles: session lookups 0.317s to 0.0014s; duplicate JSON serialization
0.0077s to 0.0030s; 257 complete certified-file hashes 1.966s to 0.571s on this host.
The comparison digests match exactly. Row streaming removes an intermediate list
and measured 0.091s/0.082s. Membership reference took 0.040s for five synthetic
dates; indexed membership took 0.022s including construction and its first cached
view. Latest membership row identities match; canonical reduction produces one
mean hash across 30 runs. These observations do not promise wall-clock speedups.
See [Python profile](../../reports/engineering/v7-performance.json)
and [hashing profile](../../reports/engineering/v7-hashing-performance.json).

Nonblocking limits: reconstructed historical membership, 60 dependent OOS
observations, unestablished historical ETF execution, sparse forward mapping,
full-snapshot archive growth, explicit ambiguous legacy
lock blocker, and logged-in-user/Docker/provider availability. No remaining
confirmed blocking runtime bug is accepted without remediation.

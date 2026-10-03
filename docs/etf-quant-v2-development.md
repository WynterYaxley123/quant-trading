# ETF-Quant V2 research status

**Blocked by historical membership evidence. No market-data Development experiments
or candidate selection were performed.** This is the task's strict-PIT hard blocker;
recovering more prices cannot repair it within the unchanged provider boundary.

The machine-readable audit is `reports/engineering/etf-quant-v2-research.json`.
The row-level rejection inventory stays in the external V2 research namespace.
V1 runtime/evidence was mounted read-only, and V1 Shadow path/size/hash metadata was
captured before work. No formal runner was invoked.

| Component | Observed stored range | Interpretation |
| --- | --- | --- |
| Shenwan membership | 2020-01-23 to 2026-09-24; 81 snapshots; 419,972 rows; 5,930 symbols | Reconstructed snapshots, all observed on 2026-09-27; strict historical availability/completeness unproven |
| Daily bars | 2016-01-04 to 2026-09-30; 2,611 distinct dates | Uneven stock/ETF coverage; earliest stored row does not prove a reliable common universe |
| Calendar | 2020-01-02 to 2027-09-30; 1,882 sessions | Includes announced future sessions; future calendar entries are not finalized market data |
| Adjustment factors | 2016-01-04 to 2026-09-30 | Stored factors alone do not certify exact eligible industry returns |
| ETF bars | 2025-04-10 to 2026-09-24; 358 dates; 115 symbols | Additional execution-history limit; amount fields have residual missingness |
| Index bars | 2025-04-10 to 2026-09-30; 361 dates; 8 symbols | Observed index range, not a selected benchmark return result |

The historical criticism's “239 days” is an immutable earlier **eligible signal
prefix**, defined in the earlier research protocol. It is not the current count of
lake trading sessions. These counts describe different populations and are not
interchangeable. No sealed performance artifact was read to establish them.

Strict-PIT start/end and coverage ratio are null; admitted sessions are zero. Five
years of admissible strict-PIT history were not achieved. A formal industry-date-symbol
coverage matrix is blocked because the historical denominator itself is unproven.
The 419,972-row rejection inventory must not be called a successful formal matrix.

For adjacent labels, mechanical overlap is 90% for H10, 97.5% for H40 and 99.1667% for
H120. Empirical autocorrelation/ESS, H120 incremental information, OLS-versus-Ridge
shrinkage, feature scaling and training-window conclusions remain **null**. Synthetic
checks verify diagnostic arithmetic; they provide no market research conclusion.

The [closed search specification](etf-quant-v2-protocol.md) contains 120 candidates;
none is market-data feasible under current admission. No date-specific protocol,
Development-selected candidate or V2 Shadow configuration is frozen. Validation
opened = false; Final OOS opened = false. Existing APIs remain restricted to their
approved historical Development/V1 schemas and do not expose V2 sealed results.

Delivered independent engineering includes a read-only capability audit, immutable
external rejection inventory, closed candidate specification, date/maturity/seal
gates, training-only transformations, numerical/dependence diagnostics, pure Ridge
fits/fusion/cache identity, compatibility aliases, canonical terminology and data-rights
review. Source tests and integrity transition record the validation evidence.

To resume formal research, the pinned boundary must actually provide verifiable
historical membership/publication/completeness evidence. This task does not change
the pin, introduce another provider or authorize weaker retrospective membership.

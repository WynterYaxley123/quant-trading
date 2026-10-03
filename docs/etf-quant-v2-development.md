# ETF-Quant V2 measured research status

The rebuilt factual history covers **2018-01-02 to 2026-09-24**, 2,120 sessions
(8.73 calendar years), and 124 industries. This is factual coverage, not 8.73 years
of independent model evaluation. The fixed universe was determined from the first
120 eligible high-confidence dates, ending 2022-01-26, before Development.
The latest comparison has 230 observable H40 targets across 271 calendar sessions.

The 9,814,532-row coverage matrix contains Tier A **0**, B **6,498,448**, C
**3,298,854**, D **17,230**. Tier D is excluded. Public annual historical stock
rosters have 99.91%–100% symbol classification coverage. This checks symbol coverage;
it does not independently prove historical industry assignment. No independent
Tier A historical snapshot was obtained, so strict-versus-reconstructed assignment
error is **null**. Pre-2021 taxonomy use is explicitly retrospective Tier C.

Empirical median temporal ESS is H10 **50.19**, H40 **15.63**, H80 **9.19**,
H120 **6.39**, on each industry's longest complete Development sequence.
Stacking industries does not create independent temporal observations. H120 adds
0.01222 Development RankIC to the revision's short/medium fusion; its prediction
correlation against H40 is 0.0313. The small H120 ESS limits this conclusion.
At raw alpha 10 and 12 months on the same 230 observed targets, H120 fusion has
RankIC 0.14175 and norm CV 0.10196; replacing H120 with H80 has 0.13612 / 0.21540,
and removing the long horizon has 0.13012 / 0.20290. Neither alternative is more
stable under this norm diagnostic. These are Development comparisons, not validation.

Raw alpha 0.01 versus OLS has coefficient-norm ratio **0.9175**, prediction
correlation **0.999734**, maximum fitted prediction difference **0.0019975**.
It is close in fitted predictions but not equivalent in coefficient shrinkage.
Features have unequal scales and design condition number 8,822. Paired Stage 1
training-only standardization changes median RankIC by −0.00322 in high-confidence
data and −0.00119 in extended history. It did not improve the measured selection.
High-confidence 12-month median RankIC is 0.1048 versus 0.0801 for 6 months;
24 months lacks 160 feasible high-confidence signals. Extended 24-month results
are weaker and have a different feasible span, limiting comparison.

The 120-specification Stage 1 had no passing candidate: an equal-calendar fold had
27 observed targets against the 30 floor. One predeclared 36-specification Stage 2
used contiguous calendar folds balanced by target **availability**, retaining
return gates. Its selected candidate removed H120, used raw features, alpha 10
and 12 months. Development RankIC was **0.130123**, spread **0.033419**, 230 signals.

That frozen candidate's **single Validation failed**: 80 signals, RankIC
**0.005498**, spread **−0.000801**. RankIC deteriorated **−0.124625**; two of four
chronological blocks had negative direction. There was no second Validation opening.

One authorized Development revision kept the 36 specifications and prioritized
the worst fold, required all four folds positive and coefficient-norm CV ≤0.2.
It selected **Ridge α=30, raw features, 12 months, H10/H40/H120 fusion
0.25/0.50/0.25**, retaining the frozen 5/19/19 factor sets. Development RankIC is
**0.143103**, spread **0.037231**, fold IC **0.06694/0.22820/0.13568/0.14016**,
coefficient-norm CV **0.064856**. This is **Validation-informed and not independently
validated**. Final OOS remains sealed. No alternative linear family was used.

Recent common-date high-confidence and extended-history coefficients agree within
3.5e−12 and their signs agree. Their 12-month fit windows contain the same Tier B
facts; this does not validate earlier Tier C assignments. Longer and earlier
extended-history comparisons change rankings and favor different feasible windows.
The high-confidence result takes priority.

Verified ETF mapping evidence became available after the research signal intervals.
Historical mapping therefore falls back to cash 100%; actual ETF turnover and cost
are zero, and no tradable ETF NAV is inferred. Revised industry top-five absolute
weight turnover is 0.74696; its 8bps cost proxy is 0.0005976 per signal. These are
counterfactual industry diagnostics, not an executable ETF performance result.
The immutable direct-mapping registry currently covers one of the 124 model
industries with two verified entries. Other direct/theme/proxy entries still require
the unchanged evidence and fresh liquidity gates; prospective cash exposure can be
substantial and is not predicted from historical unavailable evidence.

See [aggregate evidence](../reports/engineering/etf-quant-v2-build-research.json),
[candidate](../strategies/etf_quant_v2/config/candidate.json), and [protocol](etf-quant-v2-protocol.md).
V1 contracts/candidate/Shadow are unchanged. V2 Shadow has zero epochs, signals,
intents and fills. Future operation requires launch authorization and acknowledgement
of the unvalidated revision; no launcher was invoked in this task.

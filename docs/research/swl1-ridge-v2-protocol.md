# SWL1-Ridge-V2 formal protocol

This is a separate failure-informed generation, authorized after the closed
SWL1-Ridge-V1 record. Its public result-free preregistration must merge **before
any factual V2 metric**. The result-free state is
`FORMALLY_PREREGISTERED_RESULT_FREE` once that merge and remote anchor are verified.
No Development, candidate or Validation result is part of this document's
preregistration publication.

The exact machine contract is [protocol JSON](../../config/research/swl1-ridge-v2-protocol.json),
SHA256 `df832a94eba54d703110defe2e7f0169e9de93a316a7def795a38fe9e50e428a`.
Result-free implementation source commit:
`0b9a9e0` (the full commit is recorded in the JSON). It pins all V2 modules and
the read-only frozen V1 modules it imports. The factual panel SHA256 is
`20c038f87daa93cccf1515f41bda7de5b30fa70a4d1443ae6c34b770e19a5776`.

## Primary target and limitations

The primary target remains `RECONSTRUCTED_SWL1_EQUAL_WEIGHT`, on the exact
V1-admitted 30-industry universe (current taxonomy 31). Historical membership
confidence remains `RECONSTRUCTED`; no historical publication proof was upgraded.
The target is each industry's exact compounded future return minus the mean of
the **complete frozen universe**. Official L1 index returns, SWL2 and CSI300 do
not enter target choice, candidate selection or gates. No official-index
performance cross-check is authorized here. Source MIT licensing grants no
market-data redistribution rights; the private factual panel stays outside Git.

## Seen outcomes and exact split

All information used by V1 Development and Validation is seen. The proof derives
the final consumed maturity from frozen V1 phase indices and its largest horizon:

| Non-performance chronology fact | Actual value |
| --- | --- |
| Last V1 Validation signal | 2025-04-01 |
| Maximum horizon | 120 exchange sessions |
| Last V1 consumed outcome session | 2025-09-23 |
| V2 Development | 2023-08-02 through 2025-03-31; 401 signals |
| Development/Validation purge | exactly 120 exchange sessions |
| V2 Validation | 2025-09-23 through 2026-04-07; first 126 eligible signals |
| First V2 Validation outcome session | 2025-09-24 |
| Checked target intervals | 126 × 3 = 378, all outcome-unseen |

The target convention is `(t,t+h]`: returns on exchange sessions t+1 through t+h.
The first predictor endpoint may equal V1's final consumed maturity because all
its future target returns are later. This is the already merged draft's rule,
not a performance-selected interval. V1's planned unopened OOS signal range was
2025-09-24 through 2026-04-08: V2 overlaps 125 of its 126 signals and uses one
earlier endpoint. The proof's exact-range-repurpose boolean is therefore false;
the former reserved window is partly reused as V2 Validation under owner
authorization. It must never subsequently be described as independent V1 OOS.

The proof binds public V1 protocol/candidate/universe/results/status hashes,
unchanged V1 implementation hashes, matching private phase witnesses and absence
of any V1 OOS claim/result/seal. OOS objects are checked for existence, not read.
If proof fails, closure is `VALIDATION_INTERVAL_NOT_UNSEEN`, without Validation.

## Frozen design and gates

Exactly **16 specs**: penalty 0.01/0.1/1/10 × 12/24 calendar months × policies A/B.
Per fit, `alpha = penalty × training_rows`. Policy A uses existing compact five
factors for H10 and nineteen for H40/H120; B uses nineteen for every horizon.
Training-only population mean/std, complete-universe centering, independent
mature cutoffs and 0.25/0.50/0.25 horizon fusion remain fixed.

Development admission requires sufficient complete dates, every horizon mean
RankIC ≥−0.02, at least 3/4 positive equal-calendar composite blocks, consistent
universe/provenance and fully accounted drops. Selection maximizes composite
mean RankIC; 1e-12 ties prefer higher minimum horizon mean, 12m, larger penalty,
then lexical policy. There is no manual candidate choice.

Validation retains V1 thresholds: sufficient dates (at least 90% and 30), positive
composite and median composite IC, weighted positive fraction ≥0.55, weighted
spread >0, at least two positive horizon means, no mean below −0.03 and at least
3/4 positive blocks. Four block boundaries use equal calendar duration over
registered endpoints: `min(3,floor(4*day_offset/span_days))`. Dropped signals do
not move these boundaries. Spearman uses average ties; top and bottom score ties
both use ascending industry code.

Each dropped signal records signal date, phase, spec, horizon and reason code.
Valid plus dropped dates must equal the registered phase count. Actual per-fit
training rows and Ridge alpha are retained privately, with public aggregate
ranges/counts and exact trace hashes. No raw prices or daily predictions are
published.

## Publication and lifecycle

The protocol-addition commit must be result-free; original bytes must match the
fetched remote bytes, and no result may have existed earlier then been deleted.
An external GitHub merge witness binds PR/head/merge/protocol hashes and ancestry.
Factual execution takes place in a **new worktree** only after that witness passes.

Claims are exclusive and consumed before calculation. No candidate means no
Validation file. One frozen candidate may enter Validation exactly once. FAIL
closes V2 permanently; PASS yields `AWAITING_PROSPECTIVE_FINAL_OOS`.
**Final OOS is prospective only**, with no historical date range, claim or result
in this task. Both outcomes remain forward-ineligible. Future accrual requires a
separately frozen collection rule; historical backfill is forbidden.

Independent statistical confidence remains `LIMITED` because daily horizons
overlap. No trading profitability, production readiness or IID significance
claim follows. No ETF mapping/portfolio, scheduler, broker, order, deployment
promotion or formal forward forecast is authorized. V1 and both SWL2 generations
remain unchanged.

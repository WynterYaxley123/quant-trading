# SWL1-Ridge-V2 result-free design and formalization

PR #29 was a result-free draft. The owner has now authorized a separate formal
preregistration and execution. Status becomes **FORMALLY_PREREGISTERED_RESULT_FREE**
when the dedicated preregistration PR merges and exact remote bytes are verified.
No factual V2 metric has been calculated in this preregistration change.
See the canonical [formal protocol](swl1-ridge-v2-protocol.md).
Design input: [issue #28](https://github.com/WynterYaxley123/quant-trading/issues/28).

## What changes from V1, and why

| V1 observation (public artifacts) | V2 draft contract |
| --- | --- |
| Alpha 0.1–100 moved Policy B / 12m composite only 0.1192 → 0.1212; standardized `X'X` has about the training row count on its diagonal | `alpha = penalty × training rows`, penalty 0.01 / 0.1 / 1 / 10 (16 specs) |
| 12m ≈ 0.12 vs 24m ≈ 0.01 composite; one marginal admission | Development admission also needs ≥3/4 positive blocks |
| Blocks split by row count; dropped signals not recorded | Equal-calendar blocks; every dropped signal kept with its reason |
| Bottom5 ties took the highest codes | Top and bottom both break ties by ascending code |
| Protocol and results reached GitHub in one PR | Development refuses to start unless the exact protocol bytes are on a fetched remote-tracking ref with no result file at that commit |

V1's 19 factors, horizons, fusion, exact centered targets, maturity cutoffs,
training-only scaling, Validation thresholds and immutable phase claims are reused
unchanged by import. V1 sources stay hash-pinned by the V1 protocol.

## Seen data and chronology

V2 is informed by V1, so every label that entered a V1 metric is seen: through the
last V1 Validation signal plus 120 sessions. Development may reuse that history.
Validation is the first 126 eligible signals after it (on current data, V1's
never-opened planned Final OOS interval), after an exact 120-session purge.
No historical interval then remains unseen, so **Final OOS is prospective only**:
the lifecycle rejects any historical Final-OOS claim.

Resolved owner decisions:

- Accept use of V1's unopened reserved interval only after outcome-unseenness is
  proven. Exact first-126 endpoint dates are derived by the existing draft rule.
- Keep the V1 reconstructed equal-weight panel as primary target. Official L1
  index performance is excluded from this generation's selection and gates.
- Final OOS is prospective only; a Validation PASS does not enable forward.

## Procedure

1. `python -m research.swl1_ridge_v2.preregister <source-commit>` writes
   the V2 protocol JSON under `config/research/` from V1's admitted private panel.
2. Merge the result-free protocol PR and fetch it; retrieve and verify its external
   GitHub merge witness before any factual performance calculation.
3. `python -m research.swl1_ridge_v2.execute refs/remotes/origin/main` records the
   publication anchor, runs Development and at most one Validation, then stops.

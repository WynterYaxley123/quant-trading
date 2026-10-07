# SWL1-Ridge-V2 draft (not preregistered)

Status: **DRAFT_NOT_PREREGISTERED**. No V2 protocol exists, nothing has been run on
factual data, and no metric below is a V2 result. The code in `research/swl1_ridge_v2/`
is result-free and covered only by synthetic tests. Starting the generation needs
owner authorization. Design input: [issue #28](https://github.com/WynterYaxley123/quant-trading/issues/28).

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

Owner decisions before preregistration:

- Accept V1's unopened planned Final OOS window as V2 Validation, or wait for new
  prospective data for Validation too.
- Whether official SW Level-1 index closes are available as the target or as a
  cross-check of the equal-weight reconstruction. The draft keeps the V1 panel.

## Procedure

1. `python -m research.swl1_ridge_v2.preregister <source-commit>` writes
   the V2 protocol JSON under `config/research/` from V1's admitted private panel.
2. Merge that protocol **alone** and fetch it.
3. `python -m research.swl1_ridge_v2.execute refs/remotes/origin/main` records the
   publication anchor, runs Development and at most one Validation, then stops.

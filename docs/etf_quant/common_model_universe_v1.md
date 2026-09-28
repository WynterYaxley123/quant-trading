# COMMON_MODEL_UNIVERSE_V1 — formal admission record

**Status:** ADMITTED as the V1 engineering model universe for retrospective validation
and forward warm-up input. **Not** a relaxation of any frozen gate. **Not** an ex-ante
signal universe proof (historical membership PIT remains unproven).

**Admitted at:** 2026-09-28 (takeover continuation, Kimi K3), on evidence produced by
the interrupted Codex run and re-verified against the final post-`601318.SH`-repair
factor matrix.

## 1. Admission rule (deterministic, reproducible)

An industry is admitted iff **all** of the following hold at the fixed data cutoff
`2026-09-24`, measured on the SHA-256-sealed factor matrix:

1. Source-C recursive level usable at the cutoff session (frozen `5 / 0.80`
   date gate; broken recursive prefixes never restart);
2. all 19 frozen factors finite at the cutoff session;
3. at least 30 individually mature observations within **each** horizon's own
   six-month training window (H10 label cutoff `2026-09-10`,
   H40 `2026-07-30`, H120 `2026-04-02`).

No manual selection, no performance-based filtering, no threshold changes.

## 2. Result

| Measure | Value |
|---|---:|
| Frozen L2 taxonomy (4-digit, constant across window) | 162 |
| **Admitted universe** | **107** |
| Cutoff-missing industries (excluded) | 55 |
| Never-valid industries in window (visible, excluded) | 46 |
| H10 mature complete dates / observations | 128 / 13,696 |
| H40 mature complete dates / observations | 119 / 12,733 |
| H120 mature complete dates / observations | 118 / 12,626 |
| Full 162-universe complete training dates (any horizon) | **0** |

The 107-code list is sealed, with the matrices, in:

- `D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\etf_quant_readiness_20260928T091309Z_0d2dfbc6.json`
  (`diagnostic_common_universe`)
- factor matrix `etf_quant_factor_readiness_20260928T091309Z_0d2dfbc6.csv`
  SHA-256 `6771e6c352df00d9a9f2e6bc98b3b0c20b1614f93bdea8e0e3e813e133bbb482`
- source matrix `production_constituent_coverage_matrix_v3_20260928T091144Z_288178d0.csv`
  SHA-256 `6fc016bd0965b31579dd20527c1118eb60153c4539c04d9b20f26beb0b975e91`

## 3. What this admission does NOT do

- It does not lower the frozen `valid >= 5` / `coverage >= 0.80` Source-C gate.
- It does not drop the frozen full-cross-section requirement: inside the admitted
  107-universe every retained training date is a complete cross-section.
- It does not rename the universe policy inside the engineering reports: their
  `universe_policy` stays `DIAGNOSTIC_DATA_AVAILABILITY_INTERSECTION_NOT_FORMAL_ADMISSION`
  because they are historical artifacts; this document is the admission act that
  supersedes the label for V1 use, referencing the identical 107-code list.
- It does not assert the universe was knowable on 2026-09-24 (processed 2026-09-28;
  `HISTORICAL_MEMBERSHIP_PIT_UNPROVEN`).
- It does not create a shadow signal, ranking availability claim, or epoch.

## 4. Granularity contract (L2 vs L3 semantic fork, documented — not modified)

- The frozen data layer resolves membership at **width 4** (Shenwan 2021 L2,
  `level_of(code, 4)`, `session_universe` default; 162 codes in force across the
  window). All Source-C/factor/model evidence in this project lineage is L2.
- The production shadow path (`runtime/industry.py::build_industry_series`) builds
  its universe from the stored **6-digit** codes (396 in force at the latest
  snapshot, 483 over all snapshots), and the verified mapping registry keys on
  6-digit codes (`[0-9]{6}`).
- Consequence: the retrospective engineering validation (L2) and the forward
  shadow machinery (L3) operate on different but prefix-compatible taxonomies.
  V1 mapping registry entries are recorded at 6-digit granularity and name their
  parent L2 industry in `notes`; no frozen code was changed to reconcile the
  fork, and the fork is carried as a V1 **Known Limitation**.

## 5. Engineering model outputs on this universe

Three independent frozen NumPy Ridge fits (alpha `0.01`, raw X, no
standardization, same-date cross-sectional excess forward return target) were
executed on this universe at cutoff `2026-09-24` and classified
`HISTORICAL_ENGINEERING_VALIDATION_ONLY`; coefficients, intercepts, raw
predictions, z-scores and the fused 0.25/0.50/0.25 ranking with Top20/Top5 are
sealed in the engineering ridge report(s) under
`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\reports\`.
The final re-fit against the post-`601318.SH`-repair matrix is referenced by
`kimi_final_integration_manifest_v1.json`.

# Development artifact provenance — Research Dashboard API v1

Audited the actual local files on 2026-09-25 before implementing the adapter. Base Git HEAD: `9c16c787eb3d638ee8683f2644ad01c0cfa21e39`. The API branch uses a separate worktree; Git-ignored formal reports remain in the source worktree and are supplied through `RESEARCH_REPORT_ROOT`.

## Existing interfaces

- `EXISTING_DASHBOARD_API: NO`
- `EXISTING_DASHBOARD_CONTRACT: NO`
- No tracked React Dashboard, HTTP server, FastAPI, Flask, Express, Hono, Fastify, Node package, artifact HTTP adapter, or catalog/manifest service existed at BASE_HEAD.
- The [current API contract](api-contract.md) defines the implemented read-only adapter; older planning documents are retained in Git history.
- `metadata.json` already contains a per-file `content_sha256` map. It is the official artifact integrity manifest, not an API-maintained index.

## Real run identity and layout

The latest complete determinism-repeat run is:

`reports/research/shenwan_sector_index/iteration1_20260924_163607_787266_utc/`

The preceding equivalent run is `iteration1_20260924_163106_040404_utc/`; both have identical SHA256 for their 29 research-content files. The v1 catalog lists both in descending run-ID order. It does not adapt the older Development baseline runs `20260924_145948_233618_utc` and `20260924_150613_787827_utc`.

At the run root:

- `metadata.json`: `run_id`, `phase=DEVELOPMENT`, `iteration=1`, `candidate_family=[D0,D1,D2,D3]`, `research_label=SECTOR_INDEX_RESEARCH_ONLY`, `executable=false`, `strict_pit=false`, `classification_admission=FIXED_CLASSIFICATION_RESEARCH`, `validation_access=SEALED`, `final_oos_access=SEALED`, disabled ETF/portfolio/LEVEL B flags, frozen protocol/split/prediction/snapshot hashes, `git_head`, `environment_changed`, and `content_sha256`.
- `candidate_summary.json`: `comparison` (four candidate rows containing official weighted RankIC, weighted spread, three horizon RankIC/spread means and `promotion_status`), `all_candidate_aggregate_metrics`, `review_priority`, `promotion_result`, and `d0_control_sha256`.

Each of `D0/` through `D3/` contains:

| File | Real structure | API use |
| --- | --- | --- |
| `aggregate_metrics.json` | Exactly 15 metric keys. Each has `valid_dates`, `null_dates`, `mean`, `median`, `std`, `min`, `max`. | Copy into three horizon `MetricStats` sets; compare with summary's copy. |
| `per_date_metrics.csv` | 1,500 rows; `ordinal,signal_date,horizon,metric,value,null_reason,valid_sector_count`. | Structural five-metric pivot per date × horizon; no metric recalculation. |
| `predictions.csv` | 37,200 rows; `ordinal,signal_date,sector_code,sector_name,horizon,prediction_score,cross_sectional_rank,fused_score,fused_rank,top5,realized_forward_return,label_end,exclusion_reason,training_observations,training_valid_days,training_label_cutoff`. | Structural three-horizon pivot per date × sector. `sector_name` comes from this official file. |
| `training_diagnostics.csv` | 300 rows; `ordinal,signal_date,horizon,status,reason,train_start,label_cutoff,first_train_origin,last_train_origin,last_train_label_end,training_candidate_days,training_valid_days,training_observations,valid_sector_count,missing_factor_exclusions,missing_label_exclusions,numerical_failures,leakage_checks`. | Descriptive min/median/max and exclusion counts only. |
| `data_quality_diagnostics.json` | Date counts, skipped list, exclusions, numeric failures, source-invalid counts and leakage checks. | Date counts and insufficient-training count. |
| `transformation_diagnostics.json` | Hashes, zero-std count, demean residual and optional 300-row scaler/target evidence arrays. | Transformation diagnostics; null where not applicable. |
| `per_date_predictions.csv` | 12,400 date × sector rows; three predictions, fused fields, labels and training counts. | Audited but not read by v1 responses: `predictions.csv` already contains all response fields, including the official sector name, at original numeric precision. |

The five legacy D0 files are byte-identical to the original frozen baseline. The baseline directories have no Iteration-1 root `candidate_summary.json`, four-candidate family, per-date wide file or transformation diagnostics, so they are not silently presented as v1 runs. The API never opens Validation or Final OOS performance files.

The frozen candidate definitions are in `research/development_iteration1_protocol.py`; the protocol's SHA256 is pinned in the adapter and checked against every admitted `metadata.json`. The API's `TRAIN_ONLY_STANDARDIZATION` spelling normalizes the protocol's `TRAIN_ONLY_COLUMN_STANDARDIZATION`. The artifact's `NOT PROMOTED` is normalized to API `NOT_PROMOTED`. Neither mapping recomputes a candidate decision.

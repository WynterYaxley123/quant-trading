import { z } from 'zod'
import {
  ARTIFACT_FILES, CANDIDATES, METRIC_NAMES, PREDICTION_HASH,
  PROTOCOL_HASH, SECTOR_SNAPSHOT, SPLIT_HASH,
} from '../protocol.js'

const sha = z.string().regex(/^[a-f0-9]{64}$/)
const metricValue = z.number().finite().nullable()
export const metricStatsSchema = z.object({
  valid_dates: z.number().int().min(0).max(100),
  null_dates: z.number().int().min(0).max(100),
  mean: metricValue, median: metricValue, std: metricValue,
  min: metricValue, max: metricValue,
}).superRefine((value, ctx) => {
  if (value.valid_dates + value.null_dates !== 100) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'date count is not 100' })
  }
  const statistics = [value.mean, value.median, value.std, value.min, value.max]
  if ((value.valid_dates === 0 && !statistics.every((item) => item === null))
      || (value.valid_dates > 0 && statistics.some((item) => item === null))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'missing statistics and valid_dates disagree' })
  }
})

export const aggregateSchema = z.record(metricStatsSchema).superRefine((value, ctx) => {
  if (Object.keys(value).length !== 15 || METRIC_NAMES.some((name) => !(name in value))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'metric names differ from frozen 15' })
  }
})

const candidateHashes = z.record(sha).superRefine((value, ctx) => {
  if (Object.keys(value).length !== ARTIFACT_FILES.length || ARTIFACT_FILES.some((name) => !(name in value))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'candidate artifact hash manifest incomplete' })
  }
})

export const metadataSchema = z.object({
  run_id: z.string().regex(/^iteration1_\d{8}_\d{6}_\d{6}_utc$/),
  research_label: z.literal('SECTOR_INDEX_RESEARCH_ONLY'),
  phase: z.literal('DEVELOPMENT'),
  iteration: z.literal(1),
  candidate_family: z.tuple([z.literal('D0'), z.literal('D1'), z.literal('D2'), z.literal('D3')]),
  candidate_family_size: z.literal(4), new_candidate_count: z.literal(3),
  executable: z.literal(false), strict_pit: z.literal(false),
  classification_admission: z.literal('FIXED_CLASSIFICATION_RESEARCH'),
  validation_access: z.literal('SEALED'), final_oos_access: z.literal('SEALED'),
  etf_execution: z.literal('DISABLED'), synthetic_portfolio: z.literal('DISABLED'),
  level_b: z.literal('DISABLED'), synthetic_portfolio_config_hash: z.null(),
  split_policy_hash: z.literal(SPLIT_HASH),
  prediction_config_hash: z.literal(PREDICTION_HASH),
  development_iteration1_protocol_hash: z.literal(PROTOCOL_HASH),
  sector_snapshot_id: z.literal(SECTOR_SNAPSHOT),
  git_head: z.string().regex(/^[a-f0-9]{40}$/),
  environment_changed: z.boolean().nullable(),
  development_ordinals: z.tuple([z.literal(1), z.literal(100)]),
  notices: z.array(z.string()),
  content_sha256: z.object({
    'candidate_summary.json': sha,
    D0: candidateHashes, D1: candidateHashes, D2: candidateHashes, D3: candidateHashes,
  }).strict(),
}).superRefine((value, ctx) => {
  if (!value.notices.includes('NOT TRADABLE')) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'NOT TRADABLE notice absent' })
  }
})

export const comparisonSchema = z.object({
  candidate: z.enum(CANDIDATES),
  Weighted_RankIC: metricValue, Weighted_Spread: metricValue,
  RankIC_10: metricValue, RankIC_40: metricValue, RankIC_120: metricValue,
  Spread_10: metricValue, Spread_40: metricValue, Spread_120: metricValue,
  promotion_status: z.enum(['DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW', 'NOT PROMOTED']),
})

export const summarySchema = z.object({
  comparison: z.array(comparisonSchema).length(4),
  all_candidate_aggregate_metrics: z.object({
    D0: aggregateSchema, D1: aggregateSchema, D2: aggregateSchema, D3: aggregateSchema,
  }),
  review_priority: z.array(z.enum(CANDIDATES)),
  promotion_result: z.union([z.array(z.enum(CANDIDATES)), z.literal('NO_ITERATION1_CANDIDATE_PROMOTED')]),
  d0_control_sha256: z.record(sha),
}).superRefine((value, ctx) => {
  const ids = value.comparison.map((row) => row.candidate)
  if (new Set(ids).size !== 4 || CANDIDATES.some((id) => !ids.includes(id))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'comparison candidate family differs from D0-D3' })
  }
})

export const qualitySchema = z.object({
  attempted_development_dates: z.number().int().min(0),
  successful_dates: z.number().int().min(0),
  skipped_dates: z.array(z.unknown()),
  missing_factor_exclusions: z.number().int().min(0),
  missing_label_exclusions: z.number().int().min(0),
  numerical_failures: z.number().int().min(0),
  insufficient_training_cases: z.number().int().min(0),
})

const scalerRow = z.object({
  ordinal: z.number().int().min(1).max(100),
  horizon: z.union([z.literal(10), z.literal(40), z.literal(120)]),
  scaler_training_rows: z.number().int().min(1),
  per_feature_mean: z.array(z.number().finite()).length(19),
  per_feature_std: z.array(z.number().finite().nonnegative()).length(19),
  zero_std_features: z.array(z.number().int().min(0).max(18)),
})
const targetRow = z.object({
  ordinal: z.number().int().min(1).max(100),
  horizon: z.union([z.literal(10), z.literal(40), z.literal(120)]),
  training_dates: z.number().int().min(1),
  max_abs_mean: z.number().finite().nonnegative(),
})
export const transformSchema = z.object({
  zero_std_feature_occurrences: z.number().int().min(0),
  scaler_diagnostic_hash: sha.nullable(), target_diagnostic_hash: sha.nullable(),
  demean_residual_max_abs_mean: z.number().finite().nonnegative().nullable(),
  scaler_diagnostics: z.array(scalerRow).optional(), target_diagnostics: z.array(targetRow).optional(),
})

export type RunMetadata = z.infer<typeof metadataSchema>
export type CandidateSummary = z.infer<typeof summarySchema>
export type AggregateMetrics = z.infer<typeof aggregateSchema>
export type MetricStatsArtifact = z.infer<typeof metricStatsSchema>

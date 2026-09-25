import { z } from 'zod';

/**
 * READ-ONLY Research Data API V1 — frozen contract types.
 *
 * Every real API response is wrapped in the success envelope
 * `{ schemaVersion: "1.0.0", data: ... }` or the error envelope
 * `{ schemaVersion: "1.0.0", error: { code, message } }`.
 *
 * All payloads are untrusted input: they are runtime-validated with zod
 * before being handed to UI code. `any` is intentionally never used here.
 */

export const SCHEMA_VERSION = '1.0.0';

/* ------------------------------------------------------------------ */
/* Envelopes                                                           */
/* ------------------------------------------------------------------ */

export const apiErrorEnvelopeSchema = z.object({
  schemaVersion: z.string(),
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
});
export type ApiErrorEnvelope = z.infer<typeof apiErrorEnvelopeSchema>;

/* ------------------------------------------------------------------ */
/* Shared primitives                                                   */
/* ------------------------------------------------------------------ */

/** A numeric metric that may be unavailable. */
export const nullableNumber = z.number().nullable();
export type NullableNumber = z.infer<typeof nullableNumber>;

/** An ISO calendar date, e.g. "2025-01-06". */
export const isoDateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'expected ISO date YYYY-MM-DD');

/** Signal ordinals like "E001" .. "E100". */
export const ordinalSchema = z
  .string()
  .regex(/^E\d{3}$/, 'expected ordinal like E001');

export const HORIZONS = [10, 40, 120] as const;
export const horizonSchema = z.union([z.literal(10), z.literal(40), z.literal(120)]);
export type Horizon = (typeof HORIZONS)[number];

export const METRIC_KEYS = [
  'ic',
  'rankIc',
  'top5ForwardReturn',
  'universeForwardReturn',
  'top5MinusUniverse',
] as const;
export const metricKeySchema = z.enum(METRIC_KEYS);
export type MetricKey = (typeof METRIC_KEYS)[number];

/* ------------------------------------------------------------------ */
/* Health / Capabilities / Research status                             */
/* ------------------------------------------------------------------ */

export const healthSchema = z.object({
  status: z.string(),
  readOnly: z.boolean(),
  sourceOfTruth: z.string(),
});
export type Health = z.infer<typeof healthSchema>;

export const capabilitiesSchema = z.object({
  readOnly: z.boolean(),
  mutations: z.boolean(),
  candidateComparison: z.boolean(),
  developmentExplorer: z.boolean(),
  sectorExplorer: z.boolean(),
  diagnostics: z.boolean(),
  portfolio: z.boolean(),
  execution: z.boolean(),
  etf: z.boolean(),
  validationAvailable: z.boolean(),
  finalOosAvailable: z.boolean(),
});
export type Capabilities = z.infer<typeof capabilitiesSchema>;

export const researchStatusSchema = z.object({
  researchLabel: z.string(),
  phase: z.string(),
  validation: z.string(),
  finalOos: z.string(),
  executable: z.boolean(),
  tradable: z.boolean(),
  strictPit: z.boolean(),
  classificationAdmission: z.string(),
  etf: z.string(),
  syntheticPortfolio: z.string(),
  levelB: z.string(),
  sourceOfTruth: z.string(),
});
export type ResearchStatus = z.infer<typeof researchStatusSchema>;

/* ------------------------------------------------------------------ */
/* Runs                                                                */
/* ------------------------------------------------------------------ */

export const runSummarySchema = z.object({
  runId: z.string().min(1),
  phase: z.string(),
  iteration: z.number().int().nonnegative(),
  candidateIds: z.array(z.string()),
  researchLabel: z.string(),
  gitCommit: z.string(),
  protocolHash: z.string(),
  sectorSnapshotId: z.string(),
});
export type RunSummary = z.infer<typeof runSummarySchema>;

export const runDetailSchema = runSummarySchema.extend({
  executable: z.boolean(),
  strictPit: z.boolean(),
  classificationAdmission: z.string(),
  splitPolicyHash: z.string(),
  predictionConfigHash: z.string(),
  developmentIteration1ProtocolHash: z.string(),
  syntheticPortfolioConfigHash: z.string(),
  validation: z.string(),
  finalOos: z.string(),
});
export type RunDetail = z.infer<typeof runDetailSchema>;

export const runListSchema = z.object({
  items: z.array(runSummarySchema),
});
export type RunList = z.infer<typeof runListSchema>;

/* ------------------------------------------------------------------ */
/* Candidates                                                          */
/* ------------------------------------------------------------------ */

export const promotionStatusSchema = z.union([
  z.literal('DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW'),
  z.literal('NOT_PROMOTED'),
  z.null(),
]);
export type PromotionStatus = z.infer<typeof promotionStatusSchema>;

export const xPreprocessingSchema = z.union([
  z.literal('NONE'),
  z.literal('TRAIN_ONLY_STANDARDIZATION'),
  z.string(),
]);
export type XPreprocessing = z.infer<typeof xPreprocessingSchema>;

export const trainingTargetSchema = z.union([
  z.literal('ABSOLUTE_FORWARD_RETURN'),
  z.literal('CROSS_SECTIONAL_EXCESS_FORWARD_RETURN'),
  z.string(),
]);
export type TrainingTarget = z.infer<typeof trainingTargetSchema>;

export const candidateSummarySchema = z.object({
  candidateId: z.string().min(1),
  xPreprocessing: xPreprocessingSchema,
  trainingTarget: trainingTargetSchema,
  weightedRankIc: nullableNumber,
  weightedSpread: nullableNumber,
  promotionStatus: promotionStatusSchema,
});
export type CandidateSummary = z.infer<typeof candidateSummarySchema>;

export const candidateListSchema = z.object({
  items: z.array(candidateSummarySchema),
});
export type CandidateList = z.infer<typeof candidateListSchema>;

/* ------------------------------------------------------------------ */
/* Metrics                                                             */
/* ------------------------------------------------------------------ */

export const metricStatsSchema = z.object({
  validDates: z.number().int().nonnegative(),
  mean: nullableNumber,
  median: nullableNumber,
  std: nullableNumber,
  min: nullableNumber,
  max: nullableNumber,
});
export type MetricStats = z.infer<typeof metricStatsSchema>;

export const horizonMetricsSchema = z.object({
  horizon: horizonSchema,
  ic: metricStatsSchema,
  rankIc: metricStatsSchema,
  top5ForwardReturn: metricStatsSchema,
  universeForwardReturn: metricStatsSchema,
  top5MinusUniverse: metricStatsSchema,
});
export type HorizonMetrics = z.infer<typeof horizonMetricsSchema>;

export const candidateMetricsSchema = z.object({
  candidateId: z.string().min(1),
  weightedRankIc: nullableNumber,
  weightedSpread: nullableNumber,
  horizons: z.array(horizonMetricsSchema),
});
export type CandidateMetrics = z.infer<typeof candidateMetricsSchema>;

/* ------------------------------------------------------------------ */
/* Daily metrics (development explorer)                                */
/* ------------------------------------------------------------------ */

export const dailyMetricSchema = z.object({
  ordinal: ordinalSchema,
  signalDate: isoDateSchema,
  horizon: horizonSchema,
  ic: nullableNumber,
  rankIc: nullableNumber,
  top5ForwardReturn: nullableNumber,
  universeForwardReturn: nullableNumber,
  top5MinusUniverse: nullableNumber,
});
export type DailyMetric = z.infer<typeof dailyMetricSchema>;

export const dailyMetricListSchema = z.object({
  items: z.array(dailyMetricSchema),
});
export type DailyMetricList = z.infer<typeof dailyMetricListSchema>;

/* ------------------------------------------------------------------ */
/* Predictions (sector explorer)                                       */
/* ------------------------------------------------------------------ */

export const predictionSchema = z.object({
  ordinal: ordinalSchema,
  signalDate: isoDateSchema,
  sectorCode: z.string().min(1),
  sectorName: z.string().nullable(),
  pred10: nullableNumber,
  pred40: nullableNumber,
  pred120: nullableNumber,
  fusedScore: nullableNumber,
  fusedRank: nullableNumber,
  top5: z.boolean(),
  realizedForwardReturn10: nullableNumber,
  realizedForwardReturn40: nullableNumber,
  realizedForwardReturn120: nullableNumber,
  labelEnd10: isoDateSchema.nullable(),
  labelEnd40: isoDateSchema.nullable(),
  labelEnd120: isoDateSchema.nullable(),
});
export type Prediction = z.infer<typeof predictionSchema>;

export const predictionPageSchema = z.object({
  items: z.array(predictionSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
});
export type PredictionPage = z.infer<typeof predictionPageSchema>;

export interface PredictionsQuery {
  date: string;
  top5?: boolean;
  limit?: number;
  offset?: number;
}

/* ------------------------------------------------------------------ */
/* Diagnostics                                                         */
/* ------------------------------------------------------------------ */

export const nullableInt = z.number().int().nonnegative().nullable();

export const horizonDiagnosticsSchema = z.object({
  horizon: horizonSchema,
  trainingObservations: nullableInt,
  validTrainingDates: nullableInt,
  validSectorCounts: nullableInt,
  missingFactorExclusions: nullableInt,
  missingLabelExclusions: nullableInt,
  numericalFailures: nullableInt,
  insufficientTrainingCases: nullableInt,
  zeroStdFeatureOccurrences: nullableInt,
  scalerDiagnosticHash: z.string().nullable(),
  demeanResidualMaxAbsMean: nullableNumber,
  targetDiagnosticHash: z.string().nullable(),
});
export type HorizonDiagnostics = z.infer<typeof horizonDiagnosticsSchema>;

export const diagnosticsSchema = z.object({
  attemptedDates: nullableInt,
  successfulDates: nullableInt,
  skippedDates: nullableInt,
  horizons: z.array(horizonDiagnosticsSchema),
});
export type Diagnostics = z.infer<typeof diagnosticsSchema>;

/* ------------------------------------------------------------------ */
/* Integrity                                                           */
/* ------------------------------------------------------------------ */

export const integritySchema = z.object({
  researchLabel: z.string(),
  phase: z.string(),
  validation: z.string(),
  finalOos: z.string(),
  universe: z.string(),
  sectorCount: z.number().int().nonnegative(),
  featureCount: z.number().int().nonnegative(),
  alpha: z.number(),
  horizons: z.array(z.number()),
  fusion: z.array(z.number()),
  topK: z.number().int().positive(),
  splitPolicyHash: z.string(),
  predictionConfigHash: z.string(),
  developmentIteration1ProtocolHash: z.string(),
  sectorSnapshotId: z.string(),
  executable: z.boolean(),
  strictPit: z.boolean(),
  etf: z.string(),
  syntheticPortfolio: z.string(),
  levelB: z.string(),
});
export type Integrity = z.infer<typeof integritySchema>;

/* ------------------------------------------------------------------ */
/* Data port — the single seam between UI and data source              */
/* ------------------------------------------------------------------ */

export interface DailyMetricsQuery {
  horizon?: Horizon;
}

export interface ResearchDataPort {
  getHealth(signal?: AbortSignal): Promise<Health>;
  getCapabilities(signal?: AbortSignal): Promise<Capabilities>;
  getResearchStatus(signal?: AbortSignal): Promise<ResearchStatus>;
  getRuns(signal?: AbortSignal): Promise<RunSummary[]>;
  getRun(runId: string, signal?: AbortSignal): Promise<RunDetail>;
  getCandidates(runId: string, signal?: AbortSignal): Promise<CandidateSummary[]>;
  getMetrics(
    runId: string,
    candidateId: string,
    signal?: AbortSignal,
  ): Promise<CandidateMetrics>;
  getDailyMetrics(
    runId: string,
    candidateId: string,
    query?: DailyMetricsQuery,
    signal?: AbortSignal,
  ): Promise<DailyMetric[]>;
  getPredictions(
    runId: string,
    candidateId: string,
    query: PredictionsQuery,
    signal?: AbortSignal,
  ): Promise<PredictionPage>;
  getDiagnostics(
    runId: string,
    candidateId: string,
    signal?: AbortSignal,
  ): Promise<Diagnostics>;
  getIntegrity(runId: string, signal?: AbortSignal): Promise<Integrity>;
}

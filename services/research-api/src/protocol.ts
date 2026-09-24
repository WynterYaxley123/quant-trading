/** Pinned copy of the committed Iteration-1 protocol identity, never a model. */
export const SCHEMA_VERSION = '1.0.0' as const
export const PROTOCOL_HASH = 'f2080f56a3f4a77ff983d5b9cc14c0f1427f4d2c84fb1d9fc89b9a2a3cb12125'
export const SPLIT_HASH = '3b6b2d754211169039439c8b377fd9eb26d5cb5db0f80d62cffc1d19c81a7038'
export const PREDICTION_HASH = '64d5fabe6f194f416c6576d4da9cd5e2fb2ad1e699e2c074047960addaa0ed8c'
export const SECTOR_SNAPSHOT = '872bcbc2b1e59f70530f692de71fdd9c6225c37eab00483861264ed00454e500'
export const CANDIDATES = ['D0', 'D1', 'D2', 'D3'] as const
export type CandidateId = typeof CANDIDATES[number]
export const HORIZONS = [10, 40, 120] as const
export type Horizon = typeof HORIZONS[number]
export const METRIC_STEMS = [
  'IC', 'RankIC', 'Top5_forward_return', 'Universe_forward_return', 'Top5_minus_universe',
] as const
export const METRIC_NAMES = HORIZONS.flatMap((h) => METRIC_STEMS.map((stem) => `${stem}_${h}`))
export const CANDIDATE_DEFINITIONS: Record<CandidateId, {
  xPreprocessing: 'NONE' | 'TRAIN_ONLY_STANDARDIZATION'
  trainingTarget: 'ABSOLUTE_FORWARD_RETURN' | 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN'
}> = {
  D0: { xPreprocessing: 'NONE', trainingTarget: 'ABSOLUTE_FORWARD_RETURN' },
  D1: { xPreprocessing: 'TRAIN_ONLY_STANDARDIZATION', trainingTarget: 'ABSOLUTE_FORWARD_RETURN' },
  D2: { xPreprocessing: 'NONE', trainingTarget: 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN' },
  D3: { xPreprocessing: 'TRAIN_ONLY_STANDARDIZATION', trainingTarget: 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN' },
}
export const ARTIFACT_FILES = [
  'predictions.csv', 'per_date_metrics.csv', 'aggregate_metrics.json',
  'training_diagnostics.csv', 'data_quality_diagnostics.json',
  'per_date_predictions.csv', 'transformation_diagnostics.json',
] as const

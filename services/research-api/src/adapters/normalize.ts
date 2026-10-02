import { schemaError } from '../errors.js'
import { CANDIDATE_DEFINITIONS, CANDIDATES, HORIZONS, type CandidateId, type Horizon } from '../protocol.js'
import type {
  AggregateMetrics, CandidateSummary, MetricStatsArtifact, RunMetadata,
} from '../schemas/artifacts.js'
import type { DailyMetricRow, PredictionRow, TrainingRow } from '../schemas/csv.js'

export function runItem(meta: RunMetadata) {
  return {
    runId: meta.run_id, phase: meta.phase, iteration: meta.iteration,
    candidateIds: meta.candidate_family, researchLabel: meta.research_label,
    gitCommit: meta.git_head, protocolHash: meta.development_iteration1_protocol_hash,
    sectorSnapshotId: meta.sector_snapshot_id,
  }
}

export function runDetail(meta: RunMetadata) {
  return {
    ...runItem(meta), executable: meta.executable, strictPit: meta.strict_pit,
    classificationAdmission: meta.classification_admission,
    splitPolicyHash: meta.split_policy_hash,
    predictionConfigHash: meta.prediction_config_hash,
    developmentIteration1ProtocolHash: meta.development_iteration1_protocol_hash,
    syntheticPortfolioConfigHash: meta.synthetic_portfolio_config_hash,
    validation: meta.validation_access, finalOos: meta.final_oos_access,
  }
}

export function researchStatus(meta: RunMetadata | null) {
  if (!meta) return {
    artifactState: 'NOT_CONFIGURED' as const,
    researchLabel: 'SECTOR_INDEX_RESEARCH_ONLY', phase: 'NOT_CONFIGURED',
    validation: 'SEALED', finalOos: 'SEALED', executable: false, tradable: false,
    strictPit: false, classification: 'NOT_CONFIGURED', classificationAdmission: 'NOT_CONFIGURED',
    etf: 'DISABLED', syntheticPortfolio: 'DISABLED', levelB: 'DISABLED',
    sourceOfTruth: 'RESEARCH_ARTIFACTS' as const,
  }
  return {
    artifactState: 'AVAILABLE' as const,
    researchLabel: meta.research_label, phase: meta.phase,
    validation: meta.validation_access, finalOos: meta.final_oos_access,
    executable: meta.executable, tradable: false, strictPit: meta.strict_pit,
    classification: meta.classification_admission,
    classificationAdmission: meta.classification_admission,
    etf: meta.etf_execution, syntheticPortfolio: meta.synthetic_portfolio,
    levelB: meta.level_b, sourceOfTruth: 'RESEARCH_ARTIFACTS' as const,
  }
}

export function integrity(meta: RunMetadata) {
  return {
    researchLabel: meta.research_label, phase: meta.phase,
    validation: meta.validation_access, finalOos: meta.final_oos_access,
    environmentChanged: meta.environment_changed,
    gitCommit: meta.git_head,
    protocolHash: meta.development_iteration1_protocol_hash,
    classification: meta.classification_admission,
    classificationAdmission: meta.classification_admission,
    tradable: false,
    // The following values are a pinned representation of the committed
    // development_iteration1_protocol.py, gated by its SHA in metadataSchema.
    universe: 'U0_FIXED_124' as const, sectorCount: 124, featureCount: 19,
    alpha: 0.01, horizons: [...HORIZONS], fusion: [0.25, 0.50, 0.25], topK: 5,
    splitPolicyHash: meta.split_policy_hash,
    predictionConfigHash: meta.prediction_config_hash,
    developmentIteration1ProtocolHash: meta.development_iteration1_protocol_hash,
    syntheticPortfolioConfigHash: meta.synthetic_portfolio_config_hash,
    sectorSnapshotId: meta.sector_snapshot_id,
    executable: meta.executable, strictPit: meta.strict_pit,
    etf: meta.etf_execution, syntheticPortfolio: meta.synthetic_portfolio,
    levelB: meta.level_b,
  }
}

export function candidateItems(summary: CandidateSummary) {
  return CANDIDATES.map((candidateId) => {
    const row = summary.comparison.find((item) => item.candidate === candidateId)
    if (!row) schemaError('candidate_summary.json', `comparison missing ${candidateId}`)
    return {
      candidateId, ...CANDIDATE_DEFINITIONS[candidateId],
      weightedRankIc: row.Weighted_RankIC, weightedSpread: row.Weighted_Spread,
      // Official artifact spelling is "NOT PROMOTED"; this is enum normalization only.
      promotionStatus: row.promotion_status === 'NOT PROMOTED'
        ? 'NOT_PROMOTED' as const : row.promotion_status,
    }
  })
}

function stats(value: MetricStatsArtifact) {
  return {
    validDates: value.valid_dates, mean: value.mean, median: value.median,
    std: value.std, min: value.min, max: value.max,
  }
}

export function metricView(candidateId: CandidateId, aggregate: AggregateMetrics,
                           summary: CandidateSummary) {
  const row = summary.comparison.find((item) => item.candidate === candidateId)
  if (!row) schemaError('candidate_summary.json', `comparison missing ${candidateId}`)
  return {
    candidateId, weightedRankIc: row.Weighted_RankIC, weightedSpread: row.Weighted_Spread,
    horizons: HORIZONS.map((h) => ({
      horizon: h,
      ic: stats(aggregate[`IC_${h}`]), rankIc: stats(aggregate[`RankIC_${h}`]),
      top5ForwardReturn: stats(aggregate[`Top5_forward_return_${h}`]),
      universeForwardReturn: stats(aggregate[`Universe_forward_return_${h}`]),
      top5MinusUniverse: stats(aggregate[`Top5_minus_universe_${h}`]),
    })),
  }
}

export function dailyView(rows: DailyMetricRow[], context: string) {
  const grouped = new Map<string, {
    ordinal: number; signalDate: string; horizon: Horizon; values: Map<string, number | null>
  }>()
  const byOrdinal = new Map<number, string>()
  for (const row of rows) {
    const existingDate = byOrdinal.get(row.ordinal)
    if (existingDate !== undefined && existingDate !== row.signalDate) {
      schemaError(context, `ordinal ${row.ordinal} has multiple signal dates`)
    }
    byOrdinal.set(row.ordinal, row.signalDate)
    const key = `${row.ordinal}:${row.horizon}`
    let group = grouped.get(key)
    if (!group) {
      group = { ordinal: row.ordinal, signalDate: row.signalDate,
                horizon: row.horizon, values: new Map() }
      grouped.set(key, group)
    }
    if (group.values.has(row.metric)) schemaError(context, `duplicate ${key}/${row.metric}`)
    group.values.set(row.metric, row.value)
  }
  if (grouped.size !== 300 || byOrdinal.size !== 100) schemaError(context, 'incomplete Development daily grid')
  const output = [...grouped.values()].map((group) => {
    const h = group.horizon
    const names = [`IC_${h}`, `RankIC_${h}`, `Top5_forward_return_${h}`,
                   `Universe_forward_return_${h}`, `Top5_minus_universe_${h}`]
    if (group.values.size !== 5 || names.some((name) => !group.values.has(name))) {
      schemaError(context, `incomplete daily metric group E${String(group.ordinal).padStart(3, '0')}/${h}`)
    }
    return {
      ordinal: `E${String(group.ordinal).padStart(3, '0')}`,
      signalDate: group.signalDate, horizon: h,
      ic: group.values.get(`IC_${h}`)!, rankIc: group.values.get(`RankIC_${h}`)!,
      top5ForwardReturn: group.values.get(`Top5_forward_return_${h}`)!,
      universeForwardReturn: group.values.get(`Universe_forward_return_${h}`)!,
      top5MinusUniverse: group.values.get(`Top5_minus_universe_${h}`)!,
    }
  })
  return output.sort((a, b) => a.signalDate.localeCompare(b.signalDate) || a.horizon - b.horizon)
}

export function predictionView(rows: PredictionRow[], context: string) {
  const groups = new Map<string, PredictionRow[]>()
  const byOrdinal = new Map<number, string>()
  for (const row of rows) {
    const previous = byOrdinal.get(row.ordinal)
    if (previous !== undefined && previous !== row.signalDate) schemaError(context, 'ordinal date conflict')
    byOrdinal.set(row.ordinal, row.signalDate)
    const key = `${row.ordinal}:${row.sectorCode}`
    const group = groups.get(key) ?? []
    group.push(row)
    groups.set(key, group)
  }
  if (groups.size !== 12_400 || byOrdinal.size !== 100) schemaError(context, 'incomplete prediction grid')
  const output = [...groups.values()].map((group) => {
    const byHorizon = new Map(group.map((row) => [row.horizon, row]))
    if (group.length !== 3 || byHorizon.size !== 3 || HORIZONS.some((h) => !byHorizon.has(h))) {
      schemaError(context, 'prediction group lacks exactly three horizons')
    }
    const first = byHorizon.get(10)!
    if (group.some((row) => row.signalDate !== first.signalDate
        || row.sectorName !== first.sectorName || row.fusedScore !== first.fusedScore
        || row.fusedRank !== first.fusedRank || row.top5 !== first.top5)) {
      schemaError(context, 'fused score, rank, or single Top5 differs by horizon')
    }
    return {
      ordinal: `E${String(first.ordinal).padStart(3, '0')}`,
      signalDate: first.signalDate, sectorCode: first.sectorCode, sectorName: first.sectorName,
      pred10: byHorizon.get(10)!.predictionScore,
      pred40: byHorizon.get(40)!.predictionScore,
      pred120: byHorizon.get(120)!.predictionScore,
      fusedScore: first.fusedScore, fusedRank: first.fusedRank, top5: first.top5,
      realizedForwardReturn10: byHorizon.get(10)!.realizedForwardReturn,
      realizedForwardReturn40: byHorizon.get(40)!.realizedForwardReturn,
      realizedForwardReturn120: byHorizon.get(120)!.realizedForwardReturn,
      labelEnd10: byHorizon.get(10)!.labelEnd,
      labelEnd40: byHorizon.get(40)!.labelEnd,
      labelEnd120: byHorizon.get(120)!.labelEnd,
    }
  })
  const byDate = new Map<string, typeof output>()
  for (const item of output) {
    const group = byDate.get(item.signalDate) ?? []
    group.push(item)
    byDate.set(item.signalDate, group)
  }
  for (const [date, group] of byDate) {
    if (group.length !== 124 || group.filter((item) => item.top5).length !== 5) {
      schemaError(context, `${date} lacks fixed 124-sector / single Top5 coverage`)
    }
  }
  return output.sort((a, b) => a.signalDate.localeCompare(b.signalDate)
    || (a.fusedRank ?? Number.MAX_SAFE_INTEGER) - (b.fusedRank ?? Number.MAX_SAFE_INTEGER)
    || a.sectorCode.localeCompare(b.sectorCode))
}

function descriptive(values: number[]) {
  if (!values.length) return { min: null, median: null, max: null }
  const sorted = [...values].sort((a, b) => a - b)
  const center = Math.floor(sorted.length / 2)
  return {
    min: sorted[0],
    median: sorted.length % 2 ? sorted[center] : (sorted[center - 1] + sorted[center]) / 2,
    max: sorted[sorted.length - 1],
  }
}

export function diagnosticView(rows: TrainingRow[], quality: {
  attempted_development_dates: number; successful_dates: number; skipped_dates: unknown[]
  insufficient_training_cases: number
}, transform: {
  zero_std_feature_occurrences: number; scaler_diagnostic_hash: string | null
  demean_residual_max_abs_mean: number | null; target_diagnostic_hash: string | null
}, context: string) {
  if (quality.attempted_development_dates !== 100
      || quality.successful_dates + quality.skipped_dates.length !== quality.attempted_development_dates) {
    schemaError(context, 'attempted/successful/skipped date counts disagree')
  }
  return {
    attemptedDates: quality.attempted_development_dates,
    successfulDates: quality.successful_dates,
    skippedDates: quality.skipped_dates.length,
    horizons: HORIZONS.map((h) => {
      const horizonRows = rows.filter((row) => row.horizon === h)
      if (horizonRows.length !== 100 || new Set(horizonRows.map((row) => row.ordinal)).size !== 100) {
        schemaError(context, `training grid incomplete for horizon ${h}`)
      }
      return {
        horizon: h,
        trainingObservations: descriptive(horizonRows.map((row) => row.trainingObservations)),
        validTrainingDates: descriptive(horizonRows.map((row) => row.validTrainingDates)),
        validSectorCounts: descriptive(horizonRows.map((row) => row.validSectorCount)),
        missingFactorExclusions: horizonRows.reduce((sum, row) => sum + row.missingFactorExclusions, 0),
        missingLabelExclusions: horizonRows.reduce((sum, row) => sum + row.missingLabelExclusions, 0),
        numericalFailures: horizonRows.reduce((sum, row) => sum + row.numericalFailures, 0),
        insufficientTrainingCases: horizonRows.filter((row) => row.reason === 'insufficient_training').length,
      }
    }),
    zeroStdFeatureOccurrences: transform.scaler_diagnostic_hash === null
      ? null : transform.zero_std_feature_occurrences,
    scalerDiagnosticHash: transform.scaler_diagnostic_hash,
    demeanResidualMaxAbsMean: transform.target_diagnostic_hash === null
      ? null : transform.demean_residual_max_abs_mean,
    targetDiagnosticHash: transform.target_diagnostic_hash,
  }
}

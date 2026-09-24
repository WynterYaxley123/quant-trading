import { parse } from 'csv-parse/sync'
import { schemaError } from '../errors.js'
import type { Horizon } from '../protocol.js'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const SECTOR_CODE = /^\d{6}$/

export function isoDate(value: string, context: string): string {
  if (!ISO_DATE.test(value) || Number.isNaN(Date.parse(`${value}T00:00:00Z`))
      || new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) !== value) {
    schemaError(context, `invalid ISO date: ${value}`)
  }
  return value
}

export function requiredString(value: string | undefined, context: string): string {
  if (value === undefined || value === '') schemaError(context, 'required text missing')
  return value
}

export function nullableString(value: string | undefined): string | null {
  return value === undefined || value === '' ? null : value
}

function nullableDate(value: string | undefined, context: string): string | null {
  const date = nullableString(value)
  return date === null ? null : isoDate(date, context)
}

export function integer(value: string | undefined, context: string, min = 0): number {
  if (value === undefined || !/^(0|[1-9]\d*)$/.test(value)) schemaError(context, `invalid integer: ${value}`)
  const parsed = Number(value)
  if (!Number.isSafeInteger(parsed) || parsed < min) schemaError(context, `integer out of range: ${value}`)
  return parsed
}

function nullableInteger(value: string | undefined, context: string, min = 0): number | null {
  return value === undefined || value === '' ? null : integer(value, context, min)
}

export function numeric(value: string | undefined, context: string, nullable = false): number | null {
  if (value === undefined || value === '') {
    if (nullable) return null
    schemaError(context, 'required number missing')
  }
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)) {
    schemaError(context, `invalid number: ${value}`)
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) schemaError(context, `non-finite number: ${value}`)
  return parsed
}

export function boolean(value: string | undefined, context: string): boolean {
  if (value === 'True' || value === 'true') return true
  if (value === 'False' || value === 'false') return false
  schemaError(context, `invalid boolean: ${value}`)
}

export function horizon(value: string | undefined, context: string): Horizon {
  const parsed = integer(value, context, 1)
  if (parsed !== 10 && parsed !== 40 && parsed !== 120) schemaError(context, `invalid horizon: ${value}`)
  return parsed
}

export function ordinal(value: string | undefined, context: string): number {
  const parsed = integer(value, context, 1)
  if (parsed > 100) schemaError(context, `Development ordinal outside E001-E100: ${value}`)
  return parsed
}

export function sectorCode(value: string | undefined, context: string): string {
  if (value === undefined || !SECTOR_CODE.test(value)) schemaError(context, `invalid sector code: ${value}`)
  return value
}

export function csvRows(text: string, required: readonly string[], context: string): Record<string, string>[] {
  let rows: Record<string, string>[]
  try {
    rows = parse(text, {
      bom: true,
      columns: (header: string[]) => {
        if (new Set(header).size !== header.length || required.some((name) => !header.includes(name))) {
          throw new Error(`missing or duplicate CSV header; required: ${required.join(',')}`)
        }
        return header
      },
      skip_empty_lines: false,
      relax_column_count: false,
    }) as Record<string, string>[]
  } catch (error) {
    schemaError(context, error instanceof Error ? error.message : 'CSV parse failed')
  }
  if (!Array.isArray(rows)) schemaError(context, 'CSV rows missing')
  return rows
}

export const DAILY_COLUMNS = [
  'ordinal', 'signal_date', 'horizon', 'metric', 'value', 'null_reason', 'valid_sector_count',
] as const
export interface DailyMetricRow {
  ordinal: number; signalDate: string; horizon: Horizon
  metric: string; value: number | null; nullReason: string | null; validSectorCount: number
}
export function dailyMetricRows(text: string, context: string): DailyMetricRow[] {
  const rows = csvRows(text, DAILY_COLUMNS, context)
  if (rows.length !== 1500) schemaError(context, `expected 1500 metric rows, got ${rows.length}`)
  return rows.map((row, i) => {
    const at = `${context} row ${i + 2}`
    const parsedHorizon = horizon(row.horizon, `${at} horizon`)
    const metric = requiredString(row.metric, `${at} metric`)
    if (!['IC', 'RankIC', 'Top5_forward_return', 'Universe_forward_return',
          'Top5_minus_universe'].some((stem) => metric === `${stem}_${parsedHorizon}`)) {
      schemaError(at, `unexpected metric: ${metric}`)
    }
    return {
      ordinal: ordinal(row.ordinal, `${at} ordinal`),
      signalDate: isoDate(requiredString(row.signal_date, `${at} signal_date`), at),
      horizon: parsedHorizon, metric,
      value: numeric(row.value, `${at} value`, true), nullReason: nullableString(row.null_reason),
      validSectorCount: integer(row.valid_sector_count, `${at} valid_sector_count`),
    }
  })
}

export const PREDICTION_COLUMNS = [
  'ordinal', 'signal_date', 'sector_code', 'sector_name', 'horizon',
  'prediction_score', 'cross_sectional_rank', 'fused_score', 'fused_rank',
  'top5', 'realized_forward_return', 'label_end', 'exclusion_reason',
  'training_observations', 'training_valid_days', 'training_label_cutoff',
] as const
export interface PredictionRow {
  ordinal: number; signalDate: string; sectorCode: string; sectorName: string | null
  horizon: Horizon; predictionScore: number | null; fusedScore: number | null
  fusedRank: number | null; top5: boolean; realizedForwardReturn: number | null
  labelEnd: string | null
}
export function predictionRows(text: string, context: string): PredictionRow[] {
  const rows = csvRows(text, PREDICTION_COLUMNS, context)
  if (rows.length !== 37_200) schemaError(context, `expected 37200 prediction rows, got ${rows.length}`)
  return rows.map((row, i) => {
    const at = `${context} row ${i + 2}`
    const name = nullableString(row.sector_name)
    nullableInteger(row.cross_sectional_rank, `${at} cross_sectional_rank`, 1)
    nullableString(row.exclusion_reason)
    integer(row.training_observations, `${at} training_observations`)
    integer(row.training_valid_days, `${at} training_valid_days`)
    nullableDate(row.training_label_cutoff, `${at} training_label_cutoff`)
    return {
      ordinal: ordinal(row.ordinal, `${at} ordinal`),
      signalDate: isoDate(requiredString(row.signal_date, `${at} signal_date`), at),
      sectorCode: sectorCode(row.sector_code, at), sectorName: name,
      horizon: horizon(row.horizon, at),
      predictionScore: numeric(row.prediction_score, `${at} prediction_score`, true),
      fusedScore: numeric(row.fused_score, `${at} fused_score`, true),
      fusedRank: nullableInteger(row.fused_rank, `${at} fused_rank`, 1),
      top5: boolean(row.top5, at),
      realizedForwardReturn: numeric(row.realized_forward_return, `${at} realized_forward_return`, true),
      labelEnd: nullableDate(row.label_end, `${at} label_end`),
    }
  })
}

export const TRAINING_COLUMNS = [
  'ordinal', 'signal_date', 'horizon', 'status', 'reason', 'train_start',
  'label_cutoff', 'first_train_origin', 'last_train_origin', 'last_train_label_end',
  'training_candidate_days', 'training_valid_days', 'training_observations',
  'valid_sector_count', 'missing_factor_exclusions', 'missing_label_exclusions',
  'numerical_failures', 'leakage_checks',
] as const
export interface TrainingRow {
  ordinal: number; signalDate: string; horizon: Horizon; status: 'success' | 'skipped'
  reason: string | null
  trainingObservations: number; validTrainingDates: number; validSectorCount: number
  missingFactorExclusions: number; missingLabelExclusions: number; numericalFailures: number
}
export function trainingRows(text: string, context: string): TrainingRow[] {
  const rows = csvRows(text, TRAINING_COLUMNS, context)
  if (rows.length !== 300) schemaError(context, `expected 300 training rows, got ${rows.length}`)
  return rows.map((row, i) => {
    const at = `${context} row ${i + 2}`
    if (row.status !== 'success' && row.status !== 'skipped') schemaError(at, `invalid status: ${row.status}`)
    for (const column of ['train_start', 'label_cutoff', 'first_train_origin',
                          'last_train_origin', 'last_train_label_end'] as const) {
      nullableDate(row[column], `${at} ${column}`)
    }
    integer(row.training_candidate_days, `${at} training_candidate_days`)
    integer(row.leakage_checks, `${at} leakage_checks`)
    return {
      ordinal: ordinal(row.ordinal, at), signalDate: isoDate(requiredString(row.signal_date, at), at),
      horizon: horizon(row.horizon, at), status: row.status,
      reason: nullableString(row.reason),
      trainingObservations: integer(row.training_observations, at),
      validTrainingDates: integer(row.training_valid_days, at),
      validSectorCount: integer(row.valid_sector_count, at),
      missingFactorExclusions: integer(row.missing_factor_exclusions, at),
      missingLabelExclusions: integer(row.missing_label_exclusions, at),
      numericalFailures: integer(row.numerical_failures, at),
    }
  })
}

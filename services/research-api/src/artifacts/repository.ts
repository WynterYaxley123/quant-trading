import { isDeepStrictEqual } from 'node:util'
import { z } from 'zod'
import { ApiError, schemaError } from '../errors.js'
import { ARTIFACT_FILES, CANDIDATES, type CandidateId } from '../protocol.js'
import {
  aggregateSchema, metadataSchema, qualitySchema, summarySchema, transformSchema,
  type AggregateMetrics, type CandidateSummary, type RunMetadata,
} from '../schemas/artifacts.js'
import { dailyMetricRows, predictionRows, trainingRows } from '../schemas/csv.js'
import { ArtifactStorage, assertSafeSegment } from './storage.js'

const COLLECTION = 'shenwan_sector_index'
const RUN_ID = /^iteration1_\d{8}_\d{6}_\d{6}_utc$/

function parseJson<T extends z.ZodTypeAny>(text: string, schema: T, context: string): z.infer<T> {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    schemaError(context, `invalid JSON: ${String(error)}`)
  }
  const result = schema.safeParse(value)
  if (!result.success) {
    schemaError(context, result.error.issues.map((issue) =>
      `${issue.path.join('.') || 'root'}: ${issue.message}`).join('; '))
  }
  return result.data
}

function isSealedPhase(value: unknown): boolean {
  return typeof value === 'string' && /^(?:validation|final[_ -]?oos|oos)$/i.test(value)
}

export class ArtifactRepository {
  private readonly storage: ArtifactStorage

  constructor(root: string) {
    this.storage = new ArtifactStorage(root)
  }

  private checkRunId(runId: string): void {
    assertSafeSegment(runId)
    if (isSealedPhase(runId)) throw new ApiError('SEALED_PHASE', 403, 'Sealed phase is unavailable')
    if (!RUN_ID.test(runId)) throw new ApiError('RUN_NOT_FOUND', 404, 'Research run not found')
  }

  checkCandidateId(candidateId: string): CandidateId {
    assertSafeSegment(candidateId)
    if (!CANDIDATES.includes(candidateId as CandidateId)) {
      throw new ApiError('CANDIDATE_NOT_FOUND', 404, 'Research candidate not found')
    }
    return candidateId as CandidateId
  }

  async metadata(runId: string): Promise<RunMetadata> {
    this.checkRunId(runId)
    const context = `${runId}/metadata.json`
    const text = await this.storage.read([COLLECTION, runId, 'metadata.json'], null, 'RUN_NOT_FOUND')
    let raw: unknown
    try {
      raw = JSON.parse(text)
    } catch (error) {
      schemaError(context, `invalid JSON: ${String(error)}`)
    }
    if (raw && typeof raw === 'object' && 'phase' in raw
        && isSealedPhase((raw as { phase: unknown }).phase)) {
      throw new ApiError('SEALED_PHASE', 403, 'Sealed phase is unavailable')
    }
    const meta = parseJson(text, metadataSchema, context)
    if (meta.run_id !== runId) schemaError(context, 'run_id differs from directory name')
    return meta
  }

  async summary(meta: RunMetadata): Promise<CandidateSummary> {
    const name = 'candidate_summary.json'
    const context = `${meta.run_id}/${name}`
    const text = await this.storage.read(
      [COLLECTION, meta.run_id, name], meta.content_sha256[name],
    )
    return parseJson(text, summarySchema, context)
  }

  async candidateFile(meta: RunMetadata, candidateId: CandidateId,
                      name: typeof ARTIFACT_FILES[number]): Promise<string> {
    const hash = meta.content_sha256[candidateId][name]
    if (!hash) schemaError(`${meta.run_id}/metadata.json`, `missing SHA256 for ${candidateId}/${name}`)
    return this.storage.read([COLLECTION, meta.run_id, candidateId, name], hash)
  }

  async aggregate(meta: RunMetadata, candidateId: CandidateId,
                  summary: CandidateSummary): Promise<AggregateMetrics> {
    const context = `${meta.run_id}/${candidateId}/aggregate_metrics.json`
    const aggregate = parseJson(await this.candidateFile(meta, candidateId, 'aggregate_metrics.json'),
      aggregateSchema, context)
    if (!isDeepStrictEqual(aggregate, summary.all_candidate_aggregate_metrics[candidateId])) {
      schemaError(context, 'candidate aggregate differs from official candidate_summary.json')
    }
    return aggregate
  }

  async daily(meta: RunMetadata, candidateId: CandidateId) {
    return dailyMetricRows(await this.candidateFile(meta, candidateId, 'per_date_metrics.csv'),
      `${meta.run_id}/${candidateId}/per_date_metrics.csv`)
  }

  async predictions(meta: RunMetadata, candidateId: CandidateId) {
    return predictionRows(await this.candidateFile(meta, candidateId, 'predictions.csv'),
      `${meta.run_id}/${candidateId}/predictions.csv`)
  }

  async training(meta: RunMetadata, candidateId: CandidateId) {
    return trainingRows(await this.candidateFile(meta, candidateId, 'training_diagnostics.csv'),
      `${meta.run_id}/${candidateId}/training_diagnostics.csv`)
  }

  async quality(meta: RunMetadata, candidateId: CandidateId) {
    const context = `${meta.run_id}/${candidateId}/data_quality_diagnostics.json`
    return parseJson(await this.candidateFile(meta, candidateId, 'data_quality_diagnostics.json'),
      qualitySchema, context)
  }

  async transformation(meta: RunMetadata, candidateId: CandidateId) {
    const context = `${meta.run_id}/${candidateId}/transformation_diagnostics.json`
    return parseJson(await this.candidateFile(meta, candidateId, 'transformation_diagnostics.json'),
      transformSchema, context)
  }

  async runs(): Promise<RunMetadata[]> {
    const dirs = await this.storage.directories([COLLECTION])
    const runs: RunMetadata[] = []
    for (const runId of dirs.filter((name) => RUN_ID.test(name)).sort().reverse()) {
      try {
        const meta = await this.metadata(runId)
        await this.summary(meta)
        runs.push(meta)
      } catch (error) {
        if (error instanceof ApiError && error.code === 'SEALED_PHASE') continue
        throw error
      }
    }
    return runs
  }

  async latest(): Promise<RunMetadata> {
    const latest = await this.latestOrNull()
    if (!latest) throw new ApiError('RUN_NOT_FOUND', 404, 'No admitted Development run found')
    return latest
  }

  async latestOrNull(): Promise<RunMetadata | null> {
    return (await this.runs())[0] ?? null
  }
}

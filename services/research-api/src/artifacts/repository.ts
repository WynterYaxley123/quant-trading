import { isDeepStrictEqual } from 'node:util'
import { z } from 'zod'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { ApiError, schemaError } from '../errors.js'
import { ARTIFACT_FILES, CANDIDATES, type CandidateId } from '../protocol.js'
import {
  aggregateSchema, metadataSchema, qualitySchema, summarySchema, transformSchema,
  type AggregateMetrics, type CandidateSummary, type RunMetadata,
} from '../schemas/artifacts.js'
import { dailyMetricRows, predictionRows, trainingRows } from '../schemas/csv.js'
import { ArtifactStorage, assertSafeSegment } from './storage.js'
import { readApproval, type WorkspaceApproval } from './approval.js'
import type { ApiConfig } from '../config.js'
import { dailyView, predictionView } from '../adapters/normalize.js'

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
  private readonly schemaVerified = new Set<string>()

  constructor(root: string, private readonly options: Pick<ApiConfig, 'registryPath' | 'artifactId' | 'optionalRoot' | 'configurationError'> = {}) {
    this.storage = new ArtifactStorage(root)
  }

  private async approval(): Promise<WorkspaceApproval | null> {
    if (this.options.configurationError) throw new ApiError('RESEARCH_CONFIGURATION_INVALID', 500, 'Local workspace configuration is malformed; correct it and restart the service')
    return readApproval(this.options.registryPath ?? resolve(dirname(fileURLToPath(import.meta.url)), '../../config/development-workspaces.v1.json'), this.options.artifactId)
  }

  async approvedRun(runId: string) {
    this.checkRunId(runId)
    const approval = await this.approval()
    const run = approval?.runs.find((item) => item.runId === runId)
    if (!run) throw new ApiError('RESEARCH_ARTIFACT_UNAPPROVED', 403, 'Run is not in the approved Development registry')
    return { approval: approval!, run }
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
    const { run } = await this.approvedRun(runId)
    const context = `${runId}/metadata.json`
    const { text, sha256 } = await this.storage.readHashed([COLLECTION, runId, 'metadata.json'], null, 'RUN_NOT_FOUND')
    let raw: unknown
    try {
      raw = JSON.parse(text)
    } catch (error) {
      schemaError(context, `invalid JSON: ${String(error)}`)
    }
    if (raw && typeof raw === 'object' && 'phase' in raw
        && isSealedPhase((raw as { phase: unknown }).phase)) {
      throw new ApiError('RESEARCH_ARTIFACT_PHASE_FORBIDDEN', 403, 'Only approved Development metadata may be served')
    }
    // Approval is checked before any content read. The metadata SHA anchors
    // its complete content manifest; a modified manifest cannot bless new data.
    if (sha256 !== run.metadataSha256) {
      throw new ApiError('RESEARCH_ARTIFACT_HASH_MISMATCH', 500, 'Metadata SHA256 does not match its approval', context)
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
    const approval = await this.approval()
    if (this.options.optionalRoot === false) {
      try { await this.storage.root() }
      catch { throw new ApiError('RESEARCH_ARTIFACT_INVALID', 500, 'Configured artifact root is missing or inaccessible; no fallback was selected') }
    }
    const dirs = await this.storage.directories([COLLECTION])
    if (!dirs.length && this.options.optionalRoot !== false) return []
    if (!approval) throw new ApiError('RESEARCH_ARTIFACT_UNAPPROVED', 403, 'No workspace approval is registered')
    const selected = approval.runs.filter((run) => dirs.includes(run.runId))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b.runId.localeCompare(a.runId))
    if (!selected.length) throw new ApiError('RESEARCH_ARTIFACT_UNAPPROVED', 403, 'Configured catalog contains no approved Development run')
    const runs: RunMetadata[] = []
    for (const run of selected) {
      const meta = await this.metadata(run.runId)
      await this.validate(meta, run.metadataSha256)
      runs.push(meta)
    }
    return runs
  }

  private async validate(meta: RunMetadata, metadataHash: string): Promise<void> {
    const summary = await this.summary(meta)
    // All 29 declared content files are rehashed on every catalog/status
    // observation. Only schema parsing of immutable approved bytes is memoized.
    for (const id of CANDIDATES) {
      const contents = new Map<string, string>()
      for (const name of ARTIFACT_FILES) contents.set(name, await this.candidateFile(meta, id, name))
      if (!this.schemaVerified.has(metadataHash)) {
        const aggregate = parseJson(contents.get('aggregate_metrics.json')!, aggregateSchema, `${meta.run_id}/${id}/aggregate_metrics.json`)
        if (!isDeepStrictEqual(aggregate, summary.all_candidate_aggregate_metrics[id])) schemaError(meta.run_id, 'Aggregate and summary disagree')
        dailyView(dailyMetricRows(contents.get('per_date_metrics.csv')!, meta.run_id), meta.run_id)
        predictionView(predictionRows(contents.get('predictions.csv')!, meta.run_id), meta.run_id)
        trainingRows(contents.get('training_diagnostics.csv')!, meta.run_id)
        parseJson(contents.get('data_quality_diagnostics.json')!, qualitySchema, meta.run_id)
        parseJson(contents.get('transformation_diagnostics.json')!, transformSchema, meta.run_id)
      }
    }
    this.schemaVerified.add(metadataHash)
  }

  async workspace() {
    const base = { readOnly: true as const, sealedValidation: true as const, sealedFinalOos: true as const }
    try {
      const runs = await this.runs()
      const latest = runs[0] ?? null
      const approval = await this.approval()
      return { ...base, artifactState: latest ? 'AVAILABLE' as const : 'NOT_CONFIGURED' as const,
        artifactId: latest ? approval!.artifactId : null, artifactPhase: latest ? 'DEVELOPMENT' as const : null,
        approvalState: latest ? 'APPROVED' as const : 'NOT_CONFIGURED' as const,
        activeRunId: latest?.run_id ?? null, availableRunCount: runs.length,
        integrityStatus: latest ? 'PASS' as const : 'NOT_CONFIGURED' as const,
        candidateAvailability: latest ? 'AVAILABLE' as const : 'NOT_CONFIGURED' as const,
        metricsAvailability: latest ? 'AVAILABLE' as const : 'NOT_CONFIGURED' as const,
        diagnosticsAvailability: latest ? 'AVAILABLE' as const : 'NOT_CONFIGURED' as const,
        artifactError: null, latest }
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'RESEARCH_ARTIFACT_INVALID'
      return { ...base, artifactState: 'DEGRADED' as const, artifactId: null, artifactPhase: null,
        approvalState: 'REJECTED' as const, activeRunId: null, availableRunCount: 0,
        integrityStatus: 'FAIL' as const, candidateAvailability: 'DEGRADED' as const,
        metricsAvailability: 'DEGRADED' as const, diagnosticsAvailability: 'DEGRADED' as const,
        artifactError: { code, message: error instanceof ApiError ? error.message : 'Configured artifact could not be validated' }, latest: null }
    }
  }

  async integrityProof(runId: string) {
    const { approval, run } = await this.approvedRun(runId)
    const meta = await this.metadata(runId)
    await this.validate(meta, run.metadataSha256)
    return { meta, artifactId: approval.artifactId, approvalState: 'APPROVED' as const,
      metadataHash: run.metadataSha256, manifestStatus: 'PASS' as const, hashStatus: 'PASS' as const,
      schemaStatus: 'PASS' as const, verifiedContentFileCount: 29, readOnly: true as const,
      sealedValidation: true as const, sealedFinalOos: true as const }
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

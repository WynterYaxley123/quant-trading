import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { readFile, stat } from 'node:fs/promises'
import { join } from 'node:path'
import { parse } from 'csv-parse/sync'
import { createApp } from '../src/app.js'
import { loadConfig } from '../src/config.js'

const reportRoot = process.env.RESEARCH_REPORT_ROOT
const runId = 'iteration1_20260924_163607_787266_utc'
const candidates = ['D0', 'D1', 'D2', 'D3'] as const
const files = ['predictions.csv', 'per_date_metrics.csv', 'aggregate_metrics.json',
  'training_diagnostics.csv', 'data_quality_diagnostics.json',
  'per_date_predictions.csv', 'transformation_diagnostics.json']

describe.skipIf(!reportRoot)('current formal Iteration-1 artifacts, read-only', () => {
  const app = createApp(loadConfig({ RESEARCH_REPORT_ROOT: reportRoot }))
  const runDir = join(reportRoot ?? '', 'shenwan_sector_index', runId)
  let before: Map<string, string>

  async function fingerprint(): Promise<Map<string, string>> {
    const names = ['metadata.json', 'candidate_summary.json',
      ...candidates.flatMap((candidate) => files.map((file) => `${candidate}/${file}`))]
    return new Map(await Promise.all(names.map(async (name) => {
      const info = await stat(join(runDir, name))
      return [name, `${info.size}:${info.mtimeMs}`] as const
    })))
  }

  async function get(path: string) {
    const result = await app.request(`http://localhost${path}`)
    return { status: result.status, body: await result.json(), raw: result }
  }

  beforeAll(async () => { before = await fingerprint() })
  afterAll(async () => { expect(await fingerprint()).toEqual(before) })

  it('catalogs only Development Iteration-1 runs, newest first, and keeps phases sealed', async () => {
    const runs = await get('/api/v1/runs')
    expect(runs.status).toBe(200)
    expect(runs.body.data.items[0].runId).toBe(runId)
    expect(runs.body.data.items.every((item: { phase: string }) => item.phase === 'DEVELOPMENT')).toBe(true)
    expect(runs.body.data.items.map((item: { runId: string }) => item.runId))
      .not.toContain('20260924_145948_233618_utc')
    const status = await get('/api/v1/research/status')
    expect(status.body.data).toMatchObject({ researchLabel: 'SECTOR_INDEX_RESEARCH_ONLY',
      phase: 'DEVELOPMENT', validation: 'SEALED', finalOos: 'SEALED',
      executable: false, tradable: false, strictPit: false, etf: 'DISABLED',
      syntheticPortfolio: 'DISABLED', levelB: 'DISABLED' })
    const capabilities = await get('/api/v1/capabilities')
    expect(capabilities.body.data).toMatchObject({ readOnly: true, mutations: false,
      candidateComparison: true, developmentExplorer: true, sectorExplorer: true,
      diagnostics: true, portfolio: false, execution: false, etf: false,
      validationAvailable: false, finalOosAvailable: false })
    const detail = await get(`/api/v1/runs/${runId}`)
    expect(detail.body.data).toMatchObject({ runId, candidateIds: candidates,
      validation: 'SEALED', finalOos: 'SEALED', strictPit: false })
    const integrity = await get(`/api/v1/runs/${runId}/integrity`)
    expect(integrity.body.data).toMatchObject({ universe: 'U0_FIXED_124', sectorCount: 124,
      featureCount: 19, alpha: 0.01, horizons: [10, 40, 120],
      fusion: [0.25, 0.5, 0.25], topK: 5, executable: false, strictPit: false })
  })

  it('reads D0-D3 definitions and copies exact official aggregate/comparison numbers', async () => {
    const summary = JSON.parse(await readFile(join(runDir, 'candidate_summary.json'), 'utf8'))
    const candidateResponse = await get(`/api/v1/runs/${runId}/candidates`)
    expect(candidateResponse.status).toBe(200)
    expect(candidateResponse.body.data.items.map((item: { candidateId: string }) => item.candidateId))
      .toEqual(candidates)
    expect(candidateResponse.body.data.items[1]).toMatchObject({
      xPreprocessing: 'TRAIN_ONLY_STANDARDIZATION',
      trainingTarget: 'ABSOLUTE_FORWARD_RETURN', promotionStatus: 'NOT_PROMOTED',
    })
    for (const candidate of candidates) {
      const artifact = JSON.parse(await readFile(join(runDir, candidate, 'aggregate_metrics.json'), 'utf8'))
      const comparison = summary.comparison.find((row: { candidate: string }) => row.candidate === candidate)
      const result = await get(`/api/v1/runs/${runId}/candidates/${candidate}/metrics`)
      expect(result.status).toBe(200)
      expect(result.body.data.weightedRankIc).toBe(comparison.Weighted_RankIC)
      expect(result.body.data.weightedSpread).toBe(comparison.Weighted_Spread)
      for (const horizon of result.body.data.horizons) {
        const h = horizon.horizon
        expect(horizon.ic.mean).toBe(artifact[`IC_${h}`].mean)
        expect(horizon.rankIc.median).toBe(artifact[`RankIC_${h}`].median)
        expect(horizon.top5ForwardReturn.max).toBe(artifact[`Top5_forward_return_${h}`].max)
        expect(horizon.universeForwardReturn.min).toBe(artifact[`Universe_forward_return_${h}`].min)
        expect(horizon.top5MinusUniverse.std).toBe(artifact[`Top5_minus_universe_${h}`].std)
        expect(horizon.ic.validDates).toBe(artifact[`IC_${h}`].valid_dates)
      }
    }
  })

  it('normalizes existing daily rows and three-horizon predictions with exact source numbers', async () => {
    for (const candidate of candidates) {
      const dailyCsv = parse(await readFile(join(runDir, candidate, 'per_date_metrics.csv'), 'utf8'),
        { columns: true }) as Record<string, string>[]
      const daily = await get(`/api/v1/runs/${runId}/candidates/${candidate}/daily-metrics?horizon=10`)
      expect(daily.status).toBe(200)
      expect(daily.body.data.items).toHaveLength(100)
      const sourceRankIc = dailyCsv.find((row) => row.ordinal === '1' && row.metric === 'RankIC_10')!
      expect(daily.body.data.items[0].rankIc).toBe(Number(sourceRankIc.value))
      expect(daily.body.data.items[0].ordinal).toBe('E001')

      const predictionCsv = parse(await readFile(join(runDir, candidate, 'predictions.csv'), 'utf8'),
        { columns: true }) as Record<string, string>[]
      const prediction = await get(`/api/v1/runs/${runId}/candidates/${candidate}/predictions?date=2025-04-02&top5=true&limit=5`)
      expect(prediction.status).toBe(200)
      expect(prediction.body.data.total).toBe(5)
      expect(prediction.body.data.items).toHaveLength(5)
      for (const item of prediction.body.data.items) {
        const source = predictionCsv.find((row) => row.ordinal === '1' && row.sector_code === item.sectorCode
          && row.horizon === '10')!
        expect(source).toBeDefined()
        expect(item.pred10).toBe(Number(source.prediction_score))
        expect(item.fusedScore).toBe(Number(source.fused_score))
        expect(item.fusedRank).toBe(Number(source.fused_rank))
        expect(item.sectorName).toBe(source.sector_name)
        expect(item.top5).toBe(true)
      }
    }
  })

  it('sorts and paginates predictions deterministically, with accurate top5 filters', async () => {
    const base = `/api/v1/runs/${runId}/candidates/D2/predictions?date=2025-04-02`
    const all = await get(base)
    expect(all.body.data.total).toBe(124)
    expect(all.body.data.items).toHaveLength(124)
    expect(all.body.data.items[0].fusedRank).toBe(1)
    const page = await get(`${base}&limit=2&offset=1`)
    expect(page.body.data).toMatchObject({ total: 124, limit: 2, offset: 1 })
    expect(page.body.data.items).toEqual(all.body.data.items.slice(1, 3))
    expect((await get(base)).body).toEqual(all.body)
    const nonTop = await get(`${base}&top5=false`)
    expect(nonTop.body.data.total).toBe(119)
    expect(nonTop.body.data.items.every((item: { top5: boolean }) => item.top5 === false)).toBe(true)
    const absent = await get(`/api/v1/runs/${runId}/candidates/D2/predictions?date=2025-01-01`)
    expect(absent.body.data).toMatchObject({ items: [], total: 0, limit: 200, offset: 0 })
  })

  it('reports quality and transformation diagnostics without inferring absent models', async () => {
    for (const candidate of candidates) {
      const quality = JSON.parse(await readFile(join(runDir, candidate, 'data_quality_diagnostics.json'), 'utf8'))
      const transform = JSON.parse(await readFile(join(runDir, candidate, 'transformation_diagnostics.json'), 'utf8'))
      const result = await get(`/api/v1/runs/${runId}/candidates/${candidate}/diagnostics`)
      expect(result.status).toBe(200)
      expect(result.body.data.attemptedDates).toBe(quality.attempted_development_dates)
      expect(result.body.data.successfulDates).toBe(quality.successful_dates)
      expect(result.body.data.skippedDates).toBe(quality.skipped_dates.length)
      expect(result.body.data.horizons).toHaveLength(3)
      expect(result.body.data.horizons[0].validSectorCounts).toEqual({ min: 124, median: 124, max: 124 })
      expect(result.body.data.scalerDiagnosticHash).toBe(transform.scaler_diagnostic_hash)
      expect(result.body.data.targetDiagnosticHash).toBe(transform.target_diagnostic_hash)
    }
  })

  it('returns 404 for invalid candidate, 405 for mutation, and 403 for sealed attempts', async () => {
    const badCandidate = await get(`/api/v1/runs/${runId}/candidates/D4/metrics`)
    expect(badCandidate.status).toBe(404)
    expect(badCandidate.body.error.code).toBe('CANDIDATE_NOT_FOUND')
    const sealed = await get(`/api/v1/runs/${runId}/predictions?phase=final_oos`)
    expect(sealed.status).toBe(403)
    expect(sealed.body.error.code).toBe('SEALED_PHASE')
    const mutation = await app.request(`/api/v1/runs/${runId}/candidates`, { method: 'POST' })
    expect(mutation.status).toBe(405)
    expect((await mutation.json()).error.code).toBe('METHOD_NOT_ALLOWED')
  })
})

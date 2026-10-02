import { afterEach, describe, expect, it, vi } from 'vitest'
import { mkdtemp, mkdir, rm, writeFile, readFile, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createApp, rawUrlGuardResponse, rejectUnsafeRequest, ROUTE_PATHS } from '../src/app.js'
import { loadConfig } from '../src/config.js'
import { ApiError } from '../src/errors.js'
import { ArtifactStorage, assertSafeSegment } from '../src/artifacts/storage.js'
import { dailyView, predictionView } from '../src/adapters/normalize.js'
import type { DailyMetricRow, PredictionRow } from '../src/schemas/csv.js'
import { dailyMetricRows, predictionRows, trainingRows } from '../src/schemas/csv.js'
import type { Horizon } from '../src/protocol.js'

const temporary: string[] = []
afterEach(async () => {
  vi.restoreAllMocks()
  for (const path of temporary.splice(0)) await rm(path, { recursive: true, force: true })
})

async function fixtureRoot() {
  const root = await mkdtemp(join(tmpdir(), 'research-api-test-'))
  temporary.push(root)
  await mkdir(join(root, 'shenwan_sector_index'))
  return root
}

function app(root = join(tmpdir(), 'nonexistent-research-api-fixture')) {
  return createApp({ ...loadConfig({}), reportRoot: root, optionalRoot: true })
}

async function response(path: string, init?: RequestInit) {
  const result = await app().request(`http://localhost${path}`, init)
  return { status: result.status, headers: result.headers, body: await result.json() }
}

describe('stable read-only HTTP boundary', () => {
  it('rejects public listen addresses', () => {
    for (const host of ['0.0.0.0', '::', '192.168.1.10']) {
      expect(() => loadConfig({ HOST: host })).toThrow(/loopback/)
    }
    expect(loadConfig({ HOST: '::1' }).host).toBe('::1')
  })

  it('starts with an absent report root and returns honest empty observation data without writing it', async () => {
    const root = join(await fixtureRoot(), 'not-configured')
    const api = app(root)
    const health = await api.request('/api/v1/health')
    expect(health.status).toBe(200)
    for (const path of ['/api/v1/capabilities', '/api/v1/research/status', '/api/v1/runs']) {
      const result = await api.request(path)
      expect(result.status).toBe(200)
      const body = await result.json()
      if (path.endsWith('/runs')) expect(body.data.items).toEqual([])
      else expect(body.data.artifactState).toBe('NOT_CONFIGURED')
      expect(JSON.stringify(body)).not.toContain(root)
    }
    const status = await (await api.request('/api/v1/research/status')).json()
    expect(status.data).toMatchObject({ phase: 'NOT_CONFIGURED', validation: 'SEALED', finalOos: 'SEALED', executable: false, tradable: false })
    await expect(readFile(root)).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('treats optional empty catalogs as empty and rejects unapproved folders without parsing their metadata', async () => {
    const root = await fixtureRoot()
    expect((await (await app(root).request('/api/v1/runs')).json()).data.items).toEqual([])
    const runId = 'iteration1_20260101_000000_000000_utc'
    await mkdir(join(root, 'shenwan_sector_index', runId))
    await writeFile(join(root, 'shenwan_sector_index', runId, 'metadata.json'), 'invalid JSON')
    for (const path of ['/api/v1/capabilities', '/api/v1/research/status']) {
      const result = await app(root).request(path)
      expect(result.status).toBe(200)
      expect((await result.json()).data.artifactState).toBe('DEGRADED')
    }
    expect((await (await app(root).request('/api/v1/runs')).json()).error.code).toBe('RESEARCH_ARTIFACT_UNAPPROVED')
    expect((await app(root).request('/api/v1/health')).status).toBe(200)
  })

  it('rejects force and bypass queries rather than implying execution support', async () => {
    for (const path of ['/api/v1/health?force=true', '/api/v1/runs?bypass=true']) {
      const result = await response(path)
      expect(result.status).toBe(400)
      expect(result.body.error.code).toBe('BAD_QUERY')
    }
  })

  it('health does not require artifacts and advertises read-only source of truth', async () => {
    const result = await response('/api/v1/health')
    expect(result.status).toBe(200)
    expect(result.body).toEqual({ schemaVersion: '1.0.0',
      data: { status: 'ok', readOnly: true, sourceOfTruth: 'RESEARCH_ARTIFACTS' } })
  })

  it('blocks all mutations with 405 even for otherwise valid and unknown API paths', async () => {
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      for (const path of ['/api/v1/health', '/api/v1/unknown']) {
        const result = await response(path, { method })
        expect(result.status).toBe(405)
        expect(result.body.error.code).toBe('METHOD_NOT_ALLOWED')
      }
    }
  })

  it('allows HEAD and OPTIONS without exposing a mutation endpoint', async () => {
    const head = await app().request('http://localhost/api/v1/health', { method: 'HEAD' })
    expect(head.status).toBe(200)
    expect(await head.text()).toBe('')
    const options = await app().request('http://localhost/api/v1/health', {
      method: 'OPTIONS', headers: { Origin: 'http://localhost:5173',
        'Access-Control-Request-Method': 'GET' },
    })
    expect(options.status).toBe(204)
    expect(options.headers.get('access-control-allow-origin')).toBe('http://localhost:5173')
  })

  it('actively seals Validation and Final OOS paths and queries', async () => {
    for (const path of ['/api/v1/validation', '/api/v1/final-oos',
      '/api/v1/runs/validation', '/api/v1/runs?phase=validation',
      '/api/v1/runs?phase=final_oos']) {
      const result = await response(path)
      expect(result.status).toBe(403)
      expect(result.body.error.code).toBe('SEALED_PHASE')
    }
  })

  it('blocks path traversal spellings and encoded separators', async () => {
    for (const segment of ['../../', '..\\..', '%2e%2e', '%2f', '%5c', '%252e%252e',
      'C:\\outside', '/outside', 'D0/../../']) {
      expect(() => assertSafeSegment(segment)).toThrowError(ApiError)
    }
    for (const raw of ['/api/v1/runs/%2e%2e', '/api/v1/runs/../../outside',
      '/api/v1/runs/..\\..', '/api/v1/runs/%2f']) {
      expect(() => rejectUnsafeRequest(raw)).toThrowError(ApiError)
    }
    for (const path of ['/api/v1/runs/%2e%2e%2foutside',
      '/api/v1/runs/%5c..%5coutside', '/api/v1/runs/%252e%252e']) {
      const result = await response(path)
      expect(result.status).toBe(403)
      expect(result.body.error.code).toBe('PATH_TRAVERSAL_BLOCKED')
    }
  })

  it('rejects a literal traversal at the raw Node HTTP boundary before route normalization', async () => {
    const blocked = rawUrlGuardResponse('/api/v1/runs/../../outside')
    expect(blocked?.status).toBe(403)
    expect((await blocked?.json()).error.code).toBe('PATH_TRAVERSAL_BLOCKED')
    expect(rawUrlGuardResponse('/api/v1/health')).toBeNull()
  })

  it('allows only exact local CORS origins; never a wildcard', async () => {
    for (const origin of ['http://127.0.0.1:5173', 'http://localhost:5173']) {
      const result = await response('/api/v1/health', { headers: { Origin: origin } })
      expect(result.headers.get('access-control-allow-origin')).toBe(origin)
    }
    const rejected = await response('/api/v1/health', { headers: { Origin: 'http://evil.example' } })
    expect(rejected.headers.get('access-control-allow-origin')).toBeNull()
    expect(() => loadConfig({ DASHBOARD_ORIGINS: '*' })).toThrow(/never \*/)
  })

  it('rejects malformed and oversized queries before touching artifacts', async () => {
    const base = '/api/v1/runs/iteration1_20260924_163607_787266_utc/candidates/D0'
    for (const path of [
      `${base}/predictions`, `${base}/predictions?date=2025-02-30`,
      `${base}/predictions?date=2025-04-02&limit=501`,
      `${base}/predictions?date=2025-04-02&limit=0`,
      `${base}/predictions?date=2025-04-02&offset=-1`,
      `${base}/predictions?date=2025-04-02&top5=yes`,
      `${base}/predictions?date=2025-04-02&date=2025-04-03`,
      `${base}/daily-metrics?horizon=20`,
    ]) {
      const result = await response(path)
      expect(result.status).toBe(400)
      expect(result.body.error.code).toBe('BAD_QUERY')
    }
  })

  it('refuses an unapproved safe run before filesystem access', async () => {
    const root = await fixtureRoot()
    const result = await app(root).request('/api/v1/runs/iteration1_20260101_000000_000000_utc')
    expect(result.status).toBe(403)
    expect((await result.json()).error.code).toBe('RESEARCH_ARTIFACT_UNAPPROVED')
  })

  it('never reads an unapproved sealed-phase folder and refuses its direct request', async () => {
    const root = await fixtureRoot()
    const runId = 'iteration1_20260101_000000_000000_utc'
    await mkdir(join(root, 'shenwan_sector_index', runId))
    await writeFile(join(root, 'shenwan_sector_index', runId, 'metadata.json'),
      JSON.stringify({ run_id: runId, phase: 'VALIDATION' }))
    const catalog = await app(root).request('/api/v1/runs')
    expect(catalog.status).toBe(403)
    const direct = await app(root).request(`/api/v1/runs/${runId}`)
    expect(direct.status).toBe(403)
    expect((await direct.json()).error.code).toBe('RESEARCH_ARTIFACT_UNAPPROVED')
  })

  it('does not parse malformed unapproved metadata or leak an absolute path', async () => {
    const root = await fixtureRoot()
    const runId = 'iteration1_20260101_000000_000000_utc'
    await mkdir(join(root, 'shenwan_sector_index', runId))
    await writeFile(join(root, 'shenwan_sector_index', runId, 'metadata.json'),
      JSON.stringify({ run_id: runId, phase: 'DEVELOPMENT', candidate_family: ['D0'] }))
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    const result = await app(root).request(`/api/v1/runs/${runId}`)
    expect(result.status).toBe(403)
    const body = await result.json()
    expect(body.error.code).toBe('RESEARCH_ARTIFACT_UNAPPROVED')
    expect(JSON.stringify(body)).not.toContain(root)
    expect(log).not.toHaveBeenCalled()
  })

  it('rejects SHA mismatch and path escape in storage', async () => {
    const root = await fixtureRoot()
    const file = join(root, 'shenwan_sector_index', 'official.json')
    await writeFile(file, '{"ok":true}')
    const storage = new ArtifactStorage(root)
    await expect(storage.read(['shenwan_sector_index', 'official.json'], '0'.repeat(64)))
      .rejects.toMatchObject({ code: 'RESEARCH_ARTIFACT_HASH_MISMATCH' })
    await expect(storage.read(['..', 'outside'])).rejects.toMatchObject({ code: 'PATH_TRAVERSAL_BLOCKED' })
  })

  it('does not follow a directory junction outside the configured root', async () => {
    const root = await fixtureRoot()
    const outside = await mkdtemp(join(tmpdir(), 'research-api-outside-'))
    temporary.push(outside)
    await writeFile(join(outside, 'secret.json'), '{"secret":true}')
    try {
      await symlink(outside, join(root, 'shenwan_sector_index', 'linked'), 'junction')
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EPERM') return
      throw error
    }
    await expect(new ArtifactStorage(root).read(['shenwan_sector_index', 'linked', 'secret.json']))
      .rejects.toMatchObject({ code: 'PATH_TRAVERSAL_BLOCKED' })
  })
})

describe('synthetic normalization and schema checks', () => {
  it('pivots exactly five existing daily metrics without recalculation', () => {
    const stems = ['IC', 'RankIC', 'Top5_forward_return', 'Universe_forward_return',
      'Top5_minus_universe']
    const rows: DailyMetricRow[] = []
    for (let ordinal = 1; ordinal <= 100; ordinal++) {
      const date = new Date(Date.UTC(2025, 3, ordinal + 1)).toISOString().slice(0, 10)
      for (const horizon of [10, 40, 120] as Horizon[]) {
        for (let i = 0; i < stems.length; i++) {
          rows.push({ ordinal, signalDate: date, horizon,
            metric: `${stems[i]}_${horizon}`, value: ordinal + i / 10,
            nullReason: null, validSectorCount: 124 })
        }
      }
    }
    const items = dailyView(rows, 'synthetic/per_date_metrics.csv')
    expect(items).toHaveLength(300)
    expect(items[0]).toMatchObject({ ordinal: 'E001', horizon: 10, ic: 1,
      rankIc: 1.1, top5ForwardReturn: 1.2 })
    expect(items[299].ordinal).toBe('E100')
    expect(() => dailyView(rows.slice(1), 'synthetic/per_date_metrics.csv')).toThrow(/schema/i)
  })

  it('pivots one official fused Top5 across horizons and preserves source values', () => {
    const rows: PredictionRow[] = []
    for (let ordinal = 1; ordinal <= 100; ordinal++) {
      const date = new Date(Date.UTC(2025, 3, ordinal + 1)).toISOString().slice(0, 10)
      for (let sector = 0; sector < 124; sector++) {
        for (const horizon of [10, 40, 120] as Horizon[]) {
          rows.push({ ordinal, signalDate: date, sectorCode: String(801000 + sector),
            sectorName: `Sector ${sector}`, horizon, predictionScore: sector + horizon / 100,
            fusedScore: 124 - sector, fusedRank: sector + 1, top5: sector < 5,
            realizedForwardReturn: sector / 1000, labelEnd: date })
        }
      }
    }
    const items = predictionView(rows, 'synthetic/predictions.csv')
    expect(items).toHaveLength(12_400)
    expect(items[0]).toMatchObject({ ordinal: 'E001', sectorCode: '801000',
      pred10: 0.1, pred40: 0.4, pred120: 1.2, fusedRank: 1, top5: true })
    rows[0].top5 = false
    expect(() => predictionView(rows, 'synthetic/predictions.csv')).toThrow(/schema/i)
  })

  it('rejects missing columns and invalid numeric/enum values rather than coercing blanks to zero', () => {
    expect(() => dailyMetricRows('ordinal,signal_date,horizon\n1,2025-04-02,10\n', 'bad.csv'))
      .toThrow(/schema/i)
    expect(() => predictionRows('ordinal,sector_code\n1,801012\n', 'bad.csv'))
      .toThrow(/schema/i)
    const header = 'ordinal,signal_date,horizon,metric,value,null_reason,valid_sector_count\n'
    const good = '1,2025-04-02,10,IC_10,0.123,,124\n'
    const blank = '1,2025-04-02,10,IC_10,,,124\n'
    expect(dailyMetricRows(header + blank + good.repeat(1499), 'nullable.csv')[0].value).toBeNull()
    expect(() => dailyMetricRows(header + good.repeat(1499)
      + '1,2025-04-02,10,IC_10,not-a-number,,124\n', 'bad.csv')).toThrow(/schema/i)
    expect(() => dailyMetricRows(header + good.repeat(1499)
      + '1,2025-04-02,20,IC_20,0.1,,124\n', 'bad.csv')).toThrow(/schema/i)
  })

  it('validates declared but non-projected CSV evidence columns', () => {
    const predictionHeader = [
      'ordinal,signal_date,sector_code,sector_name,horizon,prediction_score,cross_sectional_rank',
      'fused_score,fused_rank,top5,realized_forward_return,label_end,exclusion_reason',
      'training_observations,training_valid_days,training_label_cutoff',
    ].join(',') + '\n'
    const prediction = '1,2025-04-02,801012,Sector,10,0.1,not-an-integer,0.2,1,True,0.3,2025-04-17,,10,2,2025-03-19\n'
    let predictionError: unknown
    try {
      predictionRows(predictionHeader + prediction.repeat(37_200), 'run/D0/predictions.csv')
    } catch (error) {
      predictionError = error
    }
    expect(predictionError).toMatchObject({ code: 'ARTIFACT_SCHEMA_ERROR',
      context: expect.stringContaining('cross_sectional_rank') })
    const trainingHeader = [
      'ordinal,signal_date,horizon,status,reason,train_start,label_cutoff,first_train_origin',
      'last_train_origin,last_train_label_end,training_candidate_days,training_valid_days',
      'training_observations,valid_sector_count,missing_factor_exclusions',
      'missing_label_exclusions,numerical_failures,leakage_checks',
    ].join(',') + '\n'
    const training = '1,2025-04-02,10,success,,not-a-date,2025-03-19,2024-09-19,2025-03-19,2025-04-02,2,2,10,124,0,0,0,10\n'
    let trainingError: unknown
    try {
      trainingRows(trainingHeader + training.repeat(300), 'run/D0/training_diagnostics.csv')
    } catch (error) {
      trainingError = error
    }
    expect(trainingError).toMatchObject({ code: 'ARTIFACT_SCHEMA_ERROR',
      context: expect.stringContaining('train_start') })
  })

  it('keeps OpenAPI route keys aligned with registered GET routes', async () => {
    const spec = await readFile(join(import.meta.dirname, '../openapi/research-dashboard-api-v1.openapi.yaml'), 'utf8')
    const declared = [...spec.matchAll(/^  (\/api\/v1\/[^:\n]+):$/gm)]
      .map((match) => match[1].replaceAll('{runId}', ':runId').replaceAll('{candidateId}', ':candidateId'))
    expect(declared.sort()).toEqual([...ROUTE_PATHS].sort())
    expect((spec.match(/^    get:$/gm) ?? [])).toHaveLength(ROUTE_PATHS.length)
    expect(spec).toContain('openapi: 3.1.0')
    expect(spec).toContain('SECTOR_INDEX_RESEARCH_ONLY')
    expect(spec).not.toMatch(/^    post:/gm)
  })
})

import { Hono } from 'hono'
import { cors } from 'hono/cors'
import type { ApiConfig } from './config.js'
import { ApiError } from './errors.js'
import { ArtifactRepository } from './artifacts/repository.js'
import { SCHEMA_VERSION, type Horizon } from './protocol.js'
import {
  candidateItems, dailyView, diagnosticView, integrity, metricView,
  predictionView, researchStatus, runDetail, runItem,
} from './adapters/normalize.js'

export const ROUTE_PATHS = [
  '/api/v1/health', '/api/v1/capabilities', '/api/v1/research/status',
  '/api/v1/runs', '/api/v1/runs/:runId', '/api/v1/runs/:runId/candidates',
  '/api/v1/runs/:runId/candidates/:candidateId/metrics',
  '/api/v1/runs/:runId/candidates/:candidateId/daily-metrics',
  '/api/v1/runs/:runId/candidates/:candidateId/predictions',
  '/api/v1/runs/:runId/candidates/:candidateId/diagnostics',
  '/api/v1/runs/:runId/integrity',
] as const

const SEALED = /(?:^|[/=_\-])(?:validation|final[_\-]?oos|oos)(?:$|[/=_\-])/i
const ENCODED_SEPARATOR = /%(?:2e|2f|5c|25|00)/i

export function rejectUnsafeRequest(rawUrl: string): void {
  // Inspect the Node incoming URL before WHATWG Request/URL normalizes dot segments.
  const rawPath = rawUrl.split('?')[0].replace(/^https?:\/\/[^/]+/i, '')
  const parsed = new URL(rawUrl, 'http://localhost')
  if (ENCODED_SEPARATOR.test(rawPath) || /\\/.test(rawPath)
      || rawPath.split('/').some((part) => part === '..')) {
    throw new ApiError('PATH_TRAVERSAL_BLOCKED', 403, 'Path traversal blocked')
  }
  if (SEALED.test(parsed.pathname) || [...parsed.searchParams.values()].some((value) => SEALED.test(value))) {
    throw new ApiError('SEALED_PHASE', 403, 'Sealed phase is unavailable')
  }
}

export function rawUrlGuardResponse(rawUrl: string): Response | null {
  try {
    rejectUnsafeRequest(rawUrl)
    return null
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json({ schemaVersion: SCHEMA_VERSION,
        error: { code: error.code, message: error.message } }, { status: error.status })
    }
    throw error
  }
}

function query(url: string, allowed: readonly string[]): URLSearchParams {
  const params = new URL(url).searchParams
  for (const key of params.keys()) {
    if (!allowed.includes(key) || params.getAll(key).length !== 1) {
      throw new ApiError('BAD_QUERY', 400, 'Unsupported or duplicate query parameter')
    }
  }
  return params
}

function dateQuery(params: URLSearchParams): string {
  const value = params.get('date')
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)
      || Number.isNaN(Date.parse(`${value}T00:00:00Z`))
      || new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) !== value) {
    throw new ApiError('BAD_QUERY', 400, 'date must be a valid YYYY-MM-DD')
  }
  return value
}

function horizonQuery(params: URLSearchParams): Horizon | null {
  const value = params.get('horizon')
  if (value === null) return null
  if (value !== '10' && value !== '40' && value !== '120') {
    throw new ApiError('BAD_QUERY', 400, 'horizon must be 10, 40, or 120')
  }
  return Number(value) as Horizon
}

function pagination(params: URLSearchParams) {
  const rawLimit = params.get('limit')
  const rawOffset = params.get('offset')
  if (rawLimit !== null && !/^[1-9]\d*$/.test(rawLimit)) {
    throw new ApiError('BAD_QUERY', 400, 'limit must be an integer from 1 to 500')
  }
  if (rawOffset !== null && !/^(0|[1-9]\d*)$/.test(rawOffset)) {
    throw new ApiError('BAD_QUERY', 400, 'offset must be a nonnegative integer')
  }
  const limit = rawLimit === null ? 200 : Number(rawLimit)
  const offset = rawOffset === null ? 0 : Number(rawOffset)
  if (!Number.isSafeInteger(limit) || limit > 500 || !Number.isSafeInteger(offset)) {
    throw new ApiError('BAD_QUERY', 400, 'pagination is out of range')
  }
  return { limit, offset }
}

export function createApp(config: ApiConfig, repo = new ArtifactRepository(config.reportRoot)) {
  const app = new Hono()
  app.use('/api/v1/*', cors({
    origin: (origin) => config.origins.includes(origin) ? origin : '',
    allowMethods: ['GET', 'HEAD', 'OPTIONS'],
    allowHeaders: ['Content-Type'],
  }))
  app.use('/api/v1/*', async (c, next) => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(c.req.method)) {
      throw new ApiError('METHOD_NOT_ALLOWED', 405, 'Research API is read-only')
    }
    const incomingRawUrl = (c.env as { incoming?: { url?: string } } | undefined)?.incoming?.url
    rejectUnsafeRequest(incomingRawUrl ?? c.req.url)
    if (c.req.method === 'OPTIONS') return c.body(null, 204)
    await next()
  })

  app.get('/api/v1/health', (c) => c.json({ schemaVersion: SCHEMA_VERSION,
    data: { status: 'ok', readOnly: true, sourceOfTruth: 'RESEARCH_ARTIFACTS' } }))

  app.get('/api/v1/capabilities', async (c) => {
    await repo.latest()
    return c.json({ schemaVersion: SCHEMA_VERSION, data: {
      readOnly: true, mutations: false,
      candidateComparison: true, developmentExplorer: true, sectorExplorer: true,
      diagnostics: true, portfolio: false, execution: false, etf: false,
      validationAvailable: false, finalOosAvailable: false,
    } })
  })

  app.get('/api/v1/research/status', async (c) => c.json({
    schemaVersion: SCHEMA_VERSION, data: researchStatus(await repo.latest()),
  }))

  app.get('/api/v1/runs', async (c) => c.json({
    schemaVersion: SCHEMA_VERSION, data: { items: (await repo.runs()).map(runItem) },
  }))

  app.get('/api/v1/runs/:runId', async (c) => c.json({
    schemaVersion: SCHEMA_VERSION, data: runDetail(await repo.metadata(c.req.param('runId'))),
  }))

  app.get('/api/v1/runs/:runId/candidates', async (c) => {
    const meta = await repo.metadata(c.req.param('runId'))
    return c.json({ schemaVersion: SCHEMA_VERSION,
      data: { items: candidateItems(await repo.summary(meta)) } })
  })

  app.get('/api/v1/runs/:runId/candidates/:candidateId/metrics', async (c) => {
    const meta = await repo.metadata(c.req.param('runId'))
    const candidateId = repo.checkCandidateId(c.req.param('candidateId'))
    const summary = await repo.summary(meta)
    const aggregate = await repo.aggregate(meta, candidateId, summary)
    return c.json({ schemaVersion: SCHEMA_VERSION, data: metricView(candidateId, aggregate, summary) })
  })

  app.get('/api/v1/runs/:runId/candidates/:candidateId/daily-metrics', async (c) => {
    const params = query(c.req.url, ['horizon'])
    const selected = horizonQuery(params)
    const meta = await repo.metadata(c.req.param('runId'))
    const candidateId = repo.checkCandidateId(c.req.param('candidateId'))
    const items = dailyView(await repo.daily(meta, candidateId),
      `${meta.run_id}/${candidateId}/per_date_metrics.csv`)
    return c.json({ schemaVersion: SCHEMA_VERSION,
      data: { items: selected === null ? items : items.filter((item) => item.horizon === selected) } })
  })

  app.get('/api/v1/runs/:runId/candidates/:candidateId/predictions', async (c) => {
    const params = query(c.req.url, ['date', 'top5', 'limit', 'offset'])
    const date = dateQuery(params)
    const rawTop5 = params.get('top5')
    if (rawTop5 !== null && rawTop5 !== 'true' && rawTop5 !== 'false') {
      throw new ApiError('BAD_QUERY', 400, 'top5 must be true or false')
    }
    const { limit, offset } = pagination(params)
    const meta = await repo.metadata(c.req.param('runId'))
    const candidateId = repo.checkCandidateId(c.req.param('candidateId'))
    const all = predictionView(await repo.predictions(meta, candidateId),
      `${meta.run_id}/${candidateId}/predictions.csv`)
    const filtered = all.filter((item) => item.signalDate === date
      && (rawTop5 === null || item.top5 === (rawTop5 === 'true')))
    return c.json({ schemaVersion: SCHEMA_VERSION,
      data: { items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset } })
  })

  app.get('/api/v1/runs/:runId/candidates/:candidateId/diagnostics', async (c) => {
    const meta = await repo.metadata(c.req.param('runId'))
    const candidateId = repo.checkCandidateId(c.req.param('candidateId'))
    const [training, quality, transform] = await Promise.all([
      repo.training(meta, candidateId), repo.quality(meta, candidateId),
      repo.transformation(meta, candidateId),
    ])
    return c.json({ schemaVersion: SCHEMA_VERSION,
      data: diagnosticView(training, quality, transform,
        `${meta.run_id}/${candidateId}/training_diagnostics.csv`) })
  })

  app.get('/api/v1/runs/:runId/integrity', async (c) => c.json({
    schemaVersion: SCHEMA_VERSION, data: integrity(await repo.metadata(c.req.param('runId'))),
  }))

  app.notFound((c) => c.json({ schemaVersion: SCHEMA_VERSION,
    error: { code: 'ROUTE_NOT_FOUND', message: 'API route not found' } }, 404))
  app.onError((error, c) => {
    if (error instanceof ApiError) {
      if (error.context) console.error(`[${error.code}] ${error.context}`)
      return c.json({ schemaVersion: SCHEMA_VERSION,
        error: { code: error.code, message: error.message } }, error.status)
    }
    console.error('[ARTIFACT_IO_ERROR] Unexpected API failure', error)
    return c.json({ schemaVersion: SCHEMA_VERSION,
      error: { code: 'ARTIFACT_IO_ERROR', message: 'Research API failed' } }, 500)
  })
  return app
}

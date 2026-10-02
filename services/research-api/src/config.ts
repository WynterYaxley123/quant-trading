import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readFileSync } from 'node:fs'
import { z } from 'zod'

export interface ApiConfig {
  reportRoot: string
  host: string
  port: number
  origins: string[]
  artifactId?: string
  optionalRoot?: boolean
  configurationError?: boolean
  registryPath?: string
}

const workspaceConfig = z.object({
  schemaVersion: z.literal('1.0.0'),
  artifactId: z.string().regex(/^[a-z0-9][a-z0-9-]*$/),
  reportRoot: z.string().min(1),
}).strict()

const DEFAULT_ORIGINS = ['http://127.0.0.1:5173', 'http://localhost:5173']

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ApiConfig {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
  let reportRoot = resolve(repoRoot, 'reports/research')
  let artifactId = env.RESEARCH_ARTIFACT_ID || undefined
  let optionalRoot = true
  let configurationError = false
  if (env.RESEARCH_REPORT_ROOT) {
    reportRoot = resolve(env.RESEARCH_REPORT_ROOT)
    optionalRoot = false
  } else if (env.RESEARCH_WORKSPACE_CONFIG) {
    optionalRoot = false
    try {
      const config = workspaceConfig.parse(JSON.parse(readFileSync(env.RESEARCH_WORKSPACE_CONFIG, 'utf8').replace(/^\uFEFF/, '')))
      reportRoot = resolve(dirname(resolve(env.RESEARCH_WORKSPACE_CONFIG)), config.reportRoot)
      artifactId ??= config.artifactId
    } catch {
      configurationError = true
    }
  }
  const host = env.HOST || '127.0.0.1'
  if (!['127.0.0.1', 'localhost', '::1'].includes(host)) {
    throw new Error('HOST must be a loopback address')
  }
  const port = env.PORT === undefined ? 8787 : Number(env.PORT)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('PORT must be an integer from 1 to 65535')
  }
  const origins = env.DASHBOARD_ORIGINS === undefined
    ? DEFAULT_ORIGINS
    : env.DASHBOARD_ORIGINS.split(',').map((origin) => origin.trim())
  if (!origins.length || origins.some((origin) => {
    try {
      const parsed = new URL(origin)
      return !['http:', 'https:'].includes(parsed.protocol) || parsed.origin !== origin || origin === '*'
    } catch {
      return true
    }
  })) {
    throw new Error('DASHBOARD_ORIGINS must be comma-separated exact http(s) origins, never *')
  }
  return { reportRoot, host, port, origins, artifactId, optionalRoot, configurationError,
    registryPath: resolve(repoRoot, 'services/research-api/config/development-workspaces.v1.json') }
}

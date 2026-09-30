import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export interface ApiConfig {
  reportRoot: string
  host: string
  port: number
  origins: string[]
}

const DEFAULT_ORIGINS = ['http://127.0.0.1:5173', 'http://localhost:5173']

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ApiConfig {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
  const reportRoot = resolve(env.RESEARCH_REPORT_ROOT || resolve(repoRoot, 'reports/research'))
  const host = env.HOST || '127.0.0.1'
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
  return { reportRoot, host, port, origins }
}

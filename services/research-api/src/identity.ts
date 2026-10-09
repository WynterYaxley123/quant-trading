/** Boot-time source/configuration proof. Reads source metadata, never research artifacts. */
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, realpathSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadConfig, type ApiConfig } from './config.js'

const serviceRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sha = (raw: string | Buffer) => createHash('sha256').update(raw).digest('hex')

export function sourceIdentity(root = serviceRoot): string {
  const files: Record<string, string> = {}
  function collect(prefix: string) {
    for (const entry of readdirSync(join(root, prefix), { withFileTypes: true })) {
      if (entry.isSymbolicLink()) throw new Error('RESEARCH_SOURCE_LINK_DENIED')
      const name = `${prefix}/${entry.name}`
      if (entry.isDirectory()) collect(name)
      else if (entry.isFile() && entry.name.endsWith('.ts')) files[name] = sha(readFileSync(join(root, name)))
    }
  }
  collect('src')
  for (const name of ['package.json', 'pnpm-lock.yaml', 'tsconfig.json', 'config/development-workspaces.v1.json']) {
    files[name] = sha(readFileSync(join(root, name)))
  }
  return sha(JSON.stringify(Object.fromEntries(Object.entries(files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))))
}

export function serviceIdentity(config: ApiConfig) {
  return {
    service: 'QUANT_RESEARCH_API',
    pid: process.pid,
    sourceSha256: sourceIdentity(),
    configurationSha256: sha(JSON.stringify({
      checkout: realpathSync(resolve(serviceRoot, '../..')),
      host: config.host, port: config.port, origins: [...config.origins].sort(),
      reportRoot: config.reportRoot, artifactId: config.artifactId ?? null,
      optionalRoot: config.optionalRoot ?? false, configurationError: config.configurationError ?? false,
      registryPath: config.registryPath ?? null,
    })),
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.stdout.write(JSON.stringify(serviceIdentity(loadConfig())) + '\n')
}

import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { loadConfig } from '../src/config.js'
import { serviceIdentity, sourceIdentity } from '../src/identity.js'
import { createApp } from '../src/app.js'

const roots: string[] = []
afterEach(() => roots.splice(0).forEach(root => rmSync(root, { recursive: true, force: true })))

describe('Research boot proof', () => {
  it('changes with source, locked dependencies and workspace registry bytes', () => {
    const root = mkdtempSync(join(tmpdir(), 'research-identity-synthetic-')); roots.push(root)
    mkdirSync(join(root, 'src')); mkdirSync(join(root, 'config'))
    const names = ['src/index.ts', 'package.json', 'pnpm-lock.yaml', 'tsconfig.json', 'config/development-workspaces.v1.json']
    for (const name of names) writeFileSync(join(root, name), 'SYNTHETIC_ONLY')
    const before = sourceIdentity(root)
    for (const name of names) {
      const saved = readFileSync(join(root, name)); writeFileSync(join(root, name), 'CHANGED_SYNTHETIC')
      expect(sourceIdentity(root)).not.toBe(before); writeFileSync(join(root, name), saved)
    }
    expect(sourceIdentity(root)).toBe(before)
  })

  it('binds actual viewer origins and workspace configuration independently of service health', async () => {
    const config = loadConfig({ HOST: '127.0.0.1', PORT: '8787', DASHBOARD_ORIGINS: 'http://127.0.0.1:5183' })
    const initial = serviceIdentity(config)
    for (const changed of [{ ...config, port: 8788 }, { ...config, origins: ['http://127.0.0.1:5184'] },
      { ...config, reportRoot: '/different-synthetic-root' }, { ...config, optionalRoot: false }]) {
      const identity = serviceIdentity(changed)
      expect(identity.configurationSha256).not.toBe(initial.configurationSha256)
      expect(identity.sourceSha256).toBe(initial.sourceSha256)
    }
    const app = createApp(config)
    const response = await app.request('/api/v1/health')
    expect((await response.json()).data.identity).toEqual(initial)
    expect(JSON.stringify(initial)).not.toContain(config.reportRoot)
  })
})

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { loadConfig } from '../src/config.js'
import { isExactOrigin } from '../src/origins.js'

const cases = JSON.parse(readFileSync(new URL('../../security/origin-cases.json', import.meta.url), 'utf8')) as {valid: string[], invalid: string[]}
describe('exact origin configuration contract', () => {
  for (const value of cases.valid) it(`accepts ${value}`, () => {
    expect(isExactOrigin(value)).toBe(true)
    expect(loadConfig({ DASHBOARD_ORIGINS: value }).origins).toEqual([value])
  })
  for (const value of cases.invalid) it(`rejects ${value}`, () => {
    expect(isExactOrigin(value)).toBe(false)
    expect(() => loadConfig({ DASHBOARD_ORIGINS: value })).toThrow()
  })
})

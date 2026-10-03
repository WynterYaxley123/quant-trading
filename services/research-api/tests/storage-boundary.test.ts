import { createHash } from 'node:crypto'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, expect, test } from 'vitest'
import { ArtifactStorage } from '../src/artifacts/storage.js'
import { metadataSchema } from '../src/schemas/artifacts.js'
import { writeRun } from './approval-fixture.js'

const roots: string[] = []
afterEach(async () => { for (const root of roots.splice(0)) await rm(root, {recursive:true,force:true}) })
async function root() {
  const value = await mkdtemp(join(tmpdir(), 'research-bounded-'))
  roots.push(value)
  return value
}
test('small hashed artifact is read exactly; mismatch and absence fail explicitly', async () => {
  const dir = await root()
  await writeFile(join(dir,'small.json'),'{}')
  const storage = new ArtifactStorage(dir,16)
  const sha = createHash('sha256').update('{}').digest('hex')
  expect(await storage.readHashed(['small.json'],sha)).toEqual({text:'{}',sha256:sha})
  await expect(storage.readHashed(['small.json'],'0'.repeat(64))).rejects.toMatchObject({code:'RESEARCH_ARTIFACT_HASH_MISMATCH'})
  await expect(storage.readHashed(['missing.json'])).rejects.toMatchObject({code:'ARTIFACT_IO_ERROR'})
  await expect(storage.readHashed(['missing.json'],null,'RUN_NOT_FOUND')).rejects.toMatchObject({code:'RUN_NOT_FOUND'})
})
test('oversized artifact is rejected before whole-file allocation', async () => {
  const dir = await root()
  await writeFile(join(dir,'large.json'),Buffer.alloc(17))
  await expect(new ArtifactStorage(dir,16).readHashed(['large.json'])).rejects.toMatchObject({code:'ARTIFACT_TOO_LARGE'})
})
test('approved hash namespace rejects arbitrary top-level extensions', async () => {
  const {metadata} = await writeRun(await root())
  expect(metadataSchema.safeParse(metadata).success).toBe(true)
  expect(metadataSchema.safeParse({...metadata,content_sha256:{...metadata.content_sha256,extra:'a'.repeat(64)}}).success).toBe(false)
})

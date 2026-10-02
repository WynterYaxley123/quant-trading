import { afterEach, describe, expect, it, vi } from 'vitest'
import { mkdtemp, mkdir, readFile, rm, symlink, utimes, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createApp } from '../src/app.js'
import { loadConfig } from '../src/config.js'
import { ArtifactRepository } from '../src/artifacts/repository.js'
import { ArtifactStorage } from '../src/artifacts/storage.js'
import { approved, fixtureRun, writeRegistry, writeRun } from './approval-fixture.js'
const roots: string[] = []
afterEach(async () => {vi.restoreAllMocks();for (const root of roots.splice(0)) await rm(root,{recursive:true,force:true})})
async function root() {const result=await mkdtemp(join(tmpdir(),'research-approval-test-'));roots.push(result);return result}
async function fixture() {
  const dir=await root(), run=await writeRun(dir)
  const registryPath=await writeRegistry(dir,[approved(fixtureRun,run.text)])
  const config={...loadConfig({RESEARCH_REPORT_ROOT:dir}),registryPath,artifactId:'test-development'}
  return {root:dir,run,registryPath,config,repo:new ArtifactRepository(dir,config)}
}
async function state(repo: ArtifactRepository) {const app=createApp(loadConfig({}),repo);return (await (await app.request('/api/v1/research/status')).json()).data}

describe('approved Development resolution and sealed file boundary', () => {
  it('admits complete approved bytes, verifies all hashes/schema, and leaves files unchanged on retry', async () => {
    const f=await fixture(), before=await readFile(join(f.run.runDir,'metadata.json'),'utf8')
    expect(await state(f.repo)).toMatchObject({artifactState:'AVAILABLE',artifactId:'test-development',approvalState:'APPROVED',availableRunCount:1,activeRunId:fixtureRun,integrityStatus:'PASS',readOnly:true,sealedValidation:true,sealedFinalOos:true})
    expect((await f.repo.integrityProof(fixtureRun)).verifiedContentFileCount).toBe(29)
    await state(f.repo)
    expect(await readFile(join(f.run.runDir,'metadata.json'),'utf8')).toBe(before)
  },15000)

  it('honors explicit root over local config, including an invalid explicit root without fallback', async () => {
    const f=await fixture(), configPath=join(f.root,'local.json')
    await writeFile(configPath,JSON.stringify({schemaVersion:'1.0.0',artifactId:'test-development',reportRoot:'wrong-root'}))
    const config={...loadConfig({RESEARCH_REPORT_ROOT:f.root,RESEARCH_WORKSPACE_CONFIG:configPath}),registryPath:f.registryPath}
    expect((await state(new ArtifactRepository(config.reportRoot,config))).artifactState).toBe('AVAILABLE')
    const bad={...loadConfig({RESEARCH_REPORT_ROOT:join(f.root,'absent'),RESEARCH_WORKSPACE_CONFIG:configPath}),registryPath:f.registryPath}
    expect(await state(new ArtifactRepository(bad.reportRoot,bad))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_INVALID'}})
  },15000)

  it('resolves a relative machine-local root and rejects malformed local configuration', async () => {
    const f=await fixture(), local=join(f.root,'local.json')
    await writeFile(local,JSON.stringify({schemaVersion:'1.0.0',artifactId:'test-development',reportRoot:'.'}))
    const config={...loadConfig({RESEARCH_WORKSPACE_CONFIG:local}),registryPath:f.registryPath}
    expect(config.reportRoot).toBe(f.root)
    expect((await state(new ArtifactRepository(config.reportRoot,config))).artifactState).toBe('AVAILABLE')
    await writeFile(local,'{broken')
    const bad=loadConfig({RESEARCH_WORKSPACE_CONFIG:local})
    expect(await state(new ArtifactRepository(bad.reportRoot,bad))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_CONFIGURATION_INVALID'}})
  },15000)

  it('keeps absent optional root and catalog honestly NOT_CONFIGURED', async () => {
    const dir=await root(), config=loadConfig({})
    for(const reportRoot of [dir,join(dir,'absent')]) expect(await state(new ArtifactRepository(reportRoot,{...config,optionalRoot:true}))).toMatchObject({artifactState:'NOT_CONFIGURED',activeRunId:null,integrityStatus:'NOT_CONFIGURED',sealedValidation:true})
  })

  it('rejects corrupt approved metadata without calling it unconfigured', async () => {
    const f=await fixture();await writeFile(join(f.run.runDir,'metadata.json'),'{corrupt')
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'ARTIFACT_SCHEMA_ERROR'}})
  })

  it('rejects changed metadata and changed content, including after an earlier successful observation', async () => {
    const f=await fixture();await state(f.repo)
    await writeFile(join(f.run.runDir,'D0','predictions.csv'),'tampered')
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_HASH_MISMATCH'}})
    await writeFile(join(f.run.runDir,'metadata.json'),JSON.stringify({...f.run.metadata,environment_changed:true}))
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_HASH_MISMATCH'}})
  },15000)

  for(const phase of ['VALIDATION','FINAL_OOS']) it(`rejects ${phase} metadata before any content file is opened`, async () => {
    const f=await fixture()
    await writeFile(join(f.run.runDir,'metadata.json'),JSON.stringify({...f.run.metadata,phase}))
    const reads=vi.spyOn(ArtifactStorage.prototype,'readHashed')
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_PHASE_FORBIDDEN'}})
    expect(reads.mock.calls.length).toBeGreaterThan(0)
    expect(reads.mock.calls.every(([segments])=>segments.at(-1)==='metadata.json')).toBe(true)
  })

  it('refuses an unapproved Development folder without opening metadata or performance', async () => {
    const f=await fixture(), other='iteration1_20260102_000000_000000_utc'
    const otherRoot=await root();await mkdir(join(otherRoot,'shenwan_sector_index',other),{recursive:true})
    await writeFile(join(otherRoot,'shenwan_sector_index',other,'metadata.json'),'{do not read}')
    const reads=vi.spyOn(ArtifactStorage.prototype,'readHashed')
    expect(await state(new ArtifactRepository(otherRoot,f.config))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_UNAPPROVED'}})
    expect(reads).not.toHaveBeenCalled()
    await expect(f.repo.metadata(other)).rejects.toMatchObject({code:'RESEARCH_ARTIFACT_UNAPPROVED'})
    expect(reads).not.toHaveBeenCalled()
  })

  it('rejects an approved run junction that escapes its configured root', async () => {
    const f=await fixture(), isolated=await root()
    await mkdir(join(isolated,'shenwan_sector_index'))
    await symlink(f.run.runDir,join(isolated,'shenwan_sector_index',fixtureRun),'junction')
    expect(await state(new ArtifactRepository(isolated,f.config))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'PATH_TRAVERSAL_BLOCKED'}})
  })

  it('orders two approved runs by registered metadata UTC time regardless of filesystem mtime', async () => {
    const f=await fixture(), newerId='iteration1_20260102_000000_000000_utc', newer=await writeRun(f.root,newerId)
    await writeRegistry(f.root,[approved(fixtureRun,f.run.text),approved(newerId,newer.text)])
    await utimes(f.run.runDir,new Date('2030-01-01'),new Date('2030-01-01'))
    expect((await f.repo.runs()).map(meta=>meta.run_id)).toEqual([newerId,fixtureRun])
    expect((await state(f.repo)).activeRunId).toBe(newerId)
  },15000)

  it('rejects approved but schema-malformed metadata and ambiguous/duplicate approval registries', async () => {
    const f=await fixture(), text=JSON.stringify({...f.run.metadata,candidate_family:['D0']})
    await writeFile(join(f.run.runDir,'metadata.json'),text);await writeRegistry(f.root,[approved(fixtureRun,text)])
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'ARTIFACT_SCHEMA_ERROR'}})
    await writeRegistry(f.root,[approved(fixtureRun,text),approved(fixtureRun,text)])
    expect(await state(f.repo)).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_APPROVAL_INVALID'}})
  })

  it('rejects ambiguous selection and unknown explicit identity before artifact access', async () => {
    const f=await fixture(), registry=JSON.parse(await readFile(f.registryPath,'utf8'))
    registry.workspaces.push({...registry.workspaces[0],artifactId:'second-approved-workspace'})
    await writeFile(f.registryPath,JSON.stringify(registry))
    const reads=vi.spyOn(ArtifactStorage.prototype,'readHashed')
    expect(await state(new ArtifactRepository(f.root,{...f.config,artifactId:undefined}))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_APPROVAL_AMBIGUOUS'}})
    expect(await state(new ArtifactRepository(f.root,{...f.config,artifactId:'unknown-workspace'}))).toMatchObject({artifactState:'DEGRADED',artifactError:{code:'RESEARCH_ARTIFACT_UNAPPROVED'}})
    expect(reads).not.toHaveBeenCalled()
  })

  it('rejects Host, Origin, write, force and sealed queries before any artifact read', async () => {
    const f=await fixture(), app=createApp(f.config), reads=vi.spyOn(ArtifactStorage.prototype,'readHashed')
    for(const [path,init] of [['/api/v1/health',{headers:{Host:'evil.example'}}],['/api/v1/health',{headers:{Origin:'https://evil.example'}}],['/api/v1/runs',{method:'POST'}],['/api/v1/runs?force=true',{}],['/api/v1/runs?bypass=true',{}],['/api/v1/runs?phase=validation',{}]] as const) expect((await app.request(path,init)).status).toBeGreaterThanOrEqual(400)
    expect(reads).not.toHaveBeenCalled()
  })
})

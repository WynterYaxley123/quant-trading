import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {overview,privateRanking,rev10Resource,CHARTS,EVIDENCE} from '../rev10.mjs';
import {createApi} from '../server.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const bytes=value=>JSON.stringify(value,null,2)+'\n';
async function fixture(t) {
  const temp=await mkdtemp(path.join(os.tmpdir(),'rev10-synthetic-'));t.after(()=>rm(temp,{recursive:true,force:true}));
  const preview=path.join(temp,'preview');await mkdir(preview);
  const specRaw=await readFile(path.join(ROOT,'config/research/swl1-rev10-short-v1.json'));
  const spec=JSON.parse(specRaw),u=JSON.parse(await readFile(path.join(ROOT,spec.universe_file)));
  const asof='2023-02-01',generation='SYNTHETIC_ONLY_TEST_FIXTURE';
  const rows=u.industries.map((code,i)=>({rank:i+1,industry_code:code,industry_name:u.metadata.find(r=>r.code===code).name,name_verified:true,rev10_score:(30-i)/10000,relative_score:(14.5-i)/10000,trailing_mean_return:-(30-i)/10000,data_asof:asof,data_completeness:'10_OF_10_FINITE_SESSIONS',source_generation:generation}));
  const ranking={status:'HISTORICAL_REPLAY',namespace:'RESEARCH_REPLAY_ONLY',asof,count:30,complete_universe:true,ranking_basis:'REV10_DESCENDING_CODE_ASCENDING_TIES',rows,top5:rows.slice(0,5),bottom5:[...rows].reverse().slice(0,5)};
  const observation={status:'HISTORICAL_REPLAY',namespace:'RESEARCH_REPLAY_ONLY',formal_forecast:false,future_numeric_rows_read:0,asof,cutoff:spec.historical_cutoff,names_reference_sha256:spec.universe_sha256,input_sha256:spec.view_sha256,source_generation:generation,window_sessions:['2023-01-18','2023-01-19','2023-01-20','2023-01-23','2023-01-24','2023-01-25','2023-01-26','2023-01-27','2023-01-30',asof]};
  const manifest={schema_version:1,namespace:'RESEARCH_REPLAY_ONLY',model_hash:sha(specRaw),asof,source_commit:spec.source_commit,count:30,files:{},implementation_sha256:{}};
  for(const [name,value] of Object.entries({'ranking.json':ranking,'scores.json':{rows},'observation.json':observation})) {const raw=bytes(value);await writeFile(path.join(preview,name),raw);manifest.files[name]=sha(raw);}
  for(const name of ['model.py','replay.py'])manifest.implementation_sha256[name]=sha(await readFile(path.join(ROOT,'research/swl1_rev10_short_v1',name)));
  const raw=bytes(manifest);await writeFile(path.join(preview,'manifest.json'),raw);
  return {preview,pin:sha(raw),ranking,manifest};
}
test('historical metrics are read from exact existing public reports; scientific states remain closed',async()=>{
  const actual=await overview(ROOT),report=JSON.parse(await readFile(path.join(ROOT,'reports/research/swl1_short_horizon_exploration/research-summary.json')));
  assert.deepEqual(actual.models.S2['10'].rank_ic,report.models.S2['10'].rank_ic);
  assert.deepEqual(actual.models.S2['5'].rank_ic,report.models.S2['5'].rank_ic);
  assert.equal(actual.readiness.real_sources_admitted,0);assert.equal(actual.readiness.formal_preregistration_active,false);
  assert.equal(actual.readiness.independent_validation_complete,false);assert.equal(actual.models.S0['10'].rank_ic.mean,null);
});
test('missing private configuration returns explicit unavailable without fabricated rows',async()=>{
  const value=await privateRanking(ROOT);assert.equal(value.count,0);assert.equal(value.asof,null);assert.equal(value.status,'UNAVAILABLE');
});
test('exact private manifest, names, full universe and extremes verified',async t=>{
  const f=await fixture(t),actual=await privateRanking(ROOT,f.preview,f.pin);
  assert.equal(actual.count,30);assert.deepEqual(actual.rows,f.ranking.rows);assert.deepEqual(actual.top5,f.ranking.top5);assert.deepEqual(actual.bottom5,f.ranking.bottom5);
  assert(!JSON.stringify(actual).includes(f.preview));assert.equal(actual.source_generation,'SYNTHETIC_ONLY_TEST_FIXTURE');
});
test('wrong pin and tampered leaf fail closed',async t=>{
  const f=await fixture(t);await assert.rejects(privateRanking(ROOT,f.preview,'a'.repeat(64)));
  await writeFile(path.join(f.preview,'ranking.json'),'{}');await assert.rejects(privateRanking(ROOT,f.preview,f.pin));
});
for(const corruption of ['missing-industry','wrong-name','wrong-order','future-asof','wrong-centering','bad-top5'])test(`synthetic internally rehashed ${corruption} denied`,async t=>{
  const f=await fixture(t),r=f.ranking;
  if(corruption==='missing-industry')r.rows.pop();
  if(corruption==='wrong-name')r.rows[0].industry_name='fabricated';
  if(corruption==='wrong-order')r.rows.reverse();
  if(corruption==='future-asof')r.asof='2026-09-30';
  if(corruption==='wrong-centering')r.rows[0].relative_score+=1;
  if(corruption==='bad-top5')r.top5=r.rows.slice(1,6);
  const raw=bytes(r);await writeFile(path.join(f.preview,'ranking.json'),raw);f.manifest.files['ranking.json']=sha(raw);
  const mr=bytes(f.manifest);await writeFile(path.join(f.preview,'manifest.json'),mr);
  await assert.rejects(privateRanking(ROOT,f.preview,sha(mr)));
});
test('all original charts and evidence links read exact pinned files',async()=>{
  for(const id of Object.keys(CHARTS)){const r=await rev10Resource(ROOT,'chart/'+id);assert.equal(r.contentType,'image/svg+xml; charset=utf-8');assert(r.raw.includes('EXPLORATORY_POST_HOC'));}
  for(const id of Object.keys(EVIDENCE))assert((await rev10Resource(ROOT,'evidence/'+id)).raw.length>0);
});
test('HTTP resources reject writes, traversal, arbitrary dates and paths',async t=>{
  const server=createApi({repoRoot:ROOT});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base=`http://127.0.0.1:${server.address().port}/api/industry-forecast/swl1-rev10/`;
  assert.equal((await fetch(base+'overview')).status,200);
  assert.equal((await fetch(base+'ranking',{method:'POST'})).status,405);
  assert.equal((await fetch(base+'ranking?date=2026-09-30')).status,404);
  assert.equal((await fetch(base+'ranking?path=secret')).status,404);
  assert.equal((await fetch(base+'evidence/private')).status,404);
  assert.equal((await fetch(base+'overview',{headers:{origin:'https://unknown.example'}})).status,403);
});

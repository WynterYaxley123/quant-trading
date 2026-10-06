import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createApi,families,observe,validateEvents,aggregate,compare} from '../server.mjs';
import {canonicalJSON} from '../../etf-quant-runner/security-audit.mjs';

const sha=b=>createHash('sha256').update(b).digest('hex');
const registry=JSON.parse(await readFile(new URL('../../../config/research/swl2-ridge-families.json',import.meta.url))).families;
const family=registry[0],now=Date.parse('2030-01-20T16:00:00+08:00');
const binding={family_id:family.family_id,source_commit:'a'.repeat(40),merge_commit:'b'.repeat(40),model_contract_hash:family.model_contract_hash,merge_at:'2030-01-02T16:00:00+08:00',freeze_at:'2030-01-03T16:00:00+08:00'};
function forecast() {
  return {schema_version:1,kind:'FORECAST',...Object.fromEntries(['family_id','source_commit','model_contract_hash'].map(k=>[k,binding[k]])),display_name:family.display_name,legacy_identity:family.legacy_identity,model_generation:1,signal_date:'2030-01-04',published_at:'2030-01-04T16:00:00+08:00',data_cutoff:'2030-01-04',taxonomy_identity:family.taxonomy_identity,industry_count:family.industry_codes.length,horizons:[10,40,120],target_contract:'SAME_DATE_CROSS_SECTION_EXCESS_INDUSTRY_RETURN',models:[],
    provenance:{data_source:'SYNTHETIC_SOURCE_C',source_commit:'c'.repeat(40),snapshot_sha256:'d'.repeat(64),data_cutoff:'2030-01-04',available_at:'2030-01-04T15:30:00+08:00',realized_series_type:'RECONSTRUCTED_SWL2_EQUAL_WEIGHT',historical_membership:'RECONSTRUCTED'},
    cross_section:family.industry_codes.map((c,i)=>({industry_code:c,industry_name:`合成行业 ${c}`,fused_rank:i+1,fused_score:-i,horizons:Object.fromEntries([10,40,120].map(h=>[h,{raw_prediction:-i,cross_section_zscore:-i,rank:i+1}]))}))};
}
function event(body,id='forecast_2030-01-04') {
  const body_json=canonicalJSON(body);return {event_id:id,body,body_json,body_hash:sha(body_json),previous_hash:null};
}
async function temp(t) {
  const root=await mkdtemp(path.join(os.tmpdir(),'industry-forecast-test-'));t.after(()=>rm(root,{recursive:true,force:true}));
  const namespace=path.join(root,'industry-forecast');await mkdir(namespace);return namespace;
}
async function generation(root,events=[event(forecast())]) {
  const namespace=path.join(root,family.family_id),run=path.join(namespace,'runs','synthetic_run');await mkdir(run,{recursive:true});
  const bodies={'binding.json':JSON.stringify(binding),'events.json':JSON.stringify({events})};
  for(const [n,b] of Object.entries(bodies))await writeFile(path.join(run,n),b);
  const manifest=JSON.stringify({run_id:'synthetic_run',schema_version:'1.0.0',contract:'FORWARD_INDUSTRY_FORECAST_LEDGER',files:Object.fromEntries(Object.entries(bodies).map(([n,b])=>[n,sha(b)]))});await writeFile(path.join(run,'manifest.json'),manifest);
  await writeFile(path.join(namespace,'latest.json'),JSON.stringify({run_id:'synthetic_run',manifest_sha256:sha(manifest)}));return run;
}
test('canonical naming, actual frozen universes and null empty metrics',async()=>{
  const f=await families();assert.deepEqual(f.map(v=>v.display_name),['SWL2-Ridge-V1','SWL2-Ridge-V2']);assert.deepEqual(f.map(v=>v.industry_codes.length),[107,124]);
  const view=await observe('',family,now);assert.equal(view.current,null);assert.equal(view.metrics[0].mean_rank_ic,null);assert.equal(view.metrics[0].top5_mean_return,null);assert.equal(view.metrics[0].matured_forecast_dates,0);
});
test('reads full immutable generation without state creation',async t=>{
  const root=await temp(t);await generation(root);const view=await observe(root,family,now);assert.equal(view.current.cross_section.length,107);assert.equal(view.current.provenance.realized_series_type,'RECONSTRUCTED_SWL2_EQUAL_WEIGHT');assert.equal(view.evaluations.length,0);assert.equal(view.metrics[0].mean_rank_ic,null);
});
test('tampered generation hash and path escape fail closed',async t=>{
  const root=await temp(t),run=await generation(root);await writeFile(path.join(run,'events.json'),'{}');await assert.rejects(observe(root,family,now));
  await writeFile(path.join(root,family.family_id,'latest.json'),JSON.stringify({run_id:'../escaped',manifest_sha256:'a'.repeat(64)}));await assert.rejects(observe(root,family,now));
});
test('symlink escape rejected',async t=>{
  if(process.platform==='win32'){t.skip('Unprivileged Windows symlink creation unavailable');return;}
  const root=await temp(t),outside=await temp(t),run=await generation(root);await rm(path.join(run,'events.json'));await writeFile(path.join(outside,'events.json'),'{}');await symlink(path.join(outside,'events.json'),path.join(run,'events.json'));await assert.rejects(observe(root,family,now));
});
for(const mutation of ['source','model','future','partial','duplicate','official','account','chain','pretransition'])test(`rejects ${mutation} event`,()=>{
  const b=forecast(),bind={...binding};let events;
  if(mutation==='source')b.source_commit='f'.repeat(40);
  if(mutation==='model')b.model_contract_hash='f'.repeat(64);
  if(mutation==='future')b.published_at='2031-01-04T16:00:00+08:00';
  if(mutation==='partial')b.cross_section=b.cross_section.slice(0,5);
  if(mutation==='official')b.provenance.realized_series_type='OFFICIAL_SWL2_INDEX';
  if(mutation==='account')b.cash=10000;
  if(mutation==='pretransition')bind.freeze_at='2030-01-04T00:00:00+08:00';
  events=[event(b)];if(mutation==='duplicate')events.push(event(b));if(mutation==='chain')events[0].previous_hash='f'.repeat(64);
  assert.throws(()=>validateEvents(events,bind,family,now));
});
test('shared matched industries comparison uses genuine common dates and same realized targets',()=>{
  const rows=family.industry_codes.map((c,i)=>({industry_code:c,forecast_score:-i,realized_return:-i/1000}));
  const e={signal_date:'2030-01-04',horizon:10,taxonomy_identity:family.taxonomy_identity,target_contract:'SAME_DATE_CROSS_SECTION_EXCESS_INDUSTRY_RETURN',realized_series_type:'RECONSTRUCTED_SWL2_EQUAL_WEIGHT',metrics:{realized:rows}};
  const result=compare({evaluations:[e,{...e,signal_date:'2030-01-05'}]},{evaluations:[e]})[0];assert.equal(result.matured_common_date_count,1);assert.equal(result.swl2_ridge_v1.mean_rank_ic,1);assert.equal(result.difference_v2_minus_v1.mean_rank_ic,0);assert.equal(result.common_industry_counts['2030-01-04'],107);
  const changed=structuredClone(e);changed.metrics.realized[0].realized_return+=.01;assert.throws(()=>compare({evaluations:[e]},{evaluations:[changed]}));
  assert.equal(aggregate([],10).median_rank_ic,null);
});
test('closed read-only routes, origins and paths',async t=>{
  const server=createApi({now:()=>now});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base=`http://127.0.0.1:${server.address().port}/api/industry-forecast`;
  const get=await fetch(`${base}/swl2-ridge-v1/current`);assert.equal(get.status,200);assert.equal((await get.json()).data.current,null);
  assert.equal((await fetch(`${base}/families`,{method:'POST'})).status,405);
  assert.equal((await fetch(`${base}/families?path=secret`)).status,404);
  assert.equal((await fetch(`${base}/families`,{headers:{Origin:'https://evil.invalid'}})).status,403);
  assert.equal((await fetch(`${base}/swl2-ridge/compare`)).status,200);
});

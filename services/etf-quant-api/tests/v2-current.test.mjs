import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {once} from 'node:events';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {observeV2Current} from '../v2-current.mjs';
import {createApi} from '../server.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
test('independent V2 route exposes an empty 10000 ledger before arming',async()=>{
  const view=await observeV2Current({repoRoot:root});
  assert.equal(view.strategy_version,'ETF_QUANT_V2');assert.equal(view.balance,'10000');
  assert.equal(view.started,false);assert.equal(view.armed,false);
  assert.equal(view.epoch_count,0);assert.deepEqual(view.nav,[]);
  assert.equal(view.mapping_summary.executable_industry_coverage,22);
  assert.equal(view.final_oos.open_count,1);assert.equal(view.broker_enabled,false);
});
test('persisted arming is read without manufacturing an epoch; forged identity fails',async t=>{
  const control=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-v2-control-'));
  t.after(()=>rm(control,{recursive:true,force:true}));
  const view=await observeV2Current({repoRoot:root});
  Object.assign(view,{armed:true,waiting_reason:'ARMED_NON_TRADING_DAY',latest_data_date:'2026-09-30'});
  await writeFile(path.join(control,'latest_observation.json'),JSON.stringify({strategy_version:'ETF_QUANT_V2',view}));
  const observed=await observeV2Current({repoRoot:root,controlRoot:control});
  assert.equal(observed.armed,true);assert.equal(observed.fill_count,0);
  view.candidate_sha256='a'.repeat(64);
  await writeFile(path.join(control,'latest_observation.json'),JSON.stringify({strategy_version:'ETF_QUANT_V2',view}));
  await assert.rejects(observeV2Current({repoRoot:root,controlRoot:control}));
});
test('V2 current HTTP boundaries remain local, bounded and read only',async t=>{
  const server=createApi({repoRoot:root});server.listen(0,'127.0.0.1');await once(server,'listening');t.after(()=>server.close());
  const base=`http://127.0.0.1:${server.address().port}/api/etf-quant/v2/current`;
  const response=await fetch(base);assert.equal(response.status,200);
  assert.equal((await response.json()).data.strategy_version,'ETF_QUANT_V2');
  for(const [url,options,status] of [[base,{method:'POST'},405],[base,{headers:{Origin:'https://external.invalid'}},403],[base+'?path=secret',{},400],[base+'/../private',{},400]])
    assert.equal((await fetch(url,options)).status,status);
  const runtime=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-v2-runtime-'));t.after(()=>rm(runtime,{recursive:true,force:true}));
  await mkdir(path.join(runtime,'runs'));
  await writeFile(path.join(runtime,'latest.json'),JSON.stringify({run_id:'../other',manifest_sha256:'a'.repeat(64)}));
  await assert.rejects(observeV2Current({repoRoot:root,runtimeRoot:runtime}));
});
test('provider waiting receipt stays visible before the first V2 business generation',async t=>{
  const control=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-v2-provider-wait-'));
  t.after(()=>rm(control,{recursive:true,force:true}));
  await writeFile(path.join(control,'latest_observation.json'),JSON.stringify({
    strategy_version:'ETF_QUANT_V2',status:'WAITING_FOR_PROVIDER_DATA',
    reason_code:'SOURCE_SESSION_INCOMPLETE',shadow_runtime_armed:true,data_cutoff:'2026-09-30'}));
  const view=await observeV2Current({repoRoot:root,controlRoot:control});
  assert.equal(view.armed,true);assert.equal(view.waiting_reason,'SOURCE_SESSION_INCOMPLETE');
  assert.equal(view.latest_data_date,'2026-09-30');assert.equal(view.epoch_count,0);
  assert.deepEqual(view.nav,[]);assert.equal(view.balance,'10000');
  const runtime=path.join(control,'SYNTHETIC-runtime'),runId='SYNTHETIC_001';
  const directory=path.join(runtime,'runs',runId);await mkdir(directory,{recursive:true});
  const started={...view,started:true,epoch_count:1,signal_count:1,intent_count:1,
    waiting_reason:null,next_accounting_state:'AWAITING_FINALIZED_T_PLUS_ONE',
    nav:[{date:'2026-09-29',normalized_nav:1}]};
  const hash=raw=>createHash('sha256').update(raw).digest('hex');
  const bodies={'state.json':'{}','view.json':JSON.stringify(started)};
  const manifest=JSON.stringify({run_id:runId,strategy_version:'ETF_QUANT_V2',
    release_sha256:view.release_sha256,created_at:'2026-09-29T08:00:00+00:00',
    files:Object.fromEntries(Object.entries(bodies).map(([name,raw])=>[name,hash(raw)]))});
  for(const [name,raw] of Object.entries({...bodies,'manifest.json':manifest}))await writeFile(path.join(directory,name),raw);
  await writeFile(path.join(runtime,'latest.json'),JSON.stringify({run_id:runId,manifest_sha256:hash(manifest)}));
  await writeFile(path.join(control,'latest_observation.json'),JSON.stringify({
    strategy_version:'ETF_QUANT_V2',status:'WAITING_FOR_PROVIDER_DATA',
    reason_code:'SOURCE_SESSION_INCOMPLETE',shadow_runtime_armed:true,
    observed_at:'2026-09-30T08:00:00+00:00',data_cutoff:'2026-09-29'}));
  const waiting=await observeV2Current({repoRoot:root,controlRoot:control,runtimeRoot:runtime});
  assert.equal(waiting.waiting_reason,'SOURCE_SESSION_INCOMPLETE');
  assert.equal(waiting.next_accounting_state,'AWAITING_FINALIZED_T_PLUS_ONE');
  assert.equal(waiting.signal_count,1);assert.equal(waiting.intent_count,1);
  assert.deepEqual(waiting.nav,started.nav);
});

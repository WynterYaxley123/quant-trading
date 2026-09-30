import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {emptyView,createApi,PREFIX} from '../server.mjs';

const sha=b=>createHash('sha256').update(b).digest('hex');
const bytes=v=>Buffer.from(JSON.stringify(v));
async function observe(t,mutate=()=>{}) {
  const root=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-formal-t0-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  const v=emptyView(), updated='2026-09-30T10:00:00Z';
  v.strategy={...v.strategy,execution_policy:'B40_WITH_CASH',
    rebalance:'EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1',cash_semantics:'UNALLOCATED_EXECUTION_CAPACITY'};
  v.status={...v.status,updated_at:updated,signal_date:'2026-09-30',cutoff:'2026-09-30',
    code_commit:'d'.repeat(40),source_commit:'e'.repeat(40),snapshot_id:'f'.repeat(64),
    mapping_hash:'a'.repeat(64),strategy_hash:'b'.repeat(64),execution_policy:'B40_WITH_CASH',phase:'SHADOW_CASH_ONLY'};
  const slots=[0,1,2,3,4].map(i=>({industry_code:String(3701+i),etf_code:null,target_weight:.2,
    cash_retained_weight:.2,mapping_type:'CASH_UNEXECUTABLE_SIGNAL',execution_reason:'NO_ORDER_UNEXECUTABLE_SIGNAL'}));
  v.mappings={...v.mappings,status:'READY',slots,entries:[],cash_weight:1,risk_asset_weight:0};
  const safety={simulation_only:true,broker_enabled:false,real_order_path:false};
  v.status.shadow_epoch={...safety,epoch_id:'SYNTHETIC_EPOCH',created_at:updated,candidate_hash:'c'.repeat(64),
    initial_capital:'10000',initial_cash:'10000',initial_positions:[],first_signal_date:'2026-09-30',
    available_from:'2026-09-29T22:00:00+08:00',source_commit:v.status.source_commit};
  v.status.formal_signal={...safety,epoch_id:'SYNTHETIC_EPOCH',candidate_hash:'c'.repeat(64),
    pit_registry_hash:'a'.repeat(64),strict_registry_hash:'b'.repeat(64),code_sha:v.status.code_commit,
    available_from:v.status.shadow_epoch.available_from,source_commit:v.status.source_commit,
    signal_date:'2026-09-30',decision_at:updated,slots,cash_weight:1,risk_asset_weight:0};
  v.status.shadow_epoch_created=true;
  mutate(v);
  const run='SYNTHETIC_FORMAL', folder=path.join(root,'runs',run);
  await mkdir(folder,{recursive:true});
  const files={'view.json':bytes(v),'state.json':bytes({synthetic:true}),'prefix.json':bytes({})};
  const meta={schema_version:'1.0.0',run_id:run,status:'SUCCESSFUL_OBSERVATION',snapshot_id:v.status.snapshot_id,
    mapping_hash:v.status.mapping_hash,strategy_hash:v.status.strategy_hash,code_commit:v.status.code_commit,
    files:Object.fromEntries(Object.entries(files).map(([k,b])=>[k,sha(b)]))};
  for(const [k,b] of Object.entries(files)) await writeFile(path.join(folder,k),b);
  const raw=bytes(meta);await writeFile(path.join(folder,'manifest.json'),raw);
  await writeFile(path.join(root,'latest.json'),bytes({run_id:run,manifest_sha256:sha(raw)}));
  const api=createApi({runtimeRoot:root,now:()=>Date.parse('2026-09-30T11:00:00Z')});
  api.listen(0,'127.0.0.1');await once(api,'listening');
  t.after(()=>new Promise(r=>api.close(r)));
  return new Promise((resolve,reject)=>http.get({hostname:'127.0.0.1',port:api.address().port,path:PREFIX+'status'},res=>{
    const b=[];res.on('data',c=>b.push(c));res.on('end',()=>resolve({status:res.statusCode,body:JSON.parse(Buffer.concat(b))}));
  }).on('error',reject));
}

test('formal T0 all-Cash epoch is readable without inventing a T1 account',async t=>{
  const r=await observe(t);assert.equal(r.status,200);assert.equal(r.body.data.epoch,null);
  assert.equal(r.body.data.shadow_epoch_created,true);assert.equal(r.body.data.phase,'SHADOW_CASH_ONLY');
});
for(const mutate of [v=>{v.status.formal_signal.candidate_hash='f'.repeat(64);},
  v=>{v.status.shadow_epoch.broker_enabled=true;},v=>{v.status.shadow_epoch.first_signal_date='2026-09-24';},
  v=>{v.status.formal_signal.available_from='2099-01-01T00:00:00Z';},
  v=>{v.status.formal_signal.slots=[];}]) {
  test('forged formal T0 provenance is rejected even with self-consistent file hashes',async t=>{
    assert.equal((await observe(t,mutate)).status,503);
  });
}

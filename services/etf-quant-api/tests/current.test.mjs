import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {once} from 'node:events';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createApi,emptyView,PREFIX} from '../server.mjs';
import {aggregateCurrent} from '../current.mjs';

const sha=b=>createHash('sha256').update(b).digest('hex');
const bytes=v=>Buffer.from(JSON.stringify(v));
async function save(file,body) {await mkdir(path.dirname(file),{recursive:true});await writeFile(file,body);}
async function fixture(t,{failed=false,started=false,usable=true}={}) {
  const temp=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-current-status-'));
  t.after(()=>rm(temp,{recursive:true,force:true}));
  const repo=path.join(temp,'repo'),control=path.join(temp,'control'),runtime=path.join(temp,'runtime');
  await Promise.all([repo,control,runtime].map(p=>mkdir(p)));
  execFileSync('git',['init','-q'],{cwd:repo});
  execFileSync('git',['-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','--allow-empty','-qm','fixture'],{cwd:repo});
  const certified={};
  const names=['reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json',
    'reports/etf_quant/production_pit_evidence_registry_v1.json','strategies/etf_quant/config/verified_mappings_v1.json'];
  for(const name of names) {const body=bytes({synthetic:name});certified[name]=sha(body);await save(path.join(repo,name),body);}
  const release={project:'ETF-Quant V1',mode:'SIMULATION_ONLY',generated_at:'2026-09-30T12:00:00Z',as_of:'2026-09-30',
    code_sha:'d'.repeat(40),candidate_hash:certified[names[0]],pit_registry_hash:certified[names[1]],strict_registry_hash:certified[names[2]],
    cnequity_pin:'e'.repeat(40),broker_enabled:false,real_order_path:false,engineering_complete:true,production_usable:usable,
    factual_pipeline:'PASS',model_readiness:{status:'PASS',as_of:'2026-09-30',horizons:{}},
    evidence:{production_pit:'PASS',strict_registry:'PASS',sws:'PASS_WITH_KNOWN_LIMITATION',known_limitation:'SYNTHETIC'},
    certified_files:certified,one_shot_command:'SYNTHETIC_READ_ONLY_COMMAND',
    superseded_failure_codes:['MODEL_WARMUP_INCOMPLETE'],superseded_before:'2026-09-30T12:00:00Z'};
  await save(path.join(repo,'reports/etf_quant/etf_quant_v1_final_release_v1.json'),bytes(release));
  const id='f'.repeat(64),calendar=Buffer.from('trade_date,is_trading\n2026-09-25,false\n2026-09-30,true\n2026-10-01,false\n2026-10-08,true\n2026-10-09,true\n');
  const manifest=bytes({snapshot_id:id,source_commit:release.cnequity_pin,data_cutoff:'2026-09-30',created_at:'2026-09-30T12:00:00Z',
    files:{'trading_calendar.csv':sha(calendar)}});
  await save(path.join(control,`exports/${id}/manifest.json`),manifest);
  await save(path.join(control,`exports/${id}/trading_calendar.csv`),calendar);
  await save(path.join(control,'latest_export.json'),bytes({snapshot_id:id,manifest_sha256:sha(manifest)}));
  await save(path.join(control,'latest_observation.json'),bytes({status:'READY_NO_SIGNAL',data_cutoff:'2026-09-30',
    shadow_runtime_armed:true,shadow_start_gate:'ARMED_FOR_NEXT_ELIGIBLE_T',refresh:{refresh_attempted:false}}));
  if(failed) {
    const failure=bytes({status:'FAILED',blocker:'MODEL_WARMUP_INCOMPLETE',processed_at:'2026-09-30T12:00:00Z',
      validation_opened:false,final_oos_read:false});
    const m=bytes({schema_version:'1.0.0',run_id:'old',status:'FAILED',files:{'failure.json':sha(failure)}});
    await save(path.join(runtime,'failures/old/failure.json'),failure);
    await save(path.join(runtime,'failures/old/manifest.json'),m);
    await save(path.join(runtime,'last_attempt.json'),bytes({run_id:'old',manifest_sha256:sha(m)}));
  }
  if(started) {
    const view=emptyView(),at='2026-09-30T13:00:00Z';
    view.strategy={...view.strategy,execution_policy:'B40_WITH_CASH',
      rebalance:'EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1',cash_semantics:'UNALLOCATED_EXECUTION_CAPACITY'};
    view.status={...view.status,updated_at:at,signal_date:'2026-09-30',cutoff:'2026-09-30',code_commit:release.code_sha,
      source_commit:release.cnequity_pin,snapshot_id:id,mapping_hash:'a'.repeat(64),strategy_hash:'b'.repeat(64),
      execution_policy:'B40_WITH_CASH',phase:'SHADOW_CASH_ONLY',shadow_epoch_created:true};
    const slots=[0,1,2,3,4].map(i=>({industry_code:String(3701+i),etf_code:null,target_weight:.2,cash_retained_weight:.2,
      mapping_type:'CASH_UNEXECUTABLE_SIGNAL',execution_reason:'NO_ORDER_UNEXECUTABLE_SIGNAL'}));
    view.mappings={...view.mappings,status:'READY',slots,entries:[],cash_weight:1,risk_asset_weight:0};
    const common={simulation_only:true,broker_enabled:false,real_order_path:false,epoch_id:'SYNTHETIC_EPOCH',candidate_hash:release.candidate_hash,
      source_commit:release.cnequity_pin,available_from:'2026-09-30T12:00:00Z'};
    view.status.shadow_epoch={...common,created_at:at,first_signal_date:'2026-09-30',initial_capital:'10000',initial_cash:'10000',initial_positions:[]};
    view.status.formal_signal={...common,signal_date:'2026-09-30',decision_at:at,code_sha:release.code_sha,
      pit_registry_hash:release.pit_registry_hash,strict_registry_hash:release.strict_registry_hash,slots,cash_weight:1,risk_asset_weight:0,t1_status:'NO_ORDER'};
    const bodies={'view.json':bytes(view),'state.json':bytes({synthetic:true}),'prefix.json':bytes({synthetic:true})};
    const m=bytes({schema_version:'1.0.0',run_id:'t0',status:'SUCCESSFUL_OBSERVATION',snapshot_id:id,
      mapping_hash:view.status.mapping_hash,strategy_hash:view.status.strategy_hash,code_commit:release.code_sha,
      files:Object.fromEntries(Object.entries(bodies).map(([k,v])=>[k,sha(v)]))});
    for(const [k,v] of Object.entries({...bodies,'manifest.json':m})) await save(path.join(runtime,'runs/t0',k),v);
    await save(path.join(runtime,'latest.json'),bytes({run_id:'t0',manifest_sha256:sha(m)}));
  }
  let time=Date.parse('2026-09-30T17:00:00Z');
  const server=createApi({runtimeRoot:runtime,controlRoot:control,repoRoot:repo,now:()=>time});
  server.listen(0,'127.0.0.1');await once(server,'listening');t.after(()=>server.close());
  const url=`http://127.0.0.1:${server.address().port}${PREFIX}`;
  return {repo,control,runtime,release,names,setTime:v=>time=Date.parse(v),
    async get(resource='current',method='GET') {const r=await fetch(url+resource,{method});return {status:r.status,body:await r.json()};}};
}
test('armed current status accepts missing formal namespace and exposes certified hashes',async t=>{
  const f=await fixture(t),r=await f.get();assert.equal(r.status,200);
  assert.equal(r.body.data.production_usable,true);assert.equal(r.body.data.shadow_runtime_armed,true);
  assert.equal(r.body.data.formal.epoch_count,0);assert.equal(r.body.data.formal.nav,null);
  assert.equal(r.body.data.latest_finalized_market_date,'2026-09-30');
  assert.equal(r.body.data.provenance.candidate_hash,f.release.candidate_hash);
  assert.equal(r.body.data.runner.status,'READY_NO_SIGNAL');assert.equal(r.body.data.broker_enabled,false);
});
test('historical model failure does not override current armed status or fabricate mapping',async t=>{
  const f=await fixture(t,{failed:true}),r=await f.get();
  assert.equal(r.status,200);assert.equal(r.body.data.historical_status.status,'SUPERSEDED / HISTORICAL');
  assert.equal(r.body.data.shadow_start_gate,'ARMED_FOR_NEXT_ELIGIBLE_T');
  assert.equal((await f.get('status')).body.data.phase,'ARMED');
  assert.equal((await f.get('health')).body.data.blockers.length,0);
  assert.equal((await f.get('mappings')).body.data.status,'AWAITING_FORMAL_SIGNAL');
});
test('verified formal epoch wins over stale pre-start receipt without inventing T1 accounting',async t=>{
  const f=await fixture(t,{started:true}),r=await f.get();assert.equal(r.status,200);
  assert.equal(r.body.data.shadow_start_gate,'STARTED');assert.equal(r.body.data.formal.epoch_id,'SYNTHETIC_EPOCH');
  assert.equal(r.body.data.formal.epoch_count,1);assert.equal(r.body.data.formal.cash_weight,1);
  assert.equal(r.body.data.formal.fill_count,0);assert.equal(r.body.data.formal.nav,null);
  assert.equal(r.body.data.formal.intent_count,null); // stale receipt cannot claim a current count
});
test('next eligible date changes with official calendar and Shanghai clock',async t=>{
  const f=await fixture(t);assert.equal((await f.get()).body.data.calendar.next_eligible_trading_date,'2026-10-08');
  f.setTime('2026-10-08T06:00:00Z');assert.equal((await f.get()).body.data.calendar.next_eligible_trading_date,'2026-10-08');
  f.setTime('2026-10-08T08:00:00Z');assert.equal((await f.get()).body.data.calendar.next_eligible_trading_date,'2026-10-09');
});
test('production usability is read from certification, never hardcoded true',async t=>{
  const f=await fixture(t,{usable:false}),r=await f.get();assert.equal(r.status,200);
  assert.equal(r.body.data.production_usable,false);assert.equal(r.body.data.shadow_runtime_armed,false);
});
test('certified input corruption fails closed with no private path or stack',async t=>{
  const f=await fixture(t);await writeFile(path.join(f.repo,f.names[0]),'tampered');
  const r=await f.get();assert.equal(r.status,503);assert.equal(r.body.error.code,'RUNTIME_INTEGRITY_BLOCKER');
  assert.ok(!JSON.stringify(r.body).includes(f.repo));
});
test('current status endpoint is read-only and query free',async t=>{
  const f=await fixture(t);assert.equal((await f.get('current','POST')).status,405);
  assert.equal((await f.get('current?file=private')).status,400);
});
test('unknown or newer failure is not silently superseded by old certification',async t=>{
  const f=await fixture(t,{failed:true});
  const release={...f.release,superseded_before:'2026-09-29T12:00:00Z'};
  await writeFile(path.join(f.repo,'reports/etf_quant/etf_quant_v1_final_release_v1.json'),bytes(release));
  const r=await f.get();assert.equal(r.body.data.historical_status,null);
  assert.equal(r.body.data.shadow_runtime_armed,false);assert.equal(r.body.data.shadow_start_gate,'BLOCKED_INTEGRITY');
  assert.equal((await f.get('health')).body.data.status,'DEGRADED');
});

test('actual versioned repository preserves frozen V1 certification through an explicit transition',async t=>{
  const f=await fixture(t),repoRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
  const release=JSON.parse(await readFile(path.join(repoRoot,'reports/etf_quant/etf_quant_v1_final_release_v1.json')));
  const id='f'.repeat(64),calendar=Buffer.from('trade_date,is_trading\n2026-09-30,true\n2026-10-04,false\n2026-10-08,true\n2026-10-09,true\n');
  const manifest=bytes({snapshot_id:id,source_commit:release.cnequity_pin,data_cutoff:'2026-09-30',created_at:'2026-09-30T12:00:00Z',files:{'trading_calendar.csv':sha(calendar)}});
  await save(path.join(f.control,`exports/${id}/manifest.json`),manifest);
  await save(path.join(f.control,`exports/${id}/trading_calendar.csv`),calendar);
  await save(path.join(f.control,'latest_export.json'),bytes({snapshot_id:id,manifest_sha256:sha(manifest)}));
  const now=()=>Date.parse('2026-10-04T08:00:00Z');
  assert.equal((await aggregateCurrent({controlRoot:f.control,repoRoot,view:emptyView(),now:now()})).formal.epoch_count,0);
  const server=createApi({runtimeRoot:f.runtime,controlRoot:f.control,repoRoot,now});
  server.listen(0,'127.0.0.1');await once(server,'listening');t.after(()=>server.close());
  const response=await fetch(`http://127.0.0.1:${server.address().port}${PREFIX}current`),body=await response.json();
  assert.equal(response.status,200);assert.equal(body.data.shadow_runtime_armed,true);
  assert.equal(body.data.provenance.candidate_hash,release.candidate_hash);
  assert.equal(body.data.formal.epoch_count,0);assert.equal(body.data.formal.signal_count,0);
  assert.equal(body.data.formal.nav,null);assert.equal(body.data.calendar.next_eligible_trading_date,'2026-10-08');
  const certificate=JSON.parse(await readFile(path.join(repoRoot,'reports/engineering/etf-quant-v2-factual-refresh-integrity.json')));
  for(const name of [...Object.keys(certificate.implementation_integrity.files),'reports/engineering/etf-quant-v2-factual-refresh-integrity.json','reports/etf_quant/etf_quant_v1_final_release_v1.json']) {
    await save(path.join(f.repo,name),await readFile(path.join(repoRoot,name)));
  }
  await save(path.join(f.repo,'services/etf-quant-api/server.mjs'),Buffer.from('UNREVIEWED_SERVER_DRIFT'));
  f.setTime('2026-10-04T08:00:00Z');
  const corrupted=await f.get();assert.equal(corrupted.status,503);
  assert.equal(corrupted.body.error.code,'RUNTIME_INTEGRITY_BLOCKER');
});

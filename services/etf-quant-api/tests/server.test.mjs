import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { mkdtemp, writeFile, mkdir, rm, symlink } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createApi, emptyView, ENDPOINTS, PREFIX, strategy } from '../server.mjs';

const sha = b=>createHash('sha256').update(b).digest('hex');
const bytes = value=>Buffer.from(JSON.stringify(value));
async function fixture(t) {
  const root=await mkdtemp(path.join(os.tmpdir(),'etf-api-synthetic-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  return root;
}
async function generation(root,view=emptyView(),mutate=()=>{}) {
  const run='SYNTHETIC_001';
  const folder=path.join(root,'runs',run);
  await mkdir(folder,{recursive:true});
  view.status.snapshot_id='a'.repeat(64);
  view.status.mapping_hash='b'.repeat(64);
  view.status.strategy_hash='c'.repeat(64);
  view.status.code_commit='d'.repeat(40);
  view.status.updated_at='2026-09-27T10:00:00Z';
  mutate(view);
  const bodies={'view.json':bytes(view),'state.json':bytes({synthetic:true}),'prefix.json':bytes({synthetic:true})};
  const manifest={schema_version:'1.0.0',run_id:run,status:'SUCCESSFUL_OBSERVATION',snapshot_id:view.status.snapshot_id,
    mapping_hash:view.status.mapping_hash,strategy_hash:view.status.strategy_hash,code_commit:view.status.code_commit,
    files:Object.fromEntries(Object.entries(bodies).map(([k,v])=>[k,sha(v)]))};
  for (const [name,body] of Object.entries(bodies)) await writeFile(path.join(folder,name),body);
  const raw=bytes(manifest);
  await writeFile(path.join(folder,'manifest.json'),raw);
  await writeFile(path.join(root,'latest.json'),bytes({run_id:run,manifest_sha256:sha(raw)}));
  return folder;
}
async function server(t,root) {
  const app=createApi({runtimeRoot:root,now:()=>Date.parse('2026-09-27T12:00:00Z')});
  app.listen(0,'127.0.0.1');
  await once(app,'listening');
  t.after(()=>new Promise(r=>app.close(r)));
  return app.address().port;
}
async function request(port,resource,method='GET',headers={}) {
  return new Promise((resolve,reject)=>{
    const req=http.request({hostname:'127.0.0.1',port,path:resource,method,headers},res=>{
      const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>{
        const text=Buffer.concat(chunks).toString();
        resolve({status:res.statusCode,headers:res.headers,body:text?JSON.parse(text):null,text});
      });
    });req.on('error',reject);req.end();
  });
}

for (const resource of Object.keys(ENDPOINTS)) test(`GET ${resource} has an independent V1 envelope`,async t=>{
  const root=await fixture(t);await generation(root);
  const reply=await request(await server(t,root),PREFIX+resource);
  assert.equal(reply.status,200);assert.equal(reply.body.schemaVersion,'1.0.0');assert.equal(reply.body.error,null);
  assert.equal(reply.body.meta.etfQuant,true);assert.equal(reply.body.meta.runId,'SYNTHETIC_001');
});

test('unconfigured runtime is explicit NOT_STARTED, not mock cash or NAV',async t=>{
  const port=await server(t,'');
  const summary=(await request(port,PREFIX+'portfolio/summary')).body.data;
  assert.equal(summary.total_equity,null);assert.equal(summary.cash,null);assert.equal(summary.sharpe,null);
  assert.deepEqual((await request(port,PREFIX+'portfolio/nav')).body.data,[]);
  assert.equal((await request(port,PREFIX+'status')).body.data.reason,'RUNTIME_ROOT_NOT_CONFIGURED');
});
for (const method of ['POST','PUT','PATCH','DELETE']) test(`${method} never mutates runtime`,async t=>{
  const root=await fixture(t);const folder=await generation(root);const port=await server(t,root);
  const response=await request(port,PREFIX+'portfolio/summary',method);
  assert.equal(response.status,405);assert.equal(response.body.error.code,'READ_ONLY_API');
  assert.equal(response.headers.allow,'GET, HEAD, OPTIONS');
});
test('HEAD and exact local OPTIONS only',async t=>{
  const port=await server(t,'');
  const head=await request(port,PREFIX+'status','HEAD');assert.equal(head.status,200);assert.equal(head.text,'');
  const good=await request(port,PREFIX+'status','OPTIONS',{Origin:'http://localhost:5173'});
  assert.equal(good.status,204);assert.equal(good.headers['access-control-allow-origin'],'http://localhost:5173');
  assert.equal((await request(port,PREFIX+'status','GET',{Origin:'https://example.invalid'})).status,403);
  assert.equal((await request(port,PREFIX+'status','GET',{Host:'evil.invalid'})).status,403);
});
for (const resource of ['../status','%2e%2e/status','portfolio%2fnav','status?file=x','status\\x','status//x']) {
  test(`raw traversal guard ${resource}`,async t=>assert.equal((await request(await server(t,''),PREFIX+resource)).status,400));
}
test('unknown closed route is 404',async t=>assert.equal((await request(await server(t,''),PREFIX+'orders')).status,404));

for (const file of ['view.json','state.json','prefix.json','manifest.json']) test(`tampered ${file} fails hash gate`,async t=>{
  const root=await fixture(t);const folder=await generation(root);
  await writeFile(path.join(folder,file),'SYNTHETIC_TAMPER');
  const response=await request(await server(t,root),PREFIX+'status');
  assert.equal(response.status,503);assert.equal(response.body.error.code,'RUNTIME_INTEGRITY_BLOCKER');
  assert.ok(!response.text.includes(root));assert.ok(!response.text.includes('stack'));
});
test('missing committed payload is corruption, not no-runtime fallback',async t=>{
  const root=await fixture(t);const folder=await generation(root);
  await rm(path.join(folder,'state.json'));
  assert.equal((await request(await server(t,root),PREFIX+'status')).status,503);
});
test('pointer traversal and realpath containment',async t=>{
  const root=await fixture(t);await generation(root);
  await writeFile(path.join(root,'latest.json'),bytes({run_id:'../escape',manifest_sha256:'a'.repeat(64)}));
  assert.equal((await request(await server(t,root),PREFIX+'status')).status,503);
});
test('repository roots are rejected',async t=>{
  const root=await fixture(t);await mkdir(path.join(root,'.git'));await generation(root);
  assert.equal((await request(await server(t,root),PREFIX+'status')).status,503);
});
for (const kind of ['absolute-path','credentials','fake-preepoch']) test(`unsafe public DTO ${kind} rejected`,async t=>{
  const root=await fixture(t);
  await generation(root,emptyView(),v=>{
    if(kind==='absolute-path')v.health.notes='D:\\SYNTHETIC\\private';
    if(kind==='credentials')v.health.password='SYNTHETIC_NOT_A_REAL_PASSWORD';
    if(kind==='fake-preepoch')v.nav=[{timestamp:'2020-01-01T00:00:00Z',normalized_nav:'1'}];
  });
  assert.equal((await request(await server(t,root),PREFIX+'health')).status,503);
});
test('stale last-success state remains visible with freshness warning',async t=>{
  const root=await fixture(t);
  await generation(root,emptyView(),v=>{v.status.updated_at='2026-09-24T10:00:00Z';});
  const data=(await request(await server(t,root),PREFIX+'health')).body.data;
  assert.equal(data.freshness,'STALE');
});
test('public frozen constants do not couple to Research',()=>{
  assert.deepEqual(strategy.fusion,{'10':.25,'40':.5,'120':.25});assert.equal(strategy.alpha,.01);
  assert.equal(strategy.h10_factors.length,5);assert.equal(strategy.h40_factors.length,19);
  assert.equal(strategy.broker_enabled,false);
});

test('directory link cannot escape the runtime root',async t=>{
  const root=await fixture(t), outside=await fixture(t);
  const folder=await generation(outside);
  await mkdir(path.join(root,'runs'));
  await symlink(folder,path.join(root,'runs','SYNTHETIC_001'),'junction');
  const {readFile}=await import('node:fs/promises');
  await writeFile(path.join(root,'latest.json'),await readFile(path.join(outside,'latest.json')));
  assert.equal((await request(await server(t,root),PREFIX+'status')).status,503);
});
for(const mutation of [v=>{v.strategy={...v.strategy,h10_factors:['d5','p5','align','vc','dd20']};},
  v=>{v.status.updated_at='2099-01-01T00:00:00Z';},v=>{v.portfolio_summary.daily_return=0;}]) {
  test('semantic/future/preepoch account drift is rejected',async t=>{
    const root=await fixture(t);await generation(root,emptyView(),mutation);
    assert.equal((await request(await server(t,root),PREFIX+'status')).status,503);
  });
}
test('failure before first epoch is explicit data blocked and still NULL account',async t=>{
  const root=await fixture(t);const run='SYNTHETIC_FAILED';await mkdir(path.join(root,'failures',run),{recursive:true});
  const failure=bytes({status:'FAILED',blocker:'CNEQUITY_RUNTIME_SMOKE_BLOCKED',processed_at:'2026-09-27T10:00:00Z',
    validation_opened:false,final_oos_read:false});
  const manifest=bytes({schema_version:'1.0.0',run_id:run,status:'FAILED',files:{'failure.json':sha(failure)}});
  await writeFile(path.join(root,'failures',run,'failure.json'),failure);
  await writeFile(path.join(root,'failures',run,'manifest.json'),manifest);
  await writeFile(path.join(root,'last_attempt.json'),bytes({run_id:run,manifest_sha256:sha(manifest)}));
  const port=await server(t,root);
  assert.equal((await request(port,PREFIX+'status')).body.data.phase,'DATA_ADMISSION_BLOCKED');
  assert.equal((await request(port,PREFIX+'health')).body.data.blockers[0],'CNEQUITY_RUNTIME_SMOKE_BLOCKED');
  assert.equal((await request(port,PREFIX+'portfolio/summary')).body.data.total_equity,null);
});

test('malformed pointer JSON is an integrity blocker with safe errors',async t=>{
  const root=await fixture(t);await generation(root);await writeFile(path.join(root,'latest.json'),'{SYNTHETIC_BAD');
  const response=await request(await server(t,root),PREFIX+'status');
  assert.equal(response.status,503);assert.ok(!response.text.includes(root));assert.ok(!response.text.includes('SyntaxError'));
});
test('genuine post-epoch observation is readable and pre-epoch dates are not',async t=>{
  const root=await fixture(t),view=emptyView();
  view.status.epoch={started_at:'2026-09-27T10:00:00Z',market_cutoff:'2026-09-27'};
  view.portfolio_summary={...view.portfolio_summary,status:'RUNNING',cash:'9900',market_value:'100',total_equity:'10000'};
  view.nav=[{timestamp:'2026-09-27T10:00:00Z',trade_date:'2026-09-27',normalized_nav:'1'}];
  view.holdings=[{asset_id:'SYNTHETIC_ETF_ONLY',quantity:'100'}];
  view.benchmark.points=[{trade_date:'2026-09-27',normalized:1}];
  const folder=await generation(root,view);const port=await server(t,root);
  assert.equal((await request(port,PREFIX+'portfolio/nav')).status,200);
  const raw=bytes({...view,nav:[{...view.nav[0],timestamp:'2020-01-01T00:00:00Z'}]});
  // Even a self-consistent file hash cannot authorize pre-epoch NAV.
  const {readFile}=await import('node:fs/promises');
  const manifest=JSON.parse(await readFile(path.join(folder,'manifest.json'),'utf8'));manifest.files['view.json']=sha(raw);
  await writeFile(path.join(folder,'view.json'),raw);const body=bytes(manifest);await writeFile(path.join(folder,'manifest.json'),body);
  await writeFile(path.join(root,'latest.json'),bytes({run_id:'SYNTHETIC_001',manifest_sha256:sha(body)}));
  assert.equal((await request(port,PREFIX+'portfolio/nav')).status,503);
});
test('a later failed attempt preserves the last successful portfolio generation',async t=>{
  const root=await fixture(t);await generation(root);
  const run='SYNTHETIC_FAILED';await mkdir(path.join(root,'failures',run),{recursive:true});
  const fail=bytes({status:'FAILED',blocker:'SYNTHETIC_CYCLE_BLOCKER',processed_at:'2026-09-27T11:00:00Z',
    validation_opened:false,final_oos_read:false});
  const manifest=bytes({schema_version:'1.0.0',run_id:run,status:'FAILED',files:{'failure.json':sha(fail)}});
  await writeFile(path.join(root,'failures',run,'failure.json'),fail);await writeFile(path.join(root,'failures',run,'manifest.json'),manifest);
  await writeFile(path.join(root,'last_attempt.json'),bytes({run_id:run,manifest_sha256:sha(manifest)}));
  const port=await server(t,root),health=await request(port,PREFIX+'health');
  assert.equal(health.body.data.status,'DEGRADED');assert.equal(health.body.meta.runId,'SYNTHETIC_001');
  assert.equal(health.body.meta.attemptRunId,run);
  assert.equal((await request(port,PREFIX+'status')).body.data.snapshot_id,'a'.repeat(64));
});
test('Python canonical JSON key order is not mistaken for strategy drift',async t=>{
  const root=await fixture(t), view=emptyView();
  const canonical=v=>Array.isArray(v)?v.map(canonical):v && typeof v==='object'
    ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
  view.strategy=canonical(view.strategy);await generation(root,view);
  assert.equal((await request(await server(t,root),PREFIX+'strategy')).status,200);
});

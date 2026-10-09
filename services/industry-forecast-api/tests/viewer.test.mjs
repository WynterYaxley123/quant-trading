import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createViewer} from '../viewer.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const sha=raw=>createHash('sha256').update(raw).digest('hex');
async function listen(server){await new Promise(r=>server.listen(0,'127.0.0.1',r));return server.address().port;}
async function fixture(t){
  const temp=await mkdtemp(path.join(os.tmpdir(),'rev10-viewer-synthetic-'));t.after(()=>rm(temp,{recursive:true,force:true}));
  const bundleRoot=path.join(temp,'web'),reviewRoot=path.join(temp,'review');await mkdir(bundleRoot);await mkdir(reviewRoot);
  const raw='<html lang="zh-CN"><body>SYNTHETIC_ONLY_TEST_FIXTURE</body></html>',model=sha(await readFile(path.join(ROOT,'config/research/swl1-rev10-short-v1.json')));
  await writeFile(path.join(bundleRoot,'index.html'),raw);await writeFile(path.join(reviewRoot,'index.html'),raw);
  const source='dashboard/src/app/Header.tsx';
  const bundle={service:'REV10_DASHBOARD_BUNDLE',model_hash:model,source_sha256:{[source]:sha(await readFile(path.join(ROOT,source)))},files:{'index.html':sha(raw)}};
  const review={private_local_only:true,classification:'EXPLORATORY_POST_HOC',model_hash:model,files:{'index.html':sha(raw)}};
  const b=JSON.stringify(bundle),r=JSON.stringify(review);await writeFile(path.join(bundleRoot,'bundle-manifest.json'),b);await writeFile(path.join(reviewRoot,'delivery-manifest.json'),r);
  return {repoRoot:ROOT,bundleRoot,bundlePin:sha(b),reviewRoot,reviewPin:sha(r),apiPort:19999};
}
test('viewer binds source, pack pins and loaded identity before serving',async t=>{
  const f=await fixture(t);await assert.rejects(createViewer({...f,bundlePin:'a'.repeat(64)}));
  await writeFile(path.join(f.bundleRoot,'index.html'),'tampered');await assert.rejects(createViewer(f));
});
test('viewer serves only known read-only local resources and rechecks bytes',async t=>{
  const f=await fixture(t),server=await createViewer(f),port=await listen(server);t.after(()=>new Promise(r=>server.close(r)));
  const base=`http://127.0.0.1:${port}`;
  const health=await (await fetch(base+'/health')).json();assert.equal(health.service,'REV10_STATIC_VIEWER');assert.equal(health.read_only,true);assert.equal(health.bundle_sha256,f.bundlePin);
  assert.equal((await fetch(base+'/industry-forecast/swl1-rev10')).status,200);assert.equal((await fetch(base+'/offline-review/index.html')).status,200);
  assert.equal((await fetch(base+'/index.html',{method:'HEAD'})).status,200);
  assert.equal((await fetch(base+'/index.html',{method:'POST'})).status,405);
  assert.equal((await fetch(base+'/index.html',{headers:{origin:'https://unknown.example'}})).status,403);
  assert.equal((await fetch(base+'/bundle-manifest.json')).status,404);assert.equal((await fetch(base+'/index.html?path=secret')).status,404);
  await writeFile(path.join(f.bundleRoot,'index.html'),'tampered');assert.equal((await fetch(base+'/index.html')).status,503);
});
test('viewer proxy permits reads only and reports API disconnection without replacement data',async t=>{
  const calls=[];
  const api=http.createServer((req,res)=>{calls.push([req.method,req.url]);res.setHeader('content-type','application/json');res.end('{"synthetic":true}');});
  const apiPort=await listen(api),f=await fixture(t),server=await createViewer({...f,apiPort}),port=await listen(server);
  t.after(()=>new Promise(r=>server.close(r)));
  const url=`http://127.0.0.1:${port}/api/industry-forecast/swl1-rev10/overview`;
  assert.equal((await fetch(url)).status,200);assert.equal((await fetch(url,{method:'POST'})).status,405);assert.equal((await fetch(url+'?date=2026-09-30')).status,404);
  assert.deepEqual(calls,[['GET','/api/industry-forecast/swl1-rev10/overview']]);
  await new Promise(r=>api.close(r));assert.equal((await fetch(url)).status,503);
});

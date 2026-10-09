/** Actual Windows launch/reuse/conflict/fallback using disposable synthetic HTML, never private returns. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync,mkdtempSync,mkdirSync,writeFileSync,rmSync,realpathSync,openSync,closeSync} from 'node:fs';
import {spawn,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),target=path.join(repo,'scripts/Show-SWL1-REV10.ps1');
const sha=raw=>createHash('sha256').update(raw).digest('hex');
test('REV10 launcher has a read-only boundary and preserves unknown processes',()=>{
  const text=readFileSync(target,'utf8');assert.match(text,/Start-Process[^\n]*-WindowStyle Hidden/);assert.match(text,/Find-REV10Port/);assert.match(text,/VERIFIED_OFFLINE_FALLBACK/);
  assert.doesNotMatch(text,/one_shot\.py|run_forecast\.py|Register-ScheduledTask|Stop-Process|pip install|pnpm install/);
});
test('actual Windows three-service launch, exact reuse, CORS, conflicts, cleanup and private fallback',{skip:process.platform!=='win32',timeout:180000},async t=>{
  // Hosted Windows TEMP may be an 8.3 alias; keep strict service realpath checks intact.
  const temp=realpathSync.native(mkdtempSync(path.join(os.tmpdir(),'rev10-launch-synthetic-'))),started=new Set();
  let unknownResearch;
  const stopOwned=id=>{
    const result=spawnSync('pwsh',['-NoProfile','-Command',"$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$env:REV10_TEST_PID);if($p -and ($p.CommandLine.Contains($env:REV10_TEST_REPO+'\\services\\industry-forecast-api\\server.mjs') -or $p.CommandLine.Contains($env:REV10_TEST_REPO+'\\services\\industry-forecast-api\\viewer.mjs') -or $p.CommandLine.Contains($env:REV10_TEST_REPO+'\\services\\research-api\\src\\index.ts'))){Stop-Process -Id $p.ProcessId -ErrorAction Stop}"],{env:{...process.env,REV10_TEST_PID:String(id),REV10_TEST_REPO:repo},encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
  };
  const foreign=http.createServer((req,res)=>res.end('UNKNOWN_SERVICE_PRESERVED'));
  await new Promise(r=>foreign.listen(0,'127.0.0.1',r));const occupied=foreign.address().port;
  const probe=http.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const dashboard=probe.address().port;await new Promise(r=>probe.close(r));
  try {
    const modelHash=sha(readFileSync(path.join(repo,'config/research/swl1-rev10-short-v1.json'))),raw='<html><body><div id="root">SYNTHETIC_ONLY_TEST_FIXTURE</div></body></html>';
    for(const leaf of ['web','review']){mkdirSync(path.join(temp,leaf));writeFileSync(path.join(temp,leaf,'index.html'),raw);}
    const source='dashboard/src/app/Header.tsx';
    writeFileSync(path.join(temp,'web','bundle-manifest.json'),JSON.stringify({service:'REV10_DASHBOARD_BUNDLE',model_hash:modelHash,source_sha256:{[source]:sha(readFileSync(path.join(repo,source)))},files:{'index.html':sha(raw)}}));
    writeFileSync(path.join(temp,'review','delivery-manifest.json'),JSON.stringify({private_local_only:true,classification:'EXPLORATORY_POST_HOC',model_hash:modelHash,files:{'index.html':sha(raw)}}));
    const parse=spawnSync('pwsh',['-NoProfile','-Command',"$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile($env:REV10_TEST_LAUNCHER,[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 1}"],{env:{...process.env,REV10_TEST_LAUNCHER:target},encoding:'utf8'});assert.equal(parse.status,0,parse.stderr);
    let invocation=0;
    const run=(apiPort=occupied,viewerPort=dashboard)=>{
      const before=Date.now();
      // Hidden long-lived children can inherit Windows anonymous pipe handles.
      // Observe the launcher exit using files, not descendant pipe EOF.
      const output=path.join(temp,`launcher-${++invocation}.stdout.log`),error=path.join(temp,`launcher-${invocation}.stderr.log`);
      const handles=[openSync(output,'w'),openSync(error,'w')];
      let result;
      try{result=spawnSync('pwsh',['-NoProfile','-File',target,'-DeliveryRoot',temp,'-ApiPort',String(apiPort),'-DashboardPort',String(viewerPort),'-NoBrowser'],{stdio:['ignore',...handles],timeout:60000});}
      finally{handles.forEach(closeSync);}
      result.stdout=readFileSync(output,'utf8');result.stderr=readFileSync(error,'utf8');
      t.diagnostic(`Launcher port ${viewerPort}: ${Date.now()-before}ms, exit ${result.status}`);
      assert.ifError(result.error);
      assert.equal(result.status,0,result.stdout+result.stderr);const start=result.stdout.indexOf('{');assert(start>=0,result.stdout);const receipt=JSON.parse(result.stdout.slice(start));for(const pid of receipt.started_pids??[])started.add(pid);return receipt;
    };
    const first=run();
    const diagnostics=first.status==='READ_ONLY_WEB_READY'?'':readdirSync(path.join(temp,'launch'),{recursive:true}).filter(name=>name.endsWith('.stderr.log')).map(name=>readFileSync(path.join(temp,'launch',name),'utf8')).join('\n');
    assert.equal(first.status,'READ_ONLY_WEB_READY',JSON.stringify(first)+'\n'+diagnostics);assert.notEqual(first.api_port,occupied);assert.equal(first.ranking_count,0);assert.equal(first.started_pids.length,3);assert.equal(first.research_api_connected,true);assert.equal(first.research_artifact_state,'NOT_CONFIGURED');
    const second=run();assert.equal(second.status,'READ_ONLY_WEB_READY');assert.equal(second.api_reused,true);assert.equal(second.viewer_reused,true);assert.equal(second.research_api_reused,true);assert.deepEqual(second.started_pids,[]);assert.equal(second.web_url,first.web_url);
    const document=await fetch(first.web_url);assert((await document.text()).includes('SYNTHETIC_ONLY_TEST_FIXTURE'));
    assert.match(document.headers.get('content-security-policy'),/connect-src 'self' http:\/\/127\.0\.0\.1:8787;/);
    assert.equal((await fetch(new URL('/research',first.web_url))).status,200);
    const origin=new URL(first.web_url).origin,base='http://127.0.0.1:8787/api/v1';
    const healthResponse=await fetch(base+'/health',{headers:{Origin:origin}});assert.equal(healthResponse.status,200);assert.equal(healthResponse.headers.get('access-control-allow-origin'),origin);
    const health=await healthResponse.json();assert.equal(health.data.readOnly,true);assert.equal(health.data.identity.service,'QUANT_RESEARCH_API');assert(first.started_pids.includes(health.data.identity.pid));
    const capabilities=await (await fetch(base+'/capabilities')).json(),status=await (await fetch(base+'/research/status')).json();
    assert.equal(capabilities.data.mutations,false);assert.equal(capabilities.data.finalOosAvailable,false);assert.equal(status.data.artifactState,'NOT_CONFIGURED');assert.equal(status.data.executable,false);
    assert.equal((await fetch(base+'/health',{headers:{Origin:'https://unknown.example'}})).status,403);
    assert.equal((await fetch(base+'/runs',{method:'POST'})).status,405);
    assert.equal((await fetch(base+'/validation')).status,403);
    const wrongOrigin=run(occupied,first.dashboard_port+1);assert.equal(wrongOrigin.status,'VERIFIED_OFFLINE_FALLBACK');assert.match(wrongOrigin.reason,/occupied by an unknown/);assert.deepEqual(wrongOrigin.cleaned_started_pids,[]);
    assert.equal((await fetch(base+'/health')).status,200);assert.equal((await fetch(new URL('/health',first.web_url))).status,200);

    // A different entry with the real entry passed as an extra argument must never
    // become trusted, even when it copies valid public health/capability responses.
    stopOwned(health.data.identity.pid);
    const apiPid=first.started_pids.find(id=>id!==health.data.identity.pid&&id!==first.started_pids.at(-1));stopOwned(apiPid);
    const unknownEntry=path.join(temp,'unknown-research.mjs');
    writeFileSync(unknownEntry,"import http from 'node:http';const health="+JSON.stringify(health)+";health.data.identity.pid=process.pid;const caps="+JSON.stringify(capabilities)+";const status="+JSON.stringify(status)+";http.createServer((req,res)=>{res.setHeader('content-type','application/json');res.setHeader('access-control-allow-origin',"+JSON.stringify(origin)+");res.end(JSON.stringify(req.url.endsWith('/health')?health:req.url.endsWith('/capabilities')?caps:status));}).listen(8787,'127.0.0.1',()=>console.log('READY'));\n");
    unknownResearch=spawn(process.execPath,[unknownEntry,path.join(repo,'services/research-api/src/index.ts')],{stdio:['ignore','pipe','pipe']});
    await new Promise((resolve,reject)=>{unknownResearch.stdout.once('data',resolve);unknownResearch.once('error',reject);unknownResearch.once('exit',code=>reject(new Error('Unknown fixture failed '+code)));});
    const conflict=run();assert.equal(conflict.status,'VERIFIED_OFFLINE_FALLBACK');assert.match(conflict.reason,/occupied by an unknown/);assert.equal(conflict.cleaned_started_pids.length,1);
    for(const id of conflict.cleaned_started_pids)assert.throws(()=>process.kill(id,0));
    assert.equal((await (await fetch(base+'/health')).json()).data.identity.pid,unknownResearch.pid);
    assert.equal((await fetch(new URL('/health',first.web_url))).status,200);
    unknownResearch.kill();await new Promise(r=>unknownResearch.once('exit',r));unknownResearch=null;
    const recovered=run();assert.equal(recovered.status,'READ_ONLY_WEB_READY');assert.equal(recovered.viewer_reused,true);assert.equal(recovered.started_pids.length,2);
    writeFileSync(path.join(temp,'web','index.html'),'corrupted');const fallback=run();assert.equal(fallback.status,'VERIFIED_OFFLINE_FALLBACK');assert.equal(fallback.web_url,null);
    assert.equal((await fetch(base+'/health')).status,200);
    assert.equal(await (await fetch(`http://127.0.0.1:${occupied}`)).text(),'UNKNOWN_SERVICE_PRESERVED');
    writeFileSync(path.join(temp,'review','index.html'),'corrupted');
    const rejected=spawnSync('pwsh',['-NoProfile','-File',target,'-DeliveryRoot',temp,'-NoBrowser'],{encoding:'utf8'});assert.notEqual(rejected.status,0);assert.match(rejected.stderr,/Delivery integrity failed/);
  } finally {
    if(unknownResearch)unknownResearch.kill();
    for(const id of started)stopOwned(id);
    await new Promise(r=>foreign.close(r));assert.equal(path.dirname(realpathSync.native(temp)),realpathSync.native(os.tmpdir()));assert(path.basename(temp).startsWith('rev10-launch-synthetic-'));rmSync(temp,{recursive:true,force:true});
  }
});

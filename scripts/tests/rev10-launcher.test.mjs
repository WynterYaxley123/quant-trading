/** Actual Windows launch/reuse/conflict/fallback using disposable synthetic HTML, never private returns. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,mkdirSync,writeFileSync,rmSync,realpathSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
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
test('actual Windows launcher parses, skips unknown listener, reuses exact identity and verifies offline fallback',{skip:process.platform!=='win32',timeout:180000},async()=>{
  const temp=mkdtempSync(path.join(os.tmpdir(),'rev10-launch-synthetic-')),started=new Set();
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
    const run=()=>{
      const result=spawnSync('pwsh',['-NoProfile','-File',target,'-DeliveryRoot',temp,'-ApiPort',String(occupied),'-DashboardPort',String(dashboard),'-NoBrowser'],{encoding:'utf8',timeout:60000});
      assert.equal(result.status,0,result.stdout+result.stderr);const start=result.stdout.indexOf('{');assert(start>=0,result.stdout);const receipt=JSON.parse(result.stdout.slice(start));for(const pid of receipt.started_pids??[])started.add(pid);return receipt;
    };
    const first=run();assert.equal(first.status,'READ_ONLY_WEB_READY',JSON.stringify(first));assert.notEqual(first.api_port,occupied);assert.equal(first.ranking_count,0);assert.equal(first.started_pids.length,2);
    const second=run();assert.equal(second.status,'READ_ONLY_WEB_READY');assert.equal(second.api_reused,true);assert.equal(second.viewer_reused,true);assert.deepEqual(second.started_pids,[]);assert.equal(second.web_url,first.web_url);
    assert((await (await fetch(first.web_url)).text()).includes('SYNTHETIC_ONLY_TEST_FIXTURE'));
    writeFileSync(path.join(temp,'web','index.html'),'corrupted');const fallback=run();assert.equal(fallback.status,'VERIFIED_OFFLINE_FALLBACK');assert.equal(fallback.web_url,null);
    assert.equal(await (await fetch(`http://127.0.0.1:${occupied}`)).text(),'UNKNOWN_SERVICE_PRESERVED');
  } finally {
    for(const id of started){const cleanup=spawnSync('pwsh',['-NoProfile','-Command',"$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$env:REV10_TEST_PID);if($p -and ($p.CommandLine.Contains($env:REV10_TEST_REPO+'\\services\\industry-forecast-api\\server.mjs') -or $p.CommandLine.Contains($env:REV10_TEST_REPO+'\\services\\industry-forecast-api\\viewer.mjs'))){Stop-Process -Id $p.ProcessId -ErrorAction Stop}"],{env:{...process.env,REV10_TEST_PID:String(id),REV10_TEST_REPO:repo},encoding:'utf8'});assert.equal(cleanup.status,0,cleanup.stderr);}
    await new Promise(r=>foreign.close(r));assert.equal(path.dirname(realpathSync(temp)),realpathSync(os.tmpdir()));assert(path.basename(temp).startsWith('rev10-launch-synthetic-'));rmSync(temp,{recursive:true,force:true});
  }
});

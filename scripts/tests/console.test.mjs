import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,readFile,writeFile,copyFile,rm,access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import net from 'node:net';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const launcher=path.join(repo,'scripts/Start-EtfQuantConsole.ps1');
const officialConfig=process.env.CONSOLE_TEST_CONFIG || 'D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json';
const executable=process.env.CONSOLE_TEST_POWERSHELL || 'pwsh.exe';
const quote=value=>"'"+String(value).replaceAll("'","''")+"'";
const enabled=process.platform==='win32' && await access(officialConfig).then(()=>true,()=>false);

async function freePort() {
  const server=net.createServer();
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const port=server.address().port;
  await new Promise(resolve=>server.close(resolve));
  return port;
}
async function connected(port) {
  return new Promise(resolve=>{
    const socket=net.connect({host:'127.0.0.1',port});
    socket.once('connect',()=>{socket.destroy();resolve(true);});
    socket.once('error',()=>resolve(false));
  });
}
async function fixture() {
  const root=await mkdtemp(path.join(tmpdir(),'quant-console-test-'));
  const configPath=path.join(root,'config.json');
  const controlRoot=path.join(root,'control');
  const runtimeRoot=path.join(root,'shadow');
  await mkdir(controlRoot); await mkdir(runtimeRoot);
  await writeFile(path.join(runtimeRoot,'sentinel.txt'),'unchanged observation fixture');
  // Only copy the four existing, approved control/calendar metadata files.
  // No market bars, models, performance, Shadow events or account payloads.
  const official=JSON.parse(await readFile(officialConfig,'utf8'));
  for(const name of ['latest_observation.json','latest_export.json']) {
    await copyFile(path.join(official.control_root,name),path.join(controlRoot,name));
  }
  const pointer=JSON.parse(await readFile(path.join(controlRoot,'latest_export.json'),'utf8'));
  assert.match(pointer.snapshot_id,/^[a-f0-9]{64}$/);
  const exportName=path.join('exports',pointer.snapshot_id);
  await mkdir(path.join(controlRoot,exportName),{recursive:true});
  for(const name of ['manifest.json','trading_calendar.csv']) {
    await copyFile(path.join(official.control_root,exportName,name),path.join(controlRoot,exportName,name));
  }
  await writeFile(configPath,JSON.stringify({runtime_root:runtimeRoot,control_root:controlRoot}));
  const ports=[];
  while(ports.length<3) {const port=await freePort();if(!ports.includes(port))ports.push(port);}
  const args=['-Config',quote(configPath),'-ResearchReportRoot',quote(path.join(root,'absent-reports')),
    '-EtfApiPort',ports[0],'-ResearchApiPort',ports[1],'-DashboardPort',ports[2]];
  const receiptPath=path.join(controlRoot,'console-logs',`services-${ports.join('-')}.json`);
  let invocation=0;
  async function receipt() {return JSON.parse((await readFile(receiptPath,'utf8')).replace(/^\uFEFF/,''));}
  async function launch(extra=[],environment={}) {
    const selected=[...args];
    for(let i=0;i<extra.length;i+=2) {
      const existing=selected.indexOf(extra[i]);
      if(existing>=0)selected.splice(existing,2);
    }
    const output=path.join(root,`invocation-${++invocation}.log`);
    const command=`try { & ${quote(launcher)} ${[...selected,...extra].join(' ')} *> ${quote(output)}; $ok=$? } `+
      `catch { $_ | Out-String | Add-Content -LiteralPath ${quote(output)}; $ok=$false }; `+
      `('CALLER_ENV=' + (@{PORT=$env:PORT;HOST=$env:HOST;VITE_DATA_MODE=$env:VITE_DATA_MODE} | ConvertTo-Json -Compress)) | Add-Content -LiteralPath ${quote(output)}; if (-not $ok) { exit 1 }`;
    // Long-lived Windows children can inherit captured pipe handles. Use files
    // and the actual parent exit event, not an execFile pipe-close wait.
    const code=await new Promise((resolve,reject)=>{
      const child=spawn(executable,['-NoProfile','-NonInteractive','-OutputFormat','Text','-EncodedCommand',Buffer.from(command,'utf16le').toString('base64')],
        {cwd:tmpdir(),env:{...process.env,...environment},windowsHide:true,stdio:'ignore'});
      const timer=setTimeout(()=>{child.kill();reject(new Error('Launcher test timeout'));},90000);
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);resolve(code);});
    });
    const stdout=(await readFile(output,'utf8')).replace(/\u001b\[[0-9;]*m/g,'');
    if(code!==0) throw Object.assign(new Error('Launcher failed'),{stdout,stderr:stdout,code});
    return {stdout,stderr:''};
  }
  async function cleanup() {
    const record=await receipt().catch(()=>({services:{}}));
    for(const [name,entry] of Object.entries(record.services)) {
      assert.ok(Number.isSafeInteger(entry.pid) && entry.pid>0);
      assert.match(entry.start_ticks,/^\d+$/);
      const source=name==='etf' ? 'services/etf-quant-api/server.mjs'
        : name==='research' ? 'services/research-api/src/index.ts' : 'dashboard/node_modules/vite/bin/vite.js';
      // Recheck PID identity even in disposable fixtures; a reused PID is never killed.
      const command=`$ErrorActionPreference='Stop'; $owned=Get-Process -Id ${entry.pid} -ErrorAction SilentlyContinue; `+
        `if ($owned) { $details=Get-CimInstance Win32_Process -Filter 'ProcessId = ${entry.pid}'; `+
        `if ($owned.StartTime.ToUniversalTime().Ticks.ToString() -ne ${quote(entry.start_ticks)} `+
        `-or $details.ExecutablePath -ne ${quote(process.execPath)} `+
        `-or $details.CommandLine.IndexOf(${quote(path.join(repo,source))},[StringComparison]::OrdinalIgnoreCase) -lt 0) `+
        `{ throw 'Fixture process identity changed; no process stopped' }; Stop-Process -Id ${entry.pid} }`;
      await new Promise((resolve,reject)=>{
        const child=spawn(executable,['-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(command,'utf16le').toString('base64')],
          {windowsHide:true,stdio:'ignore'});
        child.once('error',reject);
        child.once('exit',code=>code===0 ? resolve() : reject(new Error('Fixture cleanup ownership check failed')));
      });
    }
    const resolved=path.resolve(root),rel=path.relative(tmpdir(),resolved);
    assert.ok(rel.startsWith('quant-console-test-') && !rel.includes(path.sep));
    await rm(resolved,{recursive:true,force:true,maxRetries:6,retryDelay:200});
  }
  return {root,controlRoot,runtimeRoot,ports,args,receipt,launch,cleanup};
}

test('launcher starts all three healthy loopback services from another cwd, restores env, and safely reuses them',
  {skip:!enabled,timeout:180000},async()=>{
    const f=await fixture();
    try {
      const first=await f.launch([],{PORT:'54321',HOST:'caller-sentinel',VITE_DATA_MODE:'mock'});
      for(const name of ['ETF Quant API','Research API','Dashboard']) assert.match(first.stdout,new RegExp(`${name} +READY`));
      assert.equal((first.stdout.match(/\(STARTED\)/g)||[]).length,3);
      assert.match(first.stdout,/"PORT":"54321"/);assert.match(first.stdout,/"HOST":"caller-sentinel"/);
      assert.match(first.stdout,/"VITE_DATA_MODE":"mock"/);
      const before=await f.receipt();
      const second=await f.launch();
      assert.equal((second.stdout.match(/\(REUSED\)/g)||[]).length,3);
      assert.deepEqual(await f.receipt(),before);
      const health=await (await fetch(`http://127.0.0.1:${f.ports[1]}/api/v1/health`)).json();
      assert.equal(health.data.readOnly,true);
      const runs=await (await fetch(`http://127.0.0.1:${f.ports[1]}/api/v1/runs`)).json();
      assert.deepEqual(runs.data.items,[]);
      assert.equal(await readFile(path.join(f.runtimeRoot,'sentinel.txt'),'utf8'),'unchanged observation fixture');
      // All ordinary API requests remain observation-only, including rejected mutations.
      for(const method of ['POST','PUT','PATCH','DELETE']) {
        assert.equal((await fetch(`http://127.0.0.1:${f.ports[1]}/api/v1/health`,{method})).status,405);
      }
    } finally {await f.cleanup();}
  });

test('unrelated temporary listener is refused before any service starts and remains alive',
  {skip:!enabled,timeout:60000},async()=>{
    const f=await fixture();
    const server=net.createServer(socket=>socket.end());
    await new Promise(resolve=>server.listen(f.ports[1],'127.0.0.1',resolve));
    try {
      await assert.rejects(f.launch(),error=>{
        assert.match(error.stderr,/Research API.*port/);
        assert.match(error.stderr,/Port conflict/);
        assert.match(error.stderr,/No process was stopped/);
        return true;
      });
      assert.ok(await connected(f.ports[1]));
      assert.equal(await connected(f.ports[0]),false);
      assert.equal(await connected(f.ports[2]),false);
    } finally {await new Promise(resolve=>server.close(resolve));await f.cleanup();}
  });

test('healthy process with corrupt artifacts fails readiness and rolls back only this invocation',
  {skip:!enabled,timeout:60000},async()=>{
    const f=await fixture();
    const badRoot=path.join(f.root,'bad-reports');
    const runRoot=path.join(badRoot,'shenwan_sector_index','iteration1_20260101_000000_000000_utc');
    await mkdir(runRoot,{recursive:true});await writeFile(path.join(runRoot,'metadata.json'),'corrupt test metadata');
    try {
      await assert.rejects(f.launch(['-ResearchReportRoot',quote(badRoot),'-StartupTimeoutSeconds','5']),error=>{
        assert.match(error.stderr,/Research API.*port/);
        assert.match(error.stderr,/Command: node --import tsx/);
        assert.match(error.stderr,/Log:[\s\S]*research.stderr.log/);
        return true;
      });
      assert.deepEqual((await f.receipt()).services,{});
      for(const port of f.ports) assert.equal(await connected(port),false);
    } finally {await f.cleanup();}
  });

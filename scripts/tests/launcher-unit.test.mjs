/** Source/PowerShell syntax contracts; no private runtime or service processes. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,writeFileSync,realpathSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const target=path.join(repo,'scripts/Start-EtfQuantConsole.ps1');

test('launcher resolves checkout and allows explicit environment configuration',()=>{
  const text=readFileSync(target,'utf8');
  assert.match(text,/ETF_QUANT_CONSOLE_CONFIG/);
  assert.match(text,/\$PSScriptRoot/);
  assert.doesNotMatch(text,/one_shot\.py|docker\s+(?:run|compose)/i);
});

test('PowerShell launcher parses without starting services',{skip:process.platform!=='win32'},()=>{
  const script="$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($env:HARDENING_LAUNCHER,[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { exit 1 }";
  const result=spawnSync('pwsh',['-NoProfile','-NonInteractive','-Command',script],{
    env:{...process.env,HARDENING_LAUNCHER:target},encoding:'utf8',
  });
  assert.equal(result.status,0,result.stderr);
});

test('industry launcher has an independent read-only service boundary',()=>{
  const text=readFileSync(path.join(repo,'scripts/Start-IndustryForecastConsole.ps1'),'utf8');
  assert.match(text,/services\/industry-forecast-api\/server\.mjs/);
  assert.match(text,/VITE_INDUSTRY_FORECAST_API_BASE_URL/);
  assert.doesNotMatch(text,/one_shot\.py|run_forecast\.py|RegisterTask|ETF_QUANT_CONSOLE_CONFIG/);
});

test('industry PowerShell launcher parses without starting services',{skip:process.platform!=='win32'},()=>{
  const result=spawnSync('pwsh',['-NoProfile','-NonInteractive','-Command',"$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($env:HARDENING_LAUNCHER,[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { exit 1 }"],{env:{...process.env,HARDENING_LAUNCHER:path.join(repo,'scripts/Start-IndustryForecastConsole.ps1')},encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
});

for(const [name,v2,reason] of [
  ['partial V2 roots',{v2_runtime_root:'shadow-v2'},'Both V2 runtime and control roots are required'],
  ['overlapping V1/V2 roots',{v2_runtime_root:'shadow',v2_control_root:'control-v2'},'V1 and V2 observation roots must be disjoint'],
]) test(`launcher rejects ${name} before starting services`,{skip:process.platform!=='win32'},()=>{
  const root=mkdtempSync(path.join(tmpdir(),'quant-launcher-roots-'));
  const config=path.join(root,'config.json');
  try {
    const values=Object.fromEntries(Object.entries(v2).map(([key,value])=>[key,path.join(root,value)]));
    writeFileSync(config,JSON.stringify({runtime_root:path.join(root,'shadow'),control_root:path.join(root,'control'),...values}));
    const result=spawnSync('pwsh',['-NoProfile','-NonInteractive','-File',target,'-Config',config],{
      env:{...process.env,ETF_QUANT_V2_RUNTIME_ROOT:'',ETF_QUANT_V2_CONTROL_ROOT:''},encoding:'utf8',timeout:30000,
    });
    assert.notEqual(result.status,0);
    assert.ok((result.stderr+result.stdout).includes(reason),result.stderr+result.stdout);
  } finally {
    assert.equal(path.dirname(realpathSync(root)),realpathSync(tmpdir()));
    assert.ok(path.basename(root).startsWith('quant-launcher-roots-'));
    rmSync(root,{recursive:true,force:true});
  }
});

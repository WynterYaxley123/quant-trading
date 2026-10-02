/** Source/PowerShell syntax contracts; no private runtime or service processes. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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

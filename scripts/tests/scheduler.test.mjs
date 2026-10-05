/** Evaluate the real task definition builder without registering or waking a task. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
test('Windows task definition quotes paths and enforces least privilege, retries and one instance',
  {skip:process.platform!=='win32'},()=>{
    const script=`
      $tokens=$null;$errors=$null
      $tree=[System.Management.Automation.Language.Parser]::ParseFile($env:QUANT_TASK_INSTALLER,[ref]$tokens,[ref]$errors)
      if($errors.Count){throw 'PowerShell syntax invalid'}
      $builder=$tree.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-ForwardShadowTaskXml'},$true)
      . ([ScriptBlock]::Create($builder.Extent.Text))
      [xml]$definition=New-ForwardShadowTaskXml 'C:/Synthetic Checkout' 'C:/Synthetic Python/python.exe' 'C:/Synthetic & Config/deployment.json' 'S-1-5-21-123' '2026-10-05T16:05:00'
      $task=$definition.Task
      @{command=$task.Actions.Exec.Command;arguments=$task.Actions.Exec.Arguments;directory=$task.Actions.Exec.WorkingDirectory;
        logon=$task.Principals.Principal.LogonType;level=$task.Principals.Principal.RunLevel;
        instances=$task.Settings.MultipleInstancesPolicy;catchup=$task.Settings.StartWhenAvailable;
        interval=$task.Triggers.CalendarTrigger.Repetition.Interval;duration=$task.Triggers.CalendarTrigger.Repetition.Duration;
        retry=$task.Settings.RestartOnFailure.Count;loginDelay=$task.Triggers.LogonTrigger.Delay} | ConvertTo-Json -Compress
    `;
    const result=spawnSync('pwsh',['-NoProfile','-NonInteractive','-Command',script],{
      env:{...process.env,QUANT_TASK_INSTALLER:path.join(repo,'scripts/Install-ForwardShadowTask.ps1')},encoding:'utf8',timeout:30000,
    });
    assert.equal(result.status,0,result.stderr);
    const task=JSON.parse(result.stdout);
    assert.equal(task.command,'C:/Synthetic Python/python.exe');
    assert.equal(task.directory,'C:/Synthetic Checkout');
    assert.match(task.arguments,/-B "C:[/\\]Synthetic Checkout[/\\]services[/\\]etf-quant-runner[/\\]scheduled_wake\.py" --deployment "C:\/Synthetic & Config\/deployment\.json"/);
    assert.equal(task.logon,'InteractiveToken');assert.equal(task.level,'LeastPrivilege');
    assert.equal(task.instances,'IgnoreNew');assert.equal(task.catchup,'true');
    assert.equal(task.interval,'PT15M');assert.equal(task.duration,'PT7H');
    assert.equal(task.retry,'3');assert.equal(task.loginDelay,'PT5M');
  });

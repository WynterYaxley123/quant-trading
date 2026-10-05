[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Deployment,
    [ValidatePattern('^[A-Za-z0-9 _-]{1,80}$')][string]$TaskName = 'ETF-Quant Forward Shadow'
)
$ErrorActionPreference = 'Stop'
$schedulerRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$deploymentPath = (Resolve-Path -LiteralPath $Deployment).Path
$settings = Get-Content -LiteralPath $deploymentPath -Raw | ConvertFrom-Json
$wakePath = Join-Path $schedulerRepo 'services/etf-quant-runner/scheduled_wake.py'
& $settings.transport_python -B $wakePath --deployment $deploymentPath --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Scheduler deployment preflight failed.' }

function New-ForwardShadowTaskXml([string]$Checkout,[string]$Python,[string]$Config,[string]$Identity,[string]$Start) {
    function Xml-Text([string]$Value) { [Security.SecurityElement]::Escape($Value) }
    function Quoted-Argument([string]$Value) {
        if ($Value.Contains('"') -or $Value.EndsWith('\')) { throw 'Invalid executable argument path.' }
        '"' + $Value + '"'
    }
    $arguments = '-B ' + (Quoted-Argument (Join-Path $Checkout 'services/etf-quant-runner/scheduled_wake.py')) + ' --deployment ' + (Quoted-Argument $Config)
    @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>ETF_QUANT_CANONICAL_FORWARD_WAKE_V1</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger><Repetition><Interval>PT15M</Interval><Duration>PT7H</Duration><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><StartBoundary>$Start</StartBoundary><Enabled>true</Enabled><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>
    <LogonTrigger><Enabled>true</Enabled><Delay>PT5M</Delay><UserId>$Identity</UserId></LogonTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>$Identity</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT4H</ExecutionTimeLimit><RestartOnFailure><Interval>PT15M</Interval><Count>3</Count></RestartOnFailure></Settings>
  <Actions Context="Author"><Exec><Command>$(Xml-Text $Python)</Command><Arguments>$(Xml-Text $arguments)</Arguments><WorkingDirectory>$(Xml-Text $Checkout)</WorkingDirectory></Exec></Actions>
</Task>
"@
}
$taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
# Convert the operational Shanghai close window to the host's local wall clock.
$shanghaiStart = [DateTimeOffset]::Parse(([DateTime]::UtcNow.ToString('yyyy-MM-dd') + 'T15:05:00+08:00'))
$localStart = [TimeZoneInfo]::ConvertTime($shanghaiStart,[TimeZoneInfo]::Local).ToString('yyyy-MM-ddTHH:mm:ss')
$taskXml = New-ForwardShadowTaskXml $schedulerRepo $settings.transport_python $deploymentPath $taskIdentity $localStart
if ($PSCmdlet.ShouldProcess($TaskName,'Install current-user forward Shadow wake task')) {
    $taskService = New-Object -ComObject 'Schedule.Service'
    $taskService.Connect()
    $taskFolder = $taskService.GetFolder('\')
    $existing = $null
    try { $existing = $taskFolder.GetTask($TaskName) }
    catch [Runtime.InteropServices.COMException] {
        if ($_.Exception.HResult -ne -2147024894) { throw }
    }
    if ($existing -and $existing.Definition.RegistrationInfo.Description -ne 'ETF_QUANT_CANONICAL_FORWARD_WAKE_V1') {
        throw 'An unrelated task has this name; it was not changed.'
    }
    # Interactive token requires no stored credentials or elevation and follows
    # Docker Desktop's current-user/login lifecycle. No background service is added.
    $installed = $taskFolder.RegisterTask($TaskName,$taskXml,6,$taskIdentity,$null,3,$null)
    [pscustomobject]@{TaskName=$installed.Name;Enabled=$installed.Enabled;NextRunTime=$installed.NextRunTime;LogonType='InteractiveToken';RunLevel='LeastPrivilege'} | ConvertTo-Json -Compress
}

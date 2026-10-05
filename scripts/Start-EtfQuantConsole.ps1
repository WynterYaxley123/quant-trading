[CmdletBinding()]
param(
    [string]$Config = $env:ETF_QUANT_CONSOLE_CONFIG,
    [string]$ResearchReportRoot,
    [ValidateRange(1024,65535)][int]$EtfApiPort = 3312,
    [ValidateRange(1024,65535)][int]$ResearchApiPort = 8787,
    [ValidateRange(1024,65535)][int]$DashboardPort = 5173,
    [ValidateRange(1,120)][int]$StartupTimeoutSeconds = 30
)
$ErrorActionPreference = 'Stop'
$consoleRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $Config) {
    $consoleRoot = $env:ETF_QUANT_EXTERNAL_RUNTIME_ROOT
    if (-not $consoleRoot) {
        $legacyConfig = Get-Content -Raw -LiteralPath (Join-Path $consoleRepo 'config/legacy-runtime.json') | ConvertFrom-Json
        $consoleRoot = $legacyConfig.windows_runtime_root
    }
    $Config = Join-Path $consoleRoot 'autonomous-control-v1/config.json'
}
$consoleConfig = Get-Content -Raw -LiteralPath $Config | ConvertFrom-Json
$consoleNode = (Get-Command node -ErrorAction Stop).Source
if ([int]((& $consoleNode --version).Trim().TrimStart('v').Split('.')[0]) -lt 24) {
    throw 'The unified console requires the existing Node.js 24+ environment. No packages were installed.'
}
if (@(@($EtfApiPort,$ResearchApiPort,$DashboardPort) | Select-Object -Unique).Count -ne 3) {
    throw 'Console services require three distinct ports.'
}
$v2RuntimeRoot = if ($consoleConfig.v2_runtime_root) { $consoleConfig.v2_runtime_root } else { $env:ETF_QUANT_V2_RUNTIME_ROOT }
$v2ControlRoot = if ($consoleConfig.v2_control_root) { $consoleConfig.v2_control_root } else { $env:ETF_QUANT_V2_CONTROL_ROOT }
if ([bool]$v2RuntimeRoot -ne [bool]$v2ControlRoot) { throw 'Both V2 runtime and control roots are required.' }
$observationRoots = @{runtime_root=$consoleConfig.runtime_root;control_root=$consoleConfig.control_root}
if ($v2RuntimeRoot) { $observationRoots.v2_runtime_root=$v2RuntimeRoot; $observationRoots.v2_control_root=$v2ControlRoot }
foreach ($name in $observationRoots.Keys) {
    if (-not $observationRoots[$name] -or -not [IO.Path]::IsPathRooted($observationRoots[$name])) {
        throw "Config requires an absolute $name outside Git."
    }
    $target = [IO.Path]::GetFullPath($observationRoots[$name])
    if ($target.TrimEnd('\','/') -eq $consoleRepo -or $target.StartsWith($consoleRepo + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Config $name must be outside this checkout."
    }
}
if ($v2RuntimeRoot) {
    $resolvedRoots = @($observationRoots.Values | ForEach-Object { [IO.Path]::GetFullPath($_).TrimEnd('\','/') })
    for ($i=0; $i -lt $resolvedRoots.Count; $i++) {
        for ($j=$i+1; $j -lt $resolvedRoots.Count; $j++) {
            $a=$resolvedRoots[$i]; $b=$resolvedRoots[$j]
            if ($a.Equals($b,[StringComparison]::OrdinalIgnoreCase) `
                -or $a.StartsWith($b + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) `
                -or $b.StartsWith($a + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
                throw 'V1 and V2 observation roots must be disjoint.'
            }
        }
    }
}
if ($PSBoundParameters.ContainsKey('ResearchReportRoot') -and -not $ResearchReportRoot) { throw 'An explicit ResearchReportRoot must not be empty.' }
if (-not $PSBoundParameters.ContainsKey('ResearchReportRoot')) { $ResearchReportRoot = $env:RESEARCH_REPORT_ROOT }
if ($ResearchReportRoot) { $ResearchReportRoot = [IO.Path]::GetFullPath($ResearchReportRoot) }
$researchWorkspaceConfig = $env:RESEARCH_WORKSPACE_CONFIG
if ($researchWorkspaceConfig) { $researchWorkspaceConfig = [IO.Path]::GetFullPath($researchWorkspaceConfig) }
if (-not $researchWorkspaceConfig -and -not $ResearchReportRoot) {
    $localWorkspace = Join-Path $consoleConfig.control_root 'research-workspace.json'
    if (Test-Path -LiteralPath $localWorkspace) { $researchWorkspaceConfig = $localWorkspace }
}
$researchConfigHash = if ($researchWorkspaceConfig -and (Test-Path -LiteralPath $researchWorkspaceConfig -PathType Leaf)) {
    (Get-FileHash -LiteralPath $researchWorkspaceConfig -Algorithm SHA256).Hash
} else { 'ABSENT' }
$researchApprovalHash = (Get-FileHash -LiteralPath (Join-Path $consoleRepo 'services/research-api/config/development-workspaces.v1.json') -Algorithm SHA256).Hash
$consoleLogs = Join-Path $consoleConfig.control_root 'console-logs'
New-Item -ItemType Directory -Force -Path $consoleLogs | Out-Null
$runLogs = Join-Path $consoleLogs ('run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff') + '-' + $PID)
New-Item -ItemType Directory -Path $runLogs | Out-Null
$receiptPath = Join-Path $consoleLogs "services-$EtfApiPort-$ResearchApiPort-$DashboardPort.json"
$lockPath = $receiptPath + '.lock'
$viteEntry = Join-Path $consoleRepo 'dashboard/node_modules/vite/bin/vite.js'
$researchEntry = Join-Path $consoleRepo 'services/research-api/src/index.ts'
foreach ($entry in @($viteEntry,(Join-Path $consoleRepo 'services/research-api/node_modules/tsx/package.json'))) {
    if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) {
        throw "Existing locked dependencies are missing: $entry. Restore the frozen environment separately; the launcher installs nothing."
    }
}
$settings = @($consoleRepo,$consoleNode,$consoleConfig.runtime_root,$consoleConfig.control_root,$v2RuntimeRoot,$v2ControlRoot,$ResearchReportRoot,$researchWorkspaceConfig,$researchConfigHash,$researchApprovalHash,$env:RESEARCH_ARTIFACT_ID,$EtfApiPort,$ResearchApiPort,$DashboardPort) -join "`n"
$hasher = [Security.Cryptography.SHA256]::Create()
try { $settingsHash = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($settings)))).Replace('-','').ToLowerInvariant() }
finally { $hasher.Dispose() }

function Get-Listeners([int]$Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}
function Test-OwnedProcess($Service,$Record) {
    if (-not $Record) { return $false }
    $process = Get-Process -Id $Record.pid -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)" -ErrorAction Stop
    return $details -and $details.ExecutablePath -eq $consoleNode `
        -and $details.CommandLine.IndexOf($Service.entry,[StringComparison]::OrdinalIgnoreCase) -ge 0 `
        -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $Record.start_ticks
}
function Test-ServiceHealth($Service) {
    if ($Service.key -eq 'dashboard') {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Service.url -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content.Contains('/src/main.tsx')
    }
    if ($Service.key -eq 'research') {
        $health = Invoke-RestMethod -Uri ($Service.url + '/api/v1/health') -TimeoutSec 2
        if ($health.schemaVersion -ne '1.0.0' -or $health.data.status -ne 'ok' -or $health.data.readOnly -ne $true) { return $false }
        $capabilities = Invoke-RestMethod -Uri ($Service.url + '/api/v1/capabilities') -TimeoutSec $StartupTimeoutSeconds
        return $capabilities.data.readOnly -eq $true -and $capabilities.data.mutations -eq $false `
            -and $capabilities.data.validationAvailable -eq $false -and $capabilities.data.finalOosAvailable -eq $false
    }
    $health = Invoke-RestMethod -Uri ($Service.url + '/api/etf-quant/v1/health') -TimeoutSec 2
    $current = Invoke-RestMethod -Uri ($Service.url + '/api/etf-quant/v1/current') -TimeoutSec 2
    if ($v2RuntimeRoot) {
        $v2 = Invoke-RestMethod -Uri ($Service.url + '/api/etf-quant/v2/current') -TimeoutSec 2
        if ($v2.error -or $v2.data.strategy_version -ne 'ETF_QUANT_V2' -or $v2.data.initial_capital -ne '10000' `
            -or $v2.data.broker_enabled -ne $false -or $v2.data.real_order_path -ne $false) { return $false }
    }
    return $health.schemaVersion -eq '1.0.0' -and -not $health.error `
        -and $current.data.contract -eq 'CURRENT_ETF_QUANT_STATUS_V1' `
        -and $current.data.broker_enabled -eq $false -and $current.data.real_order_path -eq $false
}
function Wait-ServiceReady($Service,$Record) {
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $delay = 200
    do {
        if (-not (Test-OwnedProcess $Service $Record)) { throw 'Owned process exited or its identity changed.' }
        $listeners = @(Get-Listeners $Service.port)
        if ($listeners.Count) {
            if (@($listeners | Where-Object { $_.OwningProcess -ne $Record.pid -or $_.LocalAddress -ne '127.0.0.1' }).Count) {
                throw 'Port ownership or loopback binding changed during startup.'
            }
            try { if (Test-ServiceHealth $Service) { return } } catch { $Service.lastError = $_.Exception.Message }
        }
        Start-Sleep -Milliseconds $delay
        $delay = [Math]::Min(1000,$delay + 200)
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Readiness timeout after $StartupTimeoutSeconds seconds. $($Service.lastError)"
}
function Save-Receipt {
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ($receiptPath + '.tmp') -Encoding UTF8
    Move-Item -LiteralPath ($receiptPath + '.tmp') -Destination $receiptPath -Force
}

$services = @(
    [pscustomobject]@{key='etf';name='ETF Quant API';port=$EtfApiPort;url="http://127.0.0.1:$EtfApiPort";entry=(Join-Path $consoleRepo 'services/etf-quant-api/server.mjs');cwd=(Join-Path $consoleRepo 'services/etf-quant-api');args=@();lastError=''},
    [pscustomobject]@{key='research';name='Research API';port=$ResearchApiPort;url="http://127.0.0.1:$ResearchApiPort";entry=$researchEntry;cwd=(Join-Path $consoleRepo 'services/research-api');args=@('--import','tsx');lastError=''},
    [pscustomobject]@{key='dashboard';name='Dashboard';port=$DashboardPort;url="http://127.0.0.1:$DashboardPort";entry=$viteEntry;cwd=(Join-Path $consoleRepo 'dashboard');args=@();lastError=''}
)
foreach ($service in $services) {
    $launchArgs = @($service.args) + @('"' + $service.entry + '"')
    if ($service.key -eq 'dashboard') { $launchArgs += @('--host','127.0.0.1','--port',"$DashboardPort",'--strictPort') }
    $service | Add-Member -NotePropertyName launchArgs -NotePropertyValue $launchArgs
}
$savedConsoleEnv = @{}
$childEnvironment = @{
    ETF_QUANT_RUNTIME_ROOT=$consoleConfig.runtime_root; ETF_QUANT_CONTROL_ROOT=$consoleConfig.control_root; ETF_QUANT_API_PORT="$EtfApiPort"
    ETF_QUANT_V2_RUNTIME_ROOT=$v2RuntimeRoot; ETF_QUANT_V2_CONTROL_ROOT=$v2ControlRoot
    RESEARCH_REPORT_ROOT=$ResearchReportRoot; RESEARCH_WORKSPACE_CONFIG=$researchWorkspaceConfig
    RESEARCH_ARTIFACT_ID=$env:RESEARCH_ARTIFACT_ID; HOST='127.0.0.1'; PORT="$ResearchApiPort"
    DASHBOARD_ORIGINS="http://127.0.0.1:$DashboardPort,http://localhost:$DashboardPort"
    VITE_RESEARCH_API_BASE_URL="http://127.0.0.1:$ResearchApiPort/api/v1"
    VITE_ETF_QUANT_API_BASE_URL="http://127.0.0.1:$EtfApiPort"; VITE_DATA_MODE='api'
}
$started = @()
$lock = $null
$activeService = $null
try {
    try { $lock = [IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
    catch { throw "Another console launch is in progress. Lock: $lockPath" }
    $receipt = @{repo=$consoleRepo;settings_hash=$settingsHash;services=@{}}
    if (Test-Path -LiteralPath $receiptPath) {
        $previous = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        if ($previous.repo -eq $consoleRepo -and $previous.settings_hash -eq $settingsHash) {
            foreach ($property in $previous.services.PSObject.Properties) { $receipt.services[$property.Name] = $property.Value }
        }
    }
    # Preflight every port before starting anything. A port alone never proves ownership.
    foreach ($service in $services) {
        $activeService = $service
        $listeners = @(Get-Listeners $service.port)
        $record = $receipt.services[$service.key]
        if ($listeners.Count) {
            if (-not (Test-OwnedProcess $service $record) -or @($listeners | Where-Object { $_.OwningProcess -ne $record.pid -or $_.LocalAddress -ne '127.0.0.1' }).Count) {
                throw 'Port conflict: listener is not a verified instance of this checkout/configuration. No process was stopped.'
            }
        } elseif (Test-OwnedProcess $service $record) {
            throw "Owned process $($record.pid) is stale (no listener). Inspect $($record.stderr); stop that verified process before retrying."
        }
    }
    foreach ($name in $childEnvironment.Keys) {
        $savedConsoleEnv[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
        [Environment]::SetEnvironmentVariable($name,$childEnvironment[$name],'Process')
    }
    foreach ($service in $services) {
        $activeService = $service
        $record = $receipt.services[$service.key]
        $action = 'REUSED'
        if (-not @(Get-Listeners $service.port).Count) {
            $stdout = Join-Path $runLogs ($service.key + '.stdout.log')
            $stderr = Join-Path $runLogs ($service.key + '.stderr.log')
            $process = Start-Process -FilePath $consoleNode -ArgumentList $service.launchArgs -WindowStyle Hidden `
                -WorkingDirectory $service.cwd -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
            $record = @{pid=$process.Id;start_ticks=$process.StartTime.ToUniversalTime().Ticks.ToString();stdout=$stdout;stderr=$stderr}
            $receipt.services[$service.key] = $record
            $started += $service
            Save-Receipt
            $action = 'STARTED'
        }
        Wait-ServiceReady $service $record
        Write-Output ("{0,-16} READY  {1}  ({2})" -f $service.name,$service.url,$action)
        if ($service.key -eq 'research') {
            $workspace = Invoke-RestMethod -Uri ($service.url + '/api/v1/research/status') -TimeoutSec $StartupTimeoutSeconds
            if ($workspace.data.artifactState -eq 'AVAILABLE') {
                Write-Output "Research workspace DEVELOPMENT_READY | $($workspace.data.artifactId) | approved runs: $($workspace.data.availableRunCount)"
            } elseif ($workspace.data.artifactState -eq 'DEGRADED') {
                Write-Output "Research workspace DEGRADED | $($workspace.data.artifactError.code) | $($workspace.data.artifactError.message)"
            } else { Write-Output 'Research workspace NOT_CONFIGURED | no approved Development artifact configured' }
        }
    }
    Write-Output "Open http://127.0.0.1:$DashboardPort/etf-quant/overview"
    Write-Output 'READ-ONLY | SIMULATION_ONLY | no runner invocation or market-data refresh'
    Write-Output "Logs: $consoleLogs"
} catch {
    $failure = $_.Exception.Message
    $failedRecord = if ($receipt -and $activeService) { $receipt.services[$activeService.key] } else { $null }
    $failureLog = if ($failedRecord) { $failedRecord.stderr } elseif ($activeService) { Join-Path $runLogs ($activeService.key + '.stderr.log') } else { $runLogs }
    # Roll back only processes created in this invocation, verifying PID/start time/command again.
    foreach ($service in $started) {
        $record = $receipt.services[$service.key]
        if (Test-OwnedProcess $service $record) { Stop-Process -Id $record.pid -ErrorAction SilentlyContinue }
        $receipt.services.Remove($service.key)
    }
    if ($lock) { Save-Receipt }
    if ($activeService) {
        $command = 'node ' + ($activeService.launchArgs -join ' ')
        throw "Unified console NOT READY: $($activeService.name), port $($activeService.port). $failure Command: $command. Log: $failureLog. Previously running services were preserved."
    }
    throw
} finally {
    foreach ($name in $savedConsoleEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$savedConsoleEnv[$name],'Process') }
    if ($lock) { $lock.Dispose() }
}

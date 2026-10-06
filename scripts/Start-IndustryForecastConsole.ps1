[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$LogRoot,
    [string]$RuntimeRoot = '',
    [ValidateRange(1024,65535)][int]$ApiPort = 3313,
    [ValidateRange(1024,65535)][int]$DashboardPort = 5173
)
$ErrorActionPreference = 'Stop'
$forecastRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$forecastNode = (Get-Command node -ErrorAction Stop).Source
$forecastVite = Join-Path $forecastRepo 'dashboard/node_modules/vite/bin/vite.js'
if (-not (Test-Path -LiteralPath $forecastVite -PathType Leaf)) {
    throw 'Restore frozen frontend dependencies separately; the launcher installs nothing.'
}
if ($ApiPort -eq $DashboardPort) { throw 'Two distinct ports are required.' }
foreach ($port in @($ApiPort,$DashboardPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port already has a listener; existing processes were preserved."
    }
}
foreach ($target in @($LogRoot,$RuntimeRoot) | Where-Object { $_ }) {
    if (-not [IO.Path]::IsPathRooted($target)) { throw 'Explicit absolute external roots are required.' }
    $ancestor = [IO.DirectoryInfo][IO.Path]::GetFullPath($target)
    while ($ancestor) {
        if (Test-Path -LiteralPath (Join-Path $ancestor.FullName '.git')) {
            throw 'Logs and runtime must be outside every Git checkout.'
        }
        $ancestor = $ancestor.Parent
    }
}
function Quoted-ForecastArgument([string]$Value) {
    if ($Value.Contains('"') -or $Value.EndsWith('\')) { throw 'Invalid executable argument path.' }
    '"' + $Value + '"'
}
$forecastLogs = Join-Path $LogRoot ('industry-console-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff') + '-' + $PID)
New-Item -ItemType Directory -Path $forecastLogs -Force | Out-Null
$forecastEnvironment = @{
    INDUSTRY_FORECAST_API_PORT="$ApiPort"
    INDUSTRY_FORECAST_RUNTIME_ROOT=$RuntimeRoot
    DASHBOARD_ORIGINS="http://127.0.0.1:$DashboardPort,http://localhost:$DashboardPort"
    VITE_INDUSTRY_FORECAST_API_BASE_URL="http://127.0.0.1:$ApiPort/api/industry-forecast"
}
$savedForecastEnvironment = @{}
$forecastProcesses = @()
try {
    foreach ($name in $forecastEnvironment.Keys) {
        $savedForecastEnvironment[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
        [Environment]::SetEnvironmentVariable($name,$forecastEnvironment[$name],'Process')
    }
    $services = @(
        @{name='industry-api';entry=(Join-Path $forecastRepo 'services/industry-forecast-api/server.mjs');arguments=@();cwd=$forecastRepo;url="http://127.0.0.1:$ApiPort/api/industry-forecast/families"},
        @{name='dashboard';entry=$forecastVite;arguments=@('--host','127.0.0.1','--port',"$DashboardPort",'--strictPort');cwd=(Join-Path $forecastRepo 'dashboard');url="http://127.0.0.1:$DashboardPort/"}
    )
    foreach ($service in $services) {
        $process = Start-Process -FilePath $forecastNode -ArgumentList (@((Quoted-ForecastArgument $service.entry)) + $service.arguments) -WindowStyle Hidden -WorkingDirectory $service.cwd -RedirectStandardOutput (Join-Path $forecastLogs ($service.name + '.stdout.log')) -RedirectStandardError (Join-Path $forecastLogs ($service.name + '.stderr.log')) -PassThru
        $forecastProcesses += $process
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        $ready = $false
        while ([DateTime]::UtcNow -lt $deadline -and -not $process.HasExited) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $service.url -TimeoutSec 2
                $ready = $response.StatusCode -eq 200
            } catch { $ready = $false }
            if ($ready) { break }
            Start-Sleep -Milliseconds 250
            $process.Refresh()
        }
        if (-not $ready) { throw "Industry console service $($service.name) unavailable; inspect explicit log root." }
    }
    Write-Output "Industry Forecast ready: http://127.0.0.1:$DashboardPort/ | READ_ONLY | no forecast publication"
} catch {
    foreach ($process in $forecastProcesses) {
        if (-not $process.HasExited) { $process.Kill() }
    }
    throw
} finally {
    foreach ($name in $savedForecastEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name,$savedForecastEnvironment[$name],'Process')
    }
}

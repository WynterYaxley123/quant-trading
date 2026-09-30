param([string]$Config='D:/QuantForge/runtime/etf-quant-v1/autonomous-control-v1/config.json')
$ErrorActionPreference='Stop'
$consoleRepo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$consoleConfig=Get-Content -Raw -LiteralPath $Config | ConvertFrom-Json
$consoleNode=(Get-Command node -ErrorAction Stop).Source
$consoleLogs=Join-Path $consoleConfig.control_root 'console-logs'
New-Item -ItemType Directory -Force -Path $consoleLogs | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $consoleRepo 'dashboard/node_modules/vite/bin/vite.js'))) {
    throw 'Restore the existing frozen dashboard pnpm-lock.yaml environment first.'
}
$savedConsoleEnv=@{}
foreach ($name in @('ETF_QUANT_RUNTIME_ROOT','ETF_QUANT_CONTROL_ROOT','VITE_ETF_QUANT_API_BASE_URL')) {
    $savedConsoleEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:ETF_QUANT_RUNTIME_ROOT=$consoleConfig.runtime_root
    $env:ETF_QUANT_CONTROL_ROOT=$consoleConfig.control_root
    $env:VITE_ETF_QUANT_API_BASE_URL='http://127.0.0.1:3312'
    if (Get-NetTCPConnection -LocalPort 3312 -State Listen -ErrorAction SilentlyContinue) {
        $current=Invoke-RestMethod 'http://127.0.0.1:3312/api/etf-quant/v1/current'
        if ($current.data.contract -ne 'CURRENT_ETF_QUANT_STATUS_V1') { throw 'Port 3312 is occupied by another service.' }
    } else {
        Start-Process -FilePath $consoleNode -ArgumentList @('server.mjs') -WindowStyle Hidden `
          -WorkingDirectory (Join-Path $consoleRepo 'services/etf-quant-api') `
          -RedirectStandardOutput (Join-Path $consoleLogs 'api.stdout.log') `
          -RedirectStandardError (Join-Path $consoleLogs 'api.stderr.log') | Out-Null
    }
    if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $consoleNode -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') `
          -WindowStyle Hidden -WorkingDirectory (Join-Path $consoleRepo 'dashboard') `
          -RedirectStandardOutput (Join-Path $consoleLogs 'dashboard.stdout.log') `
          -RedirectStandardError (Join-Path $consoleLogs 'dashboard.stderr.log') | Out-Null
    }
    Write-Output 'http://127.0.0.1:5173/etf-quant/overview'
    Write-Output 'READ-ONLY · SIMULATION_ONLY · no runner invocation'
} finally {
    foreach ($name in $savedConsoleEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$savedConsoleEnv[$name],'Process') }
}

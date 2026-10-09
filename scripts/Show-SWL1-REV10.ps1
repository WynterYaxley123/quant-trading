[CmdletBinding()]
param(
    [string]$DeliveryRoot = 'D:\QuantForge\research\swl1-rev10-delivery',
    [ValidateRange(1024,65500)][int]$ApiPort = 3323,
    [ValidateRange(1024,65500)][int]$DashboardPort = 5183,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$rev10Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$rev10Started = @()
$rev10SavedEnvironment = @{}
$rev10OfflineVerified = $false
$rev10Offline = Join-Path $DeliveryRoot 'review\index.html'
# The shipped dashboard bundle targets 127.0.0.1:8787/api/v1; do not silently choose a different port.
$rev10ResearchPort = 8787
$rev10ResearchEntry = Join-Path $rev10Repo 'services\research-api\src\index.ts'
$rev10ResearchCwd = Join-Path $rev10Repo 'services\research-api'
function Get-REV10Hash([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Assert-REV10External([string]$Root) {
    if (-not [IO.Path]::IsPathRooted($Root)) { throw 'An absolute private delivery root is required.' }
    $rev10Ancestor = [IO.DirectoryInfo][IO.Path]::GetFullPath($Root)
    while ($rev10Ancestor) {
        if ((Test-Path -LiteralPath (Join-Path $rev10Ancestor.FullName '.git')) -or ($rev10Ancestor.Exists -and ($rev10Ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint))) { throw 'Delivery must be outside Git and must not use directory links.' }
        $rev10Ancestor = $rev10Ancestor.Parent
    }
}
function Assert-REV10Pack([string]$Root,[string]$ManifestName) {
    Assert-REV10External $Root
    $rev10ManifestPath = Join-Path $Root $ManifestName
    if ((Get-Item -LiteralPath $rev10ManifestPath).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Manifest link denied.' }
    $rev10Pack = Get-Content -LiteralPath $rev10ManifestPath -Raw | ConvertFrom-Json
    if (-not $rev10Pack.files -or @($rev10Pack.files.PSObject.Properties).Count -gt 256) { throw 'Bounded artifact inventory required.' }
    foreach ($rev10File in $rev10Pack.files.PSObject.Properties) {
        $rev10Target = [IO.Path]::GetFullPath((Join-Path $Root $rev10File.Name))
        if (-not $rev10Target.StartsWith([IO.Path]::GetFullPath($Root).TrimEnd('\') + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Artifact path escapes the delivery pack.' }
        if ((Get-Item -LiteralPath $rev10Target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Artifact link denied.' }
        Assert-REV10External ([IO.Path]::GetDirectoryName($rev10Target))
        if ((Get-REV10Hash $rev10Target) -ne $rev10File.Value) { throw "Delivery integrity failed: $($rev10File.Name)" }
    }
    $rev10Pack
}
function Get-REV10Json([string]$Url) {
    Invoke-RestMethod -Uri $Url -TimeoutSec 5 -Method Get
}
function Test-REV10Service([int]$Port,[string]$Resource,[hashtable]$Expected,[switch]$Envelope) {
    try {
        $rev10Health = Get-REV10Json "http://127.0.0.1:$Port/$Resource"
        if ($Envelope) { $rev10Health = $rev10Health.data }
        foreach ($rev10Key in $Expected.Keys) { if ($rev10Health.$rev10Key -cne $Expected[$rev10Key]) { return $false } }
        return $true
    } catch { return $false }
}
function Find-REV10Port([int]$Preferred,[string]$Resource,[hashtable]$Expected,[switch]$Envelope,[int]$ExcludedPort=0) {
    for ($rev10Candidate=$Preferred; $rev10Candidate -lt $Preferred+30; $rev10Candidate++) {
        if ($rev10Candidate -eq $ExcludedPort) { continue }
        $rev10Listening = @(Get-NetTCPConnection -LocalPort $rev10Candidate -State Listen -ErrorAction SilentlyContinue)
        if ($rev10Listening.Count -eq 0) {
            # Windows can reserve a port without a listener. Probe loopback without changing OS policy.
            $rev10Probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$rev10Candidate)
            try { $rev10Probe.Start(); return @{Port=$rev10Candidate;Reuse=$false} }
            catch [Net.Sockets.SocketException] { continue }
            finally { $rev10Probe.Stop() }
        }
        if (Test-REV10Service $rev10Candidate $Resource $Expected -Envelope:$Envelope) { return @{Port=$rev10Candidate;Reuse=$true} }
    }
    throw 'No unused or identity-matching local port; existing services preserved.'
}
function Test-REV10ResearchHealth([int]$Port,[int]$ViewerPort) {
    try {
        $rev10Base = "http://127.0.0.1:$Port/api/v1"
        $rev10Health = Get-REV10Json "$rev10Base/health"
        $rev10Caps = Get-REV10Json "$rev10Base/capabilities"
        if ($rev10Health.schemaVersion -ne '1.0.0' -or $rev10Health.data.status -ne 'ok' -or $rev10Health.data.readOnly -ne $true) { return $false }
        if ($rev10Caps.data.readOnly -ne $true -or $rev10Caps.data.mutations -ne $false -or $rev10Caps.data.validationAvailable -ne $false -or $rev10Caps.data.finalOosAvailable -ne $false) { return $false }
        $rev10Origin = "http://127.0.0.1:$ViewerPort"
        $rev10Cors = Invoke-WebRequest -UseBasicParsing -Uri "$rev10Base/health" -Method Get -Headers @{Origin=$rev10Origin} -TimeoutSec 5
        return $rev10Cors.StatusCode -eq 200 -and [string]$rev10Cors.Headers['Access-Control-Allow-Origin'] -eq $rev10Origin
    } catch { return $false }
}
function Test-REV10TrustedResearch([int]$Port,[int]$ViewerPort) {
    # Reuse only the same checkout's actual Node Research API on IPv4 loopback.
    $rev10Listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($rev10Listeners.Count -eq 0 -or @($rev10Listeners | Where-Object { $_.LocalAddress -ne '127.0.0.1' }).Count) { return $false }
    $rev10Pids = @($rev10Listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($rev10Pids.Count -ne 1) { return $false }
    try {
        $rev10Process = Get-CimInstance Win32_Process -Filter "ProcessId = $($rev10Pids[0])" -ErrorAction Stop
        if (-not $rev10Process -or $rev10Process.ExecutablePath -cne $rev10Node -or
            $rev10Process.CommandLine.IndexOf($rev10ResearchEntry,[StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
        return Test-REV10ResearchHealth $Port $ViewerPort
    } catch { return $false }
}
function Wait-REV10Research([int]$Port,[int]$ViewerPort) {
    $rev10Deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $rev10Deadline) {
        if (Test-REV10ResearchHealth $Port $ViewerPort) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'Research API not ready or its exact local CORS/readonly health rejected this dashboard origin.'
}
function Set-REV10Environment([string]$Name,[string]$Value) {
    if (-not $rev10SavedEnvironment.ContainsKey($Name)) { $rev10SavedEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name,'Process') }
    [Environment]::SetEnvironmentVariable($Name,$Value,'Process')
}
function Start-REV10Service([string]$Entry,[string]$Name) {
    if ($Entry.Contains('"')) { throw 'Invalid service path.' }
    Start-Process -FilePath $rev10Node -ArgumentList ('"' + $Entry + '"') -WindowStyle Hidden -WorkingDirectory $rev10Repo -RedirectStandardOutput (Join-Path $rev10Logs "$Name.stdout.log") -RedirectStandardError (Join-Path $rev10Logs "$Name.stderr.log") -PassThru
}
function Wait-REV10Service([int]$Port,[string]$Resource,[hashtable]$Expected,[switch]$Envelope) {
    $rev10Deadline = [DateTime]::UtcNow.AddSeconds(25)
    while ([DateTime]::UtcNow -lt $rev10Deadline) {
        if (Test-REV10Service $Port $Resource $Expected -Envelope:$Envelope) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'Read-only service health or identity check failed; inspect delivery launch logs.'
}
try {
    Assert-REV10External $DeliveryRoot
    $rev10ReviewRoot = Join-Path $DeliveryRoot 'review'
    $rev10Review = Assert-REV10Pack $rev10ReviewRoot 'delivery-manifest.json'
    if ($rev10Review.private_local_only -ne $true -or $rev10Review.classification -ne 'EXPLORATORY_POST_HOC') { throw 'Research-only offline pack required.' }
    $rev10ModelHash = Get-REV10Hash (Join-Path $rev10Repo 'config\research\swl1-rev10-short-v1.json')
    if ($rev10Review.model_hash -ne $rev10ModelHash) { throw 'Offline model identity mismatch.' }
    if (-not $rev10Review.files.'index.html') { throw 'Offline HTML entry is not bound.' }
    foreach ($rev10File in $rev10Review.source_sha256.PSObject.Properties) {
        if ($rev10File.Name -notmatch '^(reports/research/swl1_short_horizon_exploration/|config/research/|docs/research/)' -or $rev10File.Name.Contains('..')) { throw 'Invalid offline source path.' }
        if ((Get-REV10Hash (Join-Path $rev10Repo $rev10File.Name)) -ne $rev10File.Value) { throw 'Offline research source changed.' }
    }
    $rev10OfflineVerified = $true
    $rev10BundleRoot = Join-Path $DeliveryRoot 'web'
    $rev10Bundle = Assert-REV10Pack $rev10BundleRoot 'bundle-manifest.json'
    if ($rev10Bundle.service -ne 'REV10_DASHBOARD_BUNDLE' -or $rev10Bundle.model_hash -ne $rev10ModelHash) { throw 'Existing dashboard bundle required.' }
    if (-not $rev10Bundle.files.'index.html') { throw 'Dashboard HTML entry is not bound.' }
    foreach ($rev10File in $rev10Bundle.source_sha256.PSObject.Properties) {
        if (-not $rev10File.Name.StartsWith('dashboard/') -or $rev10File.Name.Contains('..')) { throw 'Invalid bundle source path.' }
        if ((Get-REV10Hash (Join-Path $rev10Repo $rev10File.Name)) -ne $rev10File.Value) { throw 'Dashboard source changed after this build.' }
    }
    $rev10PreviewRoot = ''
    $rev10PreviewPin = ''
    if ($rev10Review.preview_manifest_sha256) {
        $rev10PreviewRoot = Join-Path $DeliveryRoot 'preview'
        $rev10Preview = Assert-REV10Pack $rev10PreviewRoot 'manifest.json'
        $rev10PreviewPin = Get-REV10Hash (Join-Path $rev10PreviewRoot 'manifest.json')
        if ($rev10PreviewPin -ne $rev10Review.preview_manifest_sha256 -or $rev10Preview.namespace -ne 'RESEARCH_REPLAY_ONLY') { throw 'Private preview pin mismatch.' }
    }
    $rev10Node = (Get-Command node -ErrorAction Stop).Source
    $rev10ApiIdentity = @{service='SWL1_REV10_READ_ONLY_RESEARCH';read_only=$true;model_hash=$rev10ModelHash;module_sha256=(Get-REV10Hash (Join-Path $rev10Repo 'services\industry-forecast-api\rev10.mjs'));server_module_sha256=(Get-REV10Hash (Join-Path $rev10Repo 'services\industry-forecast-api\server.mjs'));manifest_sha256=$(if ($rev10PreviewPin) {$rev10PreviewPin} else {$null})}
    $rev10Api = Find-REV10Port $ApiPort 'api/industry-forecast/swl1-rev10/health' $rev10ApiIdentity -Envelope
    $rev10BundlePin = Get-REV10Hash (Join-Path $rev10BundleRoot 'bundle-manifest.json')
    $rev10ReviewPin = Get-REV10Hash (Join-Path $rev10ReviewRoot 'delivery-manifest.json')
    $rev10ViewerIdentity = @{service='REV10_STATIC_VIEWER';read_only=$true;bundle_sha256=$rev10BundlePin;review_sha256=$rev10ReviewPin;model_hash=$rev10ModelHash;module_sha256=(Get-REV10Hash (Join-Path $rev10Repo 'services\industry-forecast-api\viewer.mjs'));api_port=$rev10Api.Port}
    $rev10Viewer = Find-REV10Port $DashboardPort 'health' $rev10ViewerIdentity -ExcludedPort $rev10Api.Port
    if ($rev10Viewer.Port -eq $rev10Api.Port) { throw 'Distinct local ports required.' }
    $rev10Logs = Join-Path $DeliveryRoot ('launch\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff') + '-' + $PID)
    New-Item -ItemType Directory -Path $rev10Logs -Force | Out-Null
    $rev10Environment = @{
        INDUSTRY_FORECAST_API_PORT="$($rev10Api.Port)";INDUSTRY_FORECAST_RUNTIME_ROOT='';
        SWL1_REV10_PREVIEW_ROOT=$rev10PreviewRoot;SWL1_REV10_MANIFEST_SHA256=$rev10PreviewPin;
        DASHBOARD_ORIGINS="http://127.0.0.1:$($rev10Viewer.Port),http://localhost:$($rev10Viewer.Port)";
        REV10_VIEWER_PORT="$($rev10Viewer.Port)";REV10_BUNDLE_ROOT=$rev10BundleRoot;REV10_BUNDLE_SHA256=$rev10BundlePin;
        REV10_REVIEW_ROOT=$rev10ReviewRoot;REV10_REVIEW_SHA256=$rev10ReviewPin;
        HOST='127.0.0.1';PORT="$rev10ResearchPort"
    }
    foreach ($rev10Name in $rev10Environment.Keys) { Set-REV10Environment $rev10Name $rev10Environment[$rev10Name] }
    if (-not $rev10Api.Reuse) { $rev10Started += Start-REV10Service (Join-Path $rev10Repo 'services\industry-forecast-api\server.mjs') 'industry-api' }
    Wait-REV10Service $rev10Api.Port 'api/industry-forecast/swl1-rev10/health' $rev10ApiIdentity -Envelope
    # The REV10 static build uses the existing Research API default URL. Launch it,
    # or reuse a verified local instance; never hijack unknown port owners.
    $rev10ResearchListeners = @(Get-NetTCPConnection -LocalPort $rev10ResearchPort -State Listen -ErrorAction SilentlyContinue)
    $rev10ResearchReused = $rev10ResearchListeners.Count -gt 0
    if ($rev10ResearchReused) {
        if (-not (Test-REV10TrustedResearch $rev10ResearchPort $rev10Viewer.Port)) {
            throw 'Research API port 8787 is occupied by an unknown, incorrectly configured, or unhealthy process. Existing process preserved.'
        }
    } else {
        if (-not (Test-Path -LiteralPath (Join-Path $rev10ResearchCwd 'node_modules\\tsx\\package.json') -PathType Leaf)) {
            throw 'Research API locked dependencies absent: restore existing services/research-api pnpm lockfile dependencies; no automatic install.'
        }
        $rev10Started += Start-Process -FilePath $rev10Node -ArgumentList @('--import','tsx',('"' + $rev10ResearchEntry + '"')) -WindowStyle Hidden -WorkingDirectory $rev10ResearchCwd -RedirectStandardOutput (Join-Path $rev10Logs 'research-api.stdout.log') -RedirectStandardError (Join-Path $rev10Logs 'research-api.stderr.log') -PassThru
        Wait-REV10Research $rev10ResearchPort $rev10Viewer.Port
    }
    if (-not $rev10Viewer.Reuse) { $rev10Started += Start-REV10Service (Join-Path $rev10Repo 'services\industry-forecast-api\viewer.mjs') 'dashboard-viewer' }
    Wait-REV10Service $rev10Viewer.Port 'health' $rev10ViewerIdentity
    $rev10Url = "http://127.0.0.1:$($rev10Viewer.Port)/industry-forecast/swl1-rev10"
    $rev10Overview = Get-REV10Json "http://127.0.0.1:$($rev10Viewer.Port)/api/industry-forecast/swl1-rev10/overview"
    $rev10Ranking = Get-REV10Json "http://127.0.0.1:$($rev10Viewer.Port)/api/industry-forecast/swl1-rev10/ranking"
    if ($rev10Overview.data.classification -ne 'EXPLORATORY_POST_HOC' -or ($rev10PreviewPin -and $rev10Ranking.data.count -ne 30)) { throw 'REV10 content health check failed.' }
    $rev10Page = Invoke-WebRequest -UseBasicParsing -Uri $rev10Url -TimeoutSec 5
    if ($rev10Page.StatusCode -ne 200 -or -not $rev10Page.Content.Contains('id="root"')) { throw 'Existing dashboard route unavailable.' }
    $rev10ResearchStatus = Get-REV10Json "http://127.0.0.1:$rev10ResearchPort/api/v1/research/status"
    $rev10Receipt = @{status='READ_ONLY_WEB_READY';web_url=$rev10Url;api_port=$rev10Api.Port;dashboard_port=$rev10Viewer.Port;research_api_port=$rev10ResearchPort;research_api_connected=$true;research_api_reused=$rev10ResearchReused;research_artifact_state=$rev10ResearchStatus.data.artifactState;api_reused=$rev10Api.Reuse;viewer_reused=$rev10Viewer.Reuse;offline_html=$rev10Offline;ranking_asof=$rev10Ranking.data.asof;ranking_count=$rev10Ranking.data.count;started_pids=@($rev10Started | ForEach-Object {$_.Id});model_hash=$rev10ModelHash;preview_manifest_sha256=$rev10PreviewPin;formal_forecasts_created=0;live_scheduler_enabled=$false}
    $rev10Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $DeliveryRoot 'launch-receipt.json') -Encoding utf8
    if (-not $NoBrowser) { Start-Process -FilePath $rev10Url }
    $rev10Receipt | ConvertTo-Json -Depth 5
} catch {
    foreach ($rev10Process in $rev10Started) { $rev10Process.Refresh(); if (-not $rev10Process.HasExited) { $rev10Process.Kill() } }
    if (-not $rev10OfflineVerified) { throw }
    Write-Warning "Web view unavailable: $($_.Exception.Message)"
    if (-not $NoBrowser) { Start-Process -FilePath $rev10Offline }
    @{status='VERIFIED_OFFLINE_FALLBACK';offline_html=$rev10Offline;web_url=$null;reason=$_.Exception.Message} | ConvertTo-Json
} finally {
    foreach ($rev10Name in $rev10SavedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($rev10Name,$rev10SavedEnvironment[$rev10Name],'Process') }
}

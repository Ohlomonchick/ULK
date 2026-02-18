param(
    [Parameter(Mandatory = $false)]
    [string]$PnetIp = $env:PNET_IP,
    [Parameter(Mandatory = $false)]
    [switch]$OpenBrowser,
    [Parameter(Mandatory = $false)]
    [string]$Test,
    [Parameter(Mandatory = $false)]
    [switch]$KeepPnetOnFail
)

$ComposeFile = "integration_tests/docker/compose.yml"
$BaseUrl = "http://127.0.0.1:18080"

if ([string]::IsNullOrWhiteSpace($PnetIp)) {
    Write-Error "PNET_IP is required. Example: .\integration_tests\run_e2e.ps1 -PnetIp 192.168.0.108. Use -OpenBrowser to show Chromium (e.g. -PnetIp 192.168.1.11 -OpenBrowser)."
    exit 1
}

$env:PNET_IP = $PnetIp
$env:DJANGO_SETTINGS_MODULE = "Cyberpolygon.settings"
if ($OpenBrowser) {
    $env:E2E_OPEN_BROWSER = "1"
    Write-Host "E2E_OPEN_BROWSER=1 (Chromium will open, not headless)" -ForegroundColor Yellow
}

# Цель для pytest: один прогон (e2e + gunicorn) внутри контейнера
if ($Test) {
    $pathPart = if ($Test -match '^(.+?)::') { $Matches[1] } else { $Test }
    if ($pathPart -notmatch '^integration_tests[/\\]') {
        $testTarget = "integration_tests/$Test"
    } else {
        $testTarget = $Test
    }
    Write-Host "Running test(s): $testTarget" -ForegroundColor Cyan
} else {
    $testTarget = "integration_tests/"
    Write-Host "Running full integration suite (e2e + gunicorn)" -ForegroundColor Cyan
}

Write-Host "PNET_IP: $($env:PNET_IP)" -ForegroundColor Cyan
if ($KeepPnetOnFail) {
    Write-Host "KeepPnetOnFail: artifacts will be left on test failure" -ForegroundColor Yellow
}

Write-Host "[integration] docker compose up -d" -ForegroundColor Cyan
docker compose -f $ComposeFile up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed."
    exit 1
}

Write-Host "[integration] waiting for stack ready: $BaseUrl" -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(420)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -lt 500) { break }
    } catch {}
    Start-Sleep -Seconds 2
}
if ((Get-Date) -ge $deadline) {
    Write-Error "Stack did not become ready in time."
    docker compose -f $ComposeFile down -v 2>&1
    exit 1
}

$pytestArgs = @(
    "-m", "integration",
    $testTarget,
    "-vv", "-s", "--log-cli-level=INFO", "--durations=0"
)
if ($KeepPnetOnFail) { $pytestArgs += "--keep-pnet-on-fail" }

Write-Host "[integration] running pytest inside web container..." -ForegroundColor Cyan
# Без -T: TTY сохраняет нормальное форматирование и подсветку вывода pytest
docker compose -f $ComposeFile exec `
  -e INTEGRATION_STACK_EXTERNAL=1 `
  -e INTEGRATION_GUNICORN=1 `
  -e PNET_IP=$env:PNET_IP `
  -e DJANGO_SETTINGS_MODULE=Cyberpolygon.settings `
  web pytest @pytestArgs
$pytestExit = $LASTEXITCODE

Write-Host "[integration] docker compose down -v" -ForegroundColor Cyan
docker compose -f $ComposeFile down -v

exit $pytestExit

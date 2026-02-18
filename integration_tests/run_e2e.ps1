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
if ($Test) {
    $pathPart = if ($Test -match '^(.+?)::') { $Matches[1] } else { $Test }
    if ($pathPart -notmatch '^integration_tests[/\\]') {
        $testTarget = "integration_tests/$Test"
    } else {
        $testTarget = $Test
    }
    Write-Host "Running single test: $testTarget" -ForegroundColor Cyan
} else {
    $e2eTests = Get-ChildItem -Path "integration_tests" -Filter "test_*_e2e.py" | ForEach-Object { $_.FullName }
    if (-not $e2eTests -or $e2eTests.Count -eq 0) {
        Write-Error "No e2e test files found in integration_tests."
        exit 1
    }
    $testTarget = $e2eTests
}
Write-Host "Starting e2e tests with live logs..." -ForegroundColor Cyan
Write-Host "PNET_IP: $($env:PNET_IP)" -ForegroundColor Cyan
if ($KeepPnetOnFail) {
    Write-Host "KeepPnetOnFail: artifacts will be left on test failure" -ForegroundColor Yellow
}
$pytestArgs = @("-m", "integration") + $testTarget + @("-vv", "-s", "--log-cli-level=INFO", "--durations=0")
if ($KeepPnetOnFail) { $pytestArgs += "--keep-pnet-on-fail" }
pytest @pytestArgs

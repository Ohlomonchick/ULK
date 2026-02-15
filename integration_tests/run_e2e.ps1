param(
    [Parameter(Mandatory = $false)]
    [string]$PnetIp = $env:PNET_IP
)

if ([string]::IsNullOrWhiteSpace($PnetIp)) {
    Write-Error "PNET_IP is required. Example: .\\integration_tests\\run_e2e.ps1 -PnetIp 192.168.0.108"
    exit 1
}

$env:PNET_IP = $PnetIp
$env:DJANGO_SETTINGS_MODULE = "Cyberpolygon.settings"
$e2eTests = Get-ChildItem -Path "integration_tests" -Filter "test_*_e2e.py" | ForEach-Object { $_.FullName }
if (-not $e2eTests -or $e2eTests.Count -eq 0) {
    Write-Error "No e2e test files found in integration_tests."
    exit 1
}
Write-Host "Starting e2e tests with live logs..." -ForegroundColor Cyan
Write-Host "PNET_IP: $($env:PNET_IP)" -ForegroundColor Cyan
pytest -m integration @e2eTests -vv -s --log-cli-level=INFO --durations=0

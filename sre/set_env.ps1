# PowerShell script to set environment variables from run_service.sh (lines 13-15)

# Set environment variables for current PowerShell session
$env:PROD = "False"
$env:USE_POSTGRES = "yes"
$env:DB_HOST = "localhost"
$env:DB_NAME = "cyberpolygon"
$env:DB_PORT = "5431"

Write-Host "Environment variables set:" -ForegroundColor Green
Write-Host "  PROD = $env:PROD"
Write-Host "  USE_POSTGRES = $env:USE_POSTGRES"
Write-Host "  DB_HOST = $env:DB_HOST"
Write-Host "  DB_NAME = $env:DB_NAME"
Write-Host "  DB_PORT = $env:DB_PORT"

# PowerShell script to run Django development server with logging to file and console

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project root directory
Set-Location $ProjectRoot

# Load environment variables from set_env.ps1 if it exists
if (Test-Path "$ScriptDir\set_env.ps1") {
    Write-Host "Loading environment variables from set_env.ps1..." -ForegroundColor Cyan
    & "$ScriptDir\set_env.ps1"
}

# Create logs directory if it doesn't exist
$LogsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

# Generate log filename with timestamp
$LogFile = Join-Path $LogsDir "runserver_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"

Write-Host "Starting Django development server..." -ForegroundColor Green
Write-Host "Log file: $LogFile" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Check if virtual environment exists and activate it
$VenvPath = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    & $VenvPath
}

# Run server with logging to both console and file
try {
    python manage.py runserver *>&1 | Tee-Object -FilePath $LogFile
}
catch {
    Write-Host "Error running server: $_" -ForegroundColor Red
    exit 1
}
finally {
    Write-Host "`nServer stopped. Log saved to: $LogFile" -ForegroundColor Cyan
}

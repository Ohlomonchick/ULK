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
$ComposeProject = "cyberpolygon_it"
$BaseUrl = "http://127.0.0.1:18080"

function Invoke-Compose {
    docker compose -f $ComposeFile -p $ComposeProject @args
}

if ([string]::IsNullOrWhiteSpace($PnetIp)) {
    Write-Error "PNET_IP is required. Example: .\integration_tests\run_e2e.ps1 -PnetIp 192.168.0.108. Use -OpenBrowser to show Chromium (e.g. -PnetIp 192.168.1.11 -OpenBrowser)."
    exit 1
}

$env:PNET_IP = $PnetIp
# Переменные для docker-compose (compose.yml подставляет их в environment сервиса web и при exec)
$env:PNET_URL = "http://$PnetIp"
$env:PNET_BASE_DIR = "Practice Work/Test_Labs/IT_TestLabs/e2e"
$env:STUDENT_WORKSPACE = "Practice Work/Test_Labs"
$env:DJANGO_SETTINGS_MODULE = "Cyberpolygon.settings"
if ($OpenBrowser) {
    $env:E2E_OPEN_BROWSER = "1"
    Write-Host "E2E_OPEN_BROWSER=1 (Chromium will open, not headless)" -ForegroundColor Yellow
}

# Определяем, где запускать тест: на хосте (e2e) или внутри контейнера (gunicorn_only).
# Тесты в integration_tests/gunicorn/ помечены @pytest.mark.gunicorn_only и требуют
# живого процесса Gunicorn — они всегда выполняются через docker compose exec web.
# Все остальные тесты запускаются на хосте, чтобы Playwright мог использовать системный Chromium.
$isGunicornTest = $Test -and ($Test -match '(^|[/\\])gunicorn[/\\]')
$runOnHost = (-not $Test) -or (-not $isGunicornTest)
$runInContainer = (-not $Test) -or $isGunicornTest

Write-Host "PNET_IP: $($env:PNET_IP)" -ForegroundColor Cyan
if ($Test) {
    Write-Host "Test filter: $Test  (host=$runOnHost, container=$runInContainer)" -ForegroundColor Cyan
} else {
    Write-Host "Running full integration suite  (e2e on host, gunicorn inside container)" -ForegroundColor Cyan
}
if ($KeepPnetOnFail) {
    Write-Host "KeepPnetOnFail: artifacts will be left on test failure" -ForegroundColor Yellow
}

Write-Host "[integration] docker compose up -d" -ForegroundColor Cyan
Invoke-Compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed."
    exit 1
}

function Wait-StackReady {
    $deadline = (Get-Date).AddSeconds(420)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -lt 500) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "[integration] waiting for stack ready: $BaseUrl" -ForegroundColor Cyan
if (-not (Wait-StackReady)) {
    Write-Error "Stack did not become ready in time."
    Invoke-Compose down -v 2>&1
    exit 1
}

$baseArgs = @("-vv", "-s", "--log-cli-level=INFO", "--durations=0")
if ($KeepPnetOnFail) { $baseArgs += "--keep-pnet-on-fail" }

$exitCode = 0

# ── Фаза 1: e2e тесты на хосте ──────────────────────────────────────────────
# Запускаем pytest локально (хостовый Python), поэтому Playwright использует
# Chromium из системы, а не из контейнера.  Адреса — localhost с проброшенными портами.
if ($runOnHost) {
    if ($Test) {
        $pathPart = if ($Test -match '^(.+?)::') { $Matches[1] } else { $Test }
        $hostTarget = if ($pathPart -notmatch '^integration_tests[/\\]') {
            "integration_tests/$Test"
        } else { $Test }
        # Конкретный тест: используем маркер integration
        $hostArgs = @("-m", "integration") + $baseArgs + @($hostTarget)
    } else {
        # Весь каталог, кроме gunicorn/ (завязан на внутренний gunicorn-процесс)
        $hostArgs = @("-m", "integration and not gunicorn_only") + $baseArgs + @("integration_tests/")
    }
    Write-Host "[integration] phase 1 — e2e tests on HOST" -ForegroundColor Cyan
    pytest @hostArgs
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
}

# ── Фаза 2: gunicorn тесты внутри контейнера ────────────────────────────────
# Тесты с маркером gunicorn_only обращаются к http://127.0.0.1:8002 (gunicorn
# напрямую, без Nginx) и работают с /tmp/gunicorn_worker_mapping.json внутри
# контейнера — на хосте ни то, ни другое недоступно.
# После длительной фазы 1 контейнер web мог завершиться — поднимаем стек снова и ждём готовности.
if ($runInContainer) {
    $webStatus = Invoke-Compose ps web --status running -q 2>$null
    if (-not $webStatus) {
        Write-Host "[integration] web service not running, bringing stack up again for phase 2" -ForegroundColor Yellow
        Invoke-Compose up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Error "docker compose up (phase 2) failed."
            $exitCode = 1
        } else {
            Write-Host "[integration] waiting for stack ready: $BaseUrl" -ForegroundColor Cyan
            if (-not (Wait-StackReady)) {
                Write-Error "Stack did not become ready before phase 2."
                $exitCode = 1
            }
        }
    }
    if ($exitCode -eq 0) {
        if ($Test) {
            $pathPart = if ($Test -match '^(.+?)::') { $Matches[1] } else { $Test }
            $containerTarget = if ($pathPart -notmatch '^integration_tests[/\\]') {
                "integration_tests/$Test"
            } else { $Test }
        } else {
            $containerTarget = "integration_tests/gunicorn/"
        }
        Write-Host "[integration] phase 2 — gunicorn tests inside web container: $containerTarget" -ForegroundColor Cyan
        $containerArgs = @("-m", "integration") + $baseArgs + @($containerTarget)
        Invoke-Compose exec `
          -e INTEGRATION_STACK_EXTERNAL=1 `
          -e INTEGRATION_GUNICORN=1 `
          -e PNET_IP=$env:PNET_IP `
          -e DJANGO_SETTINGS_MODULE=Cyberpolygon.settings `
          web pytest @containerArgs
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    }
}

Write-Host "[integration] docker compose down -v" -ForegroundColor Cyan
Invoke-Compose down -v

exit $exitCode

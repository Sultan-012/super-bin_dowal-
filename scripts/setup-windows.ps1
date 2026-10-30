param([switch]$Development)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    if (-not (Test-Path 'backend\.venv\Scripts\python.exe')) {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 (64-bit) with the Python launcher, then reopen VS Code.' }
        py -3.12 -m venv backend\.venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 was not found. Run: py -0p. Install Python 3.12 and retry from the project root.' }
    }
    $pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
    $requirementsFile = if ($Development) { 'backend\requirements-shift-dev.txt' } else { 'backend\requirements-shift.txt' }
    & $pythonExe -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    if (-not (Test-Path '.env')) {
        Copy-Item '.env.example' '.env'
        $idempotencySecret = & $pythonExe -c 'import secrets; print(secrets.token_urlsafe(48))'
        $n8nSecret = & $pythonExe -c 'import secrets; print(secrets.token_urlsafe(48))'
        $envText = [IO.File]::ReadAllText((Join-Path $projectRoot '.env'))
        $envText = $envText.Replace('IDEMPOTENCY_SECRET=', 'IDEMPOTENCY_SECRET=' + $idempotencySecret.Trim())
        $envText = $envText.Replace('N8N_API_TOKEN=', 'N8N_API_TOKEN=' + $n8nSecret.Trim())
        [IO.File]::WriteAllText((Join-Path $projectRoot '.env'), $envText, (New-Object Text.UTF8Encoding($false)))
    }
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    Write-Host 'Dependencies and interface are ready. Fill DATABASE_URL in .env, migrate the database, then create the first administrator.'
} finally { Pop-Location }

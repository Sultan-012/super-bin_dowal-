$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { throw 'Run setup-windows.ps1 first.' }
if (-not (Test-Path (Join-Path $projectRoot '.env'))) { throw 'Create and configure .env first.' }
if (-not (Test-Path (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Build the frontend first.' }
Push-Location (Join-Path $projectRoot 'backend')
try { & $pythonExe -m uvicorn shift_app.main:create_app --factory --host 127.0.0.1 --port 8000 }
finally { Pop-Location }

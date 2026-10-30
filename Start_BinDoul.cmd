@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Run scripts\setup-windows.ps1 first. See README_AR.md.
  pause
  exit /b 1
)
if not exist ".env" (
  echo Configure .env first. See README_AR.md.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Build the interface first: npm --prefix frontend run build
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 after the server starts. Ctrl+C stops it.
cd backend
".venv\Scripts\python.exe" -m uvicorn shift_app.main:create_app --factory --host 127.0.0.1 --port 8000
if errorlevel 1 pause

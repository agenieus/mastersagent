# ============================================================
#  AI Agent - One-Click Launcher
#  Starts: Backend + Frontend (using Supabase)
# ============================================================

$ROOT     = $PSScriptRoot
$BACKEND  = "$ROOT\backend"
$FRONTEND = "$ROOT\frontend"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AI Agent - Starting All Services" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ------ 1. BACKEND ------
Write-Host "[1/2] Starting Backend (FastAPI on port 8001)..." -ForegroundColor Yellow

$backendCmd = @"
Set-Location '$BACKEND'
Write-Host ''
Write-Host '  *** BACKEND (FastAPI) ***' -ForegroundColor Cyan
Write-Host '  URL: http://localhost:8001' -ForegroundColor White
Write-Host '  Docs: http://localhost:8001/docs' -ForegroundColor White
Write-Host ''
& '$BACKEND\venv\Scripts\uvicorn.exe' main:app --reload --host 0.0.0.0 --port 8001
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
Write-Host "    Backend window opened." -ForegroundColor Green

Start-Sleep -Seconds 2

# ------ 2. FRONTEND ------
Write-Host ""
Write-Host "[2/2] Starting Frontend (Next.js on port 3000)..." -ForegroundColor Yellow

$frontendCmd = @"
Set-Location '$FRONTEND'
Write-Host ''
Write-Host '  *** FRONTEND (Next.js) ***' -ForegroundColor Cyan
Write-Host '  URL: http://localhost:3000' -ForegroundColor White
Write-Host ''
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
Write-Host "    Frontend window opened." -ForegroundColor Green

# ------ DONE ------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All services are starting!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend :  http://localhost:3000" -ForegroundColor White
Write-Host "  Backend  :  http://localhost:8001" -ForegroundColor White
Write-Host "  API Docs :  http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Health   :  http://localhost:8001/health" -ForegroundColor White
Write-Host ""
Write-Host "  Give it ~15 seconds for both servers to fully start." -ForegroundColor Gray
Write-Host "  Check the two new terminal windows for any errors." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to close this launcher window"

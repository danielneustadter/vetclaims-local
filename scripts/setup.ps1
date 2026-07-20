# VetClaims Local — first-run setup (Windows)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Write-Host "== VetClaims Local setup ==" -ForegroundColor Cyan

# 1. Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama not found. Install it from https://ollama.com/download first." -ForegroundColor Red
  exit 1
}
Write-Host "Pulling models (mistral-small:22b ~12GB, qwen3:4b, nomic-embed-text)..."
ollama pull mistral-small:22b
ollama pull qwen3:4b
ollama pull nomic-embed-text

# 2. Backend
Set-Location "$root\backend"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -r requirements.txt --quiet

# 3. Refdata (rating schedule from the eCFR — needs internet once)
Set-Location $root
if (-not (Test-Path "backend\app\refdata\data\rating_schedule.json")) {
  backend\.venv\Scripts\python.exe scripts\build_rating_schedule.py
}

# 4. Frontend
Set-Location "$root\frontend"
npm install --silent

Write-Host ""
Write-Host "Done. Start the app with:" -ForegroundColor Green
Write-Host "  cd backend; .venv\Scripts\uvicorn app.main:app --port 8600"
Write-Host "  cd frontend; npm run dev    # then open http://localhost:5173"

#!/usr/bin/env bash
# VetClaims Local — first-run setup (Linux/macOS)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
echo "== VetClaims Local setup =="

command -v ollama >/dev/null || { echo "Install Ollama first: https://ollama.com/download"; exit 1; }
echo "Pulling models (mistral-small:22b ~12GB, qwen3:4b, nomic-embed-text)..."
ollama pull mistral-small:22b
ollama pull qwen3:4b
ollama pull nomic-embed-text

cd "$root/backend"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt --quiet

cd "$root"
[ -f backend/app/refdata/data/rating_schedule.json ] || \
  backend/.venv/bin/python scripts/build_rating_schedule.py

cd "$root/frontend"
npm install --silent

echo
echo "Done. Start the app with:"
echo "  cd backend && .venv/bin/uvicorn app.main:app --port 8600"
echo "  cd frontend && npm run dev    # then open http://localhost:5173"

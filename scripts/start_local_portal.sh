#!/usr/bin/env zsh
set -e

PROJECT_ROOT="/Users/dennisschetters/ai-governance-os"
FRONTEND_ROOT="/Users/dennisschetters/ai-governance-frontend"

echo "STOP OLD PROCESSES"
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 2

echo "START BACKEND"
cd "$PROJECT_ROOT"
source venv/bin/activate
nohup uvicorn app.main:app --host 127.0.0.1 --port 8001 > /tmp/ai_governance_backend.log 2>&1 &
sleep 5
curl -s http://127.0.0.1:8001/health
echo
echo

echo "START FRONTEND"
cd "$FRONTEND_ROOT"
nohup npm run dev > /tmp/ai_governance_frontend.log 2>&1 &
sleep 5

echo "OPEN PORTAL"
open http://localhost:5173

echo
echo "DONE"
echo "BACKEND LOG: /tmp/ai_governance_backend.log"
echo "FRONTEND LOG: /tmp/ai_governance_frontend.log"

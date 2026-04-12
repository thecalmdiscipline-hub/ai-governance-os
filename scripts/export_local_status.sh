#!/usr/bin/env zsh
set -e

OUTDIR="/Users/dennisschetters/ai-governance-os/status_export"
mkdir -p "$OUTDIR"

echo "EXPORT: health"
curl -s http://127.0.0.1:8001/health > "$OUTDIR/health.json"

echo "EXPORT: login + token"
TOKEN=$(curl -s -X POST http://127.0.0.1:8001/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=dennis_admin' \
  --data-urlencode 'password=Admin123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo ${#TOKEN} > "$OUTDIR/token_length.txt"

echo "EXPORT: documents"
curl -s http://127.0.0.1:8001/documents \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/documents.json"

echo "EXPORT: workflows dashboard"
curl -s http://127.0.0.1:8001/workflows/dashboard \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/workflows_dashboard.json"

echo "EXPORT: workflows history"
curl -s "http://127.0.0.1:8001/workflows/history?limit=10" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/workflows_history.json"

echo "EXPORT: audit"
curl -s "http://127.0.0.1:8001/audit?limit=20" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/audit.json"

echo "DONE: $OUTDIR"

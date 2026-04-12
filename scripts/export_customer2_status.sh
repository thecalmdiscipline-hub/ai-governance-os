#!/usr/bin/env zsh
set -e

OUTDIR="/Users/dennisschetters/ai-governance-os/status_export_customer2"
mkdir -p "$OUTDIR"

BASE_URL="http://127.0.0.1:8001"

TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=customer2_admin' \
  --data-urlencode 'password=Customer123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo ${#TOKEN} > "$OUTDIR/token_length.txt"

curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/documents.json"

curl -s "$BASE_URL/workflows/dashboard" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/workflows_dashboard.json"

curl -s "$BASE_URL/workflows/history?limit=10" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/workflows_history.json"

curl -s "$BASE_URL/audit?limit=20" \
  -H "Authorization: Bearer $TOKEN" > "$OUTDIR/audit.json"

echo "DONE: $OUTDIR"

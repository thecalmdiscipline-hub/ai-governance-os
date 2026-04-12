#!/usr/bin/env zsh
set -e

BASE_URL="http://127.0.0.1:8001"

echo "STEP 1: health"
curl -s "$BASE_URL/health"
echo
echo

echo "STEP 2: login"
TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=dennis_admin' \
  --data-urlencode 'password=Admin123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "TOKEN LENGTH: ${#TOKEN}"
echo
echo

echo "STEP 3: upload document"
printf 'minimal smoke file' > /tmp/minimal_smoke_file.txt
UPLOAD_RESULT=$(curl -s -X POST "$BASE_URL/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/minimal_smoke_file.txt")

echo "$UPLOAD_RESULT"
echo
echo

DOC_ID=$(echo "$UPLOAD_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["document"]["id"])')

echo "STEP 4: list documents"
curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 5: run workflow"
RUN_RESULT=$(curl -s -X POST "$BASE_URL/workflows/customer-support/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"issue":"minimal smoke workflow","priority":"high"},"context":{}}')

echo "$RUN_RESULT"
echo
echo

RUN_ID=$(echo "$RUN_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["run_id"])')

echo "STEP 6: workflow card"
curl -s "$BASE_URL/workflows/runs/$RUN_ID/card" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 7: audit"
curl -s "$BASE_URL/audit?limit=10" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 8: delete document"
curl -s -X DELETE "$BASE_URL/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "MINIMAL SMOKE DONE"

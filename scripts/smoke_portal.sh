#!/usr/bin/env zsh
set -e

BASE_URL="http://127.0.0.1:8001"
USERNAME="dennis_admin"
PASS_VALUE="Admin123!"

echo "STEP 1: health"
curl -s "$BASE_URL/health"
echo
echo

echo "STEP 2: login"
curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=${USERNAME}" \
  --data-urlencode "password=${PASS_VALUE}" > /tmp/login_portal_smoke.json

cat /tmp/login_portal_smoke.json
echo
echo

TOKEN=$(python3 -c 'import json; data=json.load(open("/tmp/login_portal_smoke.json")); print(data.get("access_token",""))')

if [ -z "$TOKEN" ]; then
  echo "LOGIN FAILED"
  exit 1
fi

echo "TOKEN LENGTH: ${#TOKEN}"
echo

echo "STEP 3: upload document"
printf 'portal smoke test file' > /tmp/portal_smoke_test.txt

curl -s -X POST "$BASE_URL/documents/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/portal_smoke_test.txt" > /tmp/portal_upload_result.json

cat /tmp/portal_upload_result.json
echo
echo

DOC_ID=$(python3 -c 'import json; print(json.load(open("/tmp/portal_upload_result.json"))["document"]["id"])')

echo "DOC_ID: $DOC_ID"
echo

echo "STEP 4: documents list"
curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 5: document preview"
curl -s "$BASE_URL/documents/$DOC_ID/preview" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 6: customer support workflow"
curl -s -X POST "$BASE_URL/workflows/customer-support/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"issue":"portal smoke workflow","priority":"high"},"context":{}}' > /tmp/portal_workflow_result.json

cat /tmp/portal_workflow_result.json
echo
echo

RUN_ID=$(python3 -c 'import json; print(json.load(open("/tmp/portal_workflow_result.json"))["run_id"])')

echo "RUN_ID: $RUN_ID"
echo

echo "STEP 7: workflow card"
curl -s "$BASE_URL/workflows/runs/$RUN_ID/card" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 8: workflow history"
curl -s "$BASE_URL/workflows/history?limit=5" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 9: workflow summary"
curl -s "$BASE_URL/workflows/summary?limit=5" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 10: workflow dashboard"
curl -s "$BASE_URL/workflows/dashboard" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 11: audit"
curl -s "$BASE_URL/audit?limit=10" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "STEP 12: delete uploaded document"
curl -s -X DELETE "$BASE_URL/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
echo
echo

echo "SMOKE TEST DONE"

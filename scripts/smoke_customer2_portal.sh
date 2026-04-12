#!/usr/bin/env zsh
set -e

BASE_URL="http://127.0.0.1:8001"

echo "STEP 1: login customer2"
CUSTOMER2_TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=customer2_admin' \
  --data-urlencode 'password=Customer123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "TOKEN LENGTH: ${#CUSTOMER2_TOKEN}"
echo
echo

echo "STEP 2: upload customer2 document"
printf 'customer2 smoke file' > /tmp/customer2_smoke_file.txt

UPLOAD_RESULT=$(curl -s -X POST "$BASE_URL/documents/upload" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN" \
  -F "file=@/tmp/customer2_smoke_file.txt")

echo "$UPLOAD_RESULT"
echo
echo

DOC_ID=$(echo "$UPLOAD_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["document"]["id"])')

echo "STEP 3: customer2 documents"
curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "STEP 4: customer2 workflow"
RUN_RESULT=$(curl -s -X POST "$BASE_URL/workflows/customer-support/run" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"issue":"customer2 smoke workflow","priority":"high"},"context":{}}')

echo "$RUN_RESULT"
echo
echo

RUN_ID=$(echo "$RUN_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["run_id"])')

echo "STEP 5: customer2 workflow history"
curl -s "$BASE_URL/workflows/history?limit=10" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "STEP 6: customer2 audit"
curl -s "$BASE_URL/audit?limit=10" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "STEP 7: delete customer2 document"
curl -s -X DELETE "$BASE_URL/documents/$DOC_ID" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "STEP 8: delete customer2 workflow run"
curl -s -X DELETE "$BASE_URL/workflows/runs/$RUN_ID" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "CUSTOMER2 SMOKE DONE"

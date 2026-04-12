#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os

BASE_URL="http://127.0.0.1:8001"

echo "STEP 1: reset local state"
./scripts/reset_local_portal_state.sh
echo
echo

echo "STEP 2: ensure customer2 exists"
./scripts/create_local_customer_2.sh
echo
echo

echo "STEP 3: login tenant 1"
ADMIN_TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=dennis_admin' \
  --data-urlencode 'password=Admin123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "ADMIN TOKEN LENGTH: ${#ADMIN_TOKEN}"
echo
echo

echo "STEP 4: seed tenant 1 document"
printf 'Valqeron bronze plan includes dashboard access, workflow history, and document upload.' > /tmp/demo_tenant1.txt

curl -s -X POST "$BASE_URL/documents/upload" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/tmp/demo_tenant1.txt"
echo
echo

echo "STEP 5: seed tenant 1 workflow"
curl -s -X POST "$BASE_URL/workflows/customer-support/run" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"issue":"Demo tenant 1 workflow","priority":"high"},"context":{}}'
echo
echo

echo "STEP 6: login tenant 2"
CUSTOMER2_TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=customer2_admin' \
  --data-urlencode 'password=Customer123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "CUSTOMER2 TOKEN LENGTH: ${#CUSTOMER2_TOKEN}"
echo
echo

echo "STEP 7: seed tenant 2 document"
printf 'Customer 2 private demo document for tenant isolation.' > /tmp/demo_tenant2.txt

curl -s -X POST "$BASE_URL/documents/upload" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN" \
  -F "file=@/tmp/demo_tenant2.txt"
echo
echo

echo "STEP 8: seed tenant 2 workflow"
curl -s -X POST "$BASE_URL/workflows/customer-support/run" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"issue":"Demo tenant 2 workflow","priority":"high"},"context":{}}'
echo
echo

echo "STEP 9: verify tenant 1 documents"
curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
echo
echo

echo "STEP 10: verify tenant 2 documents"
curl -s "$BASE_URL/documents" \
  -H "Authorization: Bearer $CUSTOMER2_TOKEN"
echo
echo

echo "DEMO STATE READY"

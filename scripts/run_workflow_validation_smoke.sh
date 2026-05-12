#!/usr/bin/env zsh
set -e

BASE_URL="http://127.0.0.1:8001"

TOKEN=$(curl -s -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=dennis_admin' \
  --data-urlencode 'password=Admin123!' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "TOKEN LENGTH: ${#TOKEN}"
echo

run_check() {
  ROUTE_SLUG="$1"
  BODY="$2"

  echo "===== $ROUTE_SLUG ====="
  curl -s -X POST "$BASE_URL/workflows/$ROUTE_SLUG/run" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$BODY"
  echo
  echo
}

run_check "customer-support" '{"input":{"issue":"validation smoke","priority":"high"},"context":{}}'
run_check "document-knowledge" '{"input":{"question":"Summarize uploaded content"},"context":{}}'
run_check "compliance-monitoring" '{"input":{"scope":"internal controls"},"context":{}}'
run_check "sales-lead-qualification" '{"input":{"lead_name":"ACME","need":"automation"},"context":{}}'
run_check "invoice-processing" '{"input":{"invoice_text":"Invoice 123 amount 500"},"context":{}}'
run_check "hr-recruitment" '{"input":{"candidate_name":"Jane Doe","role":"Operations Manager"},"context":{}}'
run_check "marketing-automation" '{"input":{"campaign":"Q3 outreach","goal":"lead generation"},"context":{}}'
run_check "meeting-agenda-assistant" '{"input":{"meeting_topic":"Client onboarding"},"context":{}}'
run_check "quote-contract-generator" '{"input":{"client":"ACME","service":"AI support module"},"context":{}}'
run_check "business-intelligence" '{"input":{"question":"Show latest business insights"},"context":{}}'

echo "WORKFLOW VALIDATION SMOKE DONE"

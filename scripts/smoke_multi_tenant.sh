#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os

echo "STEP 1: reset local portal state"
./scripts/reset_local_portal_state.sh
echo
echo

echo "STEP 2: ensure customer2 exists"
./scripts/create_local_customer_2.sh
echo
echo

echo "STEP 3: smoke default local portal"
./scripts/smoke_local_portal_minimal.sh
echo
echo

echo "STEP 4: smoke customer2 portal"
./scripts/smoke_customer2_portal.sh
echo
echo

echo "STEP 5: export default tenant status"
./scripts/export_local_status.sh
echo
echo

echo "STEP 6: export customer2 status"
./scripts/export_customer2_status.sh
echo
echo

echo "MULTI TENANT SMOKE DONE"

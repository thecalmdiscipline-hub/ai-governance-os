#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os

./scripts/reset_local_admin.sh
./scripts/reset_local_documents.sh
./scripts/reset_local_runs.sh
./scripts/reset_local_audit.sh

echo "LOCAL PORTAL STATE RESET DONE"

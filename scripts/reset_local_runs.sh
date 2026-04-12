#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os
source venv/bin/activate

python3 - <<'PY'
from app.db.session import SessionLocal
from app.models.workflow_run import WorkflowRun

db = SessionLocal()
deleted = db.query(WorkflowRun).delete()
db.commit()
db.close()

print("WORKFLOW_RUN_RESET_OK", deleted)
PY

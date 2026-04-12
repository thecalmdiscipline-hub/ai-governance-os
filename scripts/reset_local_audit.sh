#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os
source venv/bin/activate

python3 - <<'PY'
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog

db = SessionLocal()
deleted = db.query(AuditLog).delete()
db.commit()
db.close()

print("AUDIT_RESET_OK", deleted)
PY

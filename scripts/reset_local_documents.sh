#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os
source venv/bin/activate

mkdir -p uploaded_documents/org_1
find uploaded_documents/org_1 -type f ! -name '862539ba3c0a4557bdf271848a6b23b4_preview_pane_test.txt' -delete

python3 - <<'PY'
from app.db.session import SessionLocal
from app.models.document import Document

KEEP = {"862539ba3c0a4557bdf271848a6b23b4_preview_pane_test.txt"}

db = SessionLocal()
rows = db.query(Document).all()

deleted = 0
for row in rows:
    if row.stored_name not in KEEP:
        db.delete(row)
        deleted += 1

db.commit()
db.close()

print("DOCUMENT_DB_RESET_OK", deleted)
PY

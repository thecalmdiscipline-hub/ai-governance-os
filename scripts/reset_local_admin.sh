#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os
source venv/bin/activate

python3 - <<'PY'
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

USERNAME = "dennis_admin"
PASSWORD = "Admin123!"
ROLE = "admin"
ORG_ID = 1

db = SessionLocal()

user = db.query(User).filter(User.username == USERNAME).first()

if user is None:
    user = User(
        username=USERNAME,
        password_hash=get_password_hash(PASSWORD),
        role=ROLE,
        organization_id=ORG_ID,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("CREATED", user.username, user.organization_id, user.role)
else:
    user.password_hash = get_password_hash(PASSWORD)
    user.role = ROLE
    user.organization_id = ORG_ID
    db.commit()
    db.refresh(user)
    print("RESET", user.username, user.organization_id, user.role)

db.close()
PY

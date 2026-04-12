#!/usr/bin/env zsh
set -e

cd /Users/dennisschetters/ai-governance-os
source venv/bin/activate

python3 - <<'PY'
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.core.security import hash_password

ORG_NAME = "Customer 2"
USERNAME = "customer2_admin"
PASSWORD = "Customer123!"
ROLE = "admin"

db = SessionLocal()

org = db.query(Organization).filter(Organization.name == ORG_NAME).first()
if org is None:
    org = Organization(name=ORG_NAME)
    db.add(org)
    db.commit()
    db.refresh(org)
    print("ORG_CREATED", org.id, org.name)
else:
    print("ORG_EXISTS", org.id, org.name)

user = db.query(User).filter(User.username == USERNAME).first()
if user is None:
    user = User(
        username=USERNAME,
        password_hash=hash_password(PASSWORD),
        role=ROLE,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("USER_CREATED", user.id, user.username, user.organization_id)
else:
    user.password_hash = hash_password(PASSWORD)
    user.role = ROLE
    user.organization_id = org.id
    db.commit()
    db.refresh(user)
    print("USER_RESET", user.id, user.username, user.organization_id)

db.close()
PY

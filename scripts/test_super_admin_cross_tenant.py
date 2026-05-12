"""
Verify that super_admin can access organizations outside their own org,
and that a regular admin cannot.

Usage:
    python scripts/test_super_admin_cross_tenant.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from app.api.dependencies import get_org_scoped_org
from app.models.user import User
from fastapi import HTTPException

PASS = "✅"
FAIL = "❌"
errors = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global errors
    mark = PASS if ok else FAIL
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        errors += 1


db = SessionLocal()

super_admin = db.query(User).filter(User.is_super_admin == True).first()
regular_admin = db.query(User).filter(
    User.is_super_admin == False,
    User.role == "admin",
).first()

if not super_admin:
    print(f"{FAIL} Geen super_admin gebruiker gevonden — seed de database eerst")
    sys.exit(1)

if not regular_admin:
    print(f"{FAIL} Geen gewone admin gebruiker gevonden")
    sys.exit(1)

own_org_id = super_admin.organization_id
other_org_id = regular_admin.organization_id

print(f"super_admin : {super_admin.username} (org {own_org_id})")
print(f"regular_admin: {regular_admin.username} (org {other_org_id})")
print()

# 1. super_admin can fetch their own org
try:
    org = get_org_scoped_org(own_org_id, super_admin, db)
    check("super_admin kan eigen org ophalen", True, f"org.name={org.name!r}")
except HTTPException as e:
    check("super_admin kan eigen org ophalen", False, str(e.detail))

# 2. super_admin can fetch another org (cross-tenant)
try:
    org = get_org_scoped_org(other_org_id, super_admin, db)
    check("super_admin kan andere org ophalen (cross-tenant)", True, f"org.name={org.name!r}")
except HTTPException as e:
    check("super_admin kan andere org ophalen (cross-tenant)", False, str(e.detail))

# 3. regular_admin can fetch their own org
try:
    org = get_org_scoped_org(other_org_id, regular_admin, db)
    check("regular_admin kan eigen org ophalen", True, f"org.name={org.name!r}")
except HTTPException as e:
    check("regular_admin kan eigen org ophalen", False, str(e.detail))

# 4. regular_admin cannot fetch super_admin's org
try:
    org = get_org_scoped_org(own_org_id, regular_admin, db)
    check("regular_admin geblokkeerd voor andere org", False, "404 verwacht maar org teruggegeven")
except HTTPException as e:
    check("regular_admin geblokkeerd voor andere org", e.status_code == 404, f"HTTP {e.status_code}")

# 5. non-existent org returns 404 for both
for user, label in [(super_admin, "super_admin"), (regular_admin, "regular_admin")]:
    try:
        get_org_scoped_org(99999, user, db)
        check(f"{label}: niet-bestaande org geeft 404", False, "geen exception")
    except HTTPException as e:
        check(f"{label}: niet-bestaande org geeft 404", e.status_code == 404, f"HTTP {e.status_code}")

db.close()

print()
if errors == 0:
    print(f"{PASS} Alle checks geslaagd")
else:
    print(f"{FAIL} {errors} check(s) gefaald")
    sys.exit(1)

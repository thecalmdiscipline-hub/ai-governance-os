#!/usr/bin/env bash
# Smoke test of the provisioning API against a running server. Creates ONE real tenant (with a demo document,
# no demo run) and checks the whole path. Prints PASS/FAIL lines only: no token, no password.
#
#   OPS_TOKEN=<access token of a super-admin who logged in with MFA> \
#   BASE_URL=https://api.valqeron.com \          (default http://127.0.0.1:8000)
#   SMOKE_ORG_NAME="ZZ Provisioning Test" \      (default: "Smoke Test <timestamp>")
#   bash scripts/smoke_provision.sh
#
# OPS_TOKEN comes from the environment; this script never mints tokens. A token is obtained by logging in
# (POST /login with username + password, then POST /login/mfa with the code) and taking access_token.
# The tenant stays behind: deactivate its users afterwards (nothing is deleted).
set -euo pipefail

: "${OPS_TOKEN:?set OPS_TOKEN (see the header of this script)}"
export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export SMOKE_ORG_NAME="${SMOKE_ORG_NAME:-Smoke Test $(date -u +%Y%m%d-%H%M%S)}"

exec python3 - <<'PY'
import json, os, secrets, sys, urllib.error, urllib.parse, urllib.request

BASE = os.environ["BASE_URL"].rstrip("/")
TOKEN = os.environ["OPS_TOKEN"]
NAME = os.environ["SMOKE_ORG_NAME"]
fails = 0

def call(method, path, body=None, token=None, form=None):
    headers, data = {}, None
    if token: headers["Authorization"] = "Bearer " + token
    if body is not None: data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    if form is not None: data = urllib.parse.urlencode(form).encode(); headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=120); return r.status, json.loads(r.read() or b"{}"), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        try: payload = json.loads(e.read() or b"{}")
        except Exception: payload = {}
        return e.code, payload, {k.lower(): v for k, v in e.headers.items()}

def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)
    if not cond: fails += 1

st, b, _ = call("GET", "/ops/whoami", token=TOKEN)
check("ops access (whoami)", st == 200 and b.get("mfa") is True, f"status={st}")
if st != 200: sys.exit(1)
st, b, _ = call("GET", "/ops/tenants", token=TOKEN)
check("tenant overview", st == 200 and len(b.get("tenants", [])) >= 1, f"tenants={len(b.get('tenants', []))}")

key = "smoke-" + secrets.token_hex(6)
workflows = ["compliance_monitor", "customer_support_ai", "document_intelligence", "business_intelligence", "sales_qualification_ai"]
body = {"idempotency_key": key, "organization_name": NAME, "country": "NL", "sector": "Smoke test", "tier": "business",
        "modules": ["core"] + workflows, "admin_username": "smoke_admin_" + secrets.token_hex(4),
        "admin_email": "smoke@example.com", "include_demo_document": True, "include_demo_run": False}
st, first, hdr = call("POST", "/ops/tenants/provision", body, TOKEN)
check("provision: 201 created", st == 201 and first.get("created") is True, f"status={st}")
check("response is not cacheable", "no-store" in hdr.get("cache-control", ""))
pw = first.get("admin_password", "")
check("one-time password present (>= 20 chars)", len(pw) >= 20, f"length={len(pw)}")
c = first.get("counts", {})
check("counts: 6 modules, 1 policy, 5 systems, 5 risks, 1 document", c == {"modules": 6, "ai_policies": 1, "ai_systems": 5, "ai_risks": 5, "documents": 1}, json.dumps(c))

st, again, _ = call("POST", "/ops/tenants/provision", body, TOKEN)
check("replay: 200 created=false, same organization, no password",
      st == 200 and again.get("created") is False and again.get("organization_id") == first.get("organization_id") and "admin_password" not in again, f"status={st}")
st, b, _ = call("POST", "/ops/tenants/provision", dict(body, modules=["core"] + workflows[:4] + ["hr_recruitment_ai"]), TOKEN)
check("same key, other modules: 409", st == 409 and b.get("error") == "idempotency_key_conflict", f"status={st}")
st, b, _ = call("POST", "/ops/tenants/provision", dict(body, idempotency_key=key + "-x", admin_username="smoke_x_" + secrets.token_hex(3), modules=["core", "customer_support_ai"], tier="business"), TOKEN)
check("tier violation: 422", st == 422 and b.get("error") == "validation_failed", f"status={st}")

st, login, _ = call("POST", "/login", form={"username": body["admin_username"], "password": pw})
check("first admin can log in, must change password", st == 200 and login.get("must_change_password") is True, f"status={st}")
tok = login.get("access_token", "")
st, b, _ = call("GET", "/modules", token=tok)
check("password gate: /modules -> 403 password_change_required", st == 403 and b == {"error": "password_change_required"}, f"status={st}")
newpw = "S-" + secrets.token_urlsafe(20)
st, _, _ = call("POST", "/auth/change-password", {"current_password": pw, "new_password": newpw}, tok)
check("password change works", st == 200, f"status={st}")
st, b, _ = call("GET", "/modules", token=tok)
check("after the change /modules works, 6 active modules", st == 200 and sum(1 for m in b if m.get("active")) == 6, f"status={st}")

print(f"organization_id={first.get('organization_id')} name={NAME!r}")
print("FAILS:", fails)
sys.exit(1 if fails else 0)
PY

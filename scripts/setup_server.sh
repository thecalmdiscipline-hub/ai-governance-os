#!/usr/bin/env bash
# =============================================================================
# setup_server.sh — One-time server setup for Valqeron on Ubuntu 24.04
#
# Usage (as root on a fresh DigitalOcean droplet):
#   bash setup_server.sh
#
# What it does:
#   - Updates system packages
#   - Installs Python 3 (Ubuntu 24.04's system Python, 3.12), Nginx, Redis,
#     PostgreSQL, Certbot
#   - Creates PostgreSQL database and user
#   - Clones the repo into /opt/valqeron
#   - Creates Python virtual environment
#   - Creates .env with generated secrets and the given OpenAI key
#   - Installs systemd service
#   - Hardens firewall with UFW
#   - For each domain in DOMAINS: bootstraps a certificate via Certbot if
#     one doesn't exist yet, then deploys its real Nginx site config from
#     nginx/sites/ (proxying to the app on :8000)
#   - Bootstraps two Organizations, an admin user, and tenant module access
#   - Runs Alembic migrations and starts the service
#
# Prerequisites:
#   - DNS A records already pointing to this server for every domain in
#     DOMAINS below. Certbot requests one SAN certificate covering all of
#     them in a single call — if any domain's DNS isn't ready yet, the
#     whole certificate request fails. Override DOMAINS (space-separated)
#     to scope a run to only the domains that are actually ready, e.g.:
#       DOMAINS="compliance.valqeron.com" bash setup_server.sh
#     and re-run later with the full list once the rest of the DNS is fixed.
#   - SSH access as root
#   - Set GIT_REPO below (or override via env var) if forking this repo
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit before running, or override via env vars
# ---------------------------------------------------------------------------
GIT_REPO="${GIT_REPO:-https://github.com/thecalmdiscipline-hub/ai-governance-os.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"
PROJECT_DIR="/opt/valqeron"
APP_USER="www-data"
DB_NAME="valqeron"
DB_USER="valqeron"
# If .env already exists, its DATABASE_URL is the source of truth for the
# DB password — reusing it (rather than generating a fresh random value on
# every run) keeps this idempotent: without it, a second run would generate
# a new password that the already-existing Postgres role doesn't have,
# breaking the deploy. See Step 2 below, which always syncs the role's
# actual password to match this value.
_EXISTING_ENV="/opt/valqeron/.env"
if [[ -z "${DB_PASSWORD:-}" && -f "$_EXISTING_ENV" ]]; then
    DB_PASSWORD=$(grep -oP '(?<=^DATABASE_URL=postgresql://valqeron:)[^@]+' "$_EXISTING_ENV" || true)
fi
DB_PASSWORD="${DB_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-dennisschetters@gmail.com}"
read -r -a DOMAINS <<< "${DOMAINS:-api.valqeron.com app.valqeron.com compliance.valqeron.com}"
OPENAI_API_KEY_VALUE="${OPENAI_API_KEY_VALUE:-}"

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
err()  { echo -e "${RED}[ERROR]${NC}  $*" >&2; }
info() { echo -e "${YELLOW}[INFO]${NC}   $*"; }
step() { echo -e "\n${BLUE}━━━ $* ${NC}"; }

if [[ $EUID -ne 0 ]]; then
    err "Run this script as root"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1 — System packages
# ---------------------------------------------------------------------------
step "Updating system packages"
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3 python3-venv python3-dev \
    python3-pip git curl wget unzip \
    nginx redis-server \
    postgresql postgresql-contrib \
    ufw certbot python3-certbot-nginx \
    build-essential libpq-dev
ok "System packages installed"

# ---------------------------------------------------------------------------
# Step 2 — PostgreSQL
# ---------------------------------------------------------------------------
step "Configuring PostgreSQL"
systemctl enable --now postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
# Always sync the role's actual password to $DB_PASSWORD, even if the role
# already existed — otherwise a role created by an earlier run (with a
# password this run never learned) silently drifts from whatever DB_PASSWORD
# this run ends up writing into .env, and every connection fails auth.
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;"
ok "PostgreSQL database '$DB_NAME' ready"

# ---------------------------------------------------------------------------
# Step 3 — Redis
# ---------------------------------------------------------------------------
step "Configuring Redis"
systemctl enable --now redis-server
redis-cli ping | grep -q PONG && ok "Redis is running" || err "Redis not responding"

# ---------------------------------------------------------------------------
# Step 4 — Project directory and repo
# ---------------------------------------------------------------------------
step "Setting up project directory"
# Needed on every re-run: after the first run chowns $PROJECT_DIR to
# $APP_USER, a plain `git` command run as root here would otherwise refuse
# to operate on a directory it doesn't own ("detected dubious ownership").
git config --global --add safe.directory "$PROJECT_DIR"
if [[ -d "$PROJECT_DIR/.git" ]]; then
    info "Repo already cloned — pulling latest"
    git -C "$PROJECT_DIR" pull origin "$GIT_BRANCH"
else
    git clone --branch "$GIT_BRANCH" "$GIT_REPO" "$PROJECT_DIR"
fi
chown -R "$APP_USER:$APP_USER" "$PROJECT_DIR"
ok "Repo ready at $PROJECT_DIR"

# ---------------------------------------------------------------------------
# Step 5 — Python virtual environment
# ---------------------------------------------------------------------------
step "Creating Python virtual environment"
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
    sudo -u "$APP_USER" python3 -m venv "$PROJECT_DIR/venv"
fi
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
ok "Virtual environment ready"

# ---------------------------------------------------------------------------
# Step 6 — .env placeholder
# ---------------------------------------------------------------------------
step "Creating .env file"
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    if [[ -z "$OPENAI_API_KEY_VALUE" ]]; then
        err "OPENAI_API_KEY_VALUE is not set — export it before running this script,"
        err "e.g.: OPENAI_API_KEY_VALUE=sk-... bash setup_server.sh"
        exit 1
    fi
    cat > "$PROJECT_DIR/.env" <<EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
AUDIT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=${OPENAI_API_KEY_VALUE}
ENVIRONMENT=production
ALLOWED_ORIGINS=https://app.valqeron.com,https://compliance.valqeron.com,https://api.valqeron.com
APP_VERSION=1.0.0
EOF
    chown "$APP_USER:$APP_USER" "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
    ok ".env created"
else
    info ".env already exists — skipping"
fi

# ---------------------------------------------------------------------------
# Step 7 — systemd service
# ---------------------------------------------------------------------------
step "Installing systemd service"
cp "$PROJECT_DIR/systemd/valqeron.service" /etc/systemd/system/valqeron.service
systemctl daemon-reload
systemctl enable valqeron
ok "systemd service installed"

# ---------------------------------------------------------------------------
# Step 8 — Nginx common config + firewall
#
# UFW is opened here, before certificates, because Certbot's HTTP-01
# challenge needs port 80 reachable from the internet.
# ---------------------------------------------------------------------------
step "Configuring Nginx (shared config) and firewall"
cp "$PROJECT_DIR/nginx/snippets/common.conf" /etc/nginx/conf.d/valqeron_common.conf
# Rate-limiting zone must live in the http context
cat > /etc/nginx/conf.d/valqeron_rate_limit.conf <<'EOF'
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
EOF
rm -f /etc/nginx/sites-enabled/default

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP"
ufw allow 443/tcp  comment "HTTPS"
ufw --force enable
ok "Shared Nginx config and firewall ready"

# ---------------------------------------------------------------------------
# Step 9 — Per-domain: bootstrap certificate, then deploy the real site config
#
# nginx refuses to load a server block whose ssl_certificate points at a
# file that doesn't exist yet, and Certbot needs a working nginx vhost on
# port 80 to complete the HTTP-01 challenge before it can issue that
# certificate — so for any domain without a cert yet, a minimal HTTP-only
# stub is deployed first, purely to let Certbot obtain the cert. Once the
# cert exists (whether just obtained or already present from a prior run),
# the real per-domain config from nginx/sites/ — proxying to the app on
# :8000, with the real security headers and rate limiting — replaces it.
# ---------------------------------------------------------------------------
step "Issuing certificates and configuring Nginx per domain"
for domain in "${DOMAINS[@]}"; do
    CERT_PATH="/etc/letsencrypt/live/${domain}/fullchain.pem"
    SITE_FILE="$PROJECT_DIR/nginx/sites/${domain}.conf"

    if [[ ! -f "$SITE_FILE" ]]; then
        err "No nginx/sites/${domain}.conf in the repo — skipping ${domain}"
        continue
    fi

    if [[ ! -f "$CERT_PATH" ]]; then
        info "${domain}: no certificate yet — deploying HTTP-only stub for ACME challenge"
        cat > "/etc/nginx/sites-available/${domain}" <<EOF
server {
    listen 80;
    server_name ${domain};
    location / { return 200 'ok'; add_header Content-Type text/plain; }
}
EOF
        ln -sf "/etc/nginx/sites-available/${domain}" "/etc/nginx/sites-enabled/${domain}"
        nginx -t && systemctl reload nginx

        certbot certonly --nginx -d "$domain" --email "$CERTBOT_EMAIL" --agree-tos --non-interactive
        ok "${domain}: certificate issued"
    else
        info "${domain}: certificate already present — skipping issuance"
    fi

    cp "$SITE_FILE" "/etc/nginx/sites-available/${domain}"
    ln -sf "/etc/nginx/sites-available/${domain}" "/etc/nginx/sites-enabled/${domain}"

    if nginx -t; then
        systemctl reload nginx
        ok "${domain}: real Nginx config deployed"
    else
        err "${domain}: Nginx config test failed after deploying real site config — aborting"
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Step 11 — Initial database setup
# ---------------------------------------------------------------------------
step "Running initial database setup"
cd "$PROJECT_DIR"
if sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" -m alembic upgrade head; then
    ok "Migrations applied"
else
    # The very first migration (a97d58eca669_initial_schema.py) was
    # autogenerated against a dev database that already had its tables —
    # it only contains FK/column tweaks, no CREATE TABLE statements, so it
    # cannot bootstrap a genuinely empty database (this had apparently never
    # been exercised against a fresh Postgres instance before). Every table
    # in this schema has always actually been created by the app's own
    # Base.metadata.create_all() call in app/main.py, which runs on every
    # startup — so fall back to that here, then stamp Alembic at head so
    # later real migrations (outbound engine, tenant_modules, etc.) are
    # correctly treated as already applied rather than re-run.
    info "alembic upgrade head failed — falling back to Base.metadata.create_all()"
    info "(see scripts/setup_server.sh comment for why) and stamping head"
    sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" -c "
from app.db.session import engine
from app.db.base import Base
from app import models  # noqa: F401 — registers every ORM model with Base.metadata
Base.metadata.create_all(bind=engine)
print('Schema created via Base.metadata.create_all()')
"
    sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" -m alembic stamp head
    ok "Migrations applied (via create_all() fallback)"
fi

# scripts/seed_modules.py hardcodes organization_id 1 and 2 and expects those
# rows to already exist — on a fresh database they don't, and the FK
# constraint on tenant_modules.organization_id (enforced by Postgres) would
# fail the whole seed transaction. Bootstrap both orgs first, matching the
# pattern in scripts/create_local_customer_2.sh, plus one admin user for org 1
# so there's something to log in with for verification.
ADMIN_PASSWORD="$(python3 -c "import secrets; print(secrets.token_urlsafe(18))")"
BOOTSTRAP_OUTPUT=$(sudo -u "$APP_USER" ADMIN_PASSWORD="$ADMIN_PASSWORD" "$PROJECT_DIR/venv/bin/python" - <<'PYEOF'
import os
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.core.security import hash_password

db = SessionLocal()
try:
    orgs = {}
    for name in ("Valqeron", "Valqeron Demo Org 2"):
        org = db.query(Organization).filter(Organization.name == name).first()
        if org is None:
            org = Organization(name=name)
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"ORG_CREATED {org.id} {org.name}")
        else:
            print(f"ORG_EXISTS {org.id} {org.name}")
        orgs[name] = org

    admin = db.query(User).filter(User.username == "admin").first()
    if admin is None:
        admin = User(
            username="admin",
            password_hash=hash_password(os.environ["ADMIN_PASSWORD"]),
            role="admin",
            organization_id=orgs["Valqeron"].id,
        )
        db.add(admin)
        db.commit()
        print("ADMIN_USER_CREATED admin", orgs["Valqeron"].id)
    else:
        print("ADMIN_USER_EXISTS admin", admin.organization_id)
finally:
    db.close()
PYEOF
)
echo "$BOOTSTRAP_OUTPUT"
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" scripts/seed_modules.py
ok "Database initialised"

if echo "$BOOTSTRAP_OUTPUT" | grep -q "ADMIN_USER_CREATED"; then
    echo -e "\n${YELLOW}Admin login — save this now, it will not be shown again:${NC}"
    echo -e "  username: admin"
    echo -e "  password: ${ADMIN_PASSWORD}"
else
    info "Admin user 'admin' already existed — password unchanged, not shown"
fi

# ---------------------------------------------------------------------------
# Step 12 — Start service
# ---------------------------------------------------------------------------
step "Starting Valqeron service"
systemctl restart valqeron

HEALTHY=false
for i in 1 2 3 4 5 6; do
    sleep 5
    if curl -sf http://localhost:8000/health > /dev/null; then
        HEALTHY=true
        break
    fi
    info "Health check attempt $i/6 not ready yet..."
done

if $HEALTHY; then
    ok "Service is running and healthy"
else
    err "Service started but health check failed after 30s — check: journalctl -u valqeron -n 50"
fi

echo -e "\n${GREEN}━━━ Setup complete ━━━${NC}"
for domain in "${DOMAINS[@]}"; do
    echo -e "  https://${domain}"
done
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Set up cron for health checks: scripts/health_check.sh"
echo -e "  2. Re-run with a wider DOMAINS list once the rest of the DNS is fixed,"
echo -e "     e.g.: DOMAINS=\"api.valqeron.com app.valqeron.com compliance.valqeron.com\" bash setup_server.sh"

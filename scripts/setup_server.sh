#!/usr/bin/env bash
# =============================================================================
# setup_server.sh — One-time server setup for Valqeron on Ubuntu 24.04
#
# Usage (as root on a fresh DigitalOcean droplet):
#   bash setup_server.sh
#
# What it does:
#   - Updates system packages
#   - Installs Python 3.11, Nginx, Redis, PostgreSQL, Certbot
#   - Creates PostgreSQL database and user
#   - Clones the repo into /opt/valqeron
#   - Creates Python virtual environment
#   - Creates .env placeholder
#   - Installs systemd service
#   - Configures Nginx for all three Valqeron domains
#   - Hardens firewall with UFW
#   - Issues HTTPS certificates via Certbot
#
# Prerequisites:
#   - DNS A records already pointing to this server for:
#       api.valqeron.com, app.valqeron.com, compliance.valqeron.com
#   - SSH access as root
#   - Set GIT_REPO and DB_PASSWORD at the top of this script
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit before running
# ---------------------------------------------------------------------------
GIT_REPO="https://github.com/YOUR_ORG/ai-governance-os.git"
GIT_BRANCH="main"
PROJECT_DIR="/opt/valqeron"
APP_USER="www-data"
DB_NAME="valqeron"
DB_USER="valqeron"
DB_PASSWORD="CHANGE_THIS_DB_PASSWORD"
CERTBOT_EMAIL="ops@valqeron.com"
DOMAINS=("api.valqeron.com" "app.valqeron.com" "compliance.valqeron.com")

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
    python3.11 python3.11-venv python3.11-dev \
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
    sudo -u "$APP_USER" python3.11 -m venv "$PROJECT_DIR/venv"
fi
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
ok "Virtual environment ready"

# ---------------------------------------------------------------------------
# Step 6 — .env placeholder
# ---------------------------------------------------------------------------
step "Creating .env file"
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    cat > "$PROJECT_DIR/.env" <<EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-REPLACE_WITH_REAL_KEY
ALLOWED_ORIGINS=https://app.valqeron.com,https://compliance.valqeron.com,https://api.valqeron.com
APP_VERSION=1.0.0
EOF
    chown "$APP_USER:$APP_USER" "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
    ok ".env created — update OPENAI_API_KEY before starting the service"
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
# Step 8 — Nginx
# ---------------------------------------------------------------------------
step "Configuring Nginx"
# Rate-limiting zone must live in the http context
cat > /etc/nginx/conf.d/valqeron_rate_limit.conf <<'EOF'
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
EOF

cp "$PROJECT_DIR/nginx/valqeron.conf" /etc/nginx/sites-available/valqeron
ln -sf /etc/nginx/sites-available/valqeron /etc/nginx/sites-enabled/valqeron
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl reload nginx
ok "Nginx configured"

# ---------------------------------------------------------------------------
# Step 9 — Firewall
# ---------------------------------------------------------------------------
step "Configuring UFW firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP"
ufw allow 443/tcp  comment "HTTPS"
ufw --force enable
ok "Firewall enabled — ports 22, 80, 443 open"

# ---------------------------------------------------------------------------
# Step 10 — HTTPS certificates
# ---------------------------------------------------------------------------
step "Issuing HTTPS certificates via Certbot"
DOMAIN_ARGS=""
for domain in "${DOMAINS[@]}"; do
    DOMAIN_ARGS="$DOMAIN_ARGS -d $domain"
done
certbot --nginx $DOMAIN_ARGS --email "$CERTBOT_EMAIL" --agree-tos --non-interactive --redirect
ok "SSL certificates issued"

# ---------------------------------------------------------------------------
# Step 11 — Initial database setup
# ---------------------------------------------------------------------------
step "Running initial database setup"
cd "$PROJECT_DIR"
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" -m alembic upgrade head
sudo -u "$APP_USER" "$PROJECT_DIR/venv/bin/python" scripts/seed_modules.py
ok "Database initialised"

# ---------------------------------------------------------------------------
# Step 12 — Start service
# ---------------------------------------------------------------------------
step "Starting Valqeron service"
systemctl start valqeron
sleep 5
if curl -sf http://localhost:8000/health > /dev/null; then
    ok "Service is running and healthy"
else
    err "Service started but health check failed — check: journalctl -u valqeron -n 50"
fi

echo -e "\n${GREEN}━━━ Setup complete ━━━${NC}"
echo -e "  App:        https://app.valqeron.com"
echo -e "  API:        https://api.valqeron.com"
echo -e "  Compliance: https://compliance.valqeron.com"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Update OPENAI_API_KEY in $PROJECT_DIR/.env"
echo -e "  2. Restart the service: systemctl restart valqeron"
echo -e "  3. Set up cron for health checks: scripts/health_check.sh"

#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Valqeron deployment script
#
# Usage (as root or sudo-capable user on the server):
#   cd /opt/valqeron && sudo bash scripts/deploy.sh
#
# What it does:
#   1. Stores current git commit for rollback
#   2. Pulls latest code from origin/main
#   3. Installs Python dependencies
#   4. Validates required .env variables
#   5. Runs Alembic migrations
#   6. Runs module seed script
#   7. Restarts the systemd service
#   8. Health-checks the app; rolls back code on failure
#
# Rollback note: code is reverted via git reset --hard if the health check
# fails. Database migrations are NOT rolled back automatically — run
# `alembic downgrade -1` manually if a migration caused the failure.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_DIR="/opt/valqeron"
VENV="$PROJECT_DIR/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
SERVICE="valqeron"
HEALTH_URL="http://localhost:8000/health"
HEALTH_RETRIES=6
HEALTH_INTERVAL=5

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
err()  { echo -e "${RED}[ERROR]${NC}  $*" >&2; }
info() { echo -e "${YELLOW}[INFO]${NC}   $*"; }
step() { echo -e "\n${BLUE}━━━ $* ${NC}"; }

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
PREV_COMMIT=""

rollback() {
    trap - ERR  # prevent recursive trap
    err "Deploy failed — rolling back to ${PREV_COMMIT:-unknown}"
    if [[ -n "$PREV_COMMIT" ]]; then
        git -C "$PROJECT_DIR" reset --hard "$PREV_COMMIT"
        ok "Code reverted to $PREV_COMMIT"
        info "Restarting service with previous code..."
        systemctl restart "$SERVICE" && ok "Service restarted" || err "Service restart failed — check journalctl -u $SERVICE"
    fi
    exit 1
}
trap rollback ERR

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
step "Pre-flight checks"

if [[ ! -d "$PROJECT_DIR" ]]; then
    err "Project directory $PROJECT_DIR not found. Run setup_server.sh first."
    exit 1
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    err ".env file not found at $PROJECT_DIR/.env"
    exit 1
fi

cd "$PROJECT_DIR"
PREV_COMMIT=$(git rev-parse HEAD)
info "Current commit: $PREV_COMMIT"
ok "Pre-flight passed"

# ---------------------------------------------------------------------------
# Step 1 — Git pull
# ---------------------------------------------------------------------------
step "Pulling latest code"
git pull origin main
NEW_COMMIT=$(git rev-parse HEAD)
if [[ "$NEW_COMMIT" == "$PREV_COMMIT" ]]; then
    info "Already up to date ($NEW_COMMIT)"
else
    ok "Updated: ${PREV_COMMIT:0:8} → ${NEW_COMMIT:0:8}"
fi

# ---------------------------------------------------------------------------
# Step 2 — Dependencies
# ---------------------------------------------------------------------------
step "Installing Python dependencies"
$PIP install --quiet --upgrade pip
$PIP install --quiet -r requirements.txt
ok "Dependencies installed"

# ---------------------------------------------------------------------------
# Step 3 — .env validation
# ---------------------------------------------------------------------------
step "Validating .env"
REQUIRED_VARS=("SECRET_KEY" "DATABASE_URL" "OPENAI_API_KEY" "REDIS_URL")
MISSING=()

for var in "${REQUIRED_VARS[@]}"; do
    value=$(grep -E "^${var}=" .env 2>/dev/null | cut -d= -f2- || true)
    if [[ -z "$value" ]]; then
        MISSING+=("$var")
        err "Missing or empty: $var"
    else
        ok "$var is set"
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    err "Aborting: fill in missing variables in .env"
    exit 1
fi

# Warn if SECRET_KEY looks like a placeholder
SECRET_VAL=$(grep "^SECRET_KEY=" .env | cut -d= -f2-)
if [[ "$SECRET_VAL" == *"your-secret-key"* || ${#SECRET_VAL} -lt 32 ]]; then
    err "SECRET_KEY looks insecure (too short or placeholder). Aborting."
    exit 1
fi
ok ".env validation passed"

# ---------------------------------------------------------------------------
# Step 4 — Alembic migrations
# ---------------------------------------------------------------------------
step "Running database migrations"
$PYTHON -m alembic upgrade head
ok "Migrations applied"

# ---------------------------------------------------------------------------
# Step 5 — Seed modules
# ---------------------------------------------------------------------------
step "Seeding tenant modules"
$PYTHON scripts/seed_modules.py
ok "Seed complete"

# ---------------------------------------------------------------------------
# Step 6 — Restart service
# ---------------------------------------------------------------------------
step "Restarting systemd service"
systemctl restart "$SERVICE"
ok "Service restarted"

# ---------------------------------------------------------------------------
# Step 7 — Health check
# ---------------------------------------------------------------------------
step "Health check ($HEALTH_URL)"
HEALTHY=false

for i in $(seq 1 $HEALTH_RETRIES); do
    info "Attempt $i/$HEALTH_RETRIES — waiting ${HEALTH_INTERVAL}s..."
    sleep "$HEALTH_INTERVAL"
    RESPONSE=$(curl -sf "$HEALTH_URL" 2>/dev/null || true)
    if [[ -n "$RESPONSE" ]]; then
        STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || true)
        if [[ "$STATUS" == "ok" ]]; then
            HEALTHY=true
            break
        else
            info "App responded but status=$STATUS"
        fi
    fi
done

if $HEALTHY; then
    ok "App is healthy — deploy complete"
    echo -e "\n${GREEN}✓ Deploy succeeded${NC} (${NEW_COMMIT:0:8})\n"
else
    err "Health check failed after $HEALTH_RETRIES attempts"
    rollback
fi

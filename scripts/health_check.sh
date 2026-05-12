#!/usr/bin/env bash
# =============================================================================
# health_check.sh — Valqeron service health monitor for cron
#
# Crontab entry (runs every minute):
#   * * * * * /opt/valqeron/scripts/health_check.sh >> /var/log/valqeron/health.log 2>&1
#
# Create log directory:
#   mkdir -p /var/log/valqeron && chown www-data:www-data /var/log/valqeron
#
# What it checks:
#   - FastAPI /health endpoint
#   - PostgreSQL reachability
#   - Redis reachability
#   - Restarts the systemd service if the app is unresponsive
# =============================================================================

set -uo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HEALTH_URL="http://localhost:8000/health"
SERVICE="valqeron"
LOG_FILE="/var/log/valqeron/health.log"
MAX_LOG_LINES=10000

# Load DATABASE_URL and REDIS_URL from .env for direct connectivity checks
ENV_FILE="/opt/valqeron/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^(DATABASE_URL|REDIS_URL)=' "$ENV_FILE")
    set +a
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() { echo "[$TIMESTAMP] $*"; }

# Rotate log file if it grows too large
if [[ -f "$LOG_FILE" ]]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE")
    if (( LINE_COUNT > MAX_LOG_LINES )); then
        tail -n 5000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
fi

# ---------------------------------------------------------------------------
# Check 1 — FastAPI /health
# ---------------------------------------------------------------------------
APP_OK=false
HTTP_STATUS=$(curl -o /dev/null -sf -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_STATUS" == "200" ]]; then
    APP_OK=true
    log "OK    app=$HTTP_STATUS"
else
    log "FAIL  app=HTTP_$HTTP_STATUS — service not responding"
fi

# ---------------------------------------------------------------------------
# Check 2 — PostgreSQL
# ---------------------------------------------------------------------------
DB_OK=false
if command -v pg_isready &>/dev/null; then
    if pg_isready -q 2>/dev/null; then
        DB_OK=true
        log "OK    postgresql=reachable"
    else
        log "FAIL  postgresql=not_ready"
    fi
else
    # Fallback: parse DATABASE_URL and try a simple connection
    if [[ -n "${DATABASE_URL:-}" ]]; then
        if python3 -c "
import sys, os
try:
    import psycopg2
    conn = psycopg2.connect(os.environ['DATABASE_URL'], connect_timeout=3)
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            DB_OK=true
            log "OK    postgresql=reachable"
        else
            log "FAIL  postgresql=connection_error"
        fi
    else
        log "WARN  postgresql=DATABASE_URL_not_set"
        DB_OK=true  # can't check, assume ok
    fi
fi

# ---------------------------------------------------------------------------
# Check 3 — Redis
# ---------------------------------------------------------------------------
REDIS_OK=false
if command -v redis-cli &>/dev/null; then
    REDIS_RESPONSE=$(redis-cli ping 2>/dev/null || echo "")
    if [[ "$REDIS_RESPONSE" == "PONG" ]]; then
        REDIS_OK=true
        log "OK    redis=PONG"
    else
        log "FAIL  redis=not_responding"
    fi
else
    log "WARN  redis=redis-cli_not_found"
    REDIS_OK=true  # can't check, assume ok
fi

# ---------------------------------------------------------------------------
# Auto-restart if app is down
# ---------------------------------------------------------------------------
if ! $APP_OK; then
    log "ACTION restarting $SERVICE service..."
    if systemctl restart "$SERVICE" 2>/dev/null; then
        sleep 8
        RECHECK=$(curl -o /dev/null -sf -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
        if [[ "$RECHECK" == "200" ]]; then
            log "OK    service recovered after restart"
        else
            log "CRIT  service still down after restart (HTTP $RECHECK) — manual intervention required"
        fi
    else
        log "CRIT  systemctl restart $SERVICE failed"
    fi
fi

# ---------------------------------------------------------------------------
# Summary exit code (useful for monitoring integrations)
# ---------------------------------------------------------------------------
if $APP_OK && $DB_OK && $REDIS_OK; then
    exit 0
else
    exit 1
fi

#!/bin/bash
# Batch P3 (2026-10-13): hourly disk-usage check. Warning >=80%, critical >=90%. On a warning
# or critical reading, tries to email Dennis by reusing the app's own, already-configured Resend
# path (app.services.support_mail.send(), same RESEND_API_KEY/SUPPORT_FROM_EMAIL/
# SUPPORT_NOTIFY_EMAIL already in /opt/valqeron/.env) -- no new secret file, nothing printed. If
# that's not configured, this script only writes the status file and a journal line; getting
# Dennis actually notified is then the external uptime service's job (see the hand-off).
set -euo pipefail

BASE=/opt/valqeron
PY="$BASE/venv/bin/python3"
STATUS_DIR=/var/lib/valqeron
STATUS_FILE="$STATUS_DIR/disk-alarm-status.json"

cd "$BASE/scripts"
LEVEL=$("$PY" backup_cli.py disk-level "$(df --output=pcent / | tail -1 | tr -d ' %')")
USE_PCT=$(df --output=pcent / | tail -1 | tr -d ' %')

# Sizes only -- never file names or contents.
BACKUPS_SIZE=$(du -sh /var/backups 2>/dev/null | awk '{print $1}')
APP_SIZE=$(du -sh /opt/valqeron 2>/dev/null | awk '{print $1}')
LOG_SIZE=$(du -sh /var/log 2>/dev/null | awk '{print $1}')

mkdir -p "$STATUS_DIR"
cat > "$STATUS_FILE" <<EOF
{"timestamp": "$(date -u +%FT%TZ)", "level": "$LEVEL", "use_percent": $USE_PCT, "sizes": {"var_backups": "$BACKUPS_SIZE", "opt_valqeron": "$APP_SIZE", "var_log": "$LOG_SIZE"}}
EOF
chmod 644 "$STATUS_FILE"

logger -t valqeron-disk-alarm "level=$LEVEL use=${USE_PCT}% backups=$BACKUPS_SIZE app=$APP_SIZE log=$LOG_SIZE"
echo "disk_alarm.sh: $LEVEL (${USE_PCT}% used)"

if [[ "$LEVEL" != "ok" ]]; then
    cd "$BASE"
    "$PY" - "$LEVEL" "$USE_PCT" <<'PYEOF' || echo "disk_alarm.sh: email notification skipped or failed (non-fatal)" >&2
import sys
from dotenv import load_dotenv
load_dotenv("/opt/valqeron/.env")
from app.services.support_mail import send, is_configured

if not is_configured():
    print("disk_alarm: no Resend config, skipping email")
    sys.exit(0)

level, pct = sys.argv[1], sys.argv[2]
status, error = send({
    "subject": f"[Valqeron] Disk {level}: {pct}% used on valqeron-prod-v2",
    "text": f"Disk usage on the production server is at {pct}% ({level}). "
            f"Check /var/lib/valqeron/disk-alarm-status.json on the server for details.",
    "html": f"<p>Disk usage on the production server is at <b>{pct}%</b> ({level}).</p>",
})
print(f"disk_alarm: email {status} ({error or 'no error'})")
PYEOF
fi

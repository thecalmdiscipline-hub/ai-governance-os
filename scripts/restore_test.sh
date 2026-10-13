#!/bin/bash
# Batch P2 (2026-10-13): weekly automated restore test, against a throwaway database that is
# always dropped (even on failure, via trap) -- never the real database, never the app's own
# port, never real users. Does not touch the encrypted backups themselves: decryption never
# happens on the server (no secret key here), so this takes a FRESH plain pg_dump of the live
# database and restores THAT into the scratch database, then compares row counts.
set -euo pipefail

BASE=/opt/valqeron
PY="$BASE/venv/bin/python3"
DB_NAME=valqeron
SCRATCH_DB=valqeron_restore_test
BACKUP_DIR=/var/backups/valqeron
STATUS_DIR=/var/lib/valqeron
STATUS_FILE="$STATUS_DIR/restore-test-status.json"
FREE_SPACE_MULTIPLIER=2.5
STALE_MAX_HOURS=36
TOLERANCE_PCT=1.0
TABLES=(organizations users audit_logs workflow_runs documents ai_systems)

cd "$BASE/scripts"
cli() { "$PY" backup_cli.py "$@"; }

write_status() {
    # $1=outcome $2=duration_seconds $3=table_count $4=extra_json_fields (may be "")
    mkdir -p "$STATUS_DIR"
    local extra="${4:-}"
    cat > "$STATUS_FILE" <<EOF
{"timestamp": "$(date -u +%FT%TZ)", "outcome": "$1", "duration_seconds": $2, "tables_checked": $3${extra}}
EOF
    chmod 600 "$STATUS_FILE"
}

drop_scratch() {
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $SCRATCH_DB;" > /dev/null 2>&1 || true
}
trap drop_scratch EXIT

START=$(date +%s)

DB_SIZE_BYTES=$(sudo -u postgres psql -tAc "SELECT pg_database_size('$DB_NAME');")
FREE_BYTES=$(df --output=avail -B1 / | tail -1 | tr -d ' ')
USE_PCT=$(df --output=pcent / | tail -1 | tr -d ' %')

if ! cli enough-space "$FREE_BYTES" "$DB_SIZE_BYTES" "$FREE_SPACE_MULTIPLIER" || [[ "$USE_PCT" -gt 80 ]]; then
    echo "restore_test.sh: skipped -- insufficient free space or disk > 80%" >&2
    write_status "skipped" 0 0
    exit 0
fi

# Backup-freshness check: a warning, not a hard failure.
LATEST_LOCAL=$(ls -1t "$BACKUP_DIR"/db-*.dump.age 2>/dev/null | head -1 || true)
STALE_FLAG=""
if [[ -n "$LATEST_LOCAL" ]]; then
    LATEST_ISO=$("$PY" - "$(basename "$LATEST_LOCAL")" <<'PYEOF'
import importlib, sys
backup_lib = importlib.import_module("backup_lib")
dt = backup_lib.parse_backup_filename(sys.argv[1])
print(dt.isoformat() if dt else "")
PYEOF
)
else
    LATEST_ISO=""
fi
if cli stale-check "$LATEST_ISO" "$STALE_MAX_HOURS"; then
    STALE_FLAG=", \"warning\": \"latest local backup is older than ${STALE_MAX_HOURS}h or missing\""
    echo "restore_test.sh: WARNING - latest local backup is stale or missing" >&2
fi

drop_scratch
sudo -u postgres createdb -O postgres "$SCRATCH_DB"

nice -n 10 ionice -c3 sudo -u postgres pg_dump -Fc "$DB_NAME" | sudo -u postgres pg_restore -d "$SCRATCH_DB" --no-owner

MISMATCH=0
for t in "${TABLES[@]}"; do
    LIVE=$(sudo -u postgres psql -tAc "SELECT count(*) FROM $t;" "$DB_NAME" 2>/dev/null || echo "")
    RESTORED=$(sudo -u postgres psql -tAc "SELECT count(*) FROM $t;" "$SCRATCH_DB" 2>/dev/null || echo "")
    if [[ -z "$LIVE" || -z "$RESTORED" ]]; then
        echo "restore_test.sh: table $t missing in live or restored copy" >&2
        MISMATCH=1
        continue
    fi
    if ! cli row-mismatch-ok "$LIVE" "$RESTORED" "$TOLERANCE_PCT"; then
        echo "restore_test.sh: row count mismatch on $t: live=$LIVE restored=$RESTORED" >&2
        MISMATCH=1
    fi
done

DURATION=$(( $(date +%s) - START ))

if [[ "$MISMATCH" -eq 1 ]]; then
    write_status "failed" "$DURATION" "${#TABLES[@]}" "$STALE_FLAG"
    logger -t valqeron-restore-test "FAILED: row count mismatch or missing table"
    exit 1
fi

write_status "ok" "$DURATION" "${#TABLES[@]}" "$STALE_FLAG"
logger -t valqeron-restore-test "ok: ${#TABLES[@]} tables checked in ${DURATION}s"
echo "restore_test.sh: ok -- ${#TABLES[@]} tables checked in ${DURATION}s"

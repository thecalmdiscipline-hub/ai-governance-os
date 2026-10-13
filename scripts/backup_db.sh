#!/bin/bash
# Batch P1 (2026-10-13): daily encrypted database backup with retention.
#
# - Dumps the "valqeron" database via peer auth as the postgres OS user (no password, nothing
#   read from .env). Encrypts with the public age key at /etc/valqeron/backup.pub (not a secret).
# - If /etc/valqeron/backup.env exists (set by Dennis himself, 600, root-only -- this script
#   never writes or prints it), uploads to the configured S3-compatible off-site destination via
#   rclone, verifies the upload, then applies local+offsite retention. Without that file, this
#   is LOCAL-ONLY (same disk, same machine) -- not a real backup; see the warning this script
#   prints and the status file's "offsite": false.
# - Retention: 14 daily + 8 weekly (Sunday) + 6 monthly (1st of month) + always the single most
#   recent backup, computed by scripts/backup_cli.py (tested logic in scripts/backup_lib.py).
set -euo pipefail

BASE=/opt/valqeron
PY="$BASE/venv/bin/python3"
DB_NAME=valqeron
BACKUP_DIR=/var/backups/valqeron
STATUS_DIR=/var/lib/valqeron
STATUS_FILE="$STATUS_DIR/backup-status.json"
PUBKEY_FILE=/etc/valqeron/backup.pub
ENV_FILE=/etc/valqeron/backup.env
DOCS_DIR="$BASE/uploaded_documents"
DUMP_MIN_BYTES=10240
FREE_SPACE_MULTIPLIER=2.0
DOCS_MAX_FREE_SPACE_FRACTION=0.20

# Non-secret off-site config (point 2 of the hand-off; the access keys in $ENV_FILE are the only
# secret part). Only used if $ENV_FILE exists.
RCLONE_REMOTE=valqeronbackup
OFFSITE_BUCKET=valqeron-backups
OFFSITE_ENDPOINT=https://ams3.digitaloceanspaces.com
OFFSITE_REGION=ams3

cd "$BASE/scripts"

cli() { "$PY" backup_cli.py "$@"; }

write_status() {
    # $1=outcome $2=size_bytes $3=checksum $4=offsite(true/false)
    mkdir -p "$STATUS_DIR"
    cat > "$STATUS_FILE" <<EOF
{"timestamp": "$(date -u +%FT%TZ)", "outcome": "$1", "size_bytes": $2, "checksum": "$3", "offsite": $4}
EOF
    chmod 600 "$STATUS_FILE"
}

fail() {
    echo "backup_db.sh: $1" >&2
    logger -t valqeron-backup "FAILED: $1"
    write_status "failed" 0 "" "false"
    exit 1
}

if [[ ! -f "$PUBKEY_FILE" ]]; then
    fail "no public key at $PUBKEY_FILE"
fi
PUBKEY="$(cat "$PUBKEY_FILE")"
if [[ "$PUBKEY" != age1* ]]; then
    fail "key at $PUBKEY_FILE does not start with age1"
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# --- disk pre-flight ---
DB_SIZE_BYTES=$(sudo -u postgres psql -tAc "SELECT pg_database_size('$DB_NAME');")
FREE_BYTES=$(df --output=avail -B1 / | tail -1 | tr -d ' ')
USE_PCT=$(df --output=pcent / | tail -1 | tr -d ' %')

if ! cli enough-space "$FREE_BYTES" "$DB_SIZE_BYTES" "$FREE_SPACE_MULTIPLIER"; then
    fail "not enough free space: ${FREE_BYTES}B free, need ${FREE_SPACE_MULTIPLIER}x ${DB_SIZE_BYTES}B"
fi
LEVEL=$(cli disk-level "$USE_PCT")
if [[ "$LEVEL" == "critical" ]]; then
    fail "disk at ${USE_PCT}% (critical)"
fi

# --- dump + encrypt (atomic: write to .tmp, rename on success) ---
TS=$(date -u +%Y-%m-%dT%H%M%S)
OUT="$BACKUP_DIR/db-$TS.dump.age"
TMP="$OUT.tmp"

nice -n 10 ionice -c3 sudo -u postgres pg_dump -Fc "$DB_NAME" | age -r "$PUBKEY" > "$TMP"
mv "$TMP" "$OUT"
chmod 600 "$OUT"

SIZE_BYTES=$(stat -c%s "$OUT")
if cli dump-too-small "$SIZE_BYTES"; then
    rm -f "$OUT"
    fail "dump too small ($SIZE_BYTES bytes) -- discarded, not kept as a backup"
fi

CHECKSUM=$(sha256sum "$OUT" | awk '{print $1}')
echo "$CHECKSUM" > "$OUT.sha256"
chmod 600 "$OUT.sha256"

# --- optional documents bundle (point: only if small enough) ---
if [[ -d "$DOCS_DIR" ]]; then
    DOCS_SIZE_BYTES=$(du -sb "$DOCS_DIR" | awk '{print $1}')
    MAX_ALLOWED=$(echo "$FREE_BYTES * $DOCS_MAX_FREE_SPACE_FRACTION" | bc | cut -d. -f1)
    if [[ "$DOCS_SIZE_BYTES" -lt "$MAX_ALLOWED" ]]; then
        DOCS_OUT="$BACKUP_DIR/docs-$TS.tar.zst.age"
        tar --zstd -cf - -C "$BASE" uploaded_documents | age -r "$PUBKEY" > "$DOCS_OUT.tmp"
        mv "$DOCS_OUT.tmp" "$DOCS_OUT"
        chmod 600 "$DOCS_OUT"
        sha256sum "$DOCS_OUT" | awk '{print $1}' > "$DOCS_OUT.sha256"
        chmod 600 "$DOCS_OUT.sha256"
    else
        echo "backup_db.sh: uploaded_documents ($DOCS_SIZE_BYTES bytes) is >= ${DOCS_MAX_FREE_SPACE_FRACTION} of free space ($FREE_BYTES bytes) -- skipping the documents bundle this run" >&2
    fi
fi

# --- off-site upload (only if configured) ---
OFFSITE=false
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    export RCLONE_CONFIG_${RCLONE_REMOTE^^}_TYPE=s3
    export RCLONE_CONFIG_${RCLONE_REMOTE^^}_PROVIDER=DigitalOcean
    export RCLONE_CONFIG_${RCLONE_REMOTE^^}_ENDPOINT="$OFFSITE_ENDPOINT"
    export RCLONE_CONFIG_${RCLONE_REMOTE^^}_REGION="$OFFSITE_REGION"
    # RCLONE_CONFIG_<REMOTE>_ACCESS_KEY_ID / _SECRET_ACCESS_KEY come from $ENV_FILE itself.

    REMOTE_PATH="$RCLONE_REMOTE:$OFFSITE_BUCKET/db/$(basename "$OUT")"
    if rclone copyto "$OUT" "$REMOTE_PATH" --checksum; then
        REMOTE_SIZE=$(rclone size "$REMOTE_PATH" --json | "$PY" -c "import json,sys; print(json.load(sys.stdin)['bytes'])")
        if [[ "$REMOTE_SIZE" == "$SIZE_BYTES" ]]; then
            OFFSITE=true
        else
            echo "backup_db.sh: off-site size mismatch ($REMOTE_SIZE vs $SIZE_BYTES) -- not marking as offsite" >&2
        fi
    else
        echo "backup_db.sh: off-site upload failed -- local backup still kept" >&2
    fi
else
    echo "backup_db.sh: WARNING - no $ENV_FILE, this backup is LOCAL ONLY (same disk, same machine). This is NOT a real backup." >&2
fi

# --- retention (runs regardless of off-site; the newest backup is always protected).
# Docs bundles (docs-<ts>.tar.zst.age) share the db dump's retention dates: same keep-set,
# applied separately since they have their own filename pattern.
"$PY" - "$BACKUP_DIR" <<'PYEOF'
import importlib
import re
import sys
from datetime import datetime
from pathlib import Path

backup_lib = importlib.import_module("backup_lib")
backup_dir = Path(sys.argv[1])
docs_re = re.compile(r"^docs-(\d{4})-(\d{2})-(\d{2})T\d{6}\.tar\.zst\.age$")


def remove(name: str, reason: str) -> None:
    (backup_dir / name).unlink(missing_ok=True)
    (backup_dir / f"{name}.sha256").unlink(missing_ok=True)
    print(f"removed old {reason} {name} (retention)")


dated_db = []
for f in backup_dir.glob("db-*.dump.age"):
    dt = backup_lib.parse_backup_filename(f.name)
    if dt:
        dated_db.append((dt.date(), f.name))
keep = backup_lib.compute_keep_set([d for d, _ in dated_db])
for d, name in dated_db:
    if d not in keep:
        remove(name, "backup")

for f in backup_dir.glob("docs-*.tar.zst.age"):
    m = docs_re.match(f.name)
    if not m:
        continue
    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    if d not in keep:
        remove(f.name, "documents bundle")
PYEOF

write_status "ok" "$SIZE_BYTES" "$CHECKSUM" "$OFFSITE"
logger -t valqeron-backup "ok: $OUT ($SIZE_BYTES bytes, offsite=$OFFSITE)"
echo "backup_db.sh: ok -- $OUT ($SIZE_BYTES bytes, offsite=$OFFSITE)"

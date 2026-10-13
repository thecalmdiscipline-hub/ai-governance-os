#!/usr/bin/env python3
"""Batch P (2026-10-13): thin, untested CLI glue over scripts/backup_lib.py's pure functions, so
the bash scripts (backup_db.sh / restore_test.sh / disk_alarm.sh) never re-implement the
retention/threshold logic themselves. Only argv parsing and stdin/stdout plumbing live here --
every actual decision is in backup_lib.py, which has its own unit tests (tests/test_backup_lib.py).
No secrets, no database content read or printed here.
"""
import sys
from datetime import date, datetime

import backup_lib


def _exit_bool(value: bool) -> None:
    sys.exit(0 if value else 1)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: backup_cli.py <command> [args...]", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "disk-level":
        print(backup_lib.disk_usage_level(float(args[0])))

    elif cmd == "enough-space":
        free_bytes, ref_bytes, multiplier = int(args[0]), int(args[1]), float(args[2])
        _exit_bool(backup_lib.has_enough_free_space(free_bytes, ref_bytes, multiplier))

    elif cmd == "dump-too-small":
        _exit_bool(backup_lib.is_dump_too_small(int(args[0])))

    elif cmd == "files-to-delete":
        # stdin: one "YYYY-MM-DD filename" pair per line (filename has no spaces).
        dated_files = []
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            date_str, name = line.split(" ", 1)
            y, m, d = (int(x) for x in date_str.split("-"))
            dated_files.append((date(y, m, d), name))
        for name in backup_lib.files_to_delete(dated_files):
            print(name)

    elif cmd == "stale-check":
        latest = datetime.fromisoformat(args[0]) if args[0] else None
        max_age_hours = float(args[1])
        _exit_bool(backup_lib.is_backup_stale(latest, datetime.utcnow(), max_age_hours))

    elif cmd == "row-mismatch-ok":
        live, restored, tolerance = int(args[0]), int(args[1]), float(args[2])
        _exit_bool(backup_lib.row_count_mismatch_is_acceptable(live, restored, tolerance))

    elif cmd == "format-filename":
        print(backup_lib.format_backup_filename(datetime.utcnow()))

    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

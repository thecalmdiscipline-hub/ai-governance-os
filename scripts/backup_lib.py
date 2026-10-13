"""Batch P (2026-10-13): pure, testable logic for scripts/{backup_db,restore_test,disk_alarm}.sh.
The bash scripts call this module for anything non-trivial (retention, filename parsing,
threshold checks); the shell itself only does I/O (pg_dump, age, rclone, systemctl). No secrets,
no database content, no network calls live here -- everything below is pure functions over
dates/sizes/filenames.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional, Set, Tuple

# db-2026-10-13T031522.dump.age -- full HHMMSS, not just the hour, so two runs inside the same
# calendar hour (e.g. a manual re-run during testing) never collide and never silently overwrite
# each other. The hand-off's own example filename only showed hour-granularity, but its own
# productiecheck explicitly requires "a second run within the same hour writes a new file without
# overwriting the first" -- those two statements conflict, and this resolves it in favour of the
# behavioural requirement. The retention logic below only ever looks at the DATE part, so the
# extra precision changes nothing for grouping/retention.
FILENAME_RE = re.compile(r"^db-(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})\.dump\.age$")


def parse_backup_filename(name: str) -> Optional[datetime]:
    """Returns the timestamp encoded in a backup filename, or None if it doesn't match."""
    m = FILENAME_RE.match(name)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups())
    try:
        return datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None


def format_backup_filename(dt: datetime) -> str:
    return dt.strftime("db-%Y-%m-%dT%H%M%S.dump.age")


def compute_keep_set(dates: List[date]) -> Set[date]:
    """GFS retention: 14 most recent daily + 8 most recent Sunday (weekly) + 6 most recent
    first-of-month (monthly) + always the single most recent date overall, even if it would
    otherwise fall outside all three buckets. `dates` may contain duplicates (de-duplicated
    internally) and need not be pre-sorted. Returns the set of dates to KEEP; everything else
    is a deletion candidate."""
    unique_dates = sorted(set(dates), reverse=True)
    if not unique_dates:
        return set()
    keep: Set[date] = set()
    keep.update(unique_dates[:14])
    sundays = [d for d in unique_dates if d.weekday() == 6]  # Monday=0 .. Sunday=6
    keep.update(sundays[:8])
    first_of_month = [d for d in unique_dates if d.day == 1]
    keep.update(first_of_month[:6])
    keep.add(unique_dates[0])
    return keep


def files_to_delete(dated_files: List[Tuple[date, str]]) -> List[str]:
    """dated_files: list of (date, filename) for existing backups. Returns the filenames that
    are safe to delete under the retention policy (i.e. not in the keep set for that date)."""
    keep = compute_keep_set([d for d, _ in dated_files])
    return [name for d, name in dated_files if d not in keep]


def disk_usage_level(percent_used: float) -> str:
    """Returns "critical" (>=90%), "warning" (>=80%), or "ok"."""
    if percent_used >= 90:
        return "critical"
    if percent_used >= 80:
        return "warning"
    return "ok"


def is_dump_too_small(size_bytes: int, floor_bytes: int = 10 * 1024) -> bool:
    """A dump below this floor is treated as a failed backup, not a tiny-but-valid one."""
    return size_bytes < floor_bytes


def has_enough_free_space(free_bytes: int, reference_size_bytes: int, multiplier: float) -> bool:
    """Generic pre-flight check: is there at least `multiplier` times `reference_size_bytes`
    of free space? P1 uses multiplier=2.0 (vs. the database size), P2 uses 2.5."""
    return free_bytes >= multiplier * reference_size_bytes


def is_backup_stale(latest_backup: Optional[datetime], now: datetime, max_age_hours: float = 36.0) -> bool:
    """P2's own check: is the newest local backup older than max_age_hours (default 36h, vs. a
    daily 03:15 schedule)? A missing backup (None) counts as stale."""
    if latest_backup is None:
        return True
    age = now - latest_backup
    return age.total_seconds() > max_age_hours * 3600


def row_count_mismatch_is_acceptable(live_count: int, restored_count: int, tolerance_pct: float = 1.0) -> bool:
    """P2's row-count comparison: a small gap (default <=1%) from concurrent writes during the
    dump is acceptable and gets reported, not treated as a failed restore test. A restored count
    that doesn't exist at all (e.g. a missing table) is the caller's job to detect separately --
    this function only compares two known counts."""
    if live_count == 0:
        return restored_count == 0
    diff_pct = abs(live_count - restored_count) / live_count * 100
    return diff_pct <= tolerance_pct

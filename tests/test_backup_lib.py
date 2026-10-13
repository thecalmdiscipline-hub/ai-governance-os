"""Batch P (2026-10-13): pure-logic tests for scripts/backup_lib.py (retention, filename
parsing, disk/size thresholds, staleness, row-count tolerance). No database, no filesystem, no
network -- everything here is pure function calls, same pattern as test_demo_scenarios.py's
importlib.import_module("scripts....")."""
import importlib
from datetime import date, datetime

backup_lib = importlib.import_module("scripts.backup_lib")


# ---------------------------------------------------------------------------
# filename parsing / formatting
# ---------------------------------------------------------------------------

def test_format_and_parse_backup_filename_round_trip():
    dt = datetime(2026, 10, 13, 3, 15, 22)
    name = backup_lib.format_backup_filename(dt)
    assert name == "db-2026-10-13T031522.dump.age"
    assert backup_lib.parse_backup_filename(name) == dt


def test_parse_backup_filename_rejects_unrelated_names():
    for bad in ("db-2026-10-13.dump.age", "readme.txt", "db-2026-13-01T000000.dump.age", ""):
        assert backup_lib.parse_backup_filename(bad) is None


def test_same_calendar_hour_two_runs_produce_different_filenames():
    # The hand-off's own productiecheck requires a second run within the same hour to never
    # overwrite the first -- full HHMMSS precision is what makes that true.
    first = backup_lib.format_backup_filename(datetime(2026, 10, 13, 3, 15, 0))
    second = backup_lib.format_backup_filename(datetime(2026, 10, 13, 3, 47, 0))
    assert first != second


# ---------------------------------------------------------------------------
# GFS retention (14 daily / 8 weekly-Sunday / 6 monthly-first-of-month / always the latest)
# ---------------------------------------------------------------------------

def test_fewer_than_fourteen_dates_keeps_everything():
    dates = [date(2026, 10, d) for d in range(1, 6)]
    assert backup_lib.compute_keep_set(dates) == set(dates)


def test_more_than_fourteen_daily_only_keeps_fourteen_most_recent():
    dates = [date(2026, 9, d) for d in range(1, 31)] + [date(2026, 10, d) for d in range(1, 15)]
    keep = backup_lib.compute_keep_set(dates)
    # Daily bucket keeps exactly the 14 most recent dates in this range (2026-10-01..14), plus
    # whatever weekly/monthly anchors happen to also qualify from further back.
    newest_14 = sorted(set(dates), reverse=True)[:14]
    for d in newest_14:
        assert d in keep


def test_a_sunday_older_than_fourteen_days_is_kept_via_the_weekly_bucket():
    # 2026-09-06 is a Sunday; make it the only date, 40 days before "today" in the list.
    sunday = date(2026, 9, 6)
    dates = [sunday] + [date(2026, 10, d) for d in range(1, 16)]  # 15 recent dailies + 1 old Sunday
    keep = backup_lib.compute_keep_set(dates)
    assert sunday.weekday() == 6
    assert sunday in keep


def test_a_non_sunday_older_than_all_buckets_is_deleted():
    old_tuesday = date(2026, 8, 4)
    assert old_tuesday.weekday() == 1
    dates = [old_tuesday] + [date(2026, 10, d) for d in range(1, 16)]
    keep = backup_lib.compute_keep_set(dates)
    assert old_tuesday not in keep


def test_first_of_month_far_in_the_past_is_kept_via_the_monthly_bucket():
    first = date(2026, 4, 1)
    dates = [first] + [date(2026, 10, d) for d in range(1, 16)]
    keep = backup_lib.compute_keep_set(dates)
    assert first in keep


def test_the_single_most_recent_date_is_always_kept_even_if_otherwise_unqualified():
    # A lone, very-old-looking "most recent" date (the only date that exists at all) must never
    # be deleted, regardless of weekday/day-of-month.
    only_date = date(2026, 10, 14)  # a Wednesday, not the 1st -- qualifies for nothing but "latest"
    assert only_date.weekday() != 6
    assert only_date.day != 1
    keep = backup_lib.compute_keep_set([only_date])
    assert keep == {only_date}


def test_files_to_delete_matches_filenames_to_their_dates():
    kept_date = date(2026, 10, 15)
    old_date = date(2026, 1, 2)  # a Friday, not the 1st -- not kept by any bucket once pushed out
    assert old_date.weekday() != 6 and old_date.day != 1
    dated_files = [
        (kept_date, "db-2026-10-15T031500.dump.age"),
        (old_date, "db-2026-01-02T031500.dump.age"),
    ]
    # 14 more recent daily entries (Oct 1-14) push old_date out of the 14-daily bucket entirely.
    padding = [(date(2026, 10, d), f"pad-{d}") for d in range(1, 15)]
    to_delete = backup_lib.files_to_delete(dated_files + padding)
    assert "db-2026-01-02T031500.dump.age" in to_delete
    assert "db-2026-10-15T031500.dump.age" not in to_delete


def test_duplicate_dates_in_input_do_not_break_retention():
    dates = [date(2026, 10, 13), date(2026, 10, 13), date(2026, 10, 12)]
    keep = backup_lib.compute_keep_set(dates)
    assert keep == {date(2026, 10, 13), date(2026, 10, 12)}


def test_empty_input_keeps_nothing_and_does_not_raise():
    assert backup_lib.compute_keep_set([]) == set()
    assert backup_lib.files_to_delete([]) == []


# ---------------------------------------------------------------------------
# disk / size thresholds
# ---------------------------------------------------------------------------

def test_disk_usage_level_thresholds():
    assert backup_lib.disk_usage_level(79.9) == "ok"
    assert backup_lib.disk_usage_level(80.0) == "warning"
    assert backup_lib.disk_usage_level(89.9) == "warning"
    assert backup_lib.disk_usage_level(90.0) == "critical"
    assert backup_lib.disk_usage_level(100.0) == "critical"


def test_is_dump_too_small():
    assert backup_lib.is_dump_too_small(0) is True
    assert backup_lib.is_dump_too_small(10 * 1024 - 1) is True
    assert backup_lib.is_dump_too_small(10 * 1024) is False
    assert backup_lib.is_dump_too_small(10 * 1024 * 1024) is False


def test_has_enough_free_space():
    assert backup_lib.has_enough_free_space(free_bytes=200, reference_size_bytes=100, multiplier=2.0) is True
    assert backup_lib.has_enough_free_space(free_bytes=199, reference_size_bytes=100, multiplier=2.0) is False
    assert backup_lib.has_enough_free_space(free_bytes=250, reference_size_bytes=100, multiplier=2.5) is True


# ---------------------------------------------------------------------------
# P2: staleness check and row-count tolerance
# ---------------------------------------------------------------------------

def test_is_backup_stale_within_window():
    now = datetime(2026, 10, 13, 12, 0, 0)
    assert backup_lib.is_backup_stale(datetime(2026, 10, 12, 3, 15, 0), now) is False  # ~33h, under 36h


def test_is_backup_stale_past_window():
    now = datetime(2026, 10, 13, 12, 0, 0)
    assert backup_lib.is_backup_stale(datetime(2026, 10, 11, 3, 15, 0), now) is True  # ~57h, over 36h


def test_is_backup_stale_when_missing():
    assert backup_lib.is_backup_stale(None, datetime(2026, 10, 13, 12, 0, 0)) is True


def test_row_count_mismatch_is_acceptable():
    assert backup_lib.row_count_mismatch_is_acceptable(1000, 1000) is True
    assert backup_lib.row_count_mismatch_is_acceptable(1000, 1005) is True  # 0.5%
    assert backup_lib.row_count_mismatch_is_acceptable(1000, 1020) is False  # 2%
    assert backup_lib.row_count_mismatch_is_acceptable(0, 0) is True
    assert backup_lib.row_count_mismatch_is_acceptable(0, 1) is False

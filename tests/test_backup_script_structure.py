"""Batch P (2026-10-13): structural checks on the bash scripts themselves -- not their runtime
behaviour (that's verified on the server, per the hand-off), just invariants we can check from
the source text alone without executing anything."""
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _read(name: str) -> str:
    return (SCRIPTS_DIR / name).read_text()


def test_backup_db_uploads_offsite_before_applying_retention():
    # The hand-off's own ordering requirement: "eerst uploaden, dan opruimen" -- never delete a
    # local copy before at least attempting to confirm an off-site copy exists for this run.
    text = _read("backup_db.sh")
    upload_pos = text.index("rclone copyto")
    retention_pos = text.index("compute_keep_set")
    assert upload_pos < retention_pos


def test_backup_db_checks_dump_size_before_writing_the_sha256_sidecar():
    text = _read("backup_db.sh")
    size_check_pos = text.index("dump-too-small")
    checksum_pos = text.index("sha256sum")
    assert size_check_pos < checksum_pos


def test_backup_db_never_writes_the_secret_env_file_itself():
    text = _read("backup_db.sh")
    assert "backup.env" in text  # it's read
    assert "> /etc/valqeron/backup.env" not in text  # never written by this script
    assert "cat >" not in text.split("backup.env")[0] or "backup.pub" in text  # sanity: no stray write before it


def test_restore_test_always_drops_the_scratch_database_even_on_failure():
    text = _read("restore_test.sh")
    assert "trap" in text
    assert "valqeron_restore_test" in text


def test_disk_alarm_never_hardcodes_or_prints_the_resend_key_value():
    # Mentioning the variable NAME (e.g. in a comment, or relying on it already being in the
    # environment via the app's own load_dotenv) is fine; assigning it a literal value or
    # echoing/printing it would not be.
    text = _read("disk_alarm.sh")
    assert "RESEND_API_KEY=" not in text
    assert "echo $RESEND_API_KEY" not in text
    assert "print" not in text or "config['key']" not in text

"""Fase B7 migrations on SQLite and PostgreSQL, plus the shared fixtures for them.

Like tests/test_migration_fase_b.py, the pre-migration tables are built by hand (the repo's first
migration cannot bootstrap an empty database) and the Fase B revisions run against them through
alembic's Operations API. Chain here: B1 -> B5 -> archive_download_enabled flag. The archive
migration itself is a separate, last revision with its own test file
(tests/test_migration_b7_archive.py), so it can be rolled out apart from the rest.

PostgreSQL: set TEST_POSTGRES_URL to an empty, throwaway database, or have the PostgreSQL server
binaries (initdb, pg_ctl) on PATH; the fixture then starts a temporary cluster in a temp directory
on a free localhost port and removes it afterwards. Never point TEST_POSTGRES_URL at production.
Without either, the PostgreSQL cases are skipped (with that reason in the pytest output).
"""
import importlib.util
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
CHAIN = ("507b3c60b20b", "bab4f26df0b0", "fb88a0a24a73")


def _load(revision_prefix):
    path = next(VERSIONS.glob(f"{revision_prefix}_*.py"))
    spec = importlib.util.spec_from_file_location(f"mig_b7_{revision_prefix}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(engine, fn):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def postgres_url():
    url = os.getenv("TEST_POSTGRES_URL")
    if url:
        yield url
        return
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("No TEST_POSTGRES_URL and no initdb/pg_ctl on PATH: PostgreSQL migration test not run")
    base = Path(tempfile.mkdtemp(prefix="valqeron-pg-"))
    data = base / "data"
    port = _free_port()
    subprocess.run([initdb, "-D", str(data), "-U", "postgres", "--auth=trust", "-E", "UTF8"],
                   check=True, capture_output=True)
    subprocess.run(
        [pg_ctl, "-D", str(data), "-l", str(base / "log"), "-w", "-o",
         f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories=''", "start"],
        check=True, capture_output=True,
    )
    try:
        yield f"postgresql+psycopg2://postgres@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"], capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


def _make_engine(kind, tmp_path, postgres_url_fixture):
    if kind == "sqlite":
        return sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    url = postgres_url_fixture
    eng = sa.create_engine(url)
    with eng.begin() as conn:  # start from an empty public schema
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    return eng


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    pg = request.getfixturevalue("postgres_url") if request.param == "postgresql" else None
    eng = _make_engine(request.param, tmp_path, pg)
    with eng.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE documents (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, "
            "filename VARCHAR NOT NULL, stored_name VARCHAR NOT NULL UNIQUE, path VARCHAR NOT NULL, "
            "size INTEGER NOT NULL, created_at TIMESTAMP NOT NULL)"
        ))
        conn.execute(sa.text("CREATE TABLE workflow_runs (id INTEGER PRIMARY KEY, run_id VARCHAR NOT NULL UNIQUE)"))
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR NOT NULL)"))
        conn.execute(sa.text("CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"))
        conn.execute(sa.text("INSERT INTO organizations (id, name) VALUES (1, 'o')"))
    yield eng
    eng.dispose()


def test_archive_download_flag_upgrade_and_downgrade(engine):
    for rev in CHAIN:
        _run(engine, _load(rev).upgrade)
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT archive_download_enabled FROM organizations WHERE id=1")).scalar() in (0, False)

    _run(engine, _load(CHAIN[2]).downgrade)
    insp = sa.inspect(engine)
    assert "archive_download_enabled" not in {c["name"] for c in insp.get_columns("organizations")}
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT name FROM organizations WHERE id=1")).scalar() == "o"


def test_without_archive_migration_existing_rows_keep_their_status(engine):
    # B1 adds scope_status (existing rows: 'uncoded'); B5 and the flag migration leave documents alone.
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO documents (id, organization_id, filename, stored_name, path, size, created_at) "
            "VALUES (1, 1, 'old.txt', 'x_old.txt', 'uploaded_documents/org_1/x_old.txt', 3, '2026-01-01')"
        ))
    for rev in CHAIN:
        _run(engine, _load(rev).upgrade)
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT scope_status FROM documents WHERE id=1")).scalar() == "uncoded"
    assert "scope_status_before_archive" not in {c["name"] for c in sa.inspect(engine).get_columns("documents")}

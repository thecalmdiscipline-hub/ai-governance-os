"""Fase B7 migration (96a4f064fbef): archive every existing document, on SQLite and PostgreSQL.

Like tests/test_migration_fase_b.py, the pre-migration tables are built by hand (the repo's first
migration cannot bootstrap an empty database) and the Fase B revisions B1 -> B5 -> B7 run against
them through alembic's Operations API.

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
CHAIN = ("507b3c60b20b", "bab4f26df0b0", "96a4f064fbef", "fb88a0a24a73")


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


def _seed(engine, tmp_path):
    """Four documents, one per status the B7 migration can meet, each with a real file on disk."""
    files = {}
    with engine.begin() as conn:
        for i, (name, status) in enumerate(
            [("a.txt", "uncoded"), ("b.txt", "coded"), ("c.txt", "archived"), ("d.txt", "uncoded")], start=1
        ):
            path = tmp_path / f"org_1_{name}"
            path.write_text(f"content {name}")
            files[i] = (str(path), path.read_bytes())
            conn.execute(sa.text(
                "INSERT INTO documents (id, organization_id, filename, stored_name, path, size, created_at, scope_status) "
                "VALUES (:id, 1, :fn, :sn, :p, 9, '2026-01-01', :st)"
            ), {"id": i, "fn": name, "sn": f"x_{name}", "p": str(path), "st": status})
        conn.execute(sa.text(
            "INSERT INTO document_scope_codes (document_id, code, created_at) VALUES (2, 'sales', '2026-01-01')"
        ))
    return files


def _rows(engine):
    with engine.begin() as conn:
        return {r.id: r for r in conn.execute(sa.text("SELECT * FROM documents ORDER BY id"))}


def _upgrade_to_b5(engine):
    for rev in CHAIN[:2]:
        _run(engine, _load(rev).upgrade)


def test_b7_upgrade_archives_every_document_keeps_rows_and_files(engine, tmp_path):
    _upgrade_to_b5(engine)
    files = _seed(engine, tmp_path)
    before = _rows(engine)

    _run(engine, _load(CHAIN[2]).upgrade)

    after = _rows(engine)
    assert len(after) == len(before) == 4
    assert {r.scope_status for r in after.values()} == {"archived"}
    assert {i: r.scope_status_before_archive for i, r in after.items()} == {
        1: "uncoded", 2: "coded", 3: None, 4: "uncoded",
    }
    for i, (path, content) in files.items():
        assert after[i].path == before[i].path == path  # no file moved
        assert Path(path).read_bytes() == content
    with engine.begin() as conn:  # codes are kept (V7: fixed once set)
        assert conn.execute(sa.text("SELECT code FROM document_scope_codes WHERE document_id=2")).scalar() == "sales"


def test_b7_downgrade_restores_saved_status_except_restored_documents(engine, tmp_path):
    _upgrade_to_b5(engine)
    _seed(engine, tmp_path)
    b7 = _load(CHAIN[2])
    _run(engine, b7.upgrade)
    with engine.begin() as conn:  # document 4 was restored by a Valqeron administrator meanwhile
        conn.execute(sa.text(
            "UPDATE documents SET scope_status='coded', scope_status_before_archive=NULL WHERE id=4"
        ))

    _run(engine, b7.downgrade)

    after = _rows(engine)
    assert {i: r.scope_status for i, r in after.items()} == {1: "uncoded", 2: "coded", 3: "archived", 4: "coded"}
    insp = sa.inspect(engine)
    assert "scope_status_before_archive" not in {c["name"] for c in insp.get_columns("documents")}


def test_b7_upgrade_on_empty_table(engine):
    _upgrade_to_b5(engine)
    _run(engine, _load(CHAIN[2]).upgrade)
    assert _rows(engine) == {}


def test_archive_download_flag_upgrade_and_downgrade(engine):
    for rev in CHAIN:
        _run(engine, _load(rev).upgrade)
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT archive_download_enabled FROM organizations WHERE id=1")).scalar() in (0, False)

    _run(engine, _load(CHAIN[3]).downgrade)
    insp = sa.inspect(engine)
    assert "archive_download_enabled" not in {c["name"] for c in insp.get_columns("organizations")}
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT name FROM organizations WHERE id=1")).scalar() == "o"

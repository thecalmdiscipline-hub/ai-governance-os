"""Fase B migrations: up and down on SQLite.

The repo's first migration cannot bootstrap an empty database (CLAUDE.md §5), so these tests build
the minimal pre-migration tables by hand and run only the Fase B revision(s) against them, through
alembic's own Operations API.
"""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load(revision_prefix):
    path = next(VERSIONS.glob(f"{revision_prefix}_*.py"))
    spec = importlib.util.spec_from_file_location(f"mig_{revision_prefix}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(engine, fn):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


@pytest.fixture()
def engine(tmp_path):
    eng = sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with eng.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE documents (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, "
            "filename VARCHAR NOT NULL, stored_name VARCHAR NOT NULL UNIQUE, path VARCHAR NOT NULL, "
            "size INTEGER NOT NULL, created_at DATETIME NOT NULL)"
        ))
        conn.execute(sa.text(
            "INSERT INTO documents (id, organization_id, filename, stored_name, path, size, created_at) "
            "VALUES (1, 1, 'old.txt', 'x_old.txt', 'uploaded_documents/org_1/x_old.txt', 3, '2026-01-01')"
        ))
    return eng


def test_b1_upgrade_adds_table_and_marks_existing_rows_uncoded(engine):
    mig = _load("507b3c60b20b")
    _run(engine, mig.upgrade)

    insp = sa.inspect(engine)
    assert "document_scope_codes" in insp.get_table_names()
    assert "scope_status" in {c["name"] for c in insp.get_columns("documents")}
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT scope_status FROM documents WHERE id=1")).scalar() == "uncoded"
        conn.execute(sa.text(
            "INSERT INTO document_scope_codes (document_id, code, created_at) VALUES (1, 'sales', '2026-01-01')"
        ))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO document_scope_codes (document_id, code, created_at) VALUES (1, 'sales', '2026-01-02')"
            ))


def test_b1_downgrade_restores_previous_schema_and_keeps_rows(engine):
    mig = _load("507b3c60b20b")
    _run(engine, mig.upgrade)
    _run(engine, mig.downgrade)

    insp = sa.inspect(engine)
    assert "document_scope_codes" not in insp.get_table_names()
    assert "scope_status" not in {c["name"] for c in insp.get_columns("documents")}
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT filename FROM documents WHERE id=1")).scalar() == "old.txt"

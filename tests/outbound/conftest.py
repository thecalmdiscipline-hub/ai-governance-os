"""
Fixtures voor outbound tests.

Gebruikt een in-memory SQLite database met FK-enforcement via PRAGMA.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Zorg dat de repo-root op het pad staat
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

os.environ["TESTING"] = "1"

from app.db.base import Base  # noqa: E402

# Importeer alle modellen zodat Base ze kent voor create_all
import app.models  # noqa: F401 — registreert alle core models
import app.outbound.models  # noqa: F401 — registreert outbound models


@pytest.fixture(scope="module")
def db_engine():
    """In-memory SQLite engine met FK-enforcement en alle tabellen aangemaakt."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    # SQLite FK enforcement inschakelen
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def session(db_engine):
    """Geeft een database-sessie die na elke test wordt teruggedraaid."""
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture(scope="function")
def test_org(session):
    """Maakt een test-organisatie aan en geeft die terug."""
    from app.models.organization import Organization

    org = Organization(name="Test Outbound Org")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

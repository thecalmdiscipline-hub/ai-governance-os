import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip().strip('"').strip("'")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
else:
    DATABASE_URL = "sqlite+pysqlite:///:memory:"

_is_sqlite = DATABASE_URL.startswith("sqlite")
_is_sqlite_memory = _is_sqlite and ":memory:" in DATABASE_URL

connect_args = {"check_same_thread": False} if _is_sqlite else {}

# In-memory SQLite (e.g. CI's DATABASE_URL=sqlite+pysqlite:///:memory:)
# needs poolclass=StaticPool: without it, SQLAlchemy's default pool hands
# out a fresh connection per checkout, and each one is its own separate,
# empty :memory: database — app/main.py's Base.metadata.create_all() would
# create tables on one throwaway connection while every actual request/test
# gets a different, table-less one ("no such table: ..."). StaticPool
# makes every checkout reuse the same single connection, so it's all one
# database for the lifetime of the process — exactly what a test run needs.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    poolclass=StaticPool if _is_sqlite_memory else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

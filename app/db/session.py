import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Primary: use DATABASE_URL (prod/dev)
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback (tests/CI): use local SQLite so imports never crash
if not DATABASE_URL:
    # file-based sqlite keeps it simple and stable
    DATABASE_URL = "sqlite:///./test.db"

# For sqlite we must set check_same_thread=False
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

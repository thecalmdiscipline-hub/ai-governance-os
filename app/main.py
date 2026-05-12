# pyright: reportArgumentType=false
# pyright: reportOptionalMemberAccess=false

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

load_dotenv()

# ---------------------------------------------------------------------------
# Startup security checks — fail fast before any route is registered
# ---------------------------------------------------------------------------

_UNSAFE_KEYS = {
    "",
    "CHANGE_THIS_IMMEDIATELY",
    "your-secret-key-here-minimum-32-characters",
    "change_this",
}

_secret_key = os.getenv("SECRET_KEY", "")

if _secret_key in _UNSAFE_KEYS:
    sys.exit(
        "FATAL: SECRET_KEY is not configured.\n"
        "Add a strong SECRET_KEY (minimum 32 characters) to your .env file.\n"
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

if len(_secret_key) < 32:
    sys.exit(
        f"FATAL: SECRET_KEY is too short ({len(_secret_key)} chars). "
        "Minimum 32 characters required."
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title=os.getenv("APP_NAME", "AI Governance OS"),
    version=os.getenv("APP_VERSION", "0.1.0"),
)

# Middleware
from app.core.middleware import setup_middleware
setup_middleware(app)

# Global exception handler
_logger = logging.getLogger("uvicorn.error")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "An unexpected error occurred."},
    )

# DB init — all models imported so SQLAlchemy registers them in metadata
from app.db.session import engine
from app.db.base import Base
from app.models import (  # noqa: F401
    AIIncident,
    AIPolicy,
    AIRisk,
    AISystem,
    AuditLog,
    ContactSubmission,
    CorrectiveAction,
    Evidence,
    Organization,
    ProductionApproval,
    User,
)

Base.metadata.create_all(bind=engine)

# Static files
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers
from app.api import workflows as workflows_api
from app.api.audit import org_audit_router, router as audit_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.governance import router as governance_router
from app.api.health import router as health_router
from app.api.microsoft import router as microsoft_router
from app.api.users import router as users_router
from app.workflows.routers import router as workflows_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(governance_router)
app.include_router(audit_router)
app.include_router(org_audit_router)
app.include_router(documents_router)
app.include_router(microsoft_router)
app.include_router(workflows_router)
app.include_router(workflows_api.router)

# -------------------------
# Static pages
# -------------------------

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/core", include_in_schema=False)
def core_page():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/status", include_in_schema=False)
def api_status():
    return {"status": "AI Governance OS running"}

# -------------------------
# Contact
# -------------------------

from app.api.dependencies import get_db
from app.models.contact_submission import ContactSubmission


class ContactSubmissionCreate(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    message: str


@app.post("/api/contact", include_in_schema=False)
def submit_contact(payload: ContactSubmissionCreate, db: Session = Depends(get_db)):
    submission = ContactSubmission(
        name=payload.name.strip(),
        email=payload.email.strip(),
        company=(payload.company.strip() if payload.company else None),
        message=payload.message.strip(),
    )
    db.add(submission)
    db.commit()
    return {"status": "received"}

import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])

_START_TIME = time.time()
_VERSION = os.getenv("APP_VERSION", "0.1.0")


@router.get("/health", include_in_schema=False)
def health_check():
    checks: dict = {}
    ok = True

    # Database
    try:
        from app.db.session import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        ok = False

    # Redis — degraded is acceptable (in-memory fallback), but we still report it
    try:
        from app.core.rate_limiter import _redis_client
        if _redis_client is not None:
            _redis_client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "fallback"  # in-memory mode — not a hard failure
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
        # Redis has an in-memory fallback — don't mark the app as degraded

    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ok" if ok else "degraded",
            "version": _VERSION,
            "uptime_seconds": int(time.time() - _START_TIME),
            "checks": checks,
        },
    )

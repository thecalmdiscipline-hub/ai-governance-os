import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

_DEFAULT_ORIGINS = [
    "https://app.valqeron.com",
    "https://api.valqeron.com",
    "https://compliance.valqeron.com",
    "http://localhost:3000",
    "http://localhost:8000",
]


def _get_allowed_origins() -> list:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return _DEFAULT_ORIGINS


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

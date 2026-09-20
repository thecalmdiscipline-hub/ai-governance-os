import os
from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        # .env also holds SECRET_KEY, OPENAI_API_KEY, ... that are read via
        # os.getenv elsewhere; without this, importing this module fails with
        # "extra_forbidden" as soon as .env contains any other key.
        extra = "ignore"

settings = Settings()


def get_hq_organization_id() -> Optional[int]:
    """Organization id of the Valqeron HQ tenant ("tenant 0"), or None if unset.

    Read from HQ_ORGANIZATION_ID at call time (so tests and a changed .env
    are picked up without re-importing). Not used by any request path yet;
    the control-plane work (Batch E/F) builds on it. A set-but-invalid value
    raises instead of silently disabling HQ behaviour.
    """
    raw = os.getenv("HQ_ORGANIZATION_ID")
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(
            f"HQ_ORGANIZATION_ID must be a positive integer organization id, got {raw!r}"
        ) from None
    if value < 1:
        raise ValueError(
            f"HQ_ORGANIZATION_ID must be a positive integer organization id, got {raw!r}"
        )
    return value

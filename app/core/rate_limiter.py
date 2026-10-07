import logging
import os
import sys
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.models.user import User

logger = logging.getLogger(__name__)

_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_MESSAGE = "Too many login attempts. Try again later."

# Batch R (2026-10-07): /ops/* has no rate limiting at all (a deliberate gap noted in CLAUDE.md —
# every existing /ops/* route only ever used rate_limit_login on /login and /login/mfa). 60/min
# per super-admin is generous enough that normal manual use, and the portal's 10s /ops/whoami
# poll (~6/min), stay nowhere near it; it only catches a runaway client or script.
_OPS_WINDOW_SECONDS = 60
_OPS_MAX_ATTEMPTS = 60
_OPS_MESSAGE = "Too many requests. Try again later."

# ---------------------------------------------------------------------------
# In-memory fallback (single-worker only)
# ---------------------------------------------------------------------------

_memory_attempts: dict = defaultdict(list)


def _check_memory(key: str, window: int, max_attempts: int, message: str) -> None:
    now = time.time()
    _memory_attempts[key] = [t for t in _memory_attempts[key] if now - t < window]
    if len(_memory_attempts[key]) >= max_attempts:
        raise HTTPException(status_code=429, detail=message)
    _memory_attempts[key].append(now)


# ---------------------------------------------------------------------------
# Redis sliding-window check
# ---------------------------------------------------------------------------

def _check_redis(client, key: str, window: int, max_attempts: int, message: str) -> None:
    """Sliding window via sorted set. Atomic via pipeline."""
    now = time.time()
    redis_key = f"rl:{key}"
    # Unique member prevents collisions when requests arrive in the same millisecond
    member = f"{now:.6f}:{os.urandom(4).hex()}"

    pipe = client.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - window)  # drop expired entries
    pipe.zcard(redis_key)                               # count before this attempt
    pipe.zadd(redis_key, {member: now})                # record this attempt
    pipe.expire(redis_key, window)
    results = pipe.execute()

    count_before = results[1]
    if count_before >= max_attempts:
        raise HTTPException(status_code=429, detail=message)


# ---------------------------------------------------------------------------
# Redis client — initialised once at import time
# ---------------------------------------------------------------------------

_redis_client = None


def _init_redis():
    global _redis_client
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("Rate limiter: connected to Redis at %s", url)
    except Exception as exc:
        _redis_client = None
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production":
            sys.exit(
                f"FATAL: Redis is required in production but is not reachable: {exc}\n"
                "Set REDIS_URL to a reachable Redis instance, "
                "or set ENVIRONMENT=development for local use."
            )
        logger.warning(
            "Rate limiter: Redis not reachable (%s). "
            "Falling back to in-memory — not suitable for multi-worker deployments.",
            exc,
        )


_init_redis()


def _in_test_mode() -> bool:
    return (
        os.getenv("TESTING") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
    )


def _check(key: str, window: int, max_attempts: int, message: str) -> None:
    if _in_test_mode():
        return

    if _redis_client is not None:
        try:
            _check_redis(_redis_client, key, window, max_attempts, message)
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "Rate limiter: Redis check failed (%s). Falling back to in-memory for this request.",
                exc,
            )

    _check_memory(key, window, max_attempts, message)


# ---------------------------------------------------------------------------
# Public dependencies
# ---------------------------------------------------------------------------

def rate_limit_login(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check(f"login:{ip}", _LOGIN_WINDOW_SECONDS, _LOGIN_MAX_ATTEMPTS, _LOGIN_MESSAGE)


def rate_limit_ops(current_user: User) -> None:
    """Keyed by the authenticated super-admin's user id, not IP — a shared office IP must not
    throttle one admin because of another's traffic. Call only after require_ops_access's own
    authorization check passes, so an unauthorized caller never spends a slot."""
    _check(f"ops:{current_user.id}", _OPS_WINDOW_SECONDS, _OPS_MAX_ATTEMPTS, _OPS_MESSAGE)

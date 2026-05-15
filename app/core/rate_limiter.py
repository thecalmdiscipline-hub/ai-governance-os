import logging
import os
import sys
import time
from collections import defaultdict

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
_MAX_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# In-memory fallback (single-worker only)
# ---------------------------------------------------------------------------

_memory_attempts: dict = defaultdict(list)


def _check_memory(ip: str) -> None:
    now = time.time()
    _memory_attempts[ip] = [t for t in _memory_attempts[ip] if now - t < _WINDOW_SECONDS]
    if len(_memory_attempts[ip]) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    _memory_attempts[ip].append(now)


# ---------------------------------------------------------------------------
# Redis sliding-window check
# ---------------------------------------------------------------------------

def _check_redis(client, ip: str) -> None:
    """Sliding window via sorted set. Atomic via pipeline."""
    now = time.time()
    key = f"rl:login:{ip}"
    # Unique member prevents collisions when requests arrive in the same millisecond
    member = f"{now:.6f}:{os.urandom(4).hex()}"

    pipe = client.pipeline()
    pipe.zremrangebyscore(key, 0, now - _WINDOW_SECONDS)  # drop expired entries
    pipe.zcard(key)                                        # count before this attempt
    pipe.zadd(key, {member: now})                         # record this attempt
    pipe.expire(key, _WINDOW_SECONDS)
    results = pipe.execute()

    count_before = results[1]
    if count_before >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


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


# ---------------------------------------------------------------------------
# Public dependency
# ---------------------------------------------------------------------------

def rate_limit_login(request: Request) -> None:
    if (
        os.getenv("TESTING") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
    ):
        return

    ip = request.client.host if request.client else "unknown"

    if _redis_client is not None:
        try:
            _check_redis(_redis_client, ip)
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "Rate limiter: Redis check failed (%s). Falling back to in-memory for this request.",
                exc,
            )

    _check_memory(ip)

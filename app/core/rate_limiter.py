import os
import redis
from fastapi import Request, HTTPException, Depends

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def rate_limit(limit: int, window: int):
    async def limiter(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"rate:{ip}:{request.url.path}"

        current = redis_client.incr(key)

        if current == 1:
            redis_client.expire(key, window)

        if current > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests"
            )

    return limiter


# Preconfigured dependencies
rate_limit_login = rate_limit(limit=10, window=60)
rate_limit_default = rate_limit(limit=60, window=60)
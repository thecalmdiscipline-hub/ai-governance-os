from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from redis import Redis
import time

# Configure Redis client
redis_client = Redis(host='localhost', port=6379, db=0)

API_KEY_HEADER = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_HEADER)

MAX_REQUESTS_IP = 100  # Maximum requests allowed per IP
TIME_WINDOW_IP = 60  # Time window in seconds

MAX_REQUESTS_USER = 100  # Maximum requests allowed per user
TIME_WINDOW_USER = 60  # Time window in seconds

# Rate Limiting Decorator
async def rate_limiter(ip: str = Depends(get_client_ip), api_key: str = Depends(api_key_header)):  
    current_time = time.time()

    # Check IP Rate Limiting
    ip_key = f"rate_limit:ip:{ip}"
    recorded_time = redis_client.get(ip_key)

    if recorded_time:
        requests_made = int(redis_client.get(ip_key + ":count") or 0)
        if requests_made >= MAX_REQUESTS_IP:
            raise HTTPException(status_code=429, detail="Too Many Requests - IP limit exceeded")
        redis_client.incr(ip_key + ":count")
    else:
        redis_client.set(ip_key, current_time, ex=TIME_WINDOW_IP)
        redis_client.set(ip_key + ":count", 1, ex=TIME_WINDOW_IP)

    # Check User Rate Limiting
    user_key = f"rate_limit:user:{api_key}"
    recorded_time = redis_client.get(user_key)

    if recorded_time:
        requests_made = int(redis_client.get(user_key + ":count") or 0)
        if requests_made >= MAX_REQUESTS_USER:
            raise HTTPException(status_code=429, detail="Too Many Requests - User limit exceeded")
        redis_client.incr(user_key + ":count")
    else:
        redis_client.set(user_key, current_time, ex=TIME_WINDOW_USER)
        redis_client.set(user_key + ":count", 1, ex=TIME_WINDOW_USER)

    return True

# Get Client IP Address
def get_client_ip():
    import fastapi
    from starlette.requests import Request

    request: Request = fastapi.request()
    return request.client.host


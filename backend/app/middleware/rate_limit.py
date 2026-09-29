import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

# Sliding window rate limiter state
# Maps key (IP or user ID) -> list of request timestamps
_request_history = defaultdict(list)

# Limits
GENERATION_BURST_LIMIT = 5   # Max 5 generation calls per minute
WINDOW_SECONDS = 60          # 1-minute window

class GenerationRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware protecting expensive generation endpoints (SEC-013).
    Prevents denial of service, resource exhaustion, and bot abuse of
    Playwright / AI / PDF pipelines.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/")
        
        # Check if requesting generation creation
        is_generate_post = (
            request.method == "POST" and 
            (path.endswith("/generate") or path.endswith("/api/v1/generate"))
        )

        if is_generate_post:
            # Determine client identity: Authorization token hash or client IP
            auth_header = request.headers.get("Authorization", "")
            client_id = auth_header[:32] if auth_header else (
                request.client.host if request.client else "unknown"
            )

            now = time.time()
            timestamps = _request_history[client_id]

            # Prune timestamps older than window
            _request_history[client_id] = [t for t in timestamps if now - t < WINDOW_SECONDS]
            timestamps = _request_history[client_id]

            if len(timestamps) >= GENERATION_BURST_LIMIT:
                retry_after = int(WINDOW_SECONDS - (now - timestamps[0])) + 1
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": "Rate limit exceeded",
                        "message": f"Too many generation requests. Please wait {retry_after} seconds.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            # Record this attempt
            _request_history[client_id].append(now)

        return await call_next(request)

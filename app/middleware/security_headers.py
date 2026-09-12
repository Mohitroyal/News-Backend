from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Production security headers middleware for FastAPI.
    Enforces modern browser defense-in-depth protections (SEC-008):
    - X-Content-Type-Options
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - X-Frame-Options
    - Strict-Transport-Security (production / HTTPS)
    """

    def __init__(self, app, is_production: bool = True):
        super().__init__(app)
        self.is_production = is_production

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 1. Prevent MIME-sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Referrer information disclosure control
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. Restrict browser feature permissions
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(self)"
        )

        # 5. Content Security Policy (allows Swagger UI, Google Fonts, CDNs, and HTTPS assets)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        # 6. HTTP Strict Transport Security (HSTS)
        if self.is_production or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

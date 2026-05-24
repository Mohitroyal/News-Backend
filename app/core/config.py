import os
import json
from typing import List, Optional, Union
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated


def parse_cors(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str):
        if v.startswith("["):
            try:
                return json.loads(v)
            except Exception:
                pass
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Read from environment or local .env file
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "NewsCraft AI"
    ENVIRONMENT: str = "production"

    # Security — MUST be set in Render env vars
    SECRET_KEY: Optional[str] = None

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # CORS — comma-separated list or JSON array
    # e.g. CORS_ORIGINS="http://localhost:3000,https://yourapp.vercel.app"
    CORS_ORIGINS: Annotated[List[str], BeforeValidator(parse_cors)] = [
        "http://localhost:3000"
    ]

    # Optional FRONTEND_URL convenience var — appended to CORS_ORIGINS at startup
    FRONTEND_URL: Optional[str] = None

    # Database — Supabase PostgreSQL connection string
    DATABASE_URL: Optional[str] = None

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "newscraft-clippings"

    # AI Engine — Groq (gsk_...) or xAI Grok key
    GROK_API_KEY: Optional[str] = None

    # Stripe
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_PRICE_ID: Optional[str] = None
    STRIPE_ENTERPRISE_PRICE_ID: Optional[str] = None

    # Redis / Celery — optional, not required for Render free tier
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Email (optional)
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None

    def get_cors_origins(self) -> List[str]:
        """Return merged CORS list including FRONTEND_URL if set."""
        origins = list(self.CORS_ORIGINS)
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        # Always allow localhost for development convenience
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins


try:
    settings = Settings()
except Exception as e:
    import sys
    import os
    print("=== ENVIRONMENT VARIABLE VALIDATION ERROR ===", file=sys.stderr)
    print(f"Failed to validate environment variables: {e}", file=sys.stderr)
    print("\nChecking environment variables status:", file=sys.stderr)
    required_vars = [
        "SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", 
        "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GROK_API_KEY"
    ]
    for var in required_vars:
        val = os.environ.get(var)
        if val:
            masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "***"
            print(f"  {var}: PRESENT (length: {len(val)}, masked: {masked})", file=sys.stderr)
        else:
            print(f"  {var}: MISSING ❌", file=sys.stderr)
    raise e


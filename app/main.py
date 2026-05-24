import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1.api import api_router
import structlog

structlog.configure()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Environment Variable Validation Logs
    print("\n" + "="*60)
    print("=== NEWSFLOW BACKEND — ENVIRONMENT VARIABLE VALIDATION LOGS ===")
    required_vars = [
        "SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", 
        "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GROK_API_KEY"
    ]
    missing_vars = []
    for var in required_vars:
        val = getattr(settings, var, None)
        if val:
            masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "***"
            print(f"  [OK]      {var:<28}: PRESENT (length: {len(val)}, masked: {masked})")
        else:
            print(f"  [MISSING] {var:<28}: MISSING ❌")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n  [WARNING] The following required variables are missing: {', '.join(missing_vars)}")
        print("  [WARNING] Application may run with degraded functionality.")
    else:
        print("\n  [SUCCESS] All required environment variables are verified and loaded.")
    print("="*60 + "\n")

    # 2. Database Connection Success/Failure Logs
    print("\n" + "="*60)
    print("=== NEWSFLOW BACKEND — DATABASE CONNECTION CHECK ===")
    try:
        from app.db.session import engine, db_url
        from sqlalchemy import text
        print(f"  [INFO] Target database type: {'SQLite (fallback)' if 'sqlite' in db_url else 'PostgreSQL (Supabase)'}")
        print("  [INFO] Testing database connectivity...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("  [SUCCESS] Successfully executed test query on the database engine.")
            else:
                print(f"  [WARNING] Test query returned unexpected result: {result}")
    except Exception as e:
        print(f"  [ERROR] Database connection check FAILED: {e}")
    print("="*60 + "\n")

    # 3. Startup Success Log
    print("\n" + "="*60)
    print(f"=== {settings.PROJECT_NAME.upper()} STARTUP SUCCESSFUL ===")
    print("  Application startup sequence complete.")
    print("  Swagger documentation is served at /docs")
    print("="*60 + "\n")

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Uses CORS_ORIGINS env var + optional FRONTEND_URL env var for flexible config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to NewsCraft AI API",
        "docs": "/docs",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
def health_check():
    """Render health-check endpoint."""
    return {"status": "ok", "service": settings.PROJECT_NAME}


# ── Static files ──────────────────────────────────────────────────────────────
# On Render, the filesystem is ephemeral between deploys.
# Uploaded images/PDFs are stored in Supabase Storage; this local static mount
# is only used as a temporary staging area before upload.
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "clippings"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── API Router ────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

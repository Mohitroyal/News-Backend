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
    print("\n" + "="*60, flush=True)
    print("=== NEWSFLOW BACKEND — ENVIRONMENT VARIABLE VALIDATION LOGS ===", flush=True)
    required_vars = [
        "SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", 
        "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GROK_API_KEY"
    ]
    missing_vars = []
    for var in required_vars:
        val = getattr(settings, var, None)
        if val:
            masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "***"
            print(f"  [OK]      {var:<28}: PRESENT (length: {len(val)}, masked: {masked})", flush=True)
        else:
            print(f"  [MISSING] {var:<28}: MISSING ❌", flush=True)
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n  [WARNING] The following required variables are missing: {', '.join(missing_vars)}", flush=True)
        print("  [WARNING] Application may run with degraded functionality.", flush=True)
    else:
        print("\n  [SUCCESS] All required environment variables are verified and loaded.", flush=True)
    print("="*60 + "\n", flush=True)

    # 2. Database Connection Success/Failure Logs (Removed blocking check)
    print("\n" + "="*60, flush=True)
    print("=== NEWSFLOW BACKEND — DATABASE CONNECTION CHECK ===", flush=True)
    print("  [INFO] Skipping synchronous DB connect check during startup to prevent Render deployment timeouts.", flush=True)
    print("="*60 + "\n", flush=True)

    # 3. Telugu Fonts Check and Auto-Download Failsafe
    print("\n" + "="*60, flush=True)
    print("=== TELUGU FONTS AUTO-DOWNLOAD CHECK ===", flush=True)
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from download_fonts import download_fonts
        download_fonts()
        print("  [SUCCESS] Telugu fonts check and auto-download completed successfully.", flush=True)
    except Exception as fe:
        print(f"  [WARNING] Telugu fonts auto-download failed or skipped: {fe}", flush=True)
    print("="*60 + "\n", flush=True)

    # 3.5 Database Auto-Migrations Failsafe
    print("\n" + "="*60, flush=True)
    print("=== DATABASE AUTO-MIGRATIONS ===", flush=True)
    try:
        from sqlalchemy import text
        from app.db.session import engine
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE clippings ADD COLUMN IF NOT EXISTS show_inner_borders BOOLEAN DEFAULT TRUE;"))
            print("  [SUCCESS] Column show_inner_borders is present.", flush=True)
    except Exception as e:
        print(f"  [WARNING] DB auto-migration skipped or failed: {e}", flush=True)
    print("="*60 + "\n", flush=True)

    # 4. Startup Success Log
    print("\n" + "="*60, flush=True)
    print(f"=== {settings.PROJECT_NAME.upper()} STARTUP SUCCESSFUL ===", flush=True)
    print("  Application startup sequence complete.", flush=True)
    print("  Swagger documentation is served at /docs", flush=True)
    print(f"  Backend Environment: {settings.ENVIRONMENT}", flush=True)
    print(f"  Active Allowed Origins: {origins}", flush=True)
    print("  Server Startup Confirmed!", flush=True)
    print("="*60 + "\n", flush=True)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://news-front.vercel.app",
    "https://news-frount.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cors_header_to_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"ok": True}


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
    return {"status": "ok", "service": settings.PROJECT_NAME, "version": "v4_bulletproof"}


@app.get("/health/generator")
async def health_generator():
    """
    Diagnostic endpoint to verify all components for NewsCraft Generation are healthy.
    """
    # 1. Playwright Check
    playwright_status = "ok"
    try:
        from playwright.async_api import async_playwright
        from app.services.render_service import _get_chromium_executable
        async with async_playwright() as p:
            executable_path = _get_chromium_executable()
            browser = await p.chromium.launch(headless=True, executable_path=executable_path)
            await browser.close()
    except Exception as e:
        playwright_status = f"failed: {e}"

    # 2. Fonts Check
    fonts_status = "ok"
    try:
        import os
        static_fonts_dir = os.path.join(os.path.dirname(__file__), "..", "static", "fonts")
        required_fonts = [
            "NotoSansTelugu-Regular.ttf",
            "NotoSansTelugu-Bold.ttf",
            "NotoSerifTelugu-Regular.ttf",
            "NotoSerifTelugu-Bold.ttf"
        ]
        missing = [f for f in required_fonts if not os.path.exists(os.path.join(static_fonts_dir, f))]
        if missing:
            print("Fonts missing during diagnostic health check. Attempting to download...")
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from download_fonts import download_fonts
            download_fonts()
            missing = [f for f in required_fonts if not os.path.exists(os.path.join(static_fonts_dir, f))]
            if missing:
                fonts_status = f"failed: missing {', '.join(missing)}"
    except Exception as e:
        fonts_status = f"failed: {e}"

    # 3. Storage Check
    storage_status = "ok"
    try:
        from app.services.storage_service import storage_service
        storage_service.validate_storage()
    except Exception as e:
        storage_status = f"failed: {e}"

    # 4. Templates Check
    templates_status = "ok"
    try:
        from app.services.render_service import render_service
        if not render_service.env:
            templates_status = "failed: Jinja2 environment not loaded"
    except Exception as e:
        templates_status = f"failed: {e}"

    # 5. Image Processing Check
    image_processing_status = "ok"
    try:
        from PIL import Image
        import io
        img = Image.new('RGB', (100, 100), color='red')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
    except Exception as e:
        image_processing_status = f"failed: {e}"

    return {
        "playwright": playwright_status,
        "fonts": fonts_status,
        "storage": storage_status,
        "templates": templates_status,
        "image_processing": image_processing_status
    }



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

# Directly attach the generate router without prefix for /generate endpoint calls
from app.api.v1.endpoints import generate, upload
app.include_router(generate.router, prefix="/generate", tags=["generation_direct"])
app.include_router(upload.router, tags=["upload_direct"])

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

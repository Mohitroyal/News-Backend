import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.api import api_router
from app.core.config import settings
import structlog

structlog.configure()
logger = structlog.get_logger()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
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

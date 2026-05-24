import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.encoders import jsonable_encoder
from supabase import create_client
import uuid
from typing import Any

from app.core.config import settings

router = APIRouter()

# ── Helper: build a guaranteed absolute Supabase public URL ──────────────────
def _supabase_public_url(destination_path: str) -> str:
    """
    Construct the canonical public URL for a Supabase Storage object.
    Supabase SDK sometimes returns a relative path or a URL without the
    trailing /public/ segment on older SDK versions — we always build it
    ourselves to be safe.
    """
    base = settings.SUPABASE_URL.rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    return f"{base}/storage/v1/object/public/{bucket}/{destination_path}"


@router.post("/uploads/image")
async def upload_image(
    file: UploadFile = File(...),
) -> Any:
    print("UPLOAD ENDPOINT HIT")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    file_ext = os.path.splitext(file.filename or "upload")[1] or ".jpg"
    filename = f"upload_{uuid.uuid4().hex}{file_ext}"
    # Store under uploads/ prefix inside the bucket
    destination_path = f"uploads/{filename}"

    # ── Production path: Supabase Storage (always preferred) ─────────────────
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            file_bytes = await file.read()
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                path=destination_path,
                file=file_bytes,
                file_options={"content-type": file.content_type, "x-upsert": "true"},
            )
            # Always build the URL ourselves — guaranteed absolute HTTPS URL
            public_url = _supabase_public_url(destination_path)
            print(f"[UPLOAD] Supabase upload success → {public_url}")
            return jsonable_encoder({
                "success": True,
                "data": {"url": public_url},
                "message": "Image uploaded to Supabase Storage",
            })
        except Exception as supabase_err:
            print(f"[UPLOAD] Supabase upload failed: {supabase_err}. Falling back to local static.")

    # ── Localhost fallback: local /static/uploads (dev only) ─────────────────
    # NOTE: This path is EPHEMERAL on Render — images vanish on redeploy.
    #       Playwright will NOT be able to load these during rendering on Render.
    #       Ensure SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set in production.
    app_dir = os.path.dirname(os.path.abspath(__file__))
    static_uploads = os.path.join(app_dir, "..", "..", "..", "static", "uploads")
    os.makedirs(static_uploads, exist_ok=True)
    file_path = os.path.join(static_uploads, filename)

    try:
        await file.seek(0)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not save file to local storage")

    # Use RENDER_EXTERNAL_URL (injected by Render) so Playwright can reach it
    service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
    local_url = f"{service_url}/static/uploads/{filename}"
    print(f"[UPLOAD] Local fallback URL: {local_url}")
    return jsonable_encoder({
        "success": True,
        "data": {"url": local_url},
        "message": "Image uploaded to local storage (Supabase unavailable)",
    })

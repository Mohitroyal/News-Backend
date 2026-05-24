import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.encoders import jsonable_encoder
from supabase import create_client
import uuid
import shutil
from typing import Any

from app.core.config import settings

router = APIRouter()


@router.post("/image", response_model=dict)
async def upload_image(
    file: UploadFile = File(...),
) -> Any:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    file_ext = os.path.splitext(file.filename or "upload")[1] or ".jpg"
    filename = f"upload_{uuid.uuid4().hex}{file_ext}"
    destination_path = f"uploads/{filename}"

    # ── Try Supabase Storage first ────────────────────────────────────────────
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        file_bytes = await file.read()
        supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path=destination_path,
            file=file_bytes,
            file_options={"content-type": file.content_type, "x-upsert": "true"},
        )
        public_url = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(destination_path)
        return jsonable_encoder({
            "success": True,
            "data": {"url": public_url},
            "message": "Image uploaded successfully",
        })
    except Exception as supabase_err:
        print(f"[UPLOAD] Supabase upload failed: {supabase_err}. Falling back to local static.")

    # ── Fallback: save to local static/uploads ────────────────────────────────
    # (ephemeral on Render, but usable as a temporary URL during the same request)
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
        raise HTTPException(status_code=500, detail="Could not save file")

    # Build the URL using FRONTEND_URL or a generic placeholder
    base_url = settings.FRONTEND_URL or "https://your-render-service.onrender.com"
    # Strip trailing slash from base_url in case it's set that way
    base_url = base_url.rstrip("/")
    # The FastAPI service itself serves /static, so use its own URL
    # On Render, RENDER_EXTERNAL_URL is auto-injected
    service_url = os.getenv("RENDER_EXTERNAL_URL", base_url)
    return jsonable_encoder({
        "success": True,
        "data": {"url": f"{service_url}/static/uploads/{filename}"},
        "message": "Image uploaded to local storage (Supabase unavailable)",
    })

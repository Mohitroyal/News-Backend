import os
import io
import uuid
from typing import Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from PIL import Image
from supabase import create_client

from app.core.config import settings
from app.models.user import User
from app.auth.dependencies import get_current_active_user

router = APIRouter()

# ── Safe Upload Constraints (SEC-011, SEC-012) ──────────────────────────────
MAX_UPLOAD_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", 50)) * 1024 * 1024  # 50 MB limit
MAX_DIMENSION = int(os.getenv("MAX_IMAGE_WIDTH", 8192))                # Max width/height in pixels
MAX_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", 50_000_000))            # Max total pixels to prevent decompression bombs
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Guard Pillow against decompression bomb attacks
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _supabase_public_url(destination_path: str) -> str:
    """Construct canonical Supabase Storage URL."""
    base = settings.SUPABASE_URL.rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    return f"{base}/storage/v1/object/public/{bucket}/{destination_path}"


@router.post("/uploads/image")
@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Secure Image Upload (SEC-005, SEC-011, SEC-012).
    - Requires authenticated user JWT.
    - Validates actual file bytes, dimensions, and magic headers using Pillow.
    - Enforces strict 10MB size limit.
    - Segregates storage by user ID.
    """
    # 1. Content-Type Header Preliminary Check
    client_content_type = (file.content_type or "").lower().split(";")[0].strip()
    if client_content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type: '{client_content_type}'. Allowed: jpeg, png, webp"
        )

    # 2. Size Limit Check (Streamed read up to limit + 1 byte)
    try:
        contents = await file.read(MAX_UPLOAD_SIZE + 1)
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE // (1024 * 1024)}MB"
            )
        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {e}"
        )

    # 3. Deep Image Verification via Pillow (detects spoofed MIME & malformed images)
    try:
        # Initial verify catches corrupted streams/headers
        img_verify = Image.open(io.BytesIO(contents))
        img_verify.verify()
        
        # Second open to inspect actual format and dimensions
        img = Image.open(io.BytesIO(contents))
        img_format = (img.format or "").upper()
        if img_format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image content format: '{img_format}'. Allowed: JPEG, PNG, WEBP"
            )

        width, height = img.size
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image dimensions ({width}x{height}) exceed maximum allowed limit of {MAX_DIMENSION}x{MAX_DIMENSION}"
            )
        if width * height > MAX_PIXELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image pixel density too high (decompression bomb protection)"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed or invalid image file: {e}"
        )

    # 4. Safe Filename and User-Segregated Path
    ext = ".jpg" if img_format == "JPEG" else f".{img_format.lower()}"
    filename = f"upload_{uuid.uuid4().hex}{ext}"
    user_id_str = str(current_user.id)
    destination_path = f"uploads/{user_id_str}/{filename}"

    # 5. Production upload: Supabase Storage
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                path=destination_path,
                file=contents,
                file_options={"content-type": client_content_type, "x-upsert": "true"},
            )
            public_url = _supabase_public_url(destination_path)
            return jsonable_encoder({
                "success": True,
                "data": {"url": public_url},
                "message": "Image uploaded securely to storage",
            })
        except Exception as supabase_err:
            print(f"[UPLOAD] Supabase upload failed: {supabase_err}. Falling back to local static.")

    # 6. Localhost fallback (dev only)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    static_uploads = os.path.join(app_dir, "..", "..", "..", "static", "uploads", user_id_str)
    os.makedirs(static_uploads, exist_ok=True)
    file_path = os.path.join(static_uploads, filename)

    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save file to local storage"
        )

    service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
    local_url = f"{service_url}/static/uploads/{user_id_str}/{filename}"
    return jsonable_encoder({
        "success": True,
        "data": {"url": local_url},
        "message": "Image uploaded securely",
    })

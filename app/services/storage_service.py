import os
import shutil
from supabase import create_client, Client
from app.core.config import settings


def _supabase_public_url(destination_path: str) -> str:
    """
    Always build a guaranteed absolute HTTPS Supabase Storage URL.
    Pattern: https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
    This is the only URL format that Playwright can load externally.
    """
    base = settings.SUPABASE_URL.rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    return f"{base}/storage/v1/object/public/{bucket}/{destination_path}"


def _rewrite_to_absolute(url: str) -> str:
    """
    If a stored image URL is a relative /static/uploads/... path (from a prior
    local-fallback upload), rewrite it to a Supabase absolute URL if Supabase
    is configured, so Playwright can load it.
    Falls back to prefixing with RENDER_EXTERNAL_URL if Supabase is not set.
    """
    if not url:
        return url

    # Already absolute — nothing to do
    if url.startswith("http://") or url.startswith("https://"):
        return url

    # Relative path — make it absolute
    if settings.SUPABASE_URL:
        # Try to map /static/uploads/<filename> → Supabase uploads/<filename>
        if "/static/uploads/" in url:
            filename = url.split("/static/uploads/")[-1]
            return _supabase_public_url(f"uploads/{filename}")

    service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
    return f"{service_url}{url}"


class StorageService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket = settings.SUPABASE_STORAGE_BUCKET

    def upload_file(self, file_path: str, destination_path: str) -> str:
        """
        Upload a file to Supabase Storage and return its guaranteed-absolute public URL.
        Falls back to local static path (dev only) if Supabase is unavailable.
        """
        try:
            with open(file_path, "rb") as f:
                self.supabase.storage.from_(self.bucket).upload(
                    path=destination_path,
                    file=f,
                    file_options={"x-upsert": "true"},
                )
            # Always build URL ourselves — SDK version-agnostic
            url = _supabase_public_url(destination_path)
            print(f"[STORAGE] Uploaded to Supabase → {url}")
            return url
        except Exception as e:
            print(f"[STORAGE] Supabase upload failed: {e}. Falling back to local storage.")
            local_dest = os.path.join(
                os.path.dirname(__file__), "..", "..", "static", destination_path
            )
            os.makedirs(os.path.dirname(local_dest), exist_ok=True)
            shutil.copy(file_path, local_dest)
            service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
            fallback_url = f"{service_url}/static/{destination_path}"
            print(f"[STORAGE] Fallback local URL → {fallback_url}")
            return fallback_url

    def delete_file(self, path: str):
        try:
            self.supabase.storage.from_(self.bucket).remove([path])
        except Exception:
            local_dest = os.path.join(
                os.path.dirname(__file__), "..", "..", "static", path
            )
            if os.path.exists(local_dest):
                os.remove(local_dest)


storage_service = StorageService()

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
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            self.supabase: Client = create_client(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
            )
        else:
            self.supabase = None
        self.bucket = settings.SUPABASE_STORAGE_BUCKET

    def validate_storage(self):
        """
        Verifies Supabase connection, bucket existence, and permissions.
        Throws exception if unhealthy.
        """
        if not self.supabase:
            raise Exception("Supabase credentials missing from configuration")
        try:
            self.supabase.storage.get_bucket(self.bucket)
        except Exception as e:
            raise Exception(f"Supabase connection/permissions failed for bucket '{self.bucket}': {e}")

    def upload_file(self, file_path: str, destination_path: str, content_type: str | None = None) -> str:
        """
        Upload a file to Supabase Storage and return its guaranteed-absolute public URL.
        Raises an exception if the upload fails to ensure silent failures do not happen.
        """
        self.validate_storage()
        if not content_type:
            if destination_path.endswith(".png"):
                content_type = "image/png"
            elif destination_path.endswith(".pdf"):
                content_type = "application/pdf"
            else:
                content_type = "application/octet-stream"
        try:
            with open(file_path, "rb") as f:
                self.supabase.storage.from_(self.bucket).upload(
                    path=destination_path,
                    file=f,
                    file_options={
                        "x-upsert": "true",
                        "content-type": content_type,
                        "cache-control": "public, max-age=3600"
                    },
                )
            # Always build URL ourselves — SDK version-agnostic
            url = _supabase_public_url(destination_path)
            print(f"[STORAGE] Uploaded to Supabase → {url}")
            return url
        except Exception as e:
            print(f"[STORAGE] Supabase upload failed: {e}")
            raise Exception(f"Supabase upload failed: {e}")

    def delete_file(self, path: str):
        try:
            self.supabase.storage.from_(self.bucket).remove([path])
        except Exception as e:
            print(f"[STORAGE] Supabase delete warning: {e}")


storage_service = StorageService()

import os
import shutil
from supabase import create_client, Client
from app.core.config import settings


class StorageService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket = settings.SUPABASE_STORAGE_BUCKET

    def upload_file(self, file_path: str, destination_path: str) -> str:
        """Uploads a file to Supabase Storage and returns its public URL.
        Falls back to local static path if Supabase is unavailable.
        """
        try:
            with open(file_path, "rb") as f:
                self.supabase.storage.from_(self.bucket).upload(
                    path=destination_path,
                    file=f,
                    file_options={"x-upsert": "true"},
                )
            url = self.supabase.storage.from_(self.bucket).get_public_url(destination_path)
            return url
        except Exception as e:
            print(f"[STORAGE] Supabase upload failed: {e}. Falling back to local storage.")
            local_dest = os.path.join(
                os.path.dirname(__file__), "..", "..", "static", destination_path
            )
            os.makedirs(os.path.dirname(local_dest), exist_ok=True)
            shutil.copy(file_path, local_dest)
            # Use RENDER_EXTERNAL_URL if available, otherwise a generic placeholder
            service_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-service.onrender.com")
            return f"{service_url}/static/{destination_path}"

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

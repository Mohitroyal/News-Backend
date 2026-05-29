import io
import urllib.request
from PIL import Image

class ImageService:
    @staticmethod
    def process_and_resize(image_url: str, max_width: int = 1200, max_height: int = 1200) -> str:
        """
        Downloads an image from a URL, resizes it using Pillow (fit='inside' equivalent),
        and returns the raw bytes or a local file path.
        For simplicity, we will save to a temp file and return the path.
        If it fails, it gracefully falls back to the original URL so generation doesn't crash.
        """
        if not image_url or not image_url.startswith("http"):
            return image_url
            
        try:
            req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                img_data = response.read()
                
            img = Image.open(io.BytesIO(img_data))
            
            # Auto-resize preserving aspect ratio (like sharp fit='inside')
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Save to temp file
                import uuid, os
                temp_filename = f"temp_resized_{uuid.uuid4().hex}.{img.format.lower() if img.format else 'jpg'}"
                img.save(temp_filename, quality=90)
                
                # We need to return a path that Playwright can access
                # For local files, playwright can load file:// or just absolute path if served by frontend,
                # but wait! Playwright loads `html` with `<img src="url">`.
                # If we return a local temp file, it won't be accessible unless we upload it back to Supabase.
                # Since we have `storage_service`, let's upload it!
                from app.services.storage_service import storage_service
                
                # Upload resized image back to supabase (as a temp image or override)
                new_url = storage_service.upload_file(temp_filename, f"clippings/resized_{uuid.uuid4().hex}.jpg")
                os.remove(temp_filename)
                
                return new_url
                
            return image_url
        except Exception as e:
            print(f"[WARNING] Image processing failed: {e}. Falling back to original URL.")
            return image_url

image_service = ImageService()

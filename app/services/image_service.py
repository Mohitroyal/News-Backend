import io
import urllib.request
import os
import uuid
import gc
from PIL import Image, ImageOps
import logging
import psutil

logger = logging.getLogger(__name__)

class ImageService:
    @staticmethod
    def _log_memory(stage: str):
        """Log current memory usage for debugging."""
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        logger.info(f"[MEMORY] {stage}: {mem_mb:.2f} MB")

    @staticmethod
    def process_and_resize(image_url: str, max_width: int = 1600, max_height: int = 1600) -> str:
        """Download, resize, possibly convert, and upload an image.

        - Max dimensions 1600x1600, preserving aspect ratio.
        - WEBP quality 75.
        - Dispose image objects promptly and trigger GC.
        """
        if not image_url or not image_url.startswith("http"):
            logger.info(f"[ImageService] Skipping non‑HTTP URL: {image_url}")
            return image_url

        try:
            logger.info(f"[ImageService] Downloading image: {image_url}")
            req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                img_data = response.read()

            img = Image.open(io.BytesIO(img_data))
            orig_format = img.format.upper() if img.format else "WEBP"
            orig_width, orig_height = img.size
            logger.info(f"[ImageService] Original size: {orig_width}x{orig_height}, format: {orig_format}")

            # Auto‑orient via EXIF
            try:
                img = ImageOps.exif_transpose(img)
            except Exception as exif_err:
                logger.warning(f"[ImageService] EXIF transpose failed: {exif_err}")

            # Determine scaling factor
            scale_factor = min(max_width / img.width, max_height / img.height)
            if scale_factor > 1.0:
                scale_factor = 1.0
            if scale_factor < 1.0:
                new_w = int(round(img.width * scale_factor))
                new_h = int(round(img.height * scale_factor))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                logger.info(f"[ImageService] Resized to: {new_w}x{new_h}")
            else:
                logger.info("[ImageService] Image within size limits, no resize performed")

            # Always convert to WEBP
            final_format = "WEBP"
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            ext = "webp"
            temp_filename = f"temp_resized_{uuid.uuid4().hex}.{ext}"
            img.save(temp_filename, format=final_format, quality=75)
            img.close()
            gc.collect()
            logger.info(f"[ImageService] Saved temporary file: {temp_filename}")

            # Upload to Supabase (or storage service)
            from app.services.storage_service import storage_service
            new_url = storage_service.upload_file(temp_filename, f"clippings/resized_{uuid.uuid4().hex}.{ext}")

            # Cleanup
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                logger.info(f"[ImageService] Deleted temporary file: {temp_filename}")

            # Log memory after processing
            ImageService._log_memory("Image Processing Completed")
            return new_url

        except Exception as e:
            logger.exception(f"[ImageService] Failed to process image: {e}")
            raise

# Export a singleton instance for import convenience
image_service = ImageService()


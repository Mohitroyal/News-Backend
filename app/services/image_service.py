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
    def process_and_resize(image_url: str, max_width: int = 800, max_height: int = 800) -> str:
        """Download, resize, possibly convert, and upload an image.

        - Max dimensions 800x800, preserving aspect ratio.
        - JPEG quality 80.
        - Convert large PNGs to JPEG to save space.
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
            orig_format = img.format.upper() if img.format else "JPEG"
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

            # Decide final format – convert PNG to JPEG if image is large
            final_format = orig_format
            if orig_format == "PNG" and (img.width > max_width or img.height > max_height):
                final_format = "JPEG"
                logger.info("[ImageService] Converting PNG to JPEG to reduce size")

            # Ensure RGB mode for JPEG
            if final_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
                img = background
            elif img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            ext = final_format.lower()
            if ext == "jpeg":
                ext = "jpg"
            temp_filename = f"temp_resized_{uuid.uuid4().hex}.{ext}"
            img.save(temp_filename, format=final_format, quality=80)
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


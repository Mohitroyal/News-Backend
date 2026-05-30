import io
import urllib.request
import os
import uuid
from PIL import Image, ImageOps

class ImageService:
    @staticmethod
    def process_and_resize(image_url: str, max_width: int = 1000, max_height: int = 900) -> str:
        """
        Downloads an image from a URL, validates format, applies EXIF auto-orientation,
        resizes it proportionally based on the requested scale algorithm to fit container,
        and uploads it back.
        """
        if not image_url or not image_url.startswith("http"):
            print(f"[3] Image Resize: SUCCESS (Skipping non-HTTP URL: {image_url})")
            return image_url
            
        try:
            print(f"[3] Image Resize: Started processing URL: {image_url}")
            req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                img_data = response.read()
                
            img = Image.open(io.BytesIO(img_data))
            
            # Read metadata and validate/convert format
            img_format = img.format.upper() if img.format else "JPEG"
            
            # If the format is not standard, we convert it rather than rejecting it
            if img_format not in ["JPEG", "JPG", "PNG", "WEBP"]:
                print(f"[3] Image Resize: Non-standard format '{img_format}' detected. Converting...")
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img_format = "PNG"
                else:
                    img_format = "JPEG"
            
            orig_width, orig_height = img.size
            print(f"[3] Image Resize: Metadata read successfully - Format: {img_format}, Dimensions: {orig_width}x{orig_height}")
            
            # Auto-orient using EXIF (critical for mobile screenshots and WhatsApp images)
            try:
                img = ImageOps.exif_transpose(img)
                trans_width, trans_height = img.size
                if trans_width != orig_width or trans_height != orig_height:
                    print(f"[3] Image Resize: Image auto-oriented via EXIF (New Dimensions: {trans_width}x{trans_height})")
            except Exception as exif_err:
                print(f"[3] Image Resize: EXIF rotation warning: {exif_err}")

            width, height = img.size
            
            # Algorithm:
            # scaleFactor = min(containerWidth / imageWidth, containerHeight / imageHeight)
            # newWidth = imageWidth * scaleFactor
            # newHeight = imageHeight * scaleFactor
            scale_factor = min(max_width / width, max_height / height)
            
            # If image is very small: Leave original size or scale slightly.
            # So if scale_factor >= 1.0, we keep the original size (scale_factor = 1.0)
            if scale_factor > 1.0:
                scale_factor = 1.0
                
            if scale_factor < 1.0:
                new_width = int(round(width * scale_factor))
                new_height = int(round(height * scale_factor))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"[3] Image Resize: Resized proportionally from {width}x{height} to {new_width}x{new_height} using scaleFactor {scale_factor:.4f}")
            else:
                print(f"[3] Image Resize: Kept original dimensions {width}x{height} (within limits)")
                
            # Ensure mode is appropriate for saving
            if img_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
                img = background
            elif img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
                
            # Save to temp file
            ext = img_format.lower()
            if ext == "jpeg":
                ext = "jpg"
            temp_filename = f"temp_resized_{uuid.uuid4().hex}.{ext}"
            img.save(temp_filename, format=img_format, quality=90)
            
            # Upload back to Supabase
            from app.services.storage_service import storage_service
            new_url = storage_service.upload_file(temp_filename, f"clippings/resized_{uuid.uuid4().hex}.{ext}")
            
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            print(f"[3] Image Resize: SUCCESS (Resized image URL: {new_url})")
            return new_url
            
        except Exception as e:
            print(f"[3] Image Resize: WARNING/FAILED ({e}). Falling back to original URL.")
            return image_url

image_service = ImageService()


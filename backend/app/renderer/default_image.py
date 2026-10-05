import os
import base64

_cached_data_url = None

def get_default_image_data_url() -> str:
    """Returns the base64 data URL for the default icon image when no image is provided."""
    global _cached_data_url
    if _cached_data_url is None:
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "assets", "up-logo.jpeg"),
            r"C:\Users\MOHIT\Desktop\newscraft-mobile\SPOT NEWS NEW (2)\newscraft-mobile (1)\newscraft-mobile\assets\up-logo.jpeg",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        ext = p.split('.')[-1].lower()
                        mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
                        _cached_data_url = f"data:{mime};base64,{b64}"
                        break
                except Exception:
                    continue
        if _cached_data_url is None:
            _cached_data_url = ""
    return _cached_data_url

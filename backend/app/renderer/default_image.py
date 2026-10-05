import os
import base64

_cached_data_url = None

def get_default_image_data_url() -> str:
    """Returns the base64 data URL for the default icon image when no image is provided."""
    global _cached_data_url
    if _cached_data_url is None:
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "assets", "default_icon.png"),
            os.path.join(os.path.dirname(__file__), "..", "..", "static", "default_icon.png"),
            r"C:\Users\MOHIT\Desktop\newscraft-mobile\SPOT NEWS NEW (2)\newscraft-mobile (1)\newscraft-mobile\assets\icon.png",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        _cached_data_url = f"data:image/png;base64,{b64}"
                        break
                except Exception:
                    continue
        if _cached_data_url is None:
            _cached_data_url = ""
    return _cached_data_url

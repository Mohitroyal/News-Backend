import os

print("[BUILD] Verifying fonts in app/static/fonts...")
fonts_dir = os.path.join(os.path.dirname(__file__), "app", "static", "fonts")
if os.path.exists(fonts_dir):
    font_files = [f for f in os.listdir(fonts_dir) if f.endswith(".ttf")]
    print(f"[BUILD] Found {len(font_files)} font files in {fonts_dir}.")
else:
    os.makedirs(fonts_dir, exist_ok=True)
    print(f"[BUILD] Created fonts directory at {fonts_dir}.")

print("[BUILD] Font verification complete.")

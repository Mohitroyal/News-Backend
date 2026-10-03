import os
import urllib.request

def download_fonts():
    static_fonts_dir = os.path.join(os.path.dirname(__file__), "static", "fonts")
    os.makedirs(static_fonts_dir, exist_ok=True)

    # ── Noto Sans / Serif fonts for all supported Indic scripts ───────────────
    # Source: Google Fonts Noto project on GitHub (hinted TTF builds)
    BASE = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf"

    fonts = {
        # ── Telugu ────────────────────────────────────────────────────────────
        "NotoSansTelugu-Regular.ttf":  f"{BASE}/NotoSansTelugu/NotoSansTelugu-Regular.ttf",
        "NotoSansTelugu-Bold.ttf":     f"{BASE}/NotoSansTelugu/NotoSansTelugu-Bold.ttf",
        "NotoSerifTelugu-Regular.ttf": f"{BASE}/NotoSerifTelugu/NotoSerifTelugu-Regular.ttf",
        "NotoSerifTelugu-Bold.ttf":    f"{BASE}/NotoSerifTelugu/NotoSerifTelugu-Bold.ttf",

        # ── Hindi / Devanagari (covers Hindi, Marathi) ─────────────────────
        "NotoSansDevanagari-Regular.ttf":  f"{BASE}/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf",
        "NotoSansDevanagari-Bold.ttf":     f"{BASE}/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf",
        "NotoSerifDevanagari-Regular.ttf": f"{BASE}/NotoSerifDevanagari/NotoSerifDevanagari-Regular.ttf",
        "NotoSerifDevanagari-Bold.ttf":    f"{BASE}/NotoSerifDevanagari/NotoSerifDevanagari-Bold.ttf",

        # ── Kannada ────────────────────────────────────────────────────────────
        "NotoSansKannada-Regular.ttf":  f"{BASE}/NotoSansKannada/NotoSansKannada-Regular.ttf",
        "NotoSansKannada-Bold.ttf":     f"{BASE}/NotoSansKannada/NotoSansKannada-Bold.ttf",
        "NotoSerifKannada-Regular.ttf": f"{BASE}/NotoSerifKannada/NotoSerifKannada-Regular.ttf",
        "NotoSerifKannada-Bold.ttf":    f"{BASE}/NotoSerifKannada/NotoSerifKannada-Bold.ttf",

        # ── Malayalam ─────────────────────────────────────────────────────────
        "NotoSansMalayalam-Regular.ttf":  f"{BASE}/NotoSansMalayalam/NotoSansMalayalam-Regular.ttf",
        "NotoSansMalayalam-Bold.ttf":     f"{BASE}/NotoSansMalayalam/NotoSansMalayalam-Bold.ttf",
        "NotoSerifMalayalam-Regular.ttf": f"{BASE}/NotoSerifMalayalam/NotoSerifMalayalam-Regular.ttf",
        "NotoSerifMalayalam-Bold.ttf":    f"{BASE}/NotoSerifMalayalam/NotoSerifMalayalam-Bold.ttf",

        # ── Tamil ─────────────────────────────────────────────────────────────
        "NotoSansTamil-Regular.ttf":  f"{BASE}/NotoSansTamil/NotoSansTamil-Regular.ttf",
        "NotoSansTamil-Bold.ttf":     f"{BASE}/NotoSansTamil/NotoSansTamil-Bold.ttf",
        "NotoSerifTamil-Regular.ttf": f"{BASE}/NotoSerifTamil/NotoSerifTamil-Regular.ttf",
        "NotoSerifTamil-Bold.ttf":    f"{BASE}/NotoSerifTamil/NotoSerifTamil-Bold.ttf",

        # ── Bengali ────────────────────────────────────────────────────────────
        "NotoSansBengali-Regular.ttf":  f"{BASE}/NotoSansBengali/NotoSansBengali-Regular.ttf",
        "NotoSansBengali-Bold.ttf":     f"{BASE}/NotoSansBengali/NotoSansBengali-Bold.ttf",
        "NotoSerifBengali-Regular.ttf": f"{BASE}/NotoSerifBengali/NotoSerifBengali-Regular.ttf",
        "NotoSerifBengali-Bold.ttf":    f"{BASE}/NotoSerifBengali/NotoSerifBengali-Bold.ttf",

        # ── Gujarati ───────────────────────────────────────────────────────────
        "NotoSansGujarati-Regular.ttf":  f"{BASE}/NotoSansGujarati/NotoSansGujarati-Regular.ttf",
        "NotoSansGujarati-Bold.ttf":     f"{BASE}/NotoSansGujarati/NotoSansGujarati-Bold.ttf",
        "NotoSerifGujarati-Regular.ttf": f"{BASE}/NotoSerifGujarati/NotoSerifGujarati-Regular.ttf",
        "NotoSerifGujarati-Bold.ttf":    f"{BASE}/NotoSerifGujarati/NotoSerifGujarati-Bold.ttf",

        # ── Punjabi / Gurmukhi ─────────────────────────────────────────────────
        "NotoSansGurmukhi-Regular.ttf":  f"{BASE}/NotoSansGurmukhi/NotoSansGurmukhi-Regular.ttf",
        "NotoSansGurmukhi-Bold.ttf":     f"{BASE}/NotoSansGurmukhi/NotoSansGurmukhi-Bold.ttf",
        "NotoSerifGurmukhi-Regular.ttf": f"{BASE}/NotoSerifGurmukhi/NotoSerifGurmukhi-Regular.ttf",
        "NotoSerifGurmukhi-Bold.ttf":    f"{BASE}/NotoSerifGurmukhi/NotoSerifGurmukhi-Bold.ttf",

        # ── Odia ───────────────────────────────────────────────────────────────
        "NotoSansOriya-Regular.ttf":  f"{BASE}/NotoSansOriya/NotoSansOriya-Regular.ttf",
        "NotoSansOriya-Bold.ttf":     f"{BASE}/NotoSansOriya/NotoSansOriya-Bold.ttf",
        "NotoSerifOriya-Regular.ttf": f"{BASE}/NotoSerifOriya/NotoSerifOriya-Regular.ttf",
        "NotoSerifOriya-Bold.ttf":    f"{BASE}/NotoSerifOriya/NotoSerifOriya-Bold.ttf",
    }

    success = 0
    skipped = 0
    errors = 0

    for filename, url in fonts.items():
        dest = os.path.join(static_fonts_dir, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            print(f"[FONT] SKIP  {filename} (already exists, {os.path.getsize(dest)//1024} KB)")
            skipped += 1
            continue
        print(f"[FONT] Downloading {filename} ...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as response, open(dest, 'wb') as out_file:
                data = response.read()
                out_file.write(data)
            print(f"[FONT] OK    {filename} ({len(data)//1024} KB)")
            success += 1
        except Exception as e:
            print(f"[FONT] ERROR {filename}: {e}")
            errors += 1

    print(f"\n[FONT] Download complete: {success} downloaded, {skipped} skipped, {errors} errors")
    print(f"[FONT] Fonts stored at: {static_fonts_dir}")

if __name__ == "__main__":
    download_fonts()

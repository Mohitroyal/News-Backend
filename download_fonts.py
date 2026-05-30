import os
import urllib.request

def download_fonts():
    static_fonts_dir = os.path.join(os.path.dirname(__file__), "static", "fonts")
    os.makedirs(static_fonts_dir, exist_ok=True)
    
    fonts = {
        "NotoSansTelugu-Regular.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTelugu/NotoSansTelugu-Regular.ttf",
        "NotoSansTelugu-Bold.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTelugu/NotoSansTelugu-Bold.ttf",
        "NotoSerifTelugu-Regular.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSerifTelugu/NotoSerifTelugu-Regular.ttf",
        "NotoSerifTelugu-Bold.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSerifTelugu/NotoSerifTelugu-Bold.ttf"
    }
    
    for filename, url in fonts.items():
        dest = os.path.join(static_fonts_dir, filename)
        if not os.path.exists(dest):
            print(f"Downloading {filename} from {url}...")
            try:
                # Add headers to avoid bot detection
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response, open(dest, 'wb') as out_file:
                    out_file.write(response.read())
                print(f"Successfully downloaded {filename} to {dest}")
            except Exception as e:
                print(f"Error downloading {filename}: {e}")
        else:
            print(f"{filename} already exists at {dest}")

if __name__ == "__main__":
    download_fonts()

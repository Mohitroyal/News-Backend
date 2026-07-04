import os
import glob
import logging
import sys
import gc
import psutil
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import asyncio
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_peak_memory() -> float:
    """Return peak memory usage (max RSS) in MB."""
    if sys.platform != 'win32':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    else:
        try:
            process = psutil.Process(os.getpid())
            return getattr(process.memory_info(), 'peak_wset', 0) / (1024 * 1024)
        except Exception:
            return 0.0


def _log_memory(stage: str):
    """Log current and peak memory usage in MB."""
    try:
        process = psutil.Process(os.getpid())
        current_mem = process.memory_info().rss / (1024 * 1024)
        peak_mem = _get_peak_memory()
        print(f"[MEMORY] {stage} - Current RSS: {current_mem:.2f} MB | Peak RSS: {peak_mem:.2f} MB")
        sys.stdout.flush()
        if current_mem > 450:
            print("[MEMORY WARNING] Memory usage is critically high! Approaching Render Free limit.")
            sys.stdout.flush()
            gc.collect()
    except Exception as e:
        print(f"[MEMORY LOG ERROR] Failed to log memory: {e}")
        sys.stdout.flush()


def _get_chromium_executable() -> str | None:
    """
    Locate the Chromium executable installed by Playwright.

    On Render the browser cache is stored at PLAYWRIGHT_BROWSERS_PATH which is
    set to /opt/render/project/.playwright so it survives between build and
    runtime containers.  We glob for the real chrome binary rather than
    relying on Playwright's internal path resolution, which breaks when the
    env-var path differs from the compile-time default.

    Returns None on localhost (Playwright will use its own default path).
    """
    browsers_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        return None  # Local dev — let Playwright find it automatically

    patterns = [
        os.path.join(browsers_path, "chromium-*/chrome-linux/chrome"),
        os.path.join(browsers_path, "chromium-*/chrome-linux/chromium"),  # fallback name
        os.path.join(browsers_path, "chromium-*/chrome"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            print(f"[PLAYWRIGHT] Using Chromium at: {matches[0]}")
            return matches[0]

    print(f"[PLAYWRIGHT] WARNING: No Chromium found under {browsers_path}. "
          "Falling back to Playwright default path.")
    return None


class RenderService:
    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), "..", "renderer", "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir))
        # Prevent concurrent Chromium instances on a 512MB RAM free tier
        self.semaphore = asyncio.Semaphore(1)

        # Build the static logo base URL from the running service URL
        # On Render: RENDER_EXTERNAL_URL = "https://newsflow-backend.onrender.com"
        service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
        self._logo_base = f"{service_url}/static/logos"

    async def render_html(self, data: Dict[str, Any], template_name: str = "classic.html") -> str:
        """Renders the newspaper template with user data."""
        # 1. Headline safety fallback
        if not data.get("headline"):
            data["headline"] = "NEWSFLASH: Special Report"

        # 2. Article safety fallback (check sections, article_content, content)
        if isinstance(data.get("sections"), str):
            data["sections"] = [data["sections"]]

        if not data.get("sections") or len(data.get("sections", [])) == 0:
            if data.get("article_content"):
                data["sections"] = [data["article_content"]] if isinstance(data.get("article_content"), str) else data.get("article_content")
            elif data.get("content"):
                data["sections"] = [data["content"]] if isinstance(data.get("content"), str) else data.get("content")
            else:
                data["sections"] = ["No article content was provided for this clipping. This is a fallback placeholder to ensure the template layout is preserved."]

        # 2b. Merge short sections to ensure tight newspaper density (no 1-line paragraphs)
        if isinstance(data.get("sections"), list) and len(data["sections"]) > 1:
            merged_sections = []
            current_section = ""
            for sec in data["sections"]:
                if current_section:
                    current_section += " " + sec
                else:
                    current_section = sec
                
                # Maintain dense newspaper blocks (min ~450 chars to ensure ~8 lines)
                if len(current_section) > 450:
                    merged_sections.append(current_section)
                    current_section = ""
            if current_section:
                if merged_sections:
                    merged_sections[-1] += " " + current_section
                else:
                    merged_sections.append(current_section)
            data["sections"] = merged_sections

        # 3. Image safety fallback
        if not data.get("image_url") and not data.get("image_urls"):
            fallback_img = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"
            data["image_url"] = fallback_img
            data["image_urls"] = [fallback_img]
        elif data.get("image_urls") and not data.get("image_url"):
            data["image_url"] = data["image_urls"][0]
        elif data.get("image_url") and not data.get("image_urls"):
            data["image_urls"] = [data["image_url"]]

        # 4. Logo/template safety fallback
        template_key = template_name.replace(".html", "")
        if not data.get("logo_id"):
            data["logo_id"] = template_key or "classic"

        # Inject service_url absolutely for loading local assets (like local fonts via @font-face)
        service_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
        data["service_url"] = service_url

        branding = {
            "bharath_reporter": {
                "primary_color": "#15a850",
                "accent_color": "#f28e1c",
                "publication_name": "Bharath Reporter",
                "logo_url": f"{self._logo_base}/bharath_reporter.svg",
            },
            "rti_express": {
                "primary_color": "#1d70b8",
                "accent_color": "#1d70b8",
                "publication_name": "RTI Express",
                "logo_url": f"{self._logo_base}/rti_express.svg",
            },
            "national_news": {
                "primary_color": "#761c9e",
                "accent_color": "#cc2424",
                "publication_name": "National News Reporter",
                "logo_url": f"{self._logo_base}/national_news.svg",
            },
            "extra_news": {
                "primary_color": "#3b82f6",
                "accent_color": "#1e40af",
                "publication_name": "The Extra News",
                "logo_url": f"{self._logo_base}/extra_news.svg",
            },
        }

        brand_key = data.get("logo_id") or template_key
        data["template_id"] = template_key
        if brand_key in branding:
            data.update(branding[brand_key])
        lang_map = {
            "en": "English",  "te": "Telugu",   "hi": "Hindi",
            "kn": "Kannada",  "ta": "Tamil",    "ml": "Malayalam",
            "mr": "Marathi",  "bn": "Bengali",  "gu": "Gujarati",
            "pa": "Punjabi",  "or": "Odia",
        }
        data["language_name"] = lang_map.get(data.get("language", "en"), "English")

        # ── Per-language primary font for logging ─────────────────────────────
        _lang_font_map = {
            "en": ("Playfair Display / Merriweather", "Latin + full Unicode"),
            "te": ("Gautami Bold + Gautami", "Telugu Unicode block U+0C00-U+0C7F"),
            "hi": ("Noto Serif Devanagari + Noto Sans Devanagari", "Devanagari U+0900–U+097F"),
            "mr": ("Noto Serif Devanagari + Noto Sans Devanagari", "Devanagari U+0900–U+097F"),
            "kn": ("Noto Serif Kannada + Noto Sans Kannada", "Kannada U+0C80–U+0CFF"),
            "ml": ("Noto Serif Malayalam + Noto Sans Malayalam", "Malayalam U+0D00–U+0D7F"),
            "ta": ("Noto Serif Tamil + Noto Sans Tamil", "Tamil U+0B80–U+0BFF"),
            "bn": ("Noto Serif Bengali + Noto Sans Bengali", "Bengali U+0980–U+09FF"),
            "gu": ("Noto Serif Gujarati + Noto Sans Gujarati", "Gujarati U+0A80–U+0AFF"),
            "pa": ("Noto Serif Gurmukhi + Noto Sans Gurmukhi", "Gurmukhi U+0A00–U+0A7F"),
            "or": ("Noto Serif Oriya + Noto Sans Oriya", "Odia U+0B00–U+0B7F"),
        }
        lang_code = data.get("language", "en")
        _sel_font, _glyph_cov = _lang_font_map.get(lang_code, ("Playfair Display", "Latin Unicode"))
        _sections = data.get("sections", [])
        _char_count = sum(len(s) for s in _sections)
        _headline_chars = len(data.get("headline", ""))
        _sub_chars = len(data.get("subheadline", "") or data.get("subtitle", ""))
        _caption_chars = sum(len(c) for c in (data.get("image_captions") or []))

        print(f"[MULTILANG] Language          : {data.get('language_name', 'English')} ({lang_code})")
        print(f"[MULTILANG] Selected Font     : {_sel_font}")
        print(f"[MULTILANG] Glyph Coverage    : {_glyph_cov}")
        print(f"[MULTILANG] Headline chars    : {_headline_chars}")
        print(f"[MULTILANG] Subheadline chars : {_sub_chars}")
        print(f"[MULTILANG] Caption chars     : {_caption_chars}")
        print(f"[MULTILANG] Body chars total  : {_char_count} across {len(_sections)} sections")
        sys.stdout.flush()

        # Resolve render URL — on production use the deployed frontend URL
        if data.get("template_id") == "custom":
            clipping_id = data.get("id", "")
            frontend_url = settings.FRONTEND_URL or os.getenv("RENDER_EXTERNAL_URL", "http://localhost:3000")
            render_url = f"{frontend_url}/render/{clipping_id}"
            return render_url  # Playwright will navigate to this URL

        try:
            template = self.env.get_template(f"{template_key}/template.html")
        except Exception:
            try:
                template = self.env.get_template(f"{template_key}.html")
            except Exception:
                template = self.env.get_template("master_layout.html")


        html = template.render(**data)

        # ── MULTILINGUAL FONT ENFORCER ──────────────────────────────────────────
        # Prevent Latin fonts (like Merriweather) from falsely claiming Devanagari 
        # support and rendering vertical bars (||||). We inject an !important CSS rule
        # to ensure the native Noto font is always the first font for all text blocks.
        indic_font_override = ""
        if lang_code in ["hi", "mr"]:
            indic_font_override = "'Noto Serif Devanagari', 'Noto Sans Devanagari'"
        elif lang_code == "kn":
            indic_font_override = "'Noto Serif Kannada', 'Noto Sans Kannada'"
        elif lang_code == "ml":
            indic_font_override = "'Noto Serif Malayalam', 'Noto Sans Malayalam'"
        elif lang_code == "te":
            indic_font_override = "'Gautami Bold', 'Gautami', 'Noto Serif Telugu', 'Noto Sans Telugu'"
        elif lang_code == "ta":
            indic_font_override = "'Noto Serif Tamil', 'Noto Sans Tamil'"
        elif lang_code == "bn":
            indic_font_override = "'Noto Serif Bengali', 'Noto Sans Bengali'"
        elif lang_code == "gu":
            indic_font_override = "'Noto Serif Gujarati', 'Noto Sans Gujarati'"
        elif lang_code == "pa":
            indic_font_override = "'Noto Serif Gurmukhi', 'Noto Sans Gurmukhi'"
        elif lang_code == "or":
            indic_font_override = "'Noto Serif Oriya', 'Noto Sans Oriya'"

        if indic_font_override:
            # Generate absolute local file paths for the fonts to bypass network/CORS issues
            font_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "fonts")).replace("\\", "/")
            
            # Map lang_code to the font family names and file prefixes
            font_file_mapping = {
                "hi": [("Noto Sans Devanagari", "NotoSansDevanagari"), ("Noto Serif Devanagari", "NotoSerifDevanagari")],
                "mr": [("Noto Sans Devanagari", "NotoSansDevanagari"), ("Noto Serif Devanagari", "NotoSerifDevanagari")],
                "kn": [("Noto Sans Kannada", "NotoSansKannada"), ("Noto Serif Kannada", "NotoSerifKannada")],
                "ml": [("Noto Sans Malayalam", "NotoSansMalayalam"), ("Noto Serif Malayalam", "NotoSerifMalayalam")],
                "te": [("Noto Sans Telugu", "NotoSansTelugu"), ("Noto Serif Telugu", "NotoSerifTelugu")],
                "ta": [("Noto Sans Tamil", "NotoSansTamil"), ("Noto Serif Tamil", "NotoSerifTamil")],
                "bn": [("Noto Sans Bengali", "NotoSansBengali"), ("Noto Serif Bengali", "NotoSerifBengali")],
                "gu": [("Noto Sans Gujarati", "NotoSansGujarati"), ("Noto Serif Gujarati", "NotoSerifGujarati")],
                "pa": [("Noto Sans Gurmukhi", "NotoSansGurmukhi"), ("Noto Serif Gurmukhi", "NotoSerifGurmukhi")],
                "or": [("Noto Sans Oriya", "NotoSansOriya"), ("Noto Serif Oriya", "NotoSerifOriya")],
            }
            
            fonts_to_load = font_file_mapping.get(lang_code, [])
            font_faces = []
            for family_name, file_prefix in fonts_to_load:
                font_faces.append(f"""
                @font-face {{
                    font-family: '{family_name}'; font-style: normal; font-weight: 400;
                    src: url('file://{font_dir}/{file_prefix}-Regular.ttf') format('truetype');
                }}
                @font-face {{
                    font-family: '{family_name}'; font-style: normal; font-weight: 700;
                    src: url('file://{font_dir}/{file_prefix}-Bold.ttf') format('truetype');
                }}
                """)
            
            local_fonts_css = f"""
            <style id="local-fonts-enforcer">
                {''.join(font_faces)}
            </style>
            """
            
            override_css = f"""
            {local_fonts_css}
            <style id="indic-font-enforcer">
                /* Force Indic font first, fallback to Latin */
                .headline, .subheadline, .subtitle, h1, h2, h3, .article-content p, .paragraph, .nc-text-region-box p, .dateline, .image-caption, .nc-image-caption, .byline-section, .byline, .nc-absolute-summary, .nc-absolute-summary h4, .nc-absolute-summary p, .nc-absolute-summary ul, .nc-absolute-summary li {{
                    font-family: {indic_font_override}, 'Playfair Display', 'Merriweather', serif !important;
                }}
            </style>
            """
            if "</head>" in html:
                html = html.replace("</head>", f"{override_css}\n</head>")
            else:
                html = f"{override_css}\n{html}"
                
        def is_dark_hex(hex_str: str) -> bool:
            if not hex_str or not hex_str.startswith('#') or len(hex_str) not in (4, 7):
                return False
            h = hex_str.lstrip('#')
            if len(h) == 3:
                h = "".join(c+c for c in h)
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                return brightness < 128
            except ValueError:
                return False

        headline_text_color = "var(--primary-color)"
        heading_bg = data.get('heading_bg')
        if heading_bg:
            if is_dark_hex(heading_bg):
                headline_text_color = "#FFFFFF" # Use white for dark backgrounds
            else:
                headline_text_color = "#111111" # Use dark text for light backgrounds

        custom_border_css = ""
        if data.get('border_color'):
            custom_border_css = f"""
            .headline-section, .headline-block {{
                border-color: {data.get('border_color')} !important;
            }}
            """

        heading_bg_css = f"""
            background-color: {heading_bg} !important;
            margin-left: -20px !important;
            margin-right: -20px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
        """ if heading_bg else ""

        dynamic_css = f"""
        <style id="dynamic-theme-override">
            :root {{
                --primary-color: {data.get('primary_color') or '#1d70b8'};
                --border-color: {data.get('border_color') or '#111111'};
            }}
            .headline-section, .headline-block {{
                {heading_bg_css}
            }}
            .headline {{
                color: {headline_text_color} !important;
                text-shadow: 0 1px 0 rgba(0,0,0,0.08);
            }}
            {custom_border_css}
            .article-content, .paragraph {{
                text-align: left !important;
            }}
        </style>
        """
        if "</body>" in html:
            html = html.replace("</body>", f"{dynamic_css}\n</body>")
        else:
            html = f"{html}\n{dynamic_css}"


                

        # Single-Page Dynamic Compression Engine Injection
        import json
        serializable_data = {
            "headline": data.get("headline", ""),
            "subheadline": data.get("subheadline", "") or data.get("subtitle", ""),
            "publication_name": data.get("publication_name", ""),
            "publication_date": data.get("publication_date", ""),
            "volume": data.get("volume", "CXIV"),
            "edition": data.get("edition", "27"),
            "location": data.get("location", "Global Edition"),
            "language_name": data.get("language_name", "English"),
            "byline": data.get("byline", ""),
            "dateline": data.get("dateline", ""),
            "template_id": data.get("template_id", "classic"),
            "logo_url": data.get("logo_url", ""),
            "primary_color": data.get("primary_color", "#000000"),
            "accent_color": data.get("accent_color", "#333333"),
            "border_color": data.get("border_color", "") or data.get("primary_color", "#000000"),
            "layout_columns": data.get("layout_columns", 3),
            "sections": data.get("sections", []),
            "image_urls": data.get("image_urls", []),
            "image_captions": data.get("image_captions", []),
            "image_layout": data.get("image_layout", "default"),
            "heading_bg": data.get("heading_bg", ""),
            "summary": data.get("summary", "") or data.get("Summary", "") or data.get("summary_text", ""),
            "bullet_points": data.get("bullet_points", []) or data.get("Bullet_points", []) or data.get("key_takeaways", []),
            "summary_bg": data.get("summary_bg", ""),
            "bullet_bg": data.get("bullet_bg", "")
        }
        # ── BULLETPROOF JSON INJECTION ───────────────────────────────────────
        # Using <script type="application/json"> isolates the JSON payload
        # from the JavaScript engine. This prevents literal Unicode line
        # separators (U+2028) or unescaped quotes from breaking JS syntax.
        json_str = json.dumps(serializable_data)
        json_str = json_str.replace("</", "<\\/") # Safely escape HTML closing tags

        # Log original article stats
        sections = data.get("sections", [])
        original_char_count = sum(len(s) for s in sections)
        print(f"[LAYOUT] Original article length: {original_char_count} chars across {len(sections)} sections")
        sys.stdout.flush()

        data_script = f"""<script type="application/json" id="newspaper-data">
{json_str}
</script>"""

        script_block = r"""
        <script>
        // ── window.onerror: Report JS errors with exact file/line/column ────
        window.onerror = function(msg, src, line, col, err) {
            console.error(
                'JS ERROR:', msg,
                'FILE:', src,
                'LINE:', line,
                'COLUMN:', col
            );
            if (!window.__LAYOUT_DONE__) {
                window.__LAYOUT_DONE__ = true;
            }
            return false;
        };
        
        document.addEventListener("DOMContentLoaded", async () => {
            const TARGET_MAX_HEIGHT = 1500;

            try {
                const dataEl = document.getElementById('newspaper-data');
                if (dataEl) {
                    window.NEWSPAPER_DATA = JSON.parse(dataEl.textContent);
                }
            } catch (e) {
                console.error('[LAYOUT] JSON Parse Error:', e);
            }
            const data = window.NEWSPAPER_DATA;
            if (!data) {
                console.error('[LAYOUT] No data found.');
                window.__LAYOUT_DONE__ = true;
                return;
            }

            const container = document.querySelector('.newspaper-container');
            if (!container) return;

            const totalChars = (data.sections || []).reduce((s, p) => s + p.length, 0);
            console.log('[LAYOUT] Article length:', totalChars, 'chars,', (data.sections||[]).length, 'sections');

            // waitReady utility with timeout
            async function waitReady() {
                const WAIT_TIMEOUT = 8000;
                try {
                    await Promise.race([
                        document.fonts.ready,
                        new Promise(r => setTimeout(r, WAIT_TIMEOUT))
                    ]);
                } catch(e) {}

                const imgPromises = Array.from(document.images).map(img => {
                    if (img.complete) return Promise.resolve();
                    return Promise.race([
                        new Promise(r => {
                            img.addEventListener('load',  r, { once: true });
                            img.addEventListener('error', r, { once: true });
                        }),
                        new Promise(r => setTimeout(r, WAIT_TIMEOUT))
                    ]);
                });
                await Promise.all(imgPromises);
            }

            const urls = data.image_urls || [];
            const captions = data.image_captions || [];
            const imgCount = urls.length;
            
            let aspectRatios = [];
            let orientations = [];

            // getImageDimensions utility
            async function getImageDimensions(url) {
                const existingImg = Array.from(document.images).find(img => img.src === url || img.getAttribute('src') === url);
                if (existingImg && existingImg.naturalWidth && existingImg.naturalHeight) {
                    return { width: existingImg.naturalWidth, height: existingImg.naturalHeight };
                }
                return Promise.race([
                    new Promise((resolve) => {
                        const img = new Image();
                        img.onload  = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
                        img.onerror = () => resolve({ width: 800, height: 600 });
                        img.src = url;
                    }),
                    new Promise(resolve => setTimeout(() => {
                        resolve({ width: 800, height: 600 });
                    }, 8000))
                ]);
            }

            // Ensure we have a compositor-canvas element
            let canvas = document.getElementById('compositor-canvas');
            if (!canvas) {
                canvas = document.createElement('div');
                canvas.id = 'compositor-canvas';
                container.appendChild(canvas);
            }
            canvas.style.position = 'relative';
            canvas.style.width = '100%';
            canvas.style.boxSizing = 'border-box';

            function getObstacles(W_canvas, S_img, imgHeightPx, H_canvas) {
                H_canvas = H_canvas || 1200;
                const obstacles = [];
                if (urls.length > 0) {
                    let S_scale = S_img;
                    let gap = 60;
                    // Dynamically rescale images based on text content size to prevent overflowing short articles
                    if (totalChars > 0 && totalChars < 3000) {
                        const scaleFactor = Math.max(0.5, 1.0 - (3000 - totalChars) / 3500);
                        S_scale = S_img * scaleFactor;
                        gap = 30;
                    }
                    // Bulletproof pattern matching: handles "Pattern B", "pattern_b", "patternB", etc.
                    const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                    const isArticleStyle = rawLayout.includes('articlestyle') || rawLayout.includes('patterng');
                    let isPatternB = rawLayout.includes('patternb') || rawLayout.includes('patterna') || rawLayout.includes('patternd') || rawLayout.includes('patternc') || rawLayout.includes('patterne') || isArticleStyle;
                    if (rawLayout === "default" || rawLayout === "") {
                        isPatternB = true;
                    }
                    const isDoublePatternB = (isPatternB && urls.length === 2) && (rawLayout.includes('patternc') || rawLayout.includes('patterna') || rawLayout === "default");
                    const isTriplePatternB = isPatternB && urls.length >= 3;

                    const aspect0 = aspectRatios[0] || 1.2;
                    
                    if (rawLayout.includes('patterng')) {
                        // Pattern G ALWAYS forces a horizontal gallery of ALL images at the top!
                        let count = urls.length;
                        if (count > 0) {
                            let gap = 16;
                            let w = (W_canvas - (gap * (count - 1))) / count;
                            
                            // Balance their heights so they align nicely (using maximum height)
                            let maxH = 0;
                            for (let i = 0; i < count; i++) {
                                let asp = aspectRatios[i] || 1.0;
                                let thisH = w / asp;
                                if (thisH > maxH) maxH = thisH;
                            }
                            
                            // Cap height to prevent insanely tall images if they are vertical
                            if (maxH > W_canvas * 0.75) maxH = W_canvas * 0.75;
                            
                            for (let i = 0; i < count; i++) {
                                obstacles.push({ url: urls[i], caption: captions[i] || '', x: Math.round(i * (w + gap)), y: 0, w: Math.round(w), h: Math.round(maxH) });
                            }
                            
                            let measureContainer = document.createElement('div');
                            measureContainer.style.position = 'absolute';
                            measureContainer.style.visibility = 'hidden';
                            measureContainer.style.width = Math.round(W_canvas / 2) + 'px';
                            measureContainer.style.fontSize = '15px';
                            measureContainer.style.lineHeight = '1.6';
                            measureContainer.style.fontFamily = 'var(--primary-font, "Playfair Display", serif)';
                            measureContainer.style.padding = '24px';
                            measureContainer.style.boxSizing = 'border-box';
                            
                            // Measure Summary
                            measureContainer.innerHTML = `<h4 style="margin: 0 0 12px 0; font-size: 18px;">Summary</h4><p style="margin: 0;">${data.summary || ''}</p>`;
                            document.body.appendChild(measureContainer);
                            let sumH = measureContainer.offsetHeight;
                            
                            // Measure Bullets
                            let bpHtml = (data.bullet_points || []).map(bp => `<li style="margin-bottom: 8px;">${bp}</li>`).join('');
                            measureContainer.innerHTML = `<h4 style="margin: 0 0 12px 0; font-size: 18px;">Key Takeaways</h4><ul style="margin: 0; padding-left: 20px;">${bpHtml}</ul>`;
                            let bulH = measureContainer.offsetHeight;
                            document.body.removeChild(measureContainer);
                            
                            let summaryH = Math.max(120, sumH, bulH);
                            
                            obstacles.push({
                                type: 'summary_bullets',
                                x: 0,
                                y: Math.round(maxH + 30),
                                w: W_canvas,
                                h: summaryH
                            });
                        } else {
                            obstacles.push({
                                type: 'summary_bullets',
                                x: 0,
                                y: 0,
                                w: W_canvas,
                                h: 200
                            });
                        }
                        return obstacles;
                    }
                    
                    if (isTriplePatternB) {
                        // Pattern E style with 3 images: Large hero on top, two smaller side-by-side below
                        let w0 = W_canvas;
                        let h0 = Math.min(w0 / aspect0, W_canvas * 0.6);
                        
                        let gap = 24;
                        let w1 = (W_canvas - gap) / 2;
                        
                        let a1 = aspectRatios[1] || 1.5;
                        let a2 = aspectRatios[2] || 1.5;
                        let h1 = w1 / a1;
                        let h2 = w1 / a2;
                        // Balance their heights so they look perfectly aligned
                        let sharedH = Math.max(h1, h2);
                        
                        obstacles.push({ url: urls[0], caption: captions[0] || '', x: 0, y: 0, w: Math.round(w0), h: Math.round(h0) });
                        obstacles.push({ url: urls[1], caption: captions[1] || '', x: 0, y: Math.round(h0 + gap), w: Math.round(w1), h: Math.round(sharedH) });
                        obstacles.push({ url: urls[2], caption: captions[2] || '', x: Math.round(w1 + gap), y: Math.round(h0 + gap), w: Math.round(w1), h: Math.round(sharedH) });
                        
                        return obstacles;
                    }
                    
                    let w0 = W_canvas * Math.max(0.40, Math.min(0.60, 0.55 * S_scale));
                    
                    let isPatternB_centered = false;
                    let imgVisW = w0;
                    let h0 = w0 / aspect0;
                    let imgX = Math.round(W_canvas - w0);
                    let imgY = 0;
                    
                    if (isDoublePatternB) {
                        let a0 = aspect0 || 1.0;
                        let a1 = aspectRatios[1] || 1.0;
                        let sharedH = (W_canvas - 24) / (a0 + a1);
                        w0 = sharedH * a0;
                        h0 = sharedH;
                        imgX = 0;
                        imgY = 0; // Both images at the top
                        imgVisW = w0;
                        isPatternB_centered = false;
                        
                        // Save sharedH for the second image
                        window.__db_sharedH = sharedH;
                        window.__db_a1 = a1;
                    } else if (isPatternB) {
                        w0 = W_canvas; // Full width obstacle to break text horizontally across all columns
                        imgX = 0;
                        imgY = 0; // Image must appear immediately before the article text
                        imgVisW = W_canvas; // 100% of content width (covers sides as requested)
                        
                        // Rescale dynamically based on exact aspect ratio and text density
                        let dynamicH = (imgVisW / aspect0) * (S_scale / S_img);
                        
                        // Prevent giant vertical images from zooming out the layout and ruining text quality
                        h0 = Math.min(dynamicH, TARGET_MAX_HEIGHT * 0.55);
                        
                        isPatternB_centered = true;
                    } else {
                        h0 = Math.min(h0, TARGET_MAX_HEIGHT * 0.3, imgHeightPx * (urls.length > 2 && totalChars < 2500 ? 0.75 : 1.0));
                    }
                    
                    obstacles.push({
                        url: urls[0],
                        caption: captions[0] || '',
                        x: imgX,
                        y: imgY,
                        w: Math.round(w0),
                        h: Math.round(h0),
                        isCentered: isPatternB_centered,
                        visW: Math.round(imgVisW)
                    });
                    
                    if (urls.length > 1) {
                        if (isDoublePatternB) {
                            let h1 = window.__db_sharedH;
                            let w1 = h1 * window.__db_a1;
                            let x1 = W_canvas - w1; // Right aligned
                            let y1 = 0; // Top aligned
                            obstacles.push({
                                url: urls[1],
                                caption: captions[1] || '',
                                x: Math.round(x1),
                                y: Math.round(y1),
                                w: Math.round(w1),
                                h: Math.round(h1)
                            });
                        } else {
                            const aspect1 = aspectRatios[1] || 1.0;
                            let w1 = W_canvas * Math.max(0.40, Math.min(0.58, 0.48 * S_scale));
                            let h1 = w1 / aspect1;
                            h1 = Math.min(h1, imgHeightPx * (urls.length > 2 && totalChars < 2500 ? 0.75 : 1.0));
                            let y1 = h0 + gap; // Spacing below Hero
                            
                            obstacles.push({
                                url: urls[1],
                                caption: captions[1] || '',
                                x: 0,
                                y: Math.round(y1),
                                w: Math.round(w1),
                                h: Math.round(h1)
                            });
                        }
                    }

                    if (urls.length > 2) {
                        const aspect2 = aspectRatios[2] || 1.0;
                        let w2 = W_canvas * Math.max(0.40, Math.min(0.58, 0.48 * S_scale));
                        let h2 = w2 / aspect2;
                        h2 = Math.min(h2, imgHeightPx * (urls.length > 2 && totalChars < 2500 ? 0.75 : 1.0));
                        let y2 = H_canvas - h2;
                        
                        obstacles.push({
                            url: urls[2],
                            caption: captions[2] || '',
                            x: Math.round(W_canvas - w2), // Align bottom-right
                            y: Math.round(y2),
                            w: Math.round(w2),
                            h: Math.round(h2)
                        });
                    }

                    if (isArticleStyle) {
                        let maxY = 0;
                        obstacles.forEach(o => {
                            if (o.y + o.h > maxY) maxY = o.y + o.h;
                        });
                        
                        let measureContainer = document.createElement('div');
                        measureContainer.style.position = 'absolute';
                        measureContainer.style.visibility = 'hidden';
                        measureContainer.style.width = Math.round(W_canvas / 2) + 'px';
                        measureContainer.style.fontSize = '15px';
                        measureContainer.style.lineHeight = '1.6';
                        measureContainer.style.fontFamily = 'var(--primary-font, "Playfair Display", serif)';
                        measureContainer.style.padding = '24px';
                        measureContainer.style.boxSizing = 'border-box';
                        
                        // Measure Summary
                        measureContainer.innerHTML = `<h4 style="margin: 0 0 12px 0; font-size: 18px;">Summary</h4><p style="margin: 0;">${data.summary || ''}</p>`;
                        document.body.appendChild(measureContainer);
                        let sumH = measureContainer.offsetHeight;
                        
                        // Measure Bullets
                        let bpHtml = (data.bullet_points || []).map(bp => `<li style="margin-bottom: 8px;">${bp}</li>`).join('');
                        measureContainer.innerHTML = `<h4 style="margin: 0 0 12px 0; font-size: 18px;">Key Takeaways</h4><ul style="margin: 0; padding-left: 20px;">${bpHtml}</ul>`;
                        let bulH = measureContainer.offsetHeight;
                        document.body.removeChild(measureContainer);
                        
                        let summaryH = Math.max(120, sumH, bulH);
                        
                        obstacles.push({
                            type: 'summary_bullets',
                            x: 0,
                            y: maxY > 0 ? maxY + 30 : 0,
                            w: W_canvas,
                            h: summaryH
                        });
                    }
                }
                return obstacles;
            }

            function runLayoutPass(conf, S, H_layout, isFinal) {
                // Clear the compositor canvas
                canvas.innerHTML = '';
                
                // Get canvas width
                const W_canvas = canvas.offsetWidth || 1060;
                
                // Calculate columns
                let N = parseInt(data.layout_columns) || 3;
                
                const G = 24; // Column gap in pixels
                const W_col = (W_canvas - (N - 1) * G) / N;
                
                const H_canvas = H_layout;
                
                // Calculate image dimensions and create absolute obstacles
                const imgHeightPx = Math.round(0.58 * W_canvas);
                let S_img = S || 1.0;
                const obstacles = getObstacles(W_canvas, S_img, imgHeightPx, H_canvas);

                // Render absolute images onto canvas if it's the final pass
                if (isFinal) {
                    obstacles.forEach(obs => {
                        if (obs.type === 'summary_bullets') {
                            const containerEl = document.createElement('div');
                            containerEl.className = 'nc-absolute-summary';
                            containerEl.style.position = 'absolute';
                            containerEl.style.left = `${obs.x}px`;
                            containerEl.style.top = `${obs.y}px`;
                            containerEl.style.width = `${obs.w}px`;
                            containerEl.style.height = `${obs.h}px`;
                            containerEl.style.boxSizing = 'border-box';
                            containerEl.style.display = 'flex';
                            containerEl.style.flexDirection = 'row';
                            containerEl.style.gap = '24px';
                            containerEl.style.zIndex = '5';
                            containerEl.style.fontFamily = 'var(--primary-font, "Playfair Display", serif)';
                            
                            let bpHtml = (data.bullet_points || []).map(bp => `<li style="margin-bottom: 8px;">${bp}</li>`).join('');
                            
                            let sumBg = data.summary_bg || '#FFF4CC';
                            let bulBg = data.bullet_bg || '#00A79D';
                            let sumHeadingColor = '#B28600';
                            let sumTextColor = '#333333';
                            let bulHeadingColor = '#CCF2F0';
                            let bulTextColor = '#FFFFFF';
                            let listStyle = 'disc';
                            let sumBorder = '#FFE066';
                            let bulBorder = '#008C83';
                            
                            if (data.template_id === 'custom') {
                                sumBg = '#F8E71C'; // Bright yellow
                                bulBg = '#00B7C6'; // Bright cyan
                                sumHeadingColor = '#000000';
                                sumTextColor = '#000000';
                                bulHeadingColor = '#FFFFFF';
                                listStyle = '"✦  "';
                                sumBorder = 'transparent';
                                bulBorder = 'transparent';
                            }
                            
                            containerEl.innerHTML = `
                                <div style="flex: 1; background-color: ${sumBg}; padding: 24px; border-radius: 12px; border: 1px solid ${sumBorder}; display: flex; flex-direction: column; justify-content: center;">
                                    <h4 style="margin: 0 0 12px 0; color: ${sumHeadingColor}; font-size: 18px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;">Summary</h4>
                                    <p style="margin: 0; font-size: 15px; line-height: 1.6; color: ${sumTextColor};">${data.summary || ''}</p>
                                </div>
                                <div style="flex: 1; background-color: ${bulBg}; padding: 24px; border-radius: 12px; border: 1px solid ${bulBorder}; display: flex; flex-direction: column; justify-content: center;">
                                    <h4 style="margin: 0 0 12px 0; color: ${bulHeadingColor}; font-size: 18px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;">Key Takeaways</h4>
                                    <ul style="margin: 0; padding-left: 20px; font-size: 15px; line-height: 1.6; color: ${bulTextColor}; list-style-type: ${listStyle};">
                                        ${bpHtml}
                                    </ul>
                                </div>
                            `;
                            canvas.appendChild(containerEl);
                            return;
                        }

                        const imgEl = document.createElement('div');
                        imgEl.className = 'nc-absolute-image';
                        imgEl.style.position = 'absolute';
                        imgEl.style.left = `${obs.x}px`;
                        imgEl.style.top = `${obs.y}px`;
                        imgEl.style.width = `${obs.w}px`;
                        imgEl.style.height = 'auto';
                        imgEl.style.boxSizing = 'border-box';
                        imgEl.style.border = `1px solid ${data.border_color || '#000'}`;
                        imgEl.style.padding = '4px';
                        imgEl.style.background = 'var(--bg-color, #F5F1E8)';
                        imgEl.style.zIndex = '5';
                        
                        let captionHeight = 0;
                        if (obs.caption) {
                            const wrapW = obs.isCentered ? obs.visW : obs.w;
                            const charsPerLine = Math.max(1, Math.floor(wrapW / 6.5));
                            const lines = Math.ceil(obs.caption.length / charsPerLine);
                            captionHeight = lines * 15;
                        }
                        const imgH = obs.h - (captionHeight ? captionHeight + 8 : 8);
                        
                        if (obs.isCentered) {
                            const isFullBleed = (obs.visW >= obs.w);
                            imgEl.style.display = 'flex';
                            imgEl.style.flexDirection = 'column';
                            imgEl.style.alignItems = 'center';
                            imgEl.style.border = 'none';
                            imgEl.style.background = 'transparent';
                            imgEl.style.padding = '0';
                            
                            const innerStyle = isFullBleed 
                                ? `width: ${obs.visW}px; display: flex; flex-direction: column; align-items: center; box-sizing: border-box;`
                                : `width: ${obs.visW}px; border: 1px solid ${data.border_color || '#000'}; padding: 4px; background: var(--bg-color, #F5F1E8); display: flex; flex-direction: column; align-items: center; box-sizing: border-box;`;

                            imgEl.innerHTML = `
                                <div style="${innerStyle}">
                                    <img src="${obs.url}" style="width: 100%; height: ${imgH}px; max-height: none !important; object-fit: cover; display: block;" />
                                    ${obs.caption ? `<div class="image-caption nc-image-caption" style="font-size: 11px; font-style: italic; color: #444; margin-top: 4px; line-height: 1.3; width: 100%; text-align: center; word-wrap: break-word;">${obs.caption}</div>` : ''}
                                </div>
                            `;
                        } else {
                            imgEl.innerHTML = `
                                <img src="${obs.url}" style="width: 100%; height: ${imgH}px; max-height: none !important; object-fit: cover; display: block;" />
                                ${obs.caption ? `<div class="image-caption nc-image-caption" style="font-size: 11px; font-style: italic; color: #444; margin-top: 4px; line-height: 1.3; word-wrap: break-word;">${obs.caption}</div>` : ''}
                            `;
                        }
                        canvas.appendChild(imgEl);
                    });
                }
                
                let inflatedObstacles = obstacles.map(obs => {
                    return {
                        x: obs.x - 12,
                        y: obs.y - 12,
                        w: obs.w + 24,
                        h: obs.h + 24
                    };
                });
                
                const rawLayoutStr = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                if (rawLayoutStr.includes('patternb') && urls.length === 2) {
                    let maxH = 0;
                    obstacles.forEach(o => {
                        if (o.y === 0 && o.h > maxH && o.type !== 'summary_bullets') {
                            maxH = o.h;
                        }
                    });
                    if (maxH > 0) {
                        inflatedObstacles.push({
                            x: -12,
                            y: -12,
                            w: W_canvas + 24,
                            h: maxH + 24
                        });
                    }
                }

                // Flow layout function
                const regions = [];
                for (let c = 0; c < N; c++) {
                    const L_c = c * (W_col + G);
                    const R_c = L_c + W_col;
                    
                    let intervals = [{ yStart: 0, yEnd: H_canvas, xOffset: 0, w: W_col }];
                    
                    inflatedObstacles.forEach(obs => {
                        const xOverlapStart = Math.max(L_c, obs.x);
                        const xOverlapEnd = Math.min(R_c, obs.x + obs.w);
                        if (xOverlapStart >= xOverlapEnd) return;
                        
                        const yOverlapStart = Math.max(0, obs.y);
                        const yOverlapEnd = Math.min(H_canvas, obs.y + obs.h);
                        if (yOverlapStart >= yOverlapEnd) return;
                        
                        const nextIntervals = [];
                        intervals.forEach(int => {
                            const yIntersectStart = Math.max(int.yStart, yOverlapStart);
                            const yIntersectEnd = Math.min(int.yEnd, yOverlapEnd);
                            
                            if (yIntersectStart >= yIntersectEnd) {
                                nextIntervals.push(int);
                                return;
                            }
                            
                            if (int.yStart < yIntersectStart) {
                                nextIntervals.push({
                                    yStart: int.yStart,
                                    yEnd: yIntersectStart,
                                    xOffset: int.xOffset,
                                    w: int.w
                                });
                            }
                            
                            const intStart = int.xOffset;
                            const intEnd = int.xOffset + int.w;
                            
                            const obsStart = obs.x - L_c;
                            const obsEnd = obs.x + obs.w - L_c;
                            
                            // Left piece
                            if (intStart < obsStart) {
                                const wRem = Math.min(intEnd, obsStart) - intStart;
                                if (wRem >= 40) {
                                    nextIntervals.push({
                                        yStart: yIntersectStart,
                                        yEnd: yIntersectEnd,
                                        xOffset: intStart,
                                        w: wRem
                                    });
                                }
                            }
                            
                            // Right piece
                            if (intEnd > obsEnd) {
                                const newStart = Math.max(intStart, obsEnd);
                                const wRem = intEnd - newStart;
                                if (wRem >= 40) {
                                    nextIntervals.push({
                                        yStart: yIntersectStart,
                                        yEnd: yIntersectEnd,
                                        xOffset: newStart,
                                        w: wRem
                                    });
                                }
                            }
                            
                            if (int.yEnd > yIntersectEnd) {
                                nextIntervals.push({
                                    yStart: yIntersectEnd,
                                    yEnd: int.yEnd,
                                    xOffset: int.xOffset,
                                    w: int.w
                                });
                            }
                        });
                        intervals = nextIntervals;
                    });
                    
                    intervals.forEach(int => {
                        const h = int.yEnd - int.yStart;
                        if (h < 24 || int.w < 40) return;
                        
                        const rBox = document.createElement('div');
                        rBox.className = 'nc-text-region-box';
                        rBox.style.position = 'absolute';
                        rBox.style.left = `${int.xOffset}px`;
                        rBox.style.top = `${int.yStart}px`;
                        rBox.style.width = `${int.w}px`;
                        rBox.style.height = `${h}px`;
                        rBox.style.boxSizing = 'border-box';
                        rBox.style.overflow = 'hidden';
                        
                        const colDiv = canvas.querySelector(`.col-${c}`) || document.createElement('div');
                        if (!canvas.contains(colDiv)) {
                            colDiv.className = `nc-column col-${c}`;
                            colDiv.style.position = 'absolute';
                            colDiv.style.left = `${L_c}px`;
                            colDiv.style.top = '0px';
                            colDiv.style.width = `${W_col}px`;
                            canvas.appendChild(colDiv);
                        }
                        colDiv.appendChild(rBox);
                        
                        regions.push({ rBox, height: h, y: int.yStart });
                    });
                }
                
                let paragraphs = [];
                for (const sec of data.sections) {
                    const cleanSec = sec.replace(/\n+/g, ' ').trim();
                    if (cleanSec) {
                        paragraphs.push(cleanSec);
                    }
                }
                if (paragraphs.length > 0 && data.dateline) {
                    paragraphs[0] = ((data.template_id === 'classic') ? `[${data.dateline}] — ` : `${data.dateline} — `) + paragraphs[0];
                }
                
                let pIdx = 0;
                let currentRegionIdx = 0;
                let activeRegion = regions[currentRegionIdx];
                
                while (activeRegion && pIdx < paragraphs.length) {
                    let text = paragraphs[pIdx];
                    const p = document.createElement('p');
                    p.innerText = text;
                    p.style.fontSize = `${conf.fontSize}px`;
                    p.style.lineHeight = conf.lineHeight;
                    p.style.marginBottom = `${conf.paraMargin}px`;
                    p.style.marginTop = '0';
                    p.style.textAlign = 'justify';
                    p.style.wordBreak = 'break-word';
                    p.style.overflowWrap = 'break-word';
                    activeRegion.rBox.appendChild(p);
                    
                    if (currentRegionIdx === regions.length - 1) {
                        if (isFinal) {
                            pIdx++;
                            continue;
                        } else {
                            if (activeRegion.rBox.scrollHeight > activeRegion.height) {
                                return false; // Overflowed the final column in search mode
                            }
                            pIdx++;
                            continue;
                        }
                    }
                    
                    if (activeRegion.rBox.scrollHeight > activeRegion.height) {
                        activeRegion.rBox.removeChild(p);
                        const words = text.split(/\s+/);
                        const testP = p.cloneNode();
                        activeRegion.rBox.appendChild(testP);
                        let wIdx = 0;
                        for (; wIdx < words.length; wIdx++) {
                            testP.innerText = words.slice(0, wIdx + 1).join(' ');
                            if (activeRegion.rBox.scrollHeight > activeRegion.height) break;
                        }
                        activeRegion.rBox.removeChild(testP);
                        if (wIdx > 0) {
                            const fitP = p.cloneNode();
                            fitP.innerText = words.slice(0, wIdx).join(' ');
                            activeRegion.rBox.appendChild(fitP);
                        }
                        const rem = words.slice(wIdx).join(' ');
                        if (rem.trim().length > 0) paragraphs.splice(pIdx, 1, rem); else pIdx++;
                        currentRegionIdx++;
                        activeRegion = regions[currentRegionIdx];
                    } else pIdx++;
                }
                
                if (pIdx < paragraphs.length) {
                    return false; // Did not fit all paragraphs
                }
                
                // Third image is now handled as an absolute obstacle at bottom-right
                
                if (isFinal) {
                    let maxY = 0;
                    regions.forEach(r => {
                        if (r.rBox.lastElementChild && r.rBox.innerText.trim() !== '') {
                            const contentHeight = r.rBox.lastElementChild.offsetTop + r.rBox.lastElementChild.offsetHeight + 4;
                            r.rBox.style.height = `${contentHeight}px`;
                            maxY = Math.max(maxY, r.y + contentHeight);
                        } else {
                            r.rBox.style.height = '0px';
                        }
                    });
                    obstacles.forEach(img => maxY = Math.max(maxY, img.y + img.h));
                    
                    canvas.style.height = `${Math.max(maxY, 150)}px`;
                    
                    // Force zero whitespace below the canvas
                    const innerBorder = document.querySelector('.inner-border');
                    if (innerBorder) {
                        innerBorder.style.flex = 'none';
                        innerBorder.style.height = 'auto';
                    }
                    const container = document.querySelector('.newspaper-container');
                    if (container) {
                        container.style.height = 'auto';
                        container.style.minHeight = '0px';
                    }
                    
                    window.__IMAGE_LAYOUT_LOGS__ = {
                        image_count: imgCount,
                        image_orientations: orientations.join(', '),
                        selected_layout: 'Region-Based Newspaper Page Compositor (Binary Search Balanced)',
                        final_dimensions: obstacles.map(obs => `${obs.w}x${obs.h}px`).join(', ')
                    };
                }
                
                return true;
            }

            async function executeLayout() {
                const dims = await Promise.all(urls.map(url => getImageDimensions(url)));
                aspectRatios = dims.map(d => (d.width && d.height) ? (d.width / d.height) : 1.0);
                await waitReady();
                
                // Force headline to fit on a single line
                const hl = document.querySelector('.headline');
                if (hl) {
                    hl.style.whiteSpace = 'nowrap';
                    hl.style.overflow = 'visible';
                    hl.style.display = 'inline-block';
                    hl.style.width = 'auto';
                    let fs = 76; // Start slightly larger to fill space if short
                    hl.style.fontSize = fs + 'px';
                    const parent = hl.parentElement;
                    const cs = window.getComputedStyle(parent);
                    const maxWidth = parent.clientWidth - parseFloat(cs.paddingLeft || 0) - parseFloat(cs.paddingRight || 0) - 4;
                    while (hl.offsetWidth > maxWidth && fs > 16) {
                        fs -= 1;
                        hl.style.fontSize = fs + 'px';
                    }
                    hl.style.display = 'block';
                    hl.style.width = '100%';
                }

                // Dynamic scaling factor S based on character count
                let S = 1.0 - (totalChars - 1400) / 3000;
                S = Math.max(0.75, Math.min(1.25, S));

                const W_canvas = canvas.offsetWidth || 1060;
                const N = parseInt(data.layout_columns) || 3;
                const W_col = (W_canvas - (N - 1) * 24) / N;
                const canvasTop = canvas.getBoundingClientRect().top + window.scrollY;
                const H_avail = Math.max(1200, TARGET_MAX_HEIGHT - canvasTop - 60);
                
                const imgHeightPx = Math.round(0.58 * W_canvas);
                let S_img = S || 1.0;
                const obstacles = getObstacles(W_canvas, S_img, imgHeightPx, H_avail);
                
                let maxObstacleY = 0;
                // Only consider the first two (fixed) obstacles for the page height floor limit
                obstacles.slice(0, 2).forEach(obs => {
                    maxObstacleY = Math.max(maxObstacleY, obs.y + obs.h);
                });
                
                // Available width for columns: N * W_col.
                // But images block some of the columns. Let's compute the available area for text.
                let blockedArea = 0;
                obstacles.forEach(obs => {
                    for (let c = 0; c < N; c++) {
                        const L_c = c * (W_col + 24);
                        const R_c = L_c + W_col;
                        const xOverlapStart = Math.max(L_c, obs.x);
                        const xOverlapEnd = Math.min(R_c, obs.x + obs.w);
                        if (xOverlapStart < xOverlapEnd) {
                            blockedArea += (xOverlapEnd - xOverlapStart) * obs.h;
                        }
                    }
                });
                
                const estFontSize = Math.sqrt(Math.max(100000, N * W_col * H_avail - blockedArea) / (totalChars * 0.54));
                const maxFontSize = (urls.length > 2 && totalChars < 2500) ? 23.0 : 21.0;
                const conf = { fontSize: Math.max(15.0, Math.min(maxFontSize, estFontSize)), lineHeight: 1.35, paraMargin: 12, imgMaxPct: 0.58, padding: 32 };

                // Let's run a binary search to find the minimum height where the text fits.
                let low = Math.max(300, Math.round(maxObstacleY + 30));
                let high = Math.max(H_avail, low + 3000);
                let H_best = high;
                
                for (let step = 0; step < 8; step++) {
                    const mid = Math.round((low + high) / 2);
                    const fits = runLayoutPass(conf, S, mid, false);
                    if (fits) {
                        H_best = mid;
                        high = mid - 1;
                    } else {
                        low = mid + 1;
                    }
                }
                
                // Final render pass with H_best (plus 4px margin for safe line wrapping rounding variations)
                runLayoutPass(conf, S, H_best + 4, true);
                
                let st = document.getElementById('nc-layout-style');
                if (!st) { st = document.createElement('style'); st.id = 'nc-layout-style'; document.head.appendChild(st); }
                st.innerHTML = `
                    * { -webkit-font-smoothing: antialiased !important; }
                    body { margin: 0 !important; padding: 0 !important; }
                    .newspaper-container { height: auto !important; min-height: unset !important; padding-bottom: 0px !important; margin-bottom: 0px !important; }
                `;
                
                // Precision shrink-wrap canvas exactly to the lowest content pixel
                let rBoxBottoms = [];
                document.querySelectorAll('.nc-text-region-box, .nc-absolute-image').forEach(el => {
                    if (el.classList.contains('nc-text-region-box')) {
                        if (el.clientHeight === 0) return;
                        if (el.innerText.trim() === '') return;
                    }
                    let bottom = el.getBoundingClientRect().bottom;
                    if (bottom > 500) {
                        console.log("[LAYOUT DEBUG] Large element found: classes=" + el.className + ", clientHeight=" + el.clientHeight + ", innerText length=" + (el.innerText ? el.innerText.trim().length : 0) + ", bottom=" + bottom);
                    }
                    rBoxBottoms.push(bottom);
                });
                
                let contentMaxY = rBoxBottoms.length > 0 ? Math.max(...rBoxBottoms) : 0;
                console.log("[LAYOUT DEBUG] contentMaxY: " + contentMaxY);
                if (contentMaxY > 0) {
                    let canvasRect = canvas.getBoundingClientRect();
                    let actualContentHeight = contentMaxY - canvasRect.top;
                    console.log("[LAYOUT DEBUG] canvasRect.top: " + canvasRect.top + ", actualContentHeight: " + actualContentHeight);
                    // Add a tiny buffer to avoid cutting off descenders
                    actualContentHeight += 2;
                    
                    // CUSTOM TEMPLATE ENHANCEMENT: Thick border + RTI Footer
                    const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                    if (data.template_id === 'custom' && rawLayout.includes('patterng')) {
                        const customBorderColor = data.border_color || '#F8E71C';
                        
                        // Apply thick border to the container
                        st.innerHTML += `
                            .newspaper-container { 
                                border: 15px solid ${customBorderColor} !important; 
                                padding-bottom: 75px !important;
                            }
                        `;
                        
                        // Build the RTI footer
                        const footerEl = document.createElement('div');
                        footerEl.style.position = 'absolute';
                        footerEl.style.bottom = '0';
                        footerEl.style.left = '0';
                        footerEl.style.width = '100%';
                        footerEl.style.height = '60px';
                        footerEl.style.backgroundColor = customBorderColor;
                        footerEl.style.display = 'flex';
                        footerEl.style.justifyContent = 'space-between';
                        footerEl.style.alignItems = 'center';
                        footerEl.style.padding = '0 30px';
                        footerEl.style.boxSizing = 'border-box';
                        footerEl.style.zIndex = '100';
                        
                        // We use the logo_url if provided, else plain text logo
                        let logoHtml = '';
                        if (data.logo_url) {
                            logoHtml = `<img src="${data.logo_url}" style="height: 40px; object-fit: contain;">`;
                        } else {
                            logoHtml = `<h2 style="margin:0; color:#111; font-family:'Playfair Display',serif; font-size: 30px; font-weight:900;">RTI EXPRESS</h2>`;
                        }
                        
                        footerEl.innerHTML = `
                            <div>${logoHtml}</div>
                            <div style="color: #111; font-size: 14px; font-family: sans-serif; text-align: right; font-weight: bold;">
                                https://www.rtiexpress.com/clip/${data.id || ''}<br>
                                ${data.location || 'Local Edition'} (${data.publication_date || ''})
                            </div>
                        `;
                        
                        // Append directly to container so it sits at the absolute bottom
                        container.appendChild(footerEl);
                    }
                    
                    canvas.style.height = actualContentHeight + 'px';
                    canvas.style.minHeight = actualContentHeight + 'px';
                    canvas.style.maxHeight = actualContentHeight + 'px';
                    canvas.setAttribute('data-computed-height', actualContentHeight);
                }
                
                window.__LAYOUT_DONE__ = true;
            }

            setTimeout(() => { if (!window.__LAYOUT_DONE__) window.__LAYOUT_DONE__ = true; }, 10000);
            executeLayout();
        });
        </script>
        """

        # Combine the data block and the logic block
        script_block = data_script + "\n" + script_block

        if "</body>" in html:
            html = html.replace("</body>", f"{script_block}</body>")
        else:
            html += script_block

        # ── SAVE DEBUG HTML ──────────────────────────────────────────────────
        try:
            debug_path = os.path.join(os.path.dirname(__file__), "debug_last_render.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:
            print(f"[DEBUG] Could not save debug HTML: {e}")
            sys.stdout.flush()

        return html

    def _auto_crop_png(self, image_path: str) -> int:
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                width, height = img_rgb.size
                pixels = img_rgb.load()
                
                # Background tolerance (accounts for #FFFFFF down to #F5F1E8)
                def is_bg(r, g, b):
                    return r >= 235 and g >= 235 and b >= 220
                
                # 1. Detect bottom border thickness by checking the middle of the bottom edge
                border_height = 0
                mid_x = width // 2
                for y in range(height - 1, height - 20, -1):
                    r, g, b = pixels[mid_x, y]
                    if not is_bg(r, g, b):
                        border_height += 1
                    else:
                        break
                
                # If no clear bottom border found, fallback to 4px
                if border_height == 0: border_height = 4
                
                # 2. Find the actual content, ignoring the bottom border region and side borders
                last_content_row = 0
                # Scan avoiding the left and right 20 pixels to bypass side borders!
                for y in range(height - border_height - 1, -1, -1):
                    has_content = False
                    # Step by 2 for speed, starting past the left border and ending before the right border
                    for x in range(20, width - 20, 2): 
                        r, g, b = pixels[x, y]
                        if not is_bg(r, g, b):
                            has_content = True
                            break
                    if has_content:
                        last_content_row = y
                        break
                
                # Calculate how much whitespace we can remove
                whitespace_start = last_content_row + 15
                whitespace_end = height - border_height
                
                # Only squash if there is a significant amount of whitespace (e.g. > 10px)
                if whitespace_end > whitespace_start + 10:
                    new_height = whitespace_start + border_height
                    # Crop original image, not the converted RGB one, to preserve original format/colors
                    top_part = img.crop((0, 0, width, whitespace_start))
                    bottom_part = img.crop((0, height - border_height, width, height))
                    
                    new_img = Image.new(img.mode, (width, new_height))
                    new_img.paste(top_part, (0, 0))
                    new_img.paste(bottom_part, (0, whitespace_start))
                    new_img.save(image_path, "PNG")
                    return new_height
                
                return height
        except Exception as e:
            print(f"[CROP ERROR] {e}")
            return 0

    async def generate_clipping_assets(self, html_content: str, png_path: str | None = None, pdf_path: str | None = None):
        """Uses Playwright to render HTML and take both a PNG screenshot and/or a PDF print."""
        async with self.semaphore:
            _log_memory("generate_clipping_assets: Enter")
            chrome_path = _get_chromium_executable()
        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=256",
                "--disable-web-security",
                "--allow-file-access-from-files"
            ],
        }
        if chrome_path: launch_kwargs["executable_path"] = chrome_path

        max_attempts = 2
        for attempt in range(max_attempts):
            browser = None
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    page = await browser.new_page(viewport={"width": 1200, "height": 1600}, device_scale_factor=2)
                    def handle_console(msg):
                        if "net::ERR_UNKNOWN_URL_SCHEME" in msg.text or "Not allowed to load local resource" in msg.text:
                            return
                        print(f"[BROWSER] {msg.type.upper()}: {msg.text}")
                    page.on("console", handle_console)
                    page.set_default_timeout(300000)

                    if html_content.startswith("http"): await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                    else: await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                    await page.wait_for_function("window.__LAYOUT_DONE__ === true", timeout=25000)

                    layout_info = await page.evaluate("""() => {
                        const canvas = document.getElementById('compositor-canvas');
                        const cont = document.querySelector('.newspaper-container');
                        
                        if (canvas && cont) {
                            // Find the absolute lowest point of any content in the canvas
                            let realMaxY = 0;
                            const computedAttr = canvas.getAttribute('data-computed-height');
                            if (computedAttr) {
                                realMaxY = parseFloat(computedAttr);
                            } else {
                                canvas.querySelectorAll('img, p, .image-caption, .nc-image-caption').forEach(el => {
                                    const rect = el.getBoundingClientRect();
                                    const canvasRect = canvas.getBoundingClientRect();
                                    const bottom = rect.bottom - canvasRect.top;
                                    if (bottom > realMaxY) {
                                        realMaxY = bottom;
                                    }
                                });
                            }
                            
                            if (realMaxY > 0) {
                                canvas.style.setProperty('flex', 'none', 'important');
                                canvas.style.setProperty('height', (realMaxY + 4) + 'px', 'important');
                                canvas.style.setProperty('min-height', '0px', 'important');
                                canvas.style.setProperty('max-height', (realMaxY + 4) + 'px', 'important');
                            }
                            
                            // Eliminate all whitespace at the bottom
                            cont.style.setProperty('padding-bottom', '0px', 'important');
                            cont.style.setProperty('min-height', '0px', 'important');
                            cont.style.setProperty('margin-bottom', '0px', 'important');
                            
                            // AGGRESSIVE SHRINK WRAP: Force container height to match canvas bottom
                            const canvasBottom = canvas.getBoundingClientRect().bottom;
                            const contTop = cont.getBoundingClientRect().top;
                            const exactHeight = Math.ceil(canvasBottom - contTop);
                            cont.style.setProperty('height', exactHeight + 'px', 'important');
                            cont.style.setProperty('max-height', exactHeight + 'px', 'important');
                        }

                        // Wait for any final reflows
                        const finalCont = document.querySelector('.newspaper-container');
                        if (finalCont) {
                            // As per requirements: "finalHeight = wrapper.getBoundingClientRect().height + bottomPadding"
                            const finalRect = finalCont.getBoundingClientRect();
                            const finalHeight = Math.ceil(finalRect.height);
                            
                            // Apply the final exact calculated height to the container
                            finalCont.style.setProperty('height', finalHeight + 'px', 'important');
                            finalCont.style.setProperty('max-height', finalHeight + 'px', 'important');
                            
                            return { width: Math.ceil(finalRect.width), height: finalHeight };
                        }

                        return { width: 1200, height: document.documentElement.scrollHeight };
                    }""")
                    
                    await page.set_viewport_size({"width": 1200, "height": layout_info.get("height", 1600) + 20})

                    final_h_px = None
                    if png_path:
                        await page.locator('.newspaper-container').first.screenshot(path=png_path, type="png")
                        # Run the PIL image auto-crop
                        final_h_px = self._auto_crop_png(png_path)
                        
                    if pdf_path:
                        pdf_h = (final_h_px / 2.0) if final_h_px else layout_info.get('height', 1600)
                        await page.pdf(path=pdf_path, width=f"{layout_info.get('width', 1060)/96.0}in", height=f"{(pdf_h+15)/96.0}in", print_background=True, margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"})

                    await browser.close()
                    return
            except Exception as e:
                if attempt == max_attempts - 1: raise
            finally:
                if browser: await browser.close()
                gc.collect()

    async def generate_png(self, html_content: str, output_path: str):
        await self.generate_clipping_assets(html_content, png_path=output_path)

    async def generate_pdf(self, html_content: str, output_path: str):
        await self.generate_clipping_assets(html_content, pdf_path=output_path)


render_service = RenderService()

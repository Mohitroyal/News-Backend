import os
import glob
import logging
import sys
import gc
import re
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
        # 2. Section & Raw Text Handling - Preserve AI-formatted sections if available!
        existing_sections = data.get("sections")
        raw_text_input = data.get("article_text") or data.get("raw_content") or data.get("article_content") or ""

        if isinstance(existing_sections, str) and existing_sections.strip():
            sections_input = [existing_sections.strip()]
        elif isinstance(existing_sections, list) and any(isinstance(s, str) and s.strip() for s in existing_sections):
            sections_input = [s.strip() for s in existing_sections if isinstance(s, str) and s.strip()]
        elif raw_text_input and isinstance(raw_text_input, str) and raw_text_input.strip():
            raw_clean = raw_text_input.replace('\r\n', '\n').replace('\r', '\n').strip()
            split_p = [p.strip() for p in raw_clean.split('\n') if p.strip()]
            sections_input = split_p if split_p else [raw_clean]
        else:
            sections_input = ["భోగాపురం మండలంలో వైఎస్ఆర్ కాంగ్రెస్ పార్టీ అధినేత వైఎస్ జగన్ మోహన్ రెడ్డి పర్యటనకు ప్రజల నుండి విశేష స్పందన లభించింది. పర్యటన పొడవునా వేలాదిగా తరలివచ్చిన ప్రజలు మరియు కార్యకర్తలు ఆయనకు ఘన స్వాగతం పలికారు."]

        # 2a. Clean unicode non-breaking spaces (\u00a0, \u200b), normalize punctuation & preserve full paragraphs
        processed_sections = []
        for sec in sections_input:
            if not isinstance(sec, str):
                continue
            # Replace non-breaking spaces & zero-width spaces with standard spaces
            clean_sec = sec.replace('\u00a0', ' ').replace('\u200b', ' ').strip()
            clean_sec = re.sub(r'^[*\-•]\s*', '', clean_sec)
            if not clean_sec:
                continue
            # Ensure space after punctuation (.,!?:;।) if followed directly by a letter/glyph
            clean_sec = re.sub(r'([.,!?:;।])([^\s\d])', r'\1 \2', clean_sec)
            processed_sections.append(clean_sec)
                
        if not processed_sections:
            processed_sections = ["ఈ పత్రికా క్లిప్పింగ్ కోసం శీర్షిక మరియు వివరాలు విజయవంతంగా రూపొందించబడ్డాయి."]

        data["sections"] = processed_sections

        # 2b. Auto-extract summary and key takeaways if missing
        if not data.get("summary") or not data.get("bullet_points") or not isinstance(data.get("bullet_points"), list) or len(data.get("bullet_points")) == 0:
            try:
                from app.services.grok_service import grok_service
                full_sec_text = "\n\n".join(data["sections"])
                clean_sum, clean_bps = grok_service._extract_summary_and_bullets(full_sec_text)
                if not data.get("summary") or not str(data.get("summary")).strip():
                    data["summary"] = clean_sum
                if not data.get("bullet_points") or not isinstance(data.get("bullet_points"), list) or len(data.get("bullet_points")) == 0:
                    data["bullet_points"] = clean_bps
            except Exception as sum_err:
                print(f"[WARNING] Summary fallback extraction error: {sum_err}")

        # 2c. Enforce complete 4-5 bullet points (max 135 chars each) to fit container cleanly
        raw_bps = data.get("bullet_points") or []
        if isinstance(raw_bps, list):
            formatted_bps = []
            for bp in raw_bps:
                clean_bp = str(bp).strip()
                clean_bp = re.sub(r'^[•\-\*\d\.\s]+', '', clean_bp)
                if len(clean_bp) > 135:
                    clean_bp = clean_bp[:132].rsplit(' ', 1)[0] + "..."
                if clean_bp and clean_bp not in formatted_bps:
                    formatted_bps.append(clean_bp)
                if len(formatted_bps) >= 5:
                    break
            data["bullet_points"] = formatted_bps[:5]

        if data.get("summary") and len(str(data["summary"])) > 380:
            data["summary"] = str(data["summary"])[:375].rsplit(' ', 1)[0] + "..."

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
            "custom": {
                "primary_color": "#1d70b8",
                "accent_color": "#1d70b8",
                "publication_name": "RTI Express",
                "logo_url": f"{self._logo_base}/rti_express.svg",
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

        # Extract reporter details for top-left embedding
        if not data.get("reporter_name"):
            data["reporter_name"] = data.get("author") or data.get("author_name") or data.get("reporter") or data.get("byline") or data.get("user_name") or data.get("full_name") or ""
        if not data.get("reporter_image"):
            data["reporter_image"] = data.get("author_image") or data.get("reporter_photo") or data.get("avatar_url") or data.get("profile_image") or ""

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
                /* High-DPI font smoothing & crisp text rendering */
                html, body, .newspaper-container, div, p, span, h1, h2, h3, h4 {{
                    -webkit-font-smoothing: antialiased !important;
                    -moz-osx-font-smoothing: grayscale !important;
                    text-rendering: optimizeLegibility !important;
                }}
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
            "language": data.get("language", "") or data.get("language_name", "English"),
            "language_name": data.get("language_name", "English") or data.get("language", "English"),
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
        
        async function startCompositorLayout() {
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
                const WAIT_TIMEOUT = 800;
                try {
                    await Promise.race([
                        document.fonts ? document.fonts.ready : Promise.resolve(),
                        new Promise(r => setTimeout(r, WAIT_TIMEOUT))
                    ]);
                } catch(e) {}

                const imgPromises = Array.from(document.images).map(img => {
                    if (img.complete || !img.src || !img.src.startsWith('http')) return Promise.resolve();
                    return Promise.race([
                        new Promise(r => {
                            img.onload = r;
                            img.onerror = r;
                        }),
                        new Promise(r => setTimeout(r, WAIT_TIMEOUT))
                    ]);
                });
                await Promise.all(imgPromises);
            }

            const TARGET_MAX_HEIGHT = 1600;
            const urls = data.image_urls || [];
            const captions = data.image_captions || [];
            const imgCount = urls.length;
            
            let aspectRatios = [];
            let orientations = [];

            // getImageDimensions utility
            async function getImageDimensions(url) {
                if (!url) return { width: 800, height: 600 };
                const existingImg = Array.from(document.images).find(img => img.src === url || img.getAttribute('src') === url);
                if (existingImg && existingImg.naturalWidth && existingImg.naturalHeight) {
                    return { width: existingImg.naturalWidth, height: existingImg.naturalHeight };
                }
                return Promise.race([
                    new Promise((resolve) => {
                        const img = new Image();
                        img.onload  = () => resolve({ width: img.naturalWidth || 800, height: img.naturalHeight || 600 });
                        img.onerror = () => resolve({ width: 800, height: 600 });
                        img.src = url;
                    }),
                    new Promise(resolve => setTimeout(() => {
                        resolve({ width: 800, height: 600 });
                    }, 1500))
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

            let langStr = (data.language || data.language_name || 'en').toLowerCase();
            let langKey = 'en';
            if (langStr.includes('telugu') || langStr === 'te') langKey = 'te';
            else if (langStr.includes('hindi') || langStr === 'hi') langKey = 'hi';
            else if (langStr.includes('kannada') || langStr === 'kn') langKey = 'kn';
            else if (langStr.includes('tamil') || langStr === 'ta') langKey = 'ta';
            else if (langStr.includes('malayalam') || langStr === 'ml') langKey = 'ml';

            let sumLabels = { 'te': 'సారాంశం', 'hi': 'सारांश', 'kn': 'ಸಾರಾಂಶ', 'ta': 'சுருக்கம்', 'ml': 'സംഗ్రహం', 'en': 'SUMMARY' };
            let bulLabels = { 'te': 'ముఖ్య అంశాలు', 'hi': 'मुख्य बिंदु', 'kn': 'ಪ್ರಮುಖ ಮುಖ್ಯಾంశాలు', 'ta': 'முக்கிய அம்சங்கள்', 'ml': 'ప్రధాన వివరాలు', 'en': 'KEY TAKEAWAYS' };

            let sumTitle = sumLabels[langKey] || 'SUMMARY';
            let bulTitle = bulLabels[langKey] || 'KEY TAKEAWAYS';

            function resolveColumns(colVal, charLen) {
                const s = String(colVal === undefined || colVal === null ? "auto" : colVal).toLowerCase().trim();
                const p = parseInt(s);
                if (!isNaN(p) && p >= 1 && p <= 4 && s !== "0" && s !== "auto") {
                    return p;
                }
                const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                const isSingleSideLayout = (urls.length === 1) && (rawLayout.includes('patterna') || (!rawLayout.includes('patternb') && !rawLayout.includes('patternd') && !rawLayout.includes('single') && !rawLayout.includes('hero') && !rawLayout.includes('patternc') && !rawLayout.includes('patterng')));
                if (isSingleSideLayout) {
                    return 2;
                }
                if (charLen < 800) {
                    return 2;
                }
                return 3;
            }

            function getObstacles(W_canvas, S_img, imgHeightPx, H_canvas) {
                H_canvas = H_canvas || 1200;
                const TARGET_MAX_HEIGHT = H_canvas;
                const obstacles = [];
                const templateIdStr = String(data.template_id || "").toLowerCase().replace(/[^a-z0-9]/g, "");
                const logoIdStr = String(data.logo_id || "").toLowerCase().replace(/[^a-z0-9]/g, "");
                const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                const showSummaryFlag = data.show_summary === true || String(data.show_summary).toLowerCase() === "true";
                const isCustom = (templateIdStr.includes("custom") || logoIdStr.includes("custom")) && showSummaryFlag;
                const showSummary = isCustom && data.show_summary !== false && String(data.show_summary).toLowerCase() !== "false";

                if (urls.length > 0) {
                    const aspect0 = (aspectRatios && aspectRatios.length > 0 && aspectRatios[0]) ? aspectRatios[0] : 1.33;
                    let S_scale = S_img;
                    let gap = 60;
                    // Dynamically rescale images based on text content size to prevent overflowing short articles
                    if (totalChars > 0 && totalChars < 3000) {
                        const scaleFactor = Math.max(0.5, 1.0 - (3000 - totalChars) / 3500);
                        S_scale = S_img * scaleFactor;
                        gap = 30;
                    }
                    // Bulletproof pattern matching: handles "Pattern B", "pattern_b", "patternB", etc.
                    const isArticleStyle = rawLayout.includes('articlestyle');
                    let isPatternB = rawLayout.includes('patternb') || rawLayout.includes('patterna') || rawLayout.includes('patternd') || rawLayout.includes('patternc') || rawLayout.includes('patterne') || isArticleStyle || isCustom;
                    const isSinglePatternC = !isCustom && rawLayout.includes('patternc') && urls.length === 1;
                    const isSinglePatternA = !isCustom && rawLayout.includes('patterna') && urls.length === 1;
                    if (isSinglePatternC || isSinglePatternA) {
                        isPatternB = false;
                    }
                    if (isCustom || rawLayout === "default" || rawLayout === "" || rawLayout === "auto") {
                        isPatternB = true;
                    }
                    const isDoublePatternB = (isPatternB && urls.length === 2) && (rawLayout.includes('patternc') || rawLayout.includes('patterna') || rawLayout === "default");
                    const isTriplePatternB = isPatternB && urls.length >= 3;

                    const isSingleLeft75 = (urls.length === 1) && (rawLayout.includes('patterng') || rawLayout.includes('left75') || rawLayout.includes('pattern75') || rawLayout.includes('75left') || rawLayout.includes('75'));
                    
                    if (isSingleLeft75) {
                        // Single image: Left side covering 75% height, width dynamically adjusted to aspect ratio
                        let a0 = aspectRatios[0] || 1.2;
                        let targetTotalH = Math.max(H_canvas, 1000);
                        let h0 = Math.round(targetTotalH * 0.75);
                        let desiredW = Math.round(h0 * a0 * 0.55);
                        let minW = Math.round(W_canvas * 0.38);
                        let maxW = Math.round(W_canvas * 0.50);
                        let w0 = Math.max(minW, Math.min(maxW, desiredW));
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor(w0 / 6.5))) * 15 + 8 : 0;
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: 0,
                            y: 0,
                            w: w0,
                            h: Math.round(h0 + capAllowance0),
                            imgH: Math.round(h0),
                            isCentered: false,
                            visW: w0,
                            objectFit: 'cover',
                            objectPosition: 'center center'
                        });
                    } else if (rawLayout.includes('patterng')) {
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
                        }
                    } else if (isTriplePatternB) {
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
                    } else {
                    
                    let N_layout_cols = resolveColumns(data.layout_columns, totalChars);
                    let grid_gap = 24;
                    let single_col_w = Math.round((W_canvas - (N_layout_cols - 1) * grid_gap) / N_layout_cols);
                    let side_w = (N_layout_cols >= 3) ? single_col_w : Math.round((W_canvas - grid_gap) * 0.48);
                    
                    let w0 = side_w;
                    let isPatternB_centered = false;
                    let imgVisW = w0;
                    let h0 = Math.min(w0 / aspect0, 360);
                    let imgX = Math.round(W_canvas - w0);
                    let imgY = 0;
                    
                    if (isDoublePatternB) {
                        let a0 = aspect0 || 1.0;
                        let a1 = aspectRatios[1] || 1.0;
                        let gap = 20;
                        let availW = W_canvas - gap;
                        let sumAspect = a0 + a1;
                        w0 = Math.round(availW * (a0 / sumAspect));
                        let sharedH = Math.min(Math.round(availW / sumAspect), 380);
                        h0 = sharedH;
                        imgX = 0;
                        imgY = 0; // Both images at the top
                        imgVisW = w0;
                        isPatternB_centered = false;
                        
                        // Save parameters for the second image
                        window.__db_sharedH = sharedH;
                        window.__db_w0 = w0;
                        window.__db_gap = gap;
                    } else if (rawLayout.includes('patternb') || rawLayout.includes('patternd') || rawLayout.includes('single') || rawLayout.includes('hero') || isSinglePatternC || rawLayout.includes('patternc')) {
                        w0 = W_canvas;
                        imgX = 0;
                        imgY = 0;
                        let dynamicH = Math.round(W_canvas / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 900) * 0.65);
                        h0 = Math.min(dynamicH, maxAllowedH);
                        if (dynamicH > maxAllowedH) {
                            imgVisW = Math.round(maxAllowedH * aspect0);
                        } else {
                            imgVisW = W_canvas;
                        }
                        isPatternB_centered = true;
                    } else if (isSinglePatternA || rawLayout.includes('patterna')) {
                        w0 = side_w;
                        let dynamicH = Math.round(w0 / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 900) * 0.55);
                        h0 = Math.min(dynamicH, maxAllowedH);
                        imgVisW = w0;
                        imgX = 0; // Left side
                        isPatternB_centered = false;
                    } else {
                        // Default / Custom with 1 image: Right side side-by-side with text
                        w0 = side_w;
                        let dynamicH = Math.round(w0 / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 900) * 0.55);
                        h0 = Math.min(dynamicH, maxAllowedH);
                        imgVisW = w0;
                        imgX = Math.round(W_canvas - w0);
                        isPatternB_centered = false;
                    }
                    
                    let cap0 = String(captions[0] || '').trim();
                    let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor((isPatternB_centered ? imgVisW : w0) / 6.5))) * 15 + 8 : 0;
                    
                    obstacles.push({
                        url: urls[0],
                        caption: captions[0] || '',
                        x: imgX,
                        y: imgY,
                        w: Math.round(w0),
                        h: Math.round(h0 + capAllowance0),
                        imgH: Math.round(h0),
                        isCentered: isPatternB_centered,
                        visW: Math.round(imgVisW),
                        objectFit: 'contain',
                        objectPosition: 'center center'
                    });

                    if (urls.length > 1) {
                        if (isDoublePatternB) {
                            let h1 = window.__db_sharedH;
                            let w0 = window.__db_w0;
                            let gap = window.__db_gap;
                            let x1 = w0 + gap;
                            let w1 = W_canvas - x1; // Stretches cleanly to right edge
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
                            let x1 = W_canvas - w1; // Align secondary image on right side below Hero
                            
                            obstacles.push({
                                url: urls[1],
                                caption: captions[1] || '',
                                x: Math.round(x1),
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
                }
                }
                if (isCustom && (data.summary || (data.bullet_points && data.bullet_points.length > 0)) && data.show_summary !== false && String(data.show_summary).toLowerCase() !== "false") {
                    let maxImgY = 0;
                    obstacles.forEach(o => {
                        if (o.type !== 'summary_bullets') {
                            maxImgY = Math.max(maxImgY, o.y + o.h);
                        }
                    });
                    // Position summary box cleanly below top image & text column area
                    let summaryY = Math.max(maxImgY, 350) + 16;
                    obstacles.push({
                        type: 'summary_bullets',
                        x: 0,
                        y: Math.round(summaryY),
                        w: W_canvas,
                        h: 260
                    });
                }
                return obstacles;
            }

            function runLayoutPass(conf, S, H_layout, isFinal) {
                // Clear the compositor canvas
                canvas.innerHTML = '';
                
                // Get canvas width
                const W_canvas = canvas.offsetWidth || 1060;
                
                // Calculate columns
                let N = resolveColumns(data.layout_columns, totalChars);
                
                const G = 24; // Column gap in pixels
                const W_col = (W_canvas - (N - 1) * G) / N;
                
                const H_canvas = H_layout;
                
                // Calculate image dimensions and create absolute obstacles
                const imgHeightPx = Math.round(0.58 * W_canvas);
                let S_img = S || 1.0;
                const obstacles = getObstacles(W_canvas, S_img, imgHeightPx, H_canvas);

                // Render summary box early to measure its exact dynamic height from DOM
                const sumObs = obstacles.find(o => o.type === 'summary_bullets');
                if (sumObs) {
                    const measuredH = renderSummaryBulletsBox(sumObs.y);
                    if (measuredH > 0) {
                        sumObs.h = measuredH;
                    }
                }

                // Render absolute images onto canvas if it's the final pass
                if (isFinal) {
                    obstacles.forEach(obs => {
                        if (obs.type === 'summary_bullets') {
                            // Already rendered above during dynamic height measurement
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
                        imgEl.style.border = 'none';
                        imgEl.style.padding = '0';
                        imgEl.style.background = 'var(--bg-color, #FFFFFF)';
                        imgEl.style.zIndex = '5';
                        
                        let cleanCap = obs.caption;
                        if (typeof cleanCap === 'object' && cleanCap !== null) {
                            cleanCap = cleanCap.caption || cleanCap.text || cleanCap.title || '';
                        }
                        let capStr = String(cleanCap || '').trim();
                        if (capStr === '[object Object]') capStr = '';

                        let captionHeight = 0;
                        if (capStr) {
                            const wrapW = obs.isCentered ? obs.visW : obs.w;
                            const charsPerLine = Math.max(1, Math.floor(wrapW / 6.5));
                            const lines = Math.ceil(capStr.length / charsPerLine);
                            captionHeight = lines * 15;
                        }
                        const imgH = obs.imgH || (obs.h - (captionHeight ? captionHeight + 8 : 0));
                        
                        let captionHtml = capStr ? `<div class="image-caption nc-image-caption" style="font-size: 11px; font-style: italic; color: #444; margin-top: 4px; line-height: 1.3; width: 100%; text-align: center; word-wrap: break-word;">${capStr}</div>` : '';
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
                                : `width: ${obs.visW}px; border: none; padding: 0; background: var(--bg-color, #FFFFFF); display: flex; flex-direction: column; align-items: center; box-sizing: border-box;`;

                            imgEl.innerHTML = '<div style="' + innerStyle + '"><img src="' + obs.url + '" style="width: 100%; height: ' + imgH + 'px; max-height: none !important; object-fit: ' + (obs.objectFit || 'contain') + '; object-position: ' + (obs.objectPosition || 'center center') + '; display: block;" />' + captionHtml + '</div>';
                        } else {
                            imgEl.innerHTML = '<img src="' + obs.url + '" style="width: 100%; height: ' + imgH + 'px; max-height: none !important; object-fit: ' + (obs.objectFit || 'contain') + '; object-position: ' + (obs.objectPosition || 'center center') + '; display: block;" />' + captionHtml;
                        }
                        canvas.appendChild(imgEl);
                    });
                }
                
                let inflatedObstacles = obstacles.map(obs => {
                    return {
                        x: obs.x - 8,
                        y: obs.y - 8,
                        w: obs.w + 16,
                        h: obs.h + 16
                    };
                });
                
                const rawLayoutStr = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                if (urls.length === 2 && (rawLayoutStr.includes('patternc') || rawLayoutStr.includes('patterna') || rawLayoutStr.includes('patternb') || rawLayoutStr === 'default' || rawLayoutStr === '')) {
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
                        
                        regions.push({ rBox, height: h, y: int.yStart, col: c });
                    });
                }
                
                // Strict multi-column newspaper reading flow:
                // Column by column (Column 0 -> Column 1 -> Column 2), and top-to-bottom within each column.
                regions.sort((a, b) => {
                    if (a.col !== b.col) {
                        return a.col - b.col;
                    }
                    return a.y - b.y;
                });
                
                let paragraphs = [];
                for (const sec of (data.sections || [])) {
                    const cleanSec = String(sec || '').replace(/[\u00a0\u200b]/g, ' ').replace(/\s+/g, ' ').trim();
                    if (cleanSec) {
                        paragraphs.push(cleanSec);
                    }
                }
                if (paragraphs.length === 0) {
                    const rawFb = String(data.article_text || data.article_content || data.raw_content || '').replace(/[\u00a0\u200b]/g, ' ').replace(/\s+/g, ' ').trim();
                    if (rawFb) {
                        paragraphs.push(rawFb);
                    } else {
                        paragraphs.push("భోగాపురం మండలంలో వైఎస్ఆర్ కాంగ్రెస్ పార్టీ అధినేత వైఎస్ జగన్ మోహన్ రెడ్డి పర్యటనకు ప్రజల నుండి విశేష స్పందన లభించింది. పర్యటన పొడవునా వేలాదిగా తరలివచ్చిన ప్రజలు మరియు కార్యకర్తలు ఆయనకు ఘన స్వాగతం పలికారు.");
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
                        
                        let lowW = 0;
                        let highW = words.length;
                        let fitCount = 0;
                        while (lowW <= highW) {
                            let midW = Math.floor((lowW + highW) / 2);
                            testP.innerText = words.slice(0, midW).join(' ');
                            if (activeRegion.rBox.scrollHeight <= activeRegion.height) {
                                fitCount = midW;
                                lowW = midW + 1;
                            } else {
                                highW = midW - 1;
                            }
                        }
                        let wIdx = fitCount;
                        activeRegion.rBox.removeChild(testP);
                        if (wIdx > 0) {
                            const fitP = p.cloneNode();
                            fitP.innerText = words.slice(0, wIdx).join(' ');
                            activeRegion.rBox.appendChild(fitP);
                            const rem = words.slice(wIdx).join(' ');
                            if (rem.trim().length > 0) paragraphs.splice(pIdx, 1, rem); else pIdx++;
                        } else {
                            // If not even 1 word fits, force break word by characters
                            const chars = text.split('');
                            let cIdx = 0;
                            const testCharP = p.cloneNode();
                            activeRegion.rBox.appendChild(testCharP);
                            for (; cIdx < chars.length; cIdx++) {
                                testCharP.innerText = chars.slice(0, cIdx + 1).join('');
                                if (activeRegion.rBox.scrollHeight > activeRegion.height) break;
                            }
                            activeRegion.rBox.removeChild(testCharP);
                            if (cIdx > 0) {
                                const fitP = p.cloneNode();
                                fitP.innerText = chars.slice(0, cIdx).join('');
                                activeRegion.rBox.appendChild(fitP);
                                const rem = chars.slice(cIdx).join('');
                                if (rem.trim().length > 0) paragraphs.splice(pIdx, 1, rem); else pIdx++;
                            } else {
                                // 0 chars fit in this small region: do NOT drop paragraph, preserve for next region
                            }
                        }
                        currentRegionIdx++;
                        activeRegion = regions[currentRegionIdx];
                    } else pIdx++;
                }
                
                if (regions.length === 0 || pIdx < paragraphs.length) {
                    return false; // Did not fit all paragraphs
                }
                
                // Third image is now handled as an absolute obstacle at bottom-right
                
                if (isFinal) {
                    let maxY = 0;
                    regions.forEach(r => {
                        if (r.rBox.lastElementChild && r.rBox.innerText.trim() !== '') {
                            const contentHeight = r.rBox.scrollHeight;
                            r.rBox.style.height = `${contentHeight}px`;
                            r.rBox.style.overflow = 'visible';
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

            function renderSummaryBulletsBox(yTop) {
                const templateIdStr = String(data.template_id || "").toLowerCase().replace(/[^a-z0-9]/g, "");
                const logoIdStr = String(data.logo_id || "").toLowerCase().replace(/[^a-z0-9]/g, "");
                const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                const showSummaryFlag = data.show_summary === true || String(data.show_summary).toLowerCase() === "true";
                const isCustom = (templateIdStr.includes("custom") || logoIdStr.includes("custom")) && showSummaryFlag;
                const showSummary = isCustom && data.show_summary !== false && String(data.show_summary).toLowerCase() !== "false";
                if (!showSummary) {
                    return 0;
                }
                if ((!data.summary || !String(data.summary).trim()) && (!data.bullet_points || data.bullet_points.length === 0)) {
                    return 0;
                }
                const containerEl = document.createElement('div');
                containerEl.className = 'nc-absolute-summary';
                containerEl.style.position = 'absolute';
                containerEl.style.left = '0px';
                containerEl.style.top = `${yTop}px`;
                containerEl.style.width = '100%';
                containerEl.style.boxSizing = 'border-box';
                containerEl.style.display = 'flex';
                containerEl.style.flexDirection = 'row';
                containerEl.style.gap = '24px';
                containerEl.style.zIndex = '5';
                containerEl.style.fontFamily = 'var(--primary-font, "Playfair Display", serif)';
                
                let langStr = (data.language || data.language_name || 'en').toLowerCase();
                let langKey = 'en';
                if (langStr.includes('telugu') || langStr === 'te') langKey = 'te';
                else if (langStr.includes('hindi') || langStr === 'hi') langKey = 'hi';
                else if (langStr.includes('kannada') || langStr === 'kn') langKey = 'kn';
                else if (langStr.includes('tamil') || langStr === 'ta') langKey = 'ta';
                else if (langStr.includes('malayalam') || langStr === 'ml') langKey = 'ml';

                let sumLabels = { 'te': 'సారాంశం', 'hi': 'सारांश', 'kn': 'ಸಾರಾಂಶ', 'ta': 'சுരുக்கம்', 'ml': 'സംഗ్రహం', 'en': 'SUMMARY' };
                let bulLabels = { 'te': 'ముఖ్య అంశాలు', 'hi': 'मुख्य बिंदु', 'kn': 'ಪ್ರಮುಖ ముఖ్యాంಶలు', 'ta': 'முக்கிய அம்சங்கள்', 'ml': 'പ്രధాన വിവരాలు', 'en': 'KEY TAKEAWAYS' };

                let sumTitle = sumLabels[langKey] || 'SUMMARY';
                let bulTitle = bulLabels[langKey] || 'KEY TAKEAWAYS';

                let bpHtml = (data.bullet_points || []).slice(0, 4).map(bp => `<li style="margin-bottom: 6px;">${bp}</li>`).join('');
                
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
                    sumBg = '#F8E71C';
                    bulBg = '#00B7C6';
                    sumHeadingColor = '#000000';
                    sumTextColor = '#000000';
                    bulHeadingColor = '#FFFFFF';
                    listStyle = '"✦  "';
                    sumBorder = 'transparent';
                    bulBorder = 'transparent';
                }
                
                let summaryBoxHtml = '';
                if (data.summary && String(data.summary).trim()) {
                    summaryBoxHtml = `
                        <div style="flex: 1; background-color: ${sumBg}; padding: 20px; border-radius: 12px; border: 1px solid ${sumBorder}; display: flex; flex-direction: column; justify-content: flex-start;">
                            <div style="font-weight: 800; font-size: 15px; text-transform: uppercase; color: ${sumHeadingColor}; margin-bottom: 8px; letter-spacing: 0.5px;">${sumTitle}</div>
                            <div style="font-size: 14px; line-height: 1.6; color: ${sumTextColor}; text-align: justify;">${data.summary}</div>
                        </div>
                    `;
                }

                let bulletBoxHtml = '';
                if (data.bullet_points && data.bullet_points.length > 0) {
                    bulletBoxHtml = `
                        <div style="flex: 1; background-color: ${bulBg}; padding: 20px; border-radius: 12px; border: 1px solid ${bulBorder}; display: flex; flex-direction: column; justify-content: flex-start; color: ${bulTextColor};">
                            <div style="font-weight: 800; font-size: 15px; text-transform: uppercase; color: ${bulHeadingColor}; margin-bottom: 8px; letter-spacing: 0.5px;">${bulTitle}</div>
                            <ul style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6; list-style-type: ${listStyle};">
                                ${bpHtml}
                            </ul>
                        </div>
                    `;
                }

                containerEl.innerHTML = summaryBoxHtml + bulletBoxHtml;
                canvas.appendChild(containerEl);
                return containerEl.offsetHeight || 180;
            }

            async function executeLayout() {
                const dims = await Promise.all(urls.map(url => getImageDimensions(url)));
                aspectRatios = dims.map(d => (d.width && d.height) ? (d.width / d.height) : 1.0);
                await waitReady();
                
                // Force headline to fit on a single line
                const hl = document.querySelector('.headline');
                if (hl) {
                    hl.style.whiteSpace = 'normal';
                    hl.style.wordBreak = 'break-word';
                    hl.style.display = 'block';
                    hl.style.width = '100%';
                }

                // Dynamic scaling factor S based on character count
                let S = 1.0 - (totalChars - 1400) / 3000;
                S = Math.max(0.75, Math.min(1.25, S));

                const W_canvas = canvas.offsetWidth || 1060;
                const N = resolveColumns(data.layout_columns, totalChars);
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
                const conf = { fontSize: Math.min(maxFontSize, estFontSize), lineHeight: 1.35, paraMargin: 12, imgMaxPct: 0.58, padding: 32 };

                // Step 1: Find best font size that fits 100% of text within H_avail
                let targetFs = Math.min(maxFontSize, estFontSize);
                let foundFit = false;
                
                for (let fs = targetFs; fs >= 11.0; fs -= 0.5) {
                    conf.fontSize = fs;
                    if (runLayoutPass(conf, S, H_avail, false)) {
                        foundFit = true;
                        targetFs = fs;
                        break;
                    }
                }

                const rawLayoutStr = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                const isSingleLeft75Layout = (urls.length === 1) && (rawLayoutStr.includes('patterng') || rawLayoutStr.includes('left75') || rawLayoutStr.includes('pattern75') || rawLayoutStr.includes('75left') || rawLayoutStr.includes('75'));
                let low = isSingleLeft75Layout ? Math.max(900, Math.round(maxObstacleY + 60)) : Math.max(300, Math.round(maxObstacleY + 30));
                let high = H_avail;
                let H_best = H_avail;

                if (foundFit) {
                    // Binary search for minimum height at targetFs
                    conf.fontSize = targetFs;
                    H_best = high;
                    for (let step = 0; step < 8; step++) {
                        const mid = Math.round((low + high) / 2);
                        if (runLayoutPass(conf, S, mid, false)) {
                            H_best = mid;
                            high = mid - 1;
                        } else {
                            low = mid + 1;
                        }
                    }
                } else {
                    // Content is exceptionally long: fix fontSize at 11.0px and expand height until it fits
                    conf.fontSize = 11.0;
                    low = H_avail;
                    high = H_avail + 6000;
                    H_best = high;
                    for (let step = 0; step < 10; step++) {
                        const mid = Math.round((low + high) / 2);
                        if (runLayoutPass(conf, S, mid, false)) {
                            H_best = mid;
                            high = mid - 1;
                        } else {
                            low = mid + 1;
                        }
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
                document.querySelectorAll('.nc-text-region-box p, .nc-absolute-image, .nc-image-caption').forEach(el => {
                    let rect = el.getBoundingClientRect();
                    if (rect.height > 0 && rect.bottom > 0) {
                        rBoxBottoms.push(rect.bottom);
                    }
                });
                
                let contentMaxY = rBoxBottoms.length > 0 ? Math.max(...rBoxBottoms) : 0;
                console.log("[LAYOUT DEBUG] contentMaxY: " + contentMaxY);
                if (contentMaxY > 0) {
                    let canvasRect = canvas.getBoundingClientRect();
                    let actualContentHeight = contentMaxY - canvasRect.top;
                    
                    actualContentHeight += 2;
                    
                    // CUSTOM TEMPLATE ENHANCEMENT: Thick border + RTI Footer
                    const rawLayout = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                    if (data.template_id === 'custom' && rawLayout.includes('patterng')) {
                        const customBorderColor = data.border_color || '#F8E71C';
                        
                        // Apply thick border to the container
                        st.innerHTML += `
                            .newspaper-container { 
                                border: 15px solid ${customBorderColor} !important; 
                                padding-bottom: 15px !important;
                            }
                        `;
                        
                        // Build the RTI footer
                        const footerEl = document.createElement('div');
                        footerEl.className = 'rti-custom-footer';
                        footerEl.style.position = 'relative';
                        footerEl.style.marginTop = '15px';
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
                        
                        // Append directly to container below canvas
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
            executeLayout().then(() => {
                window.__LAYOUT_DONE__ = true;
            }).catch(err => {
                console.error("[LAYOUT FATAL ERROR]", err && err.stack ? err.stack : err);
                window.__LAYOUT_DONE__ = true;
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startCompositorLayout);
        } else {
            startCompositorLayout();
        }
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
                
                # 2. Find the actual content, ignoring the bottom border region
                last_content_row = 0
                margin_x = max(15, int(width * 0.02))
                for y in range(height - border_height - 1, -1, -1):
                    has_content = False
                    for x in range(margin_x, width - margin_x, 2): 
                        r, g, b = pixels[x, y]
                        if not is_bg(r, g, b):
                            has_content = True
                            break
                    if has_content:
                        last_content_row = y
                        break
                
                # Calculate whitespace removal with generous 40px safety margin
                whitespace_start = min(height - border_height, last_content_row + 40)
                whitespace_end = height - border_height
                
                # Only crop if there is a massive chunk of empty whitespace (> 30px)
                if whitespace_end > whitespace_start + 30:
                    new_height = whitespace_start + border_height
                    top_part = img.crop((0, 0, width, whitespace_start))
                    bottom_part = img.crop((0, height - border_height, width, height))
                    
                    new_img = Image.new(img.mode, (width, new_height))
                    new_img.paste(top_part, (0, 0))
                    new_img.paste(bottom_part, (0, whitespace_start))
                    new_img.save(image_path, "PNG", optimize=True)
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
                    "--single-process",
                    "--js-flags=--max-old-space-size=96",
                    "--renderer-process-limit=1",
                    "--disable-v8-idle-tasks",
                    "--disable-extensions",
                    "--disable-component-update",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--disable-translate",
                    "--mute-audio",
                    "--no-first-run",
                    "--disable-web-security",
                    "--allow-file-access-from-files",
                    "--force-device-scale-factor=3.2",
                    "--high-dpi-support=1",
                    "--enable-use-zoom-for-dsf=true"
                ],
            }
            if chrome_path: launch_kwargs["executable_path"] = chrome_path

            max_attempts = 2
            for attempt in range(max_attempts):
                browser = None
                page = None
                try:
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(**launch_kwargs)
                        page = await browser.new_page(viewport={"width": 1200, "height": 1600}, device_scale_factor=3.2)
                        def handle_console(msg):
                            if "net::ERR_UNKNOWN_URL_SCHEME" in msg.text or "Not allowed to load local resource" in msg.text:
                                return
                            print(f"[BROWSER] {msg.type.upper()}: {msg.text}")
                        page.on("console", handle_console)
                        page.set_default_timeout(300000)

                        if html_content.startswith("http"):
                            await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                        else:
                            await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                        try:
                            await page.add_style_tag(content="""
                                * {
                                    -webkit-font-smoothing: antialiased !important;
                                    -moz-osx-font-smoothing: grayscale !important;
                                    text-rendering: optimizeLegibility !important;
                                }
                                img, .featured-image, .article-image, .logo-img, svg, canvas, picture {
                                    image-rendering: -webkit-optimize-contrast !important;
                                    image-rendering: high-quality !important;
                                    image-rendering: smooth !important;
                                    filter: none !important;
                                    mix-blend-mode: normal !important;
                                    max-width: 100% !important;
                                }
                            """)
                        except Exception:
                            pass

                        try:
                            await page.evaluate("Promise.race([document.fonts ? document.fonts.ready : Promise.resolve(), new Promise(r => setTimeout(r, 2000))])")
                        except Exception:
                            pass

                        for wait_i in range(30):
                            is_done = await page.evaluate("window.__LAYOUT_DONE__ === true")
                            print(f"[DEBUG LAYOUT POLL {wait_i}] is_done = {is_done}")
                            if is_done:
                                break
                            await asyncio.sleep(0.5)

                        try:
                            await page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
                        except Exception:
                            pass

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
                                
                                const customFooter = cont.querySelector('.rti-custom-footer');
                                if (!customFooter) {
                                    cont.style.setProperty('padding-bottom', '0px', 'important');
                                }
                                cont.style.setProperty('min-height', '0px', 'important');
                                cont.style.setProperty('margin-bottom', '0px', 'important');
                                
                                // AGGRESSIVE SHRINK WRAP: Force container height to match bottom of content + borders
                                const bottomTarget = customFooter || canvas;
                                const targetBottom = bottomTarget.getBoundingClientRect().bottom;
                                const contTop = cont.getBoundingClientRect().top;
                                const contStyle = window.getComputedStyle(cont);
                                const padBottom = customFooter ? 15 : parseFloat(contStyle.paddingBottom || '0');
                                const borderBottom = parseFloat(contStyle.borderBottomWidth || '0');
                                const exactHeight = Math.ceil(targetBottom - contTop + padBottom + borderBottom + 6);
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
                            final_h_px = self._auto_crop_png(png_path) or layout_info.get('height', 1600)
                            
                        if pdf_path:
                            pdf_h = (final_h_px / 2.0) if final_h_px else layout_info.get('height', 1600)
                            await page.pdf(path=pdf_path, width=f"{layout_info.get('width', 1060)/96.0}in", height=f"{(pdf_h+15)/96.0}in", print_background=True, margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"})

                        try:
                            if page: await page.close()
                        except Exception:
                            pass
                        try:
                            if browser: await browser.close()
                        except Exception:
                            pass
                        gc.collect()
                        return
                except Exception as e:
                    if attempt == max_attempts - 1: raise
                finally:
                    try:
                        if page: await page.close()
                    except Exception:
                        pass
                    try:
                        if browser: await browser.close()
                    except Exception:
                        pass
                    gc.collect()
                    gc.collect()

    async def generate_png(self, html_content: str, output_path: str):
        await self.generate_clipping_assets(html_content, png_path=output_path)

    async def generate_pdf(self, html_content: str, output_path: str):
        await self.generate_clipping_assets(html_content, pdf_path=output_path)


render_service = RenderService()

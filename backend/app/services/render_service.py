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
from typing import Dict, Any, Optional
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


def _get_chromium_executable() -> Optional[str]:
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
            fallback_img = "data:image/jpeg;base64,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"
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
            for k, v in branding[brand_key].items():
                if not data.get(k):
                    data[k] = v
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

        # Ensure date and time are available for templates (e.g. below reporter name)
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        current_date_str = now_ist.strftime("%d %b %Y")
        current_time_str = now_ist.strftime("%I:%M %p")
        current_datetime_str = f"{current_date_str} | {current_time_str}"

        pub_date = data.get("publication_date") or data.get("published_date") or data.get("date")
        if not pub_date:
            data["publication_date"] = current_date_str
            data["publication_time"] = current_time_str
            data["publication_date_time"] = current_datetime_str
        else:
            data["publication_date"] = str(pub_date)
            data["publication_time"] = data.get("publication_time") or current_time_str
            if any(t in str(pub_date).lower() for t in ["am", "pm", ":"]):
                data["publication_date_time"] = str(pub_date)
            else:
                data["publication_date_time"] = f"{pub_date} | {data['publication_time']}"

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

        raw_image_layout = str(data.get("image_layout") or "").lower().replace("_", "").replace("-", "").replace(" ", "").strip()
        template_key = template_name.replace(".html", "").lower().strip()
        data_tid = str(data.get("template_id") or "").lower().strip()
        
        _img_urls = data.get("image_urls") or ([data.get("image_url")] if data.get("image_url") else [])
        is_single_img = len(_img_urls) <= 1
        is_explicit_other_template = any(t in template_key or t in data_tid for t in ["bharath_reporter", "national_news", "custom"]) and raw_image_layout not in ["patternb", "heroimage", "singleimagepatternb"]
        
        is_pattern_b = (
            raw_image_layout in ["patternb", "heroimage", "singleimagepatternb"] or
            template_key in ["pattern_b", "hero-image", "hero_image"] or
            (is_single_img and not is_explicit_other_template)
        )

        if is_pattern_b:
            try:
                template = self.env.get_template("pattern_b/template.html")
            except Exception:
                try:
                    template = self.env.get_template("hero-image/template.html")
                except Exception:
                    template = self.env.get_template("master_layout.html")
        else:
            try:
                template = self.env.get_template(f"{template_key}/template.html")
            except Exception:
                try:
                    template = self.env.get_template(f"{template_key}.html")
                except Exception:
                    try:
                        template = self.env.get_template("rti_express/template.html")
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

        heading_bg = data.get('heading_bg')
        if heading_bg:
            if is_dark_hex(heading_bg):
                headline_text_color = "#FFFFFF" # Use white for dark backgrounds
            else:
                headline_text_color = "#111111" # Use dark text for light backgrounds
        else:
            headline_text_color = "#111111"

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

        if is_pattern_b:
            try:
                debug_path = os.path.join(os.path.dirname(__file__), "debug_last_render.html")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass
            return html

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
                return new Promise((resolve) => {
                    const img = new Image();
                    img.onload = () => resolve({ width: img.naturalWidth || 800, height: img.naturalHeight || 600 });
                    img.onerror = () => resolve({ width: 800, height: 600 });
                    img.src = url;
                    if (img.complete && img.naturalWidth) {
                        resolve({ width: img.naturalWidth, height: img.naturalHeight });
                    }
                });
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
                if (rawLayout.includes('patternd')) {
                    return 3;
                }
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
                        // Single image: Left side covering ~58% width, dynamic height based on text content
                        let w0 = Math.round(W_canvas * 0.58);
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor(w0 / 6.5))) * 15 + 8 : 0;
                        
                        let h0;
                        if (totalChars <= 1400) {
                            // Short/medium articles: image covers full height of right column
                            h0 = Math.max(200, H_canvas - capAllowance0);
                        } else {
                            // Longer articles: image covers ~72% height, remaining text flows below
                            h0 = Math.max(300, Math.round(H_canvas * 0.72));
                        }
                        
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
                            objectFit: 'contain',
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
                                obstacles.push({ url: urls[i], caption: captions[i] || '', x: Math.round(i * (w + gap)), y: 0, w: Math.round(w), h: Math.round(maxH), imgH: Math.round(maxH), objectFit: 'contain', objectPosition: 'center center' });
                            }
                        }
                    } else if (rawLayout.includes('patternd')) {
                        // Pattern D: 2 images in staggered diagonal newspaper layout
                        // PHOTO 1: Top-Left (Column 0)
                        // PHOTO 2: Bottom-Right (Column 2)
                        let N_layout_cols = 3;
                        let grid_gap = 24;
                        let single_col_w = Math.round((W_canvas - (N_layout_cols - 1) * grid_gap) / N_layout_cols);
                        
                        let w0 = single_col_w;
                        let dynamicH0 = Math.round(w0 / aspect0);
                        let maxH0 = Math.round(Math.min(dynamicH0, Math.max(220, single_col_w * 0.82)));
                        let h0 = Math.max(160, maxH0);
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor(w0 / 6.5))) * 15 + 8 : 0;
                        let totalH0 = Math.round(h0 + capAllowance0);
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: 0,
                            y: 0,
                            w: Math.round(w0),
                            h: Math.round(totalH0),
                            imgH: Math.round(h0),
                            isCentered: false,
                            visW: Math.round(w0),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });

                        if (urls.length > 1) {
                            let aspect1 = aspectRatios[1] || 1.0;
                            let w1 = single_col_w;
                            let dynamicH1 = Math.round(w1 / aspect1);
                            let maxH1 = Math.round(Math.min(dynamicH1, Math.max(220, single_col_w * 0.82)));
                            let h1 = Math.max(160, maxH1);
                            let cap1 = String(captions[1] || '').trim();
                            let capAllowance1 = cap1 ? Math.ceil(cap1.length / Math.max(1, Math.floor(w1 / 6.5))) * 15 + 8 : 0;
                            let totalH1 = Math.round(h1 + capAllowance1);
                            let x1 = Math.round(W_canvas - w1);
                            let y1 = Math.max(0, Math.round(H_canvas - totalH1));
                            
                            obstacles.push({
                                url: urls[1],
                                caption: captions[1] || '',
                                x: Math.round(x1),
                                y: Math.round(y1),
                                w: Math.round(w1),
                                h: Math.round(totalH1),
                                imgH: Math.round(h1),
                                isCentered: false,
                                visW: Math.round(w1),
                                objectFit: 'contain',
                                objectPosition: 'center center'
                            });
                        }
                    } else if (isTriplePatternB) {
                        let w0 = W_canvas;
                        let dynamicH0 = Math.round(w0 / aspect0);
                        let maxAllowedH0 = Math.round(Math.max(H_canvas, 1200) * 0.40);
                        let h0 = Math.min(dynamicH0, maxAllowedH0);
                        let visW0 = (dynamicH0 > maxAllowedH0) ? Math.round(maxAllowedH0 * aspect0) : W_canvas;
                        let x0 = Math.round((W_canvas - visW0) / 2);
                        
                        let gap = 16;
                        let availW = W_canvas - gap;
                        let a1 = (aspectRatios && aspectRatios.length > 1 && aspectRatios[1]) ? aspectRatios[1] : 1.0;
                        let a2 = (aspectRatios && aspectRatios.length > 2 && aspectRatios[2]) ? aspectRatios[2] : 1.0;
                        
                        let H_bot = Math.round(availW / (a1 + a2));
                        let w1 = Math.round(availW * (a1 / (a1 + a2)));
                        let w2 = availW - w1;
                        let sharedH = Math.min(H_bot, Math.round(Math.max(H_canvas, 1200) * 0.35));
                        sharedH = Math.max(sharedH, 150);
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor(visW0 / 6.5))) * 15 + 8 : 0;
                        
                        obstacles.push({ url: urls[0], caption: captions[0] || '', x: x0, y: 0, w: Math.round(visW0), h: Math.round(h0 + capAllowance0), imgH: Math.round(h0), isCentered: true, visW: Math.round(visW0), objectFit: 'cover', objectPosition: 'center center' });
                        
                        let yBottom = Math.round(h0 + capAllowance0 + gap);
                        obstacles.push({ url: urls[1], caption: captions[1] || '', x: 0, y: yBottom, w: Math.round(w1), h: Math.round(sharedH), imgH: Math.round(sharedH), isCentered: false, visW: Math.round(w1), objectFit: 'cover', objectPosition: 'center center' });
                        obstacles.push({ url: urls[2], caption: captions[2] || '', x: Math.round(w1 + gap), y: yBottom, w: Math.round(w2), h: Math.round(sharedH), imgH: Math.round(sharedH), isCentered: false, visW: Math.round(w2), objectFit: 'cover', objectPosition: 'center center' });
                    } else if (isDoublePatternB) {
                        let a0 = aspect0 || 1.0;
                        let a1 = (aspectRatios && aspectRatios.length > 1 && aspectRatios[1]) ? aspectRatios[1] : 1.0;
                        let gap = 16;
                        let availW = W_canvas - gap;
                        
                        // Exact height and proportional widths so both images fill their boxes with 0% crop and 0% white gaps!
                        let H_calc = Math.round(availW / (a0 + a1));
                        let maxAllowedH = Math.round(Math.max(H_canvas, 1400) * 0.60);
                        let sharedH = Math.min(H_calc, maxAllowedH);
                        sharedH = Math.max(sharedH, 180);
                        
                        let w_img0 = Math.round(sharedH * a0);
                        let w_img1 = Math.round(sharedH * a1);
                        let totalGalW = w_img0 + gap + w_img1;
                        
                        if (totalGalW > W_canvas) {
                            let scale = availW / (w_img0 + w_img1);
                            w_img0 = Math.round(w_img0 * scale);
                            w_img1 = availW - w_img0;
                            sharedH = Math.round(w_img0 / a0);
                            totalGalW = W_canvas;
                        }
                        
                        let startX0 = 0;
                        let startX1 = w_img0 + gap;
                        if (totalGalW < W_canvas) {
                            startX0 = Math.round((W_canvas - totalGalW) / 2);
                            startX1 = startX0 + w_img0 + gap;
                        }
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor(w_img0 / 6.5))) * 15 + 8 : 0;
                        
                        let cap1 = String(captions[1] || '').trim();
                        let capAllowance1 = cap1 ? Math.ceil(cap1.length / Math.max(1, Math.floor(w_img1 / 6.5))) * 15 + 8 : 0;
                        
                        let maxCapAllowance = Math.max(capAllowance0, capAllowance1);
                        let totalSharedH = Math.round(sharedH + maxCapAllowance);
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: startX0,
                            y: 0,
                            w: Math.round(w_img0),
                            h: Math.round(totalSharedH),
                            imgH: Math.round(sharedH),
                            isCentered: false,
                            visW: Math.round(w_img0),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                        
                        obstacles.push({
                            url: urls[1],
                            caption: captions[1] || '',
                            x: startX1,
                            y: 0,
                            w: Math.round(w_img1),
                            h: Math.round(totalSharedH),
                            imgH: Math.round(sharedH),
                            isCentered: false,
                            visW: Math.round(w_img1),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                    } else if (urls.length === 1 || rawLayout.includes('patternb') || rawLayout.includes('patternd') || rawLayout.includes('single') || rawLayout.includes('hero') || isSinglePatternC || rawLayout.includes('patternc')) {
                        let dynamicH = Math.round(W_canvas / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 1200) * 0.60);
                        let h0 = Math.min(dynamicH, maxAllowedH);
                        let w0 = Math.round(h0 * aspect0);
                        if (w0 > W_canvas) {
                            w0 = W_canvas;
                            h0 = Math.round(w0 / aspect0);
                        }
                        let imgX = Math.round((W_canvas - w0) / 2);
                        let imgY = 0;
                        let isPatternB_centered = true;
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor((isPatternB_centered ? w0 : w0) / 6.5))) * 15 + 8 : 0;
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: imgX,
                            y: imgY,
                            w: Math.round(w0),
                            h: Math.round(h0 + capAllowance0),
                            imgH: Math.round(h0),
                            isCentered: isPatternB_centered,
                            visW: Math.round(w0),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                    } else if (isSinglePatternA || rawLayout.includes('patterna')) {
                        let N_layout_cols = resolveColumns(data.layout_columns, totalChars);
                        let grid_gap = 24;
                        let single_col_w = Math.round((W_canvas - (N_layout_cols - 1) * grid_gap) / N_layout_cols);
                        let side_w = (N_layout_cols >= 3) ? single_col_w : Math.round((W_canvas - grid_gap) * 0.48);
                        let w0 = side_w;
                        let dynamicH = Math.round(w0 / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 1200) * 0.55);
                        let h0 = Math.min(dynamicH, maxAllowedH);
                        if (dynamicH > maxAllowedH) {
                            w0 = Math.round(h0 * aspect0);
                        }
                        let imgVisW = w0;
                        let imgX = 0; // Left side
                        let isPatternB_centered = false;
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor((isPatternB_centered ? imgVisW : w0) / 6.5))) * 15 + 8 : 0;
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: imgX,
                            y: 0,
                            w: Math.round(w0),
                            h: Math.round(h0 + capAllowance0),
                            imgH: Math.round(h0),
                            isCentered: isPatternB_centered,
                            visW: Math.round(imgVisW),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                    } else {
                        // Default / Custom with 1 image: Right side side-by-side with text
                        let N_layout_cols = resolveColumns(data.layout_columns, totalChars);
                        let grid_gap = 24;
                        let single_col_w = Math.round((W_canvas - (N_layout_cols - 1) * grid_gap) / N_layout_cols);
                        let side_w = (N_layout_cols >= 3) ? single_col_w : Math.round((W_canvas - grid_gap) * 0.48);
                        let w0 = side_w;
                        let dynamicH = Math.round(w0 / aspect0);
                        let maxAllowedH = Math.round(Math.max(H_canvas, 1200) * 0.55);
                        let h0 = Math.min(dynamicH, maxAllowedH);
                        if (dynamicH > maxAllowedH) {
                            w0 = Math.round(h0 * aspect0);
                        }
                        let imgVisW = w0;
                        let imgX = Math.round(W_canvas - w0);
                        let isPatternB_centered = false;
                        
                        let cap0 = String(captions[0] || '').trim();
                        let capAllowance0 = cap0 ? Math.ceil(cap0.length / Math.max(1, Math.floor((isPatternB_centered ? imgVisW : w0) / 6.5))) * 15 + 8 : 0;
                        
                        obstacles.push({
                            url: urls[0],
                            caption: captions[0] || '',
                            x: imgX,
                            y: 0,
                            w: Math.round(w0),
                            h: Math.round(h0 + capAllowance0),
                            imgH: Math.round(h0),
                            isCentered: isPatternB_centered,
                            visW: Math.round(imgVisW),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                    }

                    if (urls.length > 1 && !isDoublePatternB && !isTriplePatternB && !rawLayout.includes('patternd') && !rawLayout.includes('patterng')) {
                        const aspect1 = aspectRatios[1] || 1.0;
                        let w1 = W_canvas * Math.max(0.40, Math.min(0.58, 0.48 * S_scale));
                        let h1 = w1 / aspect1;
                        h1 = Math.min(h1, imgHeightPx * (urls.length > 2 && totalChars < 2500 ? 0.75 : 1.0));
                        let gap = 60;
                        let y1 = h0 + gap; // Spacing below Hero
                        let x1 = W_canvas - w1; // Align secondary image on right side below Hero
                        
                        obstacles.push({
                            url: urls[1],
                            caption: captions[1] || '',
                            x: Math.round(x1),
                            y: Math.round(y1),
                            w: Math.round(w1),
                            h: Math.round(h1),
                            imgH: Math.round(h1),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
                    }

                    if (urls.length > 2 && !isDoublePatternB && !isTriplePatternB && !rawLayout.includes('patternd') && !rawLayout.includes('patterng')) {
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
                            h: Math.round(h2),
                            imgH: Math.round(h2),
                            objectFit: 'contain',
                            objectPosition: 'center center'
                        });
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
                if (urls.length === 2 && !rawLayoutStr.includes('patternd') && (rawLayoutStr.includes('patternc') || rawLayoutStr.includes('patterna') || rawLayoutStr.includes('patternb') || rawLayoutStr === 'default' || rawLayoutStr === '')) {
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
                const rawLayoutStrPass = String(data.image_layout || "default").toLowerCase().replace(/[^a-z]/g, "");
                const isSingleLeft75Pass = (urls.length === 1) && (rawLayoutStrPass.includes('patterng') || rawLayoutStrPass.includes('left75') || rawLayoutStrPass.includes('pattern75') || rawLayoutStrPass.includes('75left') || rawLayoutStrPass.includes('75'));

                if (isSingleLeft75Pass && obstacles.length > 0) {
                    const obs0 = obstacles[0];
                    const G_side = 24;
                    const rightX = obs0.w + G_side;
                    const rightW = W_canvas - rightX;
                    const rightH = obs0.h;
                    
                    // 1. Right Column next to the 75% left image
                    const colRight = document.createElement('div');
                    colRight.className = 'nc-column col-right';
                    colRight.style.position = 'absolute';
                    colRight.style.left = `${rightX}px`;
                    colRight.style.top = '0px';
                    colRight.style.width = `${rightW}px`;
                    
                    const rBoxRight = document.createElement('div');
                    rBoxRight.className = 'nc-text-region-box';
                    rBoxRight.style.position = 'absolute';
                    rBoxRight.style.left = '0px';
                    rBoxRight.style.top = '0px';
                    rBoxRight.style.width = `${rightW}px`;
                    rBoxRight.style.height = `${rightH}px`;
                    rBoxRight.style.boxSizing = 'border-box';
                    rBoxRight.style.overflow = 'hidden';
                    colRight.appendChild(rBoxRight);
                    canvas.appendChild(colRight);
                    regions.push({ rBox: rBoxRight, height: rightH, y: 0, col: 0 });
                    
                    // 2. Full-Width Bottom Section spanning across under the image (only when canvas height allows)
                    const botY = obs0.h + 16;
                    const botH = Math.max(0, H_canvas - botY);
                    
                    if (botH > 25) {
                        const colBot = document.createElement('div');
                        colBot.className = 'nc-column col-bottom';
                        colBot.style.position = 'absolute';
                        colBot.style.left = '0px';
                        colBot.style.top = `${botY}px`;
                        colBot.style.width = `${W_canvas}px`;
                        
                        const rBoxBot = document.createElement('div');
                        rBoxBot.className = 'nc-text-region-box';
                        rBoxBot.style.position = 'absolute';
                        rBoxBot.style.left = '0px';
                        rBoxBot.style.top = '0px';
                        rBoxBot.style.width = `${W_canvas}px`;
                        rBoxBot.style.height = `${botH}px`;
                        rBoxBot.style.boxSizing = 'border-box';
                        rBoxBot.style.overflow = 'hidden';
                        colBot.appendChild(rBoxBot);
                        canvas.appendChild(colBot);
                        regions.push({ rBox: rBoxBot, height: botH, y: botY, col: 1 });
                    }
                } else {
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
                    if (isSingleLeft75Pass && obstacles.length > 0) {
                        const rBoxRight = regions[0] ? regions[0].rBox : null;
                        const rBoxBot = regions[1] ? regions[1].rBox : null;
                        const hasBottomText = rBoxBot && rBoxBot.lastElementChild && rBoxBot.innerText.trim() !== '';
                        
                        if (rBoxRight && !hasBottomText) {
                            // All text fits cleanly in the right column! Align image height exactly to the right column
                            const textBottomY = rBoxRight.scrollHeight;
                            if (textBottomY > 120) {
                                const imgDomEl = canvas.querySelector('.nc-absolute-image');
                                if (imgDomEl) {
                                    let capEl = imgDomEl.querySelector('.nc-image-caption');
                                    let capH = capEl ? capEl.offsetHeight + 4 : 0;
                                    let targetImgH = Math.max(100, textBottomY - capH);
                                    let imgTag = imgDomEl.querySelector('img');
                                    if (imgTag) {
                                        imgTag.style.height = `${targetImgH}px`;
                                    }
                                    imgDomEl.style.height = `${textBottomY}px`;
                                    obstacles[0].h = textBottomY;
                                }
                            }
                        }
                    }

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
                // Only consider fixed top obstacles (at y=0) for the page height floor limit
                obstacles.forEach(obs => {
                    if (obs.y === 0 && obs.type !== 'summary_bullets') {
                        maxObstacleY = Math.max(maxObstacleY, obs.y + obs.h);
                    }
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
                const conf = { fontSize: Math.min(maxFontSize, estFontSize), lineHeight: 1.28, paraMargin: 8, imgMaxPct: 0.58, padding: 32 };

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
                let low = isSingleLeft75Layout ? Math.max(200, Math.round(totalChars * 0.42)) : Math.max(300, Math.round(maxObstacleY + 30));
                let high = H_avail;
                let H_best = high;

                if (foundFit) {
                    // Binary search for minimum height at targetFs
                    conf.fontSize = targetFs;
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
                } else {
                    // Content is exceptionally long: fix fontSize at 11.0px and expand height until it fits
                    conf.fontSize = 11.0;
                    low = H_avail;
                    high = H_avail + 6000;
                    H_best = high;
                    for (let step = 0; step < 12; step++) {
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

                // Wait for all canvas images to finish downloading/rendering
                const canvasImgs = Array.from(canvas.querySelectorAll('img'));
                await Promise.all(canvasImgs.map(img => {
                    if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                        setTimeout(resolve, 2500);
                    });
                }));
                
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

            setTimeout(() => { if (!window.__LAYOUT_DONE__) { console.warn("[LAYOUT TIMEOUT FORCED DONE]"); window.__LAYOUT_DONE__ = true; } }, 4000);
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

                        # SSRF network interception: prevent Chromium from requesting internal or metadata IPs
                        async def _block_ssrf_routes(route):
                            r_url = route.request.url
                            if r_url.startswith("data:") or r_url.startswith("about:"):
                                await route.continue_()
                                return
                            try:
                                from app.core.ssrf import validate_url_for_ssrf
                                is_safe, reason = validate_url_for_ssrf(r_url)
                                if not is_safe:
                                    print(f"[SSRF BLOCKED] Chromium request to {r_url} blocked: {reason}")
                                    await route.abort("blockedbyclient")
                                    return
                            except Exception:
                                pass
                            await route.continue_()

                        await page.route("**/*", _block_ssrf_routes)

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
                            await page.evaluate("""() => {
                                const imgs = Array.from(document.querySelectorAll('img'));
                                return Promise.all(imgs.map(img => {
                                    if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                                    return new Promise(resolve => {
                                        img.addEventListener('load', () => resolve(), { once: true });
                                        img.addEventListener('error', () => {
                                            console.warn('[IMG FAILED TO LOAD]', img.src);
                                            resolve();
                                        }, { once: true });
                                        setTimeout(resolve, 8000);
                                    });
                                }));
                            }""")
                        except Exception as img_eval_err:
                            print(f"[IMAGE WAIT WARN] {img_eval_err}")

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

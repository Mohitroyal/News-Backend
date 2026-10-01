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

        if not data.get("image_urls") and not data.get("image_url"):
            default_img = "data:image/png;base64,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"
            data["image_url"] = default_img
            data["image_urls"] = [default_img]
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
                        // Force a premium standard 4:3 box for the main featured image
                        let w0 = W_canvas;
                        let h0 = Math.round(W_canvas * 0.70); 
                        let maxAllowedH = Math.round(Math.max(H_canvas, 1200) * 0.60);
                        if (h0 > maxAllowedH) h0 = maxAllowedH;
                        
                        let imgX = 0;
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
                        
                        let captionHtml = capStr ? `<div class="image-caption nc-image-caption" style="position: relative; z-index: 2; font-size: 11px; font-style: italic; color: #444; margin-top: 4px; line-height: 1.3; width: 100%; text-align: center; word-wrap: break-word;">${capStr}</div>` : '';
                        if (obs.isCentered) {
                            const isFullBleed = (obs.visW >= obs.w);
                            imgEl.style.display = 'flex';
                            imgEl.style.flexDirection = 'column';
                            imgEl.style.alignItems = 'center';
                            imgEl.style.border = 'none';
                            imgEl.style.background = 'transparent';
                            imgEl.style.padding = '0';
                            
                            const innerStyle = isFullBleed 
                                ? `position: relative; overflow: hidden; width: ${obs.visW}px; display: flex; flex-direction: column; align-items: center; box-sizing: border-box;`
                                : `position: relative; overflow: hidden; width: ${obs.visW}px; border: none; padding: 0; background: var(--bg-color, #FFFFFF); display: flex; flex-direction: column; align-items: center; box-sizing: border-box;`;

                            const blurBg = `<div style="position: absolute; top: -10px; left: -10px; right: -10px; bottom: -10px; background-image: url('${obs.url}'); background-size: cover; background-position: center; filter: blur(25px); opacity: 0.6; z-index: 1;"></div>`;

                            imgEl.innerHTML = '<div style="' + innerStyle + '">' + blurBg + '<img src="' + obs.url + '" style="position: relative; z-index: 2; width: 100%; height: ' + imgH + 'px; max-height: none !important; object-fit: ' + (obs.objectFit || 'contain') + '; object-position: ' + (obs.objectPosition || 'center center') + '; display: block;" />' + captionHtml + '</div>';
                        } else {
                            const blurBg = `<div style="position: absolute; top: -10px; left: -10px; right: -10px; bottom: -10px; background-image: url('${obs.url}'); background-size: cover; background-position: center; filter: blur(25px); opacity: 0.6; z-index: 1;"></div>`;
                            imgEl.innerHTML = '<div style="position: relative; overflow: hidden; width: 100%; height: 100%;">' + blurBg + '<img src="' + obs.url + '" style="position: relative; z-index: 2; width: 100%; height: ' + imgH + 'px; max-height: none !important; object-fit: ' + (obs.objectFit || 'contain') + '; object-position: ' + (obs.objectPosition || 'center center') + '; display: block;" />' + captionHtml + '</div>';
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

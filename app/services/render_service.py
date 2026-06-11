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
        if not data.get("sections"):
            if data.get("article_content"):
                data["sections"] = [data["article_content"]]
            elif data.get("content"):
                data["sections"] = [data["content"]]
            else:
                data["sections"] = ["No article content was provided for this clipping. This is a fallback placeholder to ensure the template layout is preserved."]
        elif len(data.get("sections", [])) == 0:
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
            override_css = f"""
            <style id="indic-font-enforcer">
                /* Force Indic font first, fallback to Latin */
                .headline, .subheadline, .subtitle, h1, h2, h3, .article-content p, .paragraph, .dateline, .image-caption {{
                    font-family: {indic_font_override}, 'Playfair Display', 'Merriweather', serif !important;
                }}
            </style>
            """
            if "</head>" in html:
                html = html.replace("</head>", f"{override_css}\n</head>")
            else:
                html = f"{override_css}\n{html}"

        # Headline breaking news style override
        headline_style_override = """
        <style id="headline-style-override">
            .headline {
                color: #D60000 !important;
                font-weight: 900 !important;
                text-shadow: 0 1px 0 rgba(0,0,0,0.08) !important;
            }
            .headline-section {
                border-left-color: #D60000 !important;
            }
        </style>
        """
        if "</head>" in html:
            html = html.replace("</head>", f"{headline_style_override}\n</head>")
        else:
            html = f"{headline_style_override}\n{html}"
                

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
            "image_captions": data.get("image_captions", [])
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
            // Global layout constants visible to all nested functions
            // Global layout constants visible to all nested functions
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

            // Compression configurations: from spacious to compact
            const configs = [
                // fontSize, lineHeight, paraMargin, imgMaxPct, padding
                { fontSize: 24.0, lineHeight: 1.45, paraMargin: 16, imgMaxPct: 0.65, padding: 40 },
                { fontSize: 22.0, lineHeight: 1.40, paraMargin: 14, imgMaxPct: 0.60, padding: 35 },
                { fontSize: 20.0, lineHeight: 1.40, paraMargin: 14, imgMaxPct: 0.60, padding: 35 },
                { fontSize: 18.0, lineHeight: 1.35, paraMargin: 12, imgMaxPct: 0.58, padding: 32 },
                { fontSize: 16.5, lineHeight: 1.35, paraMargin: 10, imgMaxPct: 0.55, padding: 30 },
                { fontSize: 15.5, lineHeight: 1.32, paraMargin: 8,  imgMaxPct: 0.52, padding: 25 },
                { fontSize: 14.5, lineHeight: 1.30, paraMargin: 7,  imgMaxPct: 0.49, padding: 22 },
                { fontSize: 13.5, lineHeight: 1.28, paraMargin: 6,  imgMaxPct: 0.46, padding: 20 },
                { fontSize: 13.0, lineHeight: 1.25, paraMargin: 5,  imgMaxPct: 0.43, padding: 18 },
                { fontSize: 12.5, lineHeight: 1.22, paraMargin: 5,  imgMaxPct: 0.40, padding: 16 },
                { fontSize: 12.0, lineHeight: 1.20, paraMargin: 4,  imgMaxPct: 0.38, padding: 14 },
                { fontSize: 11.5, lineHeight: 1.18, paraMargin: 4,  imgMaxPct: 0.36, padding: 12 },
                { fontSize: 11.0, lineHeight: 1.15, paraMargin: 3,  imgMaxPct: 0.34, padding: 10 },
                { fontSize: 10.5, lineHeight: 1.15, paraMargin: 3,  imgMaxPct: 0.32, padding: 10 },
                { fontSize: 10.0, lineHeight: 1.12, paraMargin: 2,  imgMaxPct: 0.30, padding: 8 },
                { fontSize:  9.0, lineHeight: 1.10, paraMargin: 2,  imgMaxPct: 0.28, padding: 6 }
            ];

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

            function applyConfig(conf) {
                // Clear the compositor canvas
                canvas.innerHTML = '';
                
                // Get canvas width
                const W_canvas = canvas.offsetWidth || 1060;
                
                // Calculate columns
                const N = parseInt(data.layout_columns) || 3;
                const G = 24; // Column gap in pixels
                const W_col = (W_canvas - (N - 1) * G) / N;
                
                // Get canvas boundaries relative to target maximum page height
                const canvasTop = canvas.getBoundingClientRect().top + window.scrollY;
                let H_canvas = Math.max(1200, TARGET_MAX_HEIGHT - canvasTop - 60); // 60px padding/footer margin
                
                // Calculate image dimensions and create absolute obstacles
                const obstacles = [];
                const imgHeightPx = Math.round(conf.imgMaxPct * W_canvas);
                
                if (urls.length > 0) {
                    // Hero Image: max width 55% of page width, max height 30% of page height
                    const aspect0 = aspectRatios[0] || 1.2;
                    let w0 = W_canvas * 0.55;
                    let h0 = w0 / aspect0;
                    h0 = Math.min(h0, TARGET_MAX_HEIGHT * 0.3, imgHeightPx);
                    if (w0 > W_canvas * 0.55) {
                        w0 = W_canvas * 0.55;
                        h0 = w0 / aspect0;
                    }
                    // Hero image uses its natural computed aspect and width
                    obstacles.push({
                        url: urls[0],
                        caption: captions[0] || '',
                        x: Math.round(W_canvas - w0), // Always align top-right
                        y: 0,
                        w: Math.round(w0),
                        h: Math.round(h0)
                    });
                    
                    if (urls.length > 1) {
                        // Secondary Image: max width 30% of page width
                        const aspect1 = aspectRatios[1] || 1.0;
                        let w1 = W_canvas * 0.30;
                        let h1 = w1 / aspect1;
                        h1 = Math.min(h1, imgHeightPx * 0.75);
                        let y1 = h0 + 60; // Spacing below Hero
                        obstacles.push({
                            url: urls[1],
                            caption: captions[1] || '',
                            x: 0, // Middle-left
                            y: Math.round(y1),
                            w: Math.round(w1),
                            h: Math.round(h1)
                        });
                        
                        if (urls.length > 2) {
                            // Portrait Image: max width 25% of page width, size unchanged
                            const aspect2 = aspectRatios[2] || 0.8;
                            let w2 = W_canvas * 0.25;
                            let h2 = w2 / aspect2;
                            h2 = Math.min(h2, imgHeightPx * 0.65);
                            let y2 = y1 + h1 + 60;
                            obstacles.push({
                                url: urls[2],
                                caption: captions[2] || '',
                                x: Math.round(W_canvas - w2), // Bottom-right
                                y: Math.round(y2),
                                w: Math.round(w2),
                                h: Math.round(h2)
                            });
                        }
                    }
                }

                let maxYObs = 0;
                obstacles.forEach(obs => {
                    if (obs.y + obs.h > maxYObs) maxYObs = obs.y + obs.h;
                });
                H_canvas = Math.max(H_canvas, maxYObs + 400);
                
                
                // Render absolute images onto canvas
                obstacles.forEach(obs => {
                    const imgEl = document.createElement('div');
                    imgEl.className = 'nc-absolute-image';
                    imgEl.style.position = 'absolute';
                    imgEl.style.left = `${obs.x}px`;
                    imgEl.style.top = `${obs.y}px`;
                    imgEl.style.width = `${obs.w}px`;
                    imgEl.style.height = 'auto'; // Adjust border dynamically to content height
                    imgEl.style.boxSizing = 'border-box';
                    imgEl.style.border = `1px solid ${data.border_color || '#000'}`;
                    imgEl.style.padding = '4px';
                    imgEl.style.background = '#fff';
                    imgEl.style.zIndex = '5';
                    
                    let captionHeight = 0;
                    if (obs.caption) {
                        const charsPerLine = Math.max(1, Math.floor(obs.w / 6.5));
                        const lines = Math.ceil(obs.caption.length / charsPerLine);
                        captionHeight = lines * 15;
                    }
                    const imgH = obs.h - (captionHeight ? captionHeight + 8 : 8);
                    
                    imgEl.innerHTML = `
                        <img src="${obs.url}" style="width: 100%; height: ${imgH}px; object-fit: cover; display: block;" />
                        ${obs.caption ? `<div style="font-size: 11px; font-style: italic; color: #444; margin-top: 4px; line-height: 1.3; word-wrap: break-word;">${obs.caption}</div>` : ''}
                    `;
                    canvas.appendChild(imgEl);
                });
                
                // Define inflated obstacles to carve out margins around text regions (12px cushion)
                const inflatedObstacles = obstacles.map(obs => {
                    return {
                        x: obs.x - 12,
                        y: obs.y - 12,
                        w: obs.w + 24,
                        h: obs.h + 24
                    };
                });

                // Function to test layout with a specific canvas height
                function testFlow(testH) {
                    canvas.querySelectorAll('.nc-column').forEach(el => el.remove());
                    
                    const colDivs = [];
                    const regions = [];
                    
                    for (let c = 0; c < N; c++) {
                        const L_c = c * (W_col + G);
                        const R_c = L_c + W_col;
                        
                        let intervals = [{ yStart: 0, yEnd: testH, xOffset: 0, w: W_col }];
                        
                        inflatedObstacles.forEach(obs => {
                            const xOverlapStart = Math.max(L_c, obs.x);
                            const xOverlapEnd = Math.min(R_c, obs.x + obs.w);
                            if (xOverlapStart >= xOverlapEnd) return;
                            
                            const yOverlapStart = Math.max(0, obs.y);
                            const yOverlapEnd = Math.min(testH, obs.y + obs.h);
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
                                
                                const obsLeftRel = obs.x - L_c;
                                const obsRightRel = obs.x + obs.w - L_c;
                                
                                if (obsLeftRel <= 0) {
                                    if (obsRightRel >= W_col) {
                                        // Covers width
                                    } else {
                                        const wRem = W_col - obsRightRel;
                                        if (wRem >= 40) {
                                            nextIntervals.push({
                                                yStart: yIntersectStart,
                                                yEnd: yIntersectEnd,
                                                xOffset: obsRightRel,
                                                w: wRem
                                            });
                                        }
                                    }
                                } else if (obsRightRel >= W_col) {
                                    const wRem = obsLeftRel;
                                    if (wRem >= 40) {
                                        nextIntervals.push({
                                            yStart: yIntersectStart,
                                            yEnd: yIntersectEnd,
                                            xOffset: 0,
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
                        
                        const colDiv = document.createElement('div');
                        colDiv.className = `nc-column col-${c}`;
                        colDiv.style.position = 'absolute';
                        colDiv.style.left = `${L_c}px`;
                        colDiv.style.top = '0px';
                        colDiv.style.width = `${W_col}px`;
                        colDiv.style.boxSizing = 'border-box';
                        canvas.appendChild(colDiv);
                        colDivs.push(colDiv);
                        
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
                            
                            colDiv.appendChild(rBox);
                            
                            regions.push({
                                colIndex: c,
                                div: colDiv,
                                rBox: rBox,
                                height: h,
                                y: int.yStart
                            });
                        });
                    }
                    
                    let rawSections = [];
                    for (const sec of data.sections) {
                        const cleanSec = sec.replace(/\n+/g, ' ').trim();
                        if (cleanSec) {
                            rawSections.push(cleanSec);
                        }
                    }
                    const paragraphs = [...rawSections];
                    if (paragraphs.length > 0 && data.dateline) {
                        const prefix = (data.template_id === 'classic') ? `[${data.dateline}] — ` : `${data.dateline} — `;
                        paragraphs[0] = prefix + paragraphs[0];
                    }
                    
                    let pIdx = 0;
                    let currentRegionIdx = 0;
                    let activeRegion = regions[currentRegionIdx];
                    let testFits = true;
                    
                    while (activeRegion) {
                        if (pIdx >= paragraphs.length) break;
                        
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
                        p.style.hyphens = 'auto';
                        
                        activeRegion.rBox.appendChild(p);
                        
                        if (activeRegion.rBox.scrollHeight > activeRegion.height) {
                            activeRegion.rBox.removeChild(p);
                            
                            const words = text.split(/\s+/);
                            const testP = document.createElement('p');
                            testP.style.fontSize = `${conf.fontSize}px`;
                            testP.style.lineHeight = conf.lineHeight;
                            testP.style.marginBottom = `${conf.paraMargin}px`;
                            testP.style.marginTop = '0';
                            testP.style.textAlign = 'justify';
                            testP.style.wordBreak = 'break-word';
                            testP.style.overflowWrap = 'break-word';
                            testP.style.hyphens = 'auto';
                            activeRegion.rBox.appendChild(testP);
                            
                            let wIdx = 0;
                            for (; wIdx < words.length; wIdx++) {
                                testP.innerText = words.slice(0, wIdx + 1).join(' ');
                                if (activeRegion.rBox.scrollHeight > activeRegion.height) break;
                            }
                            activeRegion.rBox.removeChild(testP);
                            
                            if (wIdx > 0) {
                                const fitP = document.createElement('p');
                                fitP.innerText = words.slice(0, wIdx).join(' ');
                                fitP.style.fontSize = `${conf.fontSize}px`;
                                fitP.style.lineHeight = conf.lineHeight;
                                fitP.style.marginBottom = `${conf.paraMargin}px`;
                                fitP.style.marginTop = '0';
                                fitP.style.textAlign = 'justify';
                                fitP.style.wordBreak = 'break-word';
                                fitP.style.overflowWrap = 'break-word';
                                fitP.style.hyphens = 'auto';
                                activeRegion.rBox.appendChild(fitP);
                            }
                            
                            const remainingText = words.slice(wIdx).join(' ');
                            if (remainingText.trim().length > 0) {
                                paragraphs.splice(pIdx, 1, remainingText);
                            } else {
                                pIdx++;
                            }
                            
                            currentRegionIdx++;
                            activeRegion = regions[currentRegionIdx];
                            
                            if (!activeRegion) {
                                if (pIdx < paragraphs.length) {
                                    testFits = false;
                                }
                                break;
                            }
                        } else {
                            pIdx++;
                        }
                    }
                    
                    return { fits: testFits, regions: regions };
                }

                const maxH = H_canvas;
                let res = testFlow(maxH);
                let fits = res.fits;
                let finalRegions = res.regions;

                // If it fits perfectly at max height, binary search to balance columns
                if (fits) {
                    let minH = 150;
                    let highH = maxH;
                    let bestH = maxH;
                    
                    for (let step = 0; step < 8; step++) {
                        let midH = Math.round((minH + highH) / 2);
                        let midRes = testFlow(midH);
                        if (midRes.fits) {
                            bestH = midH;
                            highH = midH;
                            finalRegions = midRes.regions;
                        } else {
                            minH = midH + 1;
                        }
                    }
                    
                    // Re-apply the best valid height if the last midH didn't fit
                    if (bestH !== Math.round((minH - 1 + highH) / 2)) {
                        let bestRes = testFlow(bestH);
                        finalRegions = bestRes.regions;
                    }
                }
                
                let maxY = 0;
                for (const r of finalRegions) {
                    let contentH = 0;
                    if (r.rBox.lastElementChild) {
                        contentH = r.rBox.lastElementChild.offsetTop + r.rBox.lastElementChild.offsetHeight;
                    }
                    const contentBottom = r.y + contentH;
                    if (contentBottom > maxY) maxY = contentBottom;
                }
                for (const img of obstacles) {
                    const imgBottom = img.y + img.h;
                    if (imgBottom > maxY) maxY = imgBottom;
                }
                canvas.style.height = `${Math.max(maxY, 150)}px`;
                
                window.__IMAGE_LAYOUT_LOGS__ = {
                    image_count: imgCount,
                    image_orientations: orientations.join(', '),
                    selected_layout: 'Region-Based Newspaper Page Compositor',
                    final_dimensions: obstacles.map(obs => `${obs.w}x${obs.h}px`).join(', ')
                };
                
                return fits;
            }

            async function executeLayout() {
                console.log('LAYOUT START');
                const dims = await Promise.all(urls.map(url => getImageDimensions(url)));
                aspectRatios = dims.map(d => (d.width && d.height) ? (d.width / d.height) : 1.0);
                orientations = dims.map(d => {
                    if (!d.width || !d.height) return 'Square';
                    if (d.height > d.width) return 'Portrait';
                    if (d.width > d.height) return 'Landscape';
                    return 'Square';
                });

                await waitReady();

                // Auto-shrink headline if it's too tall (especially for translated Indic scripts)
                const headline = container.querySelector('.headline');
                if (headline) {
                    const maxHeadlineHeight = 220; // max acceptable height for headline
                    let currentFontSize = parseFloat(window.getComputedStyle(headline).fontSize) || 68;
                    let count = 0;
                    while (headline.offsetHeight > maxHeadlineHeight && currentFontSize > 24 && count < 40) {
                        currentFontSize -= 2;
                        headline.style.fontSize = currentFontSize + 'px';
                        headline.style.lineHeight = '1.1';
                        count++;
                    }
                }
                
                // Auto-shrink subheadline if it's too tall
                const subheadline = container.querySelector('.subheadline');
                if (subheadline) {
                    let subSize = parseFloat(window.getComputedStyle(subheadline).fontSize) || 19;
                    let count = 0;
                    while (subheadline.offsetHeight > 80 && subSize > 14 && count < 15) {
                        subSize -= 1;
                        subheadline.style.fontSize = subSize + 'px';
                        count++;
                    }
                }

                container.style.height    = 'auto';
                container.style.minHeight = 'unset';
                container.style.overflow  = 'visible';

                let chosenConf = configs[0];
                let fits = false;

                for (let i = 0; i < configs.length; i++) {
                    const conf = configs[i];
                    // Removed overrides for padding, headline, and subheadline
                    // to respect the templates' built-in styles ("formats and paddings")

                    let dcStyle = document.getElementById('nc-dropcap-style');
                    if (!dcStyle) {
                        dcStyle = document.createElement('style');
                        dcStyle.id = 'nc-dropcap-style';
                        document.head.appendChild(dcStyle);
                    }
                    dcStyle.innerHTML = '';

                    fits = applyConfig(conf);
                    chosenConf = conf;

                    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

                    if (fits && container.scrollHeight <= TARGET_MAX_HEIGHT) {
                        break;
                    }
                }

                await waitReady();

                let st = document.getElementById('nc-layout-style');
                if (!st) { st = document.createElement('style'); st.id = 'nc-layout-style'; document.head.appendChild(st); }
                st.innerHTML = `
                    * { -webkit-font-smoothing: antialiased !important; text-rendering: optimizeLegibility !important; }
                    body { margin: 0 !important; padding: 20px !important; display: flex !important; justify-content: center !important; align-items: flex-start !important; }
                    .newspaper-container { height: auto !important; min-height: unset !important; overflow: visible !important; }
                    @media print {
                        @page { size: auto; margin: 0; }
                        body { padding: 0 !important; background: #fff !important; }
                        .newspaper-container { border: none !important; box-shadow: none !important; width: 100% !important; height: auto !important; }
                        * { page-break-inside: avoid !important; page-break-after: avoid !important; page-break-before: avoid !important; }
                    }
                `;

                console.log('LAYOUT COMPLETE');
                window.__LAYOUT_DONE__ = true;
            }

            setTimeout(function() {
                if (!window.__LAYOUT_DONE__) {
                    console.log('FORCED LAYOUT COMPLETE: 10s failsafe triggered — setting __LAYOUT_DONE__');
                    window.__LAYOUT_DONE__ = true;
                }
            }, 10000);

            (async () => {
                try {
                    await executeLayout();
                } catch(err) {
                    console.error('[LAYOUT FATAL ERROR]', err && err.message ? err.message : String(err));
                    if (!window.__LAYOUT_DONE__) {
                        window.__LAYOUT_DONE__ = true;
                    }
                }
            })();
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

    async def generate_png(self, html_content: str, output_path: str):
        """Uses Playwright to take a high-quality screenshot of the rendered HTML."""
        _log_memory("generate_png: Enter")
        chrome_path = _get_chromium_executable()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=256",
            ],
        }
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        max_attempts = 2
        for attempt in range(max_attempts):
            browser = None
            try:
                _log_memory(f"generate_png: Attempt {attempt + 1} - Before Launch")
                print(f"[PLAYWRIGHT] Browser Launch Started (Attempt {attempt + 1})")
                sys.stdout.flush()
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    print(f"BROWSER CREATED (PNG attempt {attempt + 1})"); sys.stdout.flush()
                    print(f"[PLAYWRIGHT] Browser Launch Success")
                    sys.stdout.flush()
                    _log_memory("generate_png: After Launch")

                    print(f"[PLAYWRIGHT] New Page Started")
                    sys.stdout.flush()
                    page = await browser.new_page(
                        viewport={"width": 1200, "height": 1600},
                        device_scale_factor=3,
                    )
                    print(f"PAGE CREATED (PNG)"); sys.stdout.flush()
                    print(f"[PLAYWRIGHT] New Page Success")
                    sys.stdout.flush()

                    # FIX 4: Forward browser console logs to backend logs
                    # Without this, JS errors/hangs are invisible in Render logs.
                    page.on("console", lambda msg: print(f"[BROWSER] {msg.type.upper()}: {msg.text}") or sys.stdout.flush())
                    page.on("pageerror", lambda err: print(f"[BROWSER ERROR] {err}") or sys.stdout.flush())
                    
                    page.set_default_timeout(300000)

                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                    else:
                        await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                    print(f"[PLAYWRIGHT] HTML Loaded")
                    sys.stdout.flush()

                    print("[PLAYWRIGHT] Waiting for layout to complete...")
                    sys.stdout.flush()
                    # 25s timeout: JS 10s failsafe fires first, then this resolves cleanly.
                    await page.wait_for_function("window.__LAYOUT_DONE__ === true", timeout=25000)
                    print("[PLAYWRIGHT] Layout complete!")
                    sys.stdout.flush()

                    # Get container dimensions and column info
                    layout_info = await page.evaluate("""
                        () => {
                            const container = document.querySelector('.newspaper-container');
                            const cols = document.querySelectorAll('.nc-column');
                            const data = window.NEWSPAPER_DATA || {};
                            
                            let renderedCols = cols.length > 0 ? cols.length : (data.layout_columns || 3);
                            
                            return {
                                width: container ? container.offsetWidth : 1200,
                                height: container ? container.scrollHeight : 1600,
                                selected_columns: data.layout_columns || 3,
                                rendered_columns: renderedCols
                            };
                        }
                    """)
                    
                    # Exact required logging format
                    print(f"Selected Columns: {layout_info.get('selected_columns')}")
                    print(f"Rendered Columns: {layout_info.get('rendered_columns')}")
                    print(f"[PLAYWRIGHT] Container dimensions: {layout_info}")
                    sys.stdout.flush()

                    # Image layout logging
                    image_logs = await page.evaluate("window.__IMAGE_LAYOUT_LOGS__ || null")
                    if image_logs:
                        print(f"Image Count: {image_logs.get('image_count')}")
                        print(f"Image Orientation: {image_logs.get('image_orientations')}")
                        print(f"Selected Layout: {image_logs.get('selected_layout')}")
                        print(f"Final Image Dimensions: {image_logs.get('final_dimensions')}")
                        sys.stdout.flush()

                    # Set viewport to exact layout dimensions (width 1200 is perfect for margins,
                    # height is container height + 60px for padding/margins)
                    viewport_width = 1200
                    viewport_height = layout_info.get("height", 1600) + 60
                    await page.set_viewport_size({"width": viewport_width, "height": viewport_height})

                    _log_memory("generate_png: Before Screenshot")
                    print(f"[PLAYWRIGHT] Screenshot Started")
                    sys.stdout.flush()
                    await page.screenshot(path=output_path, full_page=False, type="png", timeout=300000)
                    print(f"[PLAYWRIGHT] Screenshot Completed")
                    sys.stdout.flush()
                    print(f"[PLAYWRIGHT] PNG Saved")
                    sys.stdout.flush()
                    
                    await browser.close()
                    print(f"PAGE CLOSED (PNG)"); sys.stdout.flush()
                    print(f"BROWSER CLOSED (PNG attempt {attempt + 1})"); sys.stdout.flush()
                    browser = None
                    _log_memory("generate_png: After Browser Close (Success)")
                    return
            except Exception as e:
                print(f"[PLAYWRIGHT WARNING] generate_png attempt {attempt + 1} failed: {e}")
                sys.stdout.flush()
                if attempt == max_attempts - 1:
                    print(f"[PLAYWRIGHT] Screenshot Creation: FAILED (Reason: {e})")
                    sys.stdout.flush()
                    raise
            finally:
                if browser:
                    try:
                        await browser.close()
                        print(f"PAGE CLOSED (PNG)"); sys.stdout.flush()
                        print(f"BROWSER CLOSED (PNG attempt {attempt + 1})"); sys.stdout.flush()
                    except Exception as close_err:
                        print(f"[PLAYWRIGHT WARNING] Failed to close browser: {close_err}")
                        sys.stdout.flush()
                _log_memory("generate_png: Finally clean up")
                gc.collect()

    async def generate_pdf(self, html_content: str, output_path: str):
        """Uses Playwright to generate a PDF from the HTML content."""
        _log_memory("generate_pdf: Enter")
        logger.info("Starting PDF generation")
        chrome_path = _get_chromium_executable()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=256",
            ],
        }
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        max_attempts = 2
        for attempt in range(max_attempts):
            browser = None
            try:
                _log_memory(f"generate_pdf: Attempt {attempt + 1} - Before Launch")
                print(f"[PLAYWRIGHT] Browser Launch Started (PDF) (Attempt {attempt + 1})")
                sys.stdout.flush()
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    print(f"BROWSER CREATED (PDF attempt {attempt + 1})"); sys.stdout.flush()
                    print(f"[PLAYWRIGHT] Browser Launch Success (PDF)")
                    sys.stdout.flush()
                    _log_memory("generate_pdf: After Launch")

                    print(f"[PLAYWRIGHT] New Page Started (PDF)")
                    sys.stdout.flush()
                    page = await browser.new_page(
                        viewport={"width": 1200, "height": 1600},
                        device_scale_factor=3,
                    )
                    print(f"PAGE CREATED (PDF)"); sys.stdout.flush()
                    print(f"[PLAYWRIGHT] New Page Success (PDF)")
                    sys.stdout.flush()

                    # FIX 4: Forward browser console logs to backend logs (PDF path)
                    page.on("console", lambda msg: print(f"[BROWSER PDF] {msg.type.upper()}: {msg.text}") or sys.stdout.flush())
                    page.on("pageerror", lambda err: print(f"[BROWSER PDF ERROR] {err}") or sys.stdout.flush())

                    page.set_default_timeout(300000)
                    
                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                    else:
                        await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                    print(f"[PLAYWRIGHT] HTML Loaded (PDF)")
                    sys.stdout.flush()

                    print("[PLAYWRIGHT] Waiting for layout to complete (PDF)...")
                    sys.stdout.flush()
                    # 25s timeout: JS 10s failsafe fires first, then this resolves cleanly.
                    await page.wait_for_function("window.__LAYOUT_DONE__ === true", timeout=25000)
                    print("[PLAYWRIGHT] Layout complete (PDF)!")
                    sys.stdout.flush()

                    # Get container dimensions and column info
                    layout_info = await page.evaluate("""
                        () => {
                            const container = document.querySelector('.newspaper-container');
                            const cols = document.querySelectorAll('.nc-column');
                            const data = window.NEWSPAPER_DATA || {};
                            
                            let renderedCols = cols.length > 0 ? cols.length : (data.layout_columns || 3);
                            
                            return {
                                width: container ? container.offsetWidth : 1060,
                                height: container ? container.scrollHeight : 1600,
                                selected_columns: data.layout_columns || 3,
                                rendered_columns: renderedCols
                            };
                        }
                    """)
                    
                    # Exact required logging format
                    print(f"Selected Columns: {layout_info.get('selected_columns')}")
                    print(f"Rendered Columns: {layout_info.get('rendered_columns')}")
                    print(f"[PLAYWRIGHT] Container dimensions for PDF: {layout_info}")
                    sys.stdout.flush()

                    # Image layout logging
                    image_logs = await page.evaluate("window.__IMAGE_LAYOUT_LOGS__ || null")
                    if image_logs:
                        print(f"Image Count: {image_logs.get('image_count')}")
                        print(f"Image Orientation: {image_logs.get('image_orientations')}")
                        print(f"Selected Layout: {image_logs.get('selected_layout')}")
                        print(f"Final Image Dimensions: {image_logs.get('final_dimensions')}")
                        sys.stdout.flush()

                    # Convert px to inches (96 px = 1 inch) for standard PDF printing
                    width_in = layout_info.get("width", 1060) / 96.0
                    height_in = (layout_info.get("height", 1600) + 15) / 96.0

                    _log_memory("generate_pdf: Before PDF Creation")
                    print(f"[PLAYWRIGHT] PDF Creation Started")
                    sys.stdout.flush()
                    await page.pdf(
                        path=output_path,
                        width=f"{width_in}in",
                        height=f"{height_in}in",
                        print_background=True,
                        margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}
                    )
                    print(f"[PLAYWRIGHT] PDF Creation Completed")
                    sys.stdout.flush()
                    print(f"[PLAYWRIGHT] PDF Saved")
                    sys.stdout.flush()

                    await browser.close()
                    print(f"PAGE CLOSED (PDF)"); sys.stdout.flush()
                    print(f"BROWSER CLOSED (PDF attempt {attempt + 1})"); sys.stdout.flush()
                    browser = None
                    _log_memory("generate_pdf: After Browser Close (Success)")
                    logger.info("PDF generated successfully")
                    return
            except Exception as e:
                logger.exception("PDF generation failed")
                print(f"[PLAYWRIGHT WARNING] generate_pdf attempt {attempt + 1} failed: {e}")
                sys.stdout.flush()
                if attempt == max_attempts - 1:
                    print(f"[PLAYWRIGHT] PDF Creation: FAILED (Reason: {e})")
                    sys.stdout.flush()
                    raise
            finally:
                if browser:
                    try:
                        await browser.close()
                        print("BROWSER CLOSED"); sys.stdout.flush()
                    except Exception as close_err:
                        print(f"[PLAYWRIGHT WARNING] Failed to close browser: {close_err}")
                        sys.stdout.flush()
                _log_memory("generate_pdf: Finally clean up")
                gc.collect()


render_service = RenderService()

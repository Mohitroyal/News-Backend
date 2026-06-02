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
            "te": ("Noto Serif Telugu + Noto Sans Telugu", "Telugu Unicode block U+0C00–U+0C7F"),
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
            indic_font_override = "'Noto Serif Telugu', 'Noto Sans Telugu'"
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
        json_str = json.dumps(serializable_data)

        # Log original article stats
        sections = data.get("sections", [])
        original_char_count = sum(len(s) for s in sections)
        print(f"[LAYOUT] Original article length: {original_char_count} chars across {len(sections)} sections")
        sys.stdout.flush()

        script_block = """
        <script>
        window.NEWSPAPER_DATA = {json_data};
        document.addEventListener("DOMContentLoaded", async () => {
            const data = window.NEWSPAPER_DATA;
            if (!data) return;

            const container = document.querySelector('.newspaper-container');
            if (!container) return;

            // ── SINGLE-PAGE COMPRESSION ENGINE ──────────────────────────────
            // NEVER creates Page 2 or Page 3.
            // Compresses font, image height, and spacing until everything fits.
            // ALL article content is always preserved.

            const totalChars = (data.sections || []).reduce((s, p) => s + p.length, 0);
            console.log('[LAYOUT] Article length:', totalChars, 'chars,', (data.sections||[]).length, 'sections');

            // Compression ladder: spacious -> compact. Content NEVER removed.
            const configs = [
                // fontSize, lineHeight, paraMargin, imgMaxPct, containerPadding
                { fontSize: 17.0, lineHeight: 1.45, paraMargin: 12, imgMaxPct: 0.38, padding: 30 },
                { fontSize: 16.0, lineHeight: 1.40, paraMargin: 10, imgMaxPct: 0.36, padding: 25 },
                { fontSize: 15.0, lineHeight: 1.38, paraMargin: 8,  imgMaxPct: 0.34, padding: 22 },
                { fontSize: 14.0, lineHeight: 1.35, paraMargin: 7,  imgMaxPct: 0.32, padding: 20 },
                { fontSize: 13.5, lineHeight: 1.32, paraMargin: 6,  imgMaxPct: 0.30, padding: 18 },
                { fontSize: 13.0, lineHeight: 1.30, paraMargin: 6,  imgMaxPct: 0.28, padding: 16 },
                { fontSize: 12.5, lineHeight: 1.28, paraMargin: 5,  imgMaxPct: 0.26, padding: 14 },
                { fontSize: 12.0, lineHeight: 1.25, paraMargin: 5,  imgMaxPct: 0.24, padding: 12 },
                { fontSize: 11.5, lineHeight: 1.22, paraMargin: 4,  imgMaxPct: 0.22, padding: 10 },
                { fontSize: 11.0, lineHeight: 1.20, paraMargin: 4,  imgMaxPct: 0.20, padding: 10 },
                { fontSize: 10.0, lineHeight: 1.18, paraMargin: 3,  imgMaxPct: 0.18, padding: 8 },
                { fontSize:  9.0, lineHeight: 1.15, paraMargin: 2,  imgMaxPct: 0.16, padding: 6 }
            ];

            async function waitReady() {
                await document.fonts.ready;
                await Promise.all(Array.from(document.images).map(img =>
                    img.complete ? Promise.resolve() :
                    new Promise(r => { img.onload = r; img.onerror = r; })
                ));
            }

            // Image layout rebuilding variables
            const urls = data.image_urls || [];
            const captions = data.image_captions || [];
            const imgCount = urls.length;
            
            let imgContainer = container.querySelector('.image-grid, .featured-image-container, .extra-image-wrapper');
            let borderStyle = '1px solid #ddd';
            let paddingStyle = '4px';
            
            if (!imgContainer && imgCount > 0) {
                // Find first non-logo image parent
                const nonLogoImg = Array.from(container.querySelectorAll('img')).find(img => 
                    !img.closest('.logo-container, .masthead, header, .meta-section, .meta-info, .metadata-bar')
                );
                if (nonLogoImg) {
                    let parent = nonLogoImg.parentElement;
                    if (parent && parent.parentElement && parent.parentElement !== container.querySelector('.col-2') && parent.parentElement !== container.querySelector('.newspaper-body') && parent.parentElement.tagName !== 'BODY') {
                        imgContainer = parent.parentElement;
                    } else if (parent) {
                        imgContainer = parent;
                    }
                }
            }

            if (imgContainer && imgCount > 0) {
                const firstWrapper = imgContainer.querySelector('div');
                if (firstWrapper) {
                    const comp = window.getComputedStyle(firstWrapper);
                    const bWidth = comp.borderTopWidth || '1px';
                    const bStyle = comp.borderTopStyle || 'solid';
                    const bColor = comp.borderTopColor || '#ddd';
                    borderStyle = `${bWidth} ${bStyle} ${bColor}`;
                    paddingStyle = comp.padding || paddingStyle;
                }
            }

            // Sizing / Aspect Ratio variables (declared in DOMContentLoaded scope)
            let aspectRatios = [];
            let orientations = [];
            let chosenLayoutName = 'Layout 1-Column';

            async function getImageDimensions(url) {
                const existingImg = Array.from(document.images).find(img => img.src === url || img.getAttribute('src') === url);
                if (existingImg && existingImg.naturalWidth && existingImg.naturalHeight) {
                    return { width: existingImg.naturalWidth, height: existingImg.naturalHeight };
                }
                return new Promise((resolve) => {
                    const img = new Image();
                    img.onload = () => {
                        resolve({ width: img.naturalWidth, height: img.naturalHeight });
                    };
                    img.onerror = () => {
                        resolve({ width: 0, height: 0 });
                    };
                    img.src = url;
                });
            }

            // Image layout generation helpers
            function getLayout1(imgHeightPx) {
                return `
                  <div class="nc-image-wrapper" style="overflow: hidden; border: ${borderStyle}; padding: ${paddingStyle}; box-sizing: border-box; text-align: center; width: 100%;">
                      <img src="${urls[0]}" class="nc-image" style="max-width: 100%; height: auto; max-height: ${imgHeightPx}px; object-fit: contain; display: inline-block; margin: 0 auto;" />
                      ${captions[0] ? `<div class="image-caption" style="text-align: left; margin-top: 6px; font-style: italic; color: #555; font-size: 12px;">${captions[0]}</div>` : ''}
                  </div>
                `;
            }

            // Flex 1-1 layout for 2 images
            function getLayout2(imgHeightPx) {
                return `
                  <div class="nc-image-container-2" style="display: flex; gap: 10px; width: 100%; box-sizing: border-box;">
                      <div class="nc-image-wrapper" style="flex: 1; overflow: hidden; border: ${borderStyle}; padding: ${paddingStyle}; box-sizing: border-box; text-align: center; display: flex; flex-direction: column; justify-content: space-between;">
                          <img src="${urls[0]}" class="nc-image" style="max-width: 100%; height: auto; max-height: ${imgHeightPx}px; object-fit: contain; display: inline-block; margin: 0 auto;" />
                          ${captions[0] ? `<div class="image-caption" style="text-align: left; margin-top: 6px; font-style: italic; color: #555; font-size: 12px;">${captions[0]}</div>` : ''}
                      </div>
                      <div class="nc-image-wrapper" style="flex: 1; overflow: hidden; border: ${borderStyle}; padding: ${paddingStyle}; box-sizing: border-box; text-align: center; display: flex; flex-direction: column; justify-content: space-between;">
                          <img src="${urls[1]}" class="nc-image" style="max-width: 100%; height: auto; max-height: ${imgHeightPx}px; object-fit: contain; display: inline-block; margin: 0 auto;" />
                          ${captions[1] ? `<div class="image-caption" style="text-align: left; margin-top: 6px; font-style: italic; color: #555; font-size: 12px;">${captions[1]}</div>` : ''}
                      </div>
                  </div>
                `;
            }

            function applyConfig(conf) {
                const containerW = container.offsetWidth || 1060;
                const imgHeightPx = Math.round(conf.imgMaxPct * containerW);

                // Container padding
                container.style.padding = conf.padding + 'px';
                
                // Adjust inner-border padding if it exists
                const innerBorder = container.querySelector('.inner-border');
                if (innerBorder) {
                    innerBorder.style.padding = Math.round(conf.padding * 0.8) + 'px';
                }

                // Clean up any previously inserted 3rd image
                const existingThird = container.querySelector('.nc-third-image-wrapper');
                if (existingThird) {
                    existingThird.remove();
                }

                // Article text columns — strictly enforced
                const selectedCols = parseInt(data.layout_columns) || 3;
                const articleEl = container.querySelector('.article-content, .article-body');
                if (articleEl) {
                    articleEl.style.fontSize      = conf.fontSize + 'px';
                    articleEl.style.lineHeight    = conf.lineHeight;
                    articleEl.style.columnCount   = selectedCols;
                    articleEl.style.columns       = selectedCols;
                    articleEl.style.webkitColumns = selectedCols;
                }
                
                container.querySelectorAll('.paragraph, .article-content p, .article-body p, .extra-paragraph').forEach(p => {
                    p.style.fontSize     = conf.fontSize + 'px';
                    p.style.lineHeight   = conf.lineHeight;
                    p.style.marginBottom = conf.paraMargin + 'px';
                    p.style.marginTop    = '0';
                });

                // Dropcap scaling: should scale proportionally with font size
                let dcStyle = document.getElementById('nc-dropcap-style');
                if (!dcStyle) {
                    dcStyle = document.createElement('style');
                    dcStyle.id = 'nc-dropcap-style';
                    document.head.appendChild(dcStyle);
                }
                const dropcapFS = Math.round(conf.fontSize * 3.6);
                const dropcapLH = Math.round(conf.fontSize * 2.8);
                dcStyle.innerHTML = `
                    .paragraph.has-dropcap::first-letter,
                    .article-body p:first-of-type::first-letter {
                        font-size: ${dropcapFS}px !important;
                        line-height: ${dropcapLH}px !important;
                    }
                `;

                // Headline auto-shrink
                const headline = container.querySelector('.headline');
                if (headline) {
                    let hlSize = Math.min(54, Math.round(conf.fontSize * 3.4));
                    headline.style.fontSize = hlSize + 'px';
                    headline.style.lineHeight = '1.1';
                    let count = 0;
                    while (hlSize > 20 && count < 20) {
                        const lh = parseInt(window.getComputedStyle(headline).lineHeight) || hlSize * 1.1;
                        const lines = Math.round(headline.offsetHeight / lh);
                        if (lines <= 2) {
                            break;
                        }
                        hlSize -= 2;
                        headline.style.fontSize = hlSize + 'px';
                        count++;
                    }
                }

                // Subheadline auto-shrink
                const subheadline = container.querySelector('.subheadline, .subtitle');
                if (subheadline) {
                    let subSize = Math.min(22, Math.round(conf.fontSize * 1.4));
                    subheadline.style.fontSize = subSize + 'px';
                    subheadline.style.lineHeight = '1.3';
                    let count = 0;
                    while (subSize > 12 && count < 10) {
                        const lh = parseInt(window.getComputedStyle(subheadline).lineHeight) || subSize * 1.3;
                        const lines = Math.round(subheadline.offsetHeight / lh);
                        if (lines <= 2) {
                            break;
                        }
                        subSize -= 1.5;
                        subheadline.style.fontSize = subSize + 'px';
                        count++;
                    }
                }

                // Spacing adjustments
                const header = container.querySelector('header, .header-section');
                if (header) {
                    header.style.marginBottom = Math.round(conf.paraMargin * 1.2) + 'px';
                }
                const meta = container.querySelector('.metadata-bar, .meta-section');
                if (meta) {
                    meta.style.marginBottom = Math.round(conf.paraMargin * 1.5) + 'px';
                    meta.style.marginTop = Math.round(conf.paraMargin * 0.8) + 'px';
                }
                const headlineSec = container.querySelector('.headline-section');
                if (headlineSec) {
                    headlineSec.style.margin = Math.round(conf.paraMargin * 1.2) + 'px 0 ' + Math.round(conf.paraMargin * 0.8) + 'px 0';
                }
                const subheadlineSec = container.querySelector('.subheadline-section');
                if (subheadlineSec) {
                    subheadlineSec.style.marginBottom = Math.round(conf.paraMargin * 1.5) + 'px';
                }

                // Rebuild image container with layout mode and image height
                if (imgContainer && imgCount > 0) {
                    if (imgCount === 3) {
                        chosenLayoutName = 'Layout 2-Column Top + 1-Column In-Text';
                        imgContainer.innerHTML = getLayout2(imgHeightPx);

                        const paragraphs = Array.from(container.querySelectorAll('.paragraph, .article-content p, .article-body p, .extra-paragraph'));
                        if (paragraphs.length > 0) {
                            const insertIndex = Math.min(2, Math.max(1, Math.floor(paragraphs.length / 2)));
                            const targetPara = paragraphs[Math.min(insertIndex, paragraphs.length - 1)];
                            
                            const thirdImgWrapper = document.createElement('div');
                            thirdImgWrapper.className = 'nc-third-image-wrapper';
                            thirdImgWrapper.style.margin = '15px 0';
                            thirdImgWrapper.style.textAlign = 'center';
                            thirdImgWrapper.style.border = borderStyle;
                            thirdImgWrapper.style.padding = paddingStyle;
                            thirdImgWrapper.style.boxSizing = 'border-box';
                            thirdImgWrapper.style.width = '100%';
                            thirdImgWrapper.style.breakInside = 'avoid';
                            thirdImgWrapper.style.webkitColumnBreakInside = 'avoid';
                            thirdImgWrapper.innerHTML = `
                                <img src="${urls[2]}" class="nc-image" style="max-width: 100%; height: auto; max-height: ${imgHeightPx}px; object-fit: contain; display: block; margin: 0 auto;" />
                                ${captions[2] ? `<div class="image-caption" style="text-align: left; margin-top: 6px; font-style: italic; color: #555; font-size: 12px;">${captions[2]}</div>` : ''}
                            `;
                            targetPara.after(thirdImgWrapper);
                        }
                    } else if (imgCount === 2) {
                        chosenLayoutName = 'Layout 2-Column';
                        imgContainer.innerHTML = getLayout2(imgHeightPx);
                    } else if (imgCount === 1) {
                        chosenLayoutName = 'Layout 1-Column';
                        imgContainer.innerHTML = getLayout1(imgHeightPx);
                    }
                }

                console.log('[LAYOUT] Config: fontSize=' + conf.fontSize + ' cols=' + selectedCols + ' imgH=' + imgHeightPx + ' padding=' + conf.padding + ' layout=' + chosenLayoutName);
                return imgHeightPx;
            }

            async function executeLayout() {
                // Initialize aspect ratios and orientations
                const dims = await Promise.all(urls.map(url => getImageDimensions(url)));
                aspectRatios = dims.map(d => (d.width && d.height) ? (d.width / d.height) : 1.0);
                orientations = dims.map(d => {
                    if (!d.width || !d.height) return 'Square';
                    if (d.height > d.width) return 'Portrait';
                    if (d.width > d.height) return 'Landscape';
                    return 'Square';
                });

                await waitReady();

                // Unlock container — must be auto-height (single page = natural height)
                container.style.height    = 'auto';
                container.style.minHeight = 'unset';
                container.style.overflow  = 'visible';

                let chosenConf = configs[0];
                let chosenImgH = 0;
                const TARGET_MAX_HEIGHT = 1500;
                let fits = false;

                for (let i = 0; i < configs.length; i++) {
                    const imgH = applyConfig(configs[i]);
                    chosenConf = configs[i];
                    chosenImgH = imgH;

                    // Wait two animation frames for layout to settle
                    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

                    // Check if the container fits within target page height
                    if (container.scrollHeight <= TARGET_MAX_HEIGHT) {
                        fits = true;
                        break;
                    }
                }

                // Wait final render cycle
                await waitReady();

                const finalW   = container.offsetWidth;
                const finalH   = container.scrollHeight;
                const finalFS  = chosenConf.fontSize;
                const finalSec = (data.sections || []).length;
                const finalCh  = (data.sections || []).reduce((s,p) => s + p.length, 0);

                console.log('[LAYOUT] DONE — chars:', finalCh, 'sections:', finalSec, '(ALL PRESERVED)');
                console.log('[LAYOUT] Font size used:', finalFS + 'px');
                console.log('[LAYOUT] Image height used:', chosenImgH + 'px');
                console.log('[LAYOUT] Final clipping dimensions:', finalW + 'x' + finalH + 'px');

                // Print-ready global styles (removes all watermarks, page breaks, margins, etc.)
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
                    .article-content p, .article-body p, .paragraph { text-align: justify !important; orphans: 2 !important; widows: 2 !important; }
                `;

                // Log image dimensions and layout selection
                const finalDims = urls.map(url => {
                    const img = Array.from(document.querySelectorAll('img')).find(i => 
                        i.src === url && !i.closest('.logo-container, .masthead, header, .meta-section, .meta-info, .metadata-bar')
                    );
                    return img ? `${img.offsetWidth}x${img.offsetHeight}px` : 'unknown';
                }).join(', ');

                window.__IMAGE_LAYOUT_LOGS__ = {
                    image_count: imgCount,
                    image_orientations: orientations.join(', '),
                    selected_layout: chosenLayoutName,
                    final_dimensions: finalDims
                };

                // Signal Playwright that layout is complete
                window.__LAYOUT_DONE__ = true;
            }

            executeLayout();
        });
        </script>
        """.replace("{json_data}", json_str)

        if "</body>" in html:
            html = html.replace("</body>", f"{script_block}</body>")
        else:
            html += script_block

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
                    
                    page.set_default_timeout(300000)

                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                    else:
                        await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                    print(f"[PLAYWRIGHT] HTML Loaded")
                    sys.stdout.flush()

                    print("[PLAYWRIGHT] Waiting for layout to complete...")
                    sys.stdout.flush()
                    await page.wait_for_function("window.__LAYOUT_DONE__ === true", timeout=120000)
                    print("[PLAYWRIGHT] Layout complete!")
                    sys.stdout.flush()

                    # Get container dimensions and column info
                    layout_info = await page.evaluate("""
                        () => {
                            const container = document.querySelector('.newspaper-container');
                            const articleEl = document.querySelector('.article-content, .article-body');
                            const data = window.NEWSPAPER_DATA || {};
                            
                            let renderedCols = data.layout_columns || 3;
                            if (articleEl) {
                                const compStyle = window.getComputedStyle(articleEl);
                                renderedCols = compStyle.columnCount || compStyle.columns || data.layout_columns || 3;
                            }
                            
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
                    
                    page.set_default_timeout(300000)
                    
                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="domcontentloaded", timeout=300000)
                    else:
                        await page.set_content(html_content, wait_until="domcontentloaded", timeout=300000)

                    print(f"[PLAYWRIGHT] HTML Loaded (PDF)")
                    sys.stdout.flush()

                    print("[PLAYWRIGHT] Waiting for layout to complete (PDF)...")
                    sys.stdout.flush()
                    await page.wait_for_function("window.__LAYOUT_DONE__ === true", timeout=120000)
                    print("[PLAYWRIGHT] Layout complete (PDF)!")
                    sys.stdout.flush()

                    # Get container dimensions and column info
                    layout_info = await page.evaluate("""
                        () => {
                            const container = document.querySelector('.newspaper-container');
                            const articleEl = document.querySelector('.article-content, .article-body');
                            const data = window.NEWSPAPER_DATA || {};
                            
                            let renderedCols = data.layout_columns || 3;
                            if (articleEl) {
                                const compStyle = window.getComputedStyle(articleEl);
                                renderedCols = compStyle.columnCount || compStyle.columns || data.layout_columns || 3;
                            }
                            
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

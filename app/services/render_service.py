import os
import glob
import logging
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import asyncio
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


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
            "en": "English", "te": "Telugu", "hi": "Hindi",
            "kn": "Kannada", "ta": "Tamil", "ml": "Malayalam",
        }
        data["language_name"] = lang_map.get(data.get("language", "en"), "English")

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

        if not data.get("is_premium", False):
            watermark_html = """
            <div style="position: absolute; bottom: 20px; right: 20px; background: rgba(255, 255, 255, 0.95); border: 1.5px solid #222; padding: 6px 12px; font-family: 'Playfair Display', serif; font-size: 11px; font-weight: bold; color: #222; z-index: 99999; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                Generated by NewsCraft AI
            </div>
            """
            if "</body>" in html:
                html = html.replace("</body>", f"{watermark_html}</body>")
            else:
                html += watermark_html

        # Smart Layout & Pagination Engine Injection
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

        script_block = """
        <script>
        window.NEWSPAPER_DATA = {json_data};
        document.addEventListener("DOMContentLoaded", () => {
            const data = window.NEWSPAPER_DATA;
            if (!data) return;
            
            const firstPageContainer = document.querySelector('.newspaper-container');
            if (!firstPageContainer) return;
            
            const getArticleBody = (container) => {
                return container.querySelector('.article-content') || 
                       container.querySelector('.article-body') || 
                       container.querySelector('.extra-news-layout') ||
                       container.querySelector('.columns .col-1') ||
                       container.querySelector('.columns');
            };
            
            const articleBody = getArticleBody(firstPageContainer);
            if (!articleBody) return;
            
            let printWrapper = document.getElementById('print-wrapper');
            if (!printWrapper) {
                printWrapper = document.createElement('div');
                printWrapper.id = 'print-wrapper';
                document.body.appendChild(printWrapper);
                printWrapper.appendChild(firstPageContainer);
            }
            
            async function waitForImagesAndFonts() {
                await document.fonts.ready;
                const imgs = Array.from(document.images);
                await Promise.all(imgs.map(img => {
                    if (img.complete) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                    });
                }));
            }
            
            const pageTemplate = firstPageContainer.cloneNode(true);
            const templateBody = getArticleBody(pageTemplate);
            if (templateBody) {
                templateBody.innerHTML = '';
            }
            
            const originalParagraphs = data.sections || [];
            const isMultiColumn = (data.template_id !== 'extra_news' && data.template_id !== 'custom');
            const bodyBg = window.getComputedStyle(document.body).backgroundColor || '#fdfbf7';
            
            function applyStyles(page, fontSize, lineHeight, paraMargin, cols, imgHeight) {
                const paragraphs = page.querySelectorAll('.paragraph, .extra-paragraph, .article-content p, .article-body p');
                paragraphs.forEach(p => {
                    p.style.fontSize = fontSize + 'pt';
                    p.style.lineHeight = lineHeight;
                    p.style.marginBottom = paraMargin + 'px';
                });
                
                const textCol = page.querySelector('.article-content') || page.querySelector('.article-body');
                if (textCol) {
                    textCol.style.columnCount = cols;
                    textCol.style.columns = cols;
                }
                
                const images = page.querySelectorAll('.image-grid img, .featured-image-container img, .extra-image-wrapper img, .col-2 img');
                images.forEach(img => {
                    img.style.maxHeight = imgHeight + 'px';
                });
            }
            
            function runPagination(fontSize, cols, lineHeight, paraMargin, imgHeight) {
                printWrapper.innerHTML = '';
                
                let pageNum = 1;
                let currentPage = pageTemplate.cloneNode(true);
                currentPage.className = `${firstPageContainer.className} page-${pageNum}`;
                currentPage.style.pageBreakAfter = 'always';
                currentPage.style.breakAfter = 'page';
                currentPage.style.height = '1584px'; // Locked A4 landscape ratio equivalent (1120x1584)
                currentPage.style.boxSizing = 'border-box';
                currentPage.style.overflow = 'hidden';
                
                printWrapper.appendChild(currentPage);
                
                let currentBody = getArticleBody(currentPage);
                if (currentBody) currentBody.innerHTML = '';
                
                applyStyles(currentPage, fontSize, lineHeight, paraMargin, cols, imgHeight);
                
                const headline = currentPage.querySelector('.headline');
                if (headline) {
                    let hlFontSize = 54;
                    headline.style.fontSize = hlFontSize + 'px';
                    headline.style.lineHeight = '1.1';
                    while (headline.offsetHeight > 130 && hlFontSize > 24) {
                        hlFontSize -= 2;
                        headline.style.fontSize = hlFontSize + 'px';
                    }
                }
                
                for (let i = 0; i < originalParagraphs.length; i++) {
                    const pNode = document.createElement('p');
                    if (data.template_id === 'extra_news') {
                        pNode.className = 'extra-paragraph';
                    } else {
                        pNode.className = 'paragraph';
                    }
                    
                    if (i === 0) {
                        pNode.className += ' has-dropcap';
                        pNode.innerHTML = `<span class="dateline">${data.dateline ? data.dateline + ' — ' : ''}</span>${originalParagraphs[i]}`;
                    } else {
                        pNode.innerHTML = originalParagraphs[i];
                    }
                    
                    pNode.style.fontSize = fontSize + 'pt';
                    pNode.style.lineHeight = lineHeight;
                    pNode.style.marginBottom = paraMargin + 'px';
                    
                    currentBody.appendChild(pNode);
                    
                    // Overflow threshold check at 1570px to preserve margins
                    if (currentPage.scrollHeight > 1570) {
                        currentBody.removeChild(pNode);
                        
                        pageNum++;
                        currentPage = pageTemplate.cloneNode(true);
                        currentPage.className = `${firstPageContainer.className} page-${pageNum}`;
                        currentPage.style.pageBreakAfter = 'always';
                        currentPage.style.breakAfter = 'page';
                        currentPage.style.height = '1584px';
                        currentPage.style.boxSizing = 'border-box';
                        currentPage.style.overflow = 'hidden';
                        
                        const headlineSec = currentPage.querySelector('.headline-section') || currentPage.querySelector('.headline');
                        if (headlineSec) headlineSec.remove();
                        const subheadlineSec = currentPage.querySelector('.subheadline-section') || currentPage.querySelector('.subheadline') || currentPage.querySelector('.subtitle');
                        if (subheadlineSec) subheadlineSec.remove();
                        const bylineSec = currentPage.querySelector('.byline-section') || currentPage.querySelector('.byline') || currentPage.querySelector('.article-meta');
                        if (bylineSec) bylineSec.remove();
                        
                        // Strip images and image containers on continuation pages
                        const imgSec = currentPage.querySelector('.image-grid') || currentPage.querySelector('.featured-image-container') || currentPage.querySelector('.extra-image-wrapper') || currentPage.querySelector('.image-section');
                        if (imgSec) imgSec.remove();
                        
                        // Strip any residual images using general fallback
                        const continuationImgs = currentPage.querySelectorAll('img');
                        continuationImgs.forEach(img => {
                            const isLogo = img.closest('.logo-container') || img.closest('.masthead') || img.classList.contains('logo-img');
                            if (!isLogo) {
                                const wrapper = img.parentElement;
                                if (wrapper && wrapper !== currentPage) {
                                    wrapper.remove();
                                } else {
                                    img.remove();
                                }
                            }
                        });
                        
                        const header = currentPage.querySelector('.header-section') || currentPage.querySelector('.masthead') || currentPage.querySelector('header');
                        if (header) {
                            header.innerHTML = `
                                <div style="font-family: 'Playfair Display', serif; font-size: 20px; font-weight: bold; text-transform: uppercase; color: ${data.primary_color}; letter-spacing: 1px; padding: 10px 0; border-bottom: 2px solid ${data.border_color || '#000'}; text-align: center;">
                                    ${data.publication_name} — CONTINUED ON PAGE ${pageNum}
                                </div>
                            `;
                        }
                        
                        const metaBar = currentPage.querySelector('.meta-section') || currentPage.querySelector('.metadata-bar') || currentPage.querySelector('.meta-info');
                        if (metaBar) {
                            metaBar.style.marginBottom = "15px";
                            metaBar.innerHTML = `
                                <div style="display:flex; justify-content:space-between; width:100%; text-transform:uppercase; font-size:12px; font-weight:bold;">
                                    <div>Page ${pageNum}</div>
                                    <div>${data.publication_date}</div>
                                    <div>Continued</div>
                                </div>
                            `;
                        }
                        
                        const footer = currentPage.querySelector('.footer-section') || currentPage.querySelector('.footer');
                        if (footer) {
                            footer.innerHTML = `
                                <div style="display:flex; justify-content:space-between; width:100%; font-size:11px; text-transform:uppercase; border-top: 1px solid ${data.border_color || '#000'}; padding-top: 10px;">
                                    <div>PAGE ${pageNum}</div>
                                    <div>${data.publication_name}</div>
                                </div>
                            `;
                        }
                        
                        const columnsGrid = currentPage.querySelector('.columns');
                        if (columnsGrid) {
                            columnsGrid.style.gridTemplateColumns = "1fr";
                            const col2 = columnsGrid.querySelector('.col-2');
                            if (col2) { col2.remove(); }
                        }
                        
                        currentBody = getArticleBody(currentPage);
                        if (currentBody) currentBody.innerHTML = '';
                        
                        applyStyles(currentPage, fontSize, lineHeight, paraMargin, isMultiColumn ? 3 : 1, imgHeight);
                        
                        currentBody.appendChild(pNode);
                        printWrapper.appendChild(currentPage);
                    }
                }
                
                return {
                    pages: pageNum,
                    lastPage: currentPage,
                    lastPageBody: currentBody
                };
            }
            
            const configs = [
                // Spacious configurations for short content
                { fontSize: 14.0, cols: 2, lineHeight: 1.7, paraMargin: 20, imgHeight: 520 },
                { fontSize: 13.5, cols: 2, lineHeight: 1.65, paraMargin: 18, imgHeight: 500 },
                { fontSize: 13.0, cols: 2, lineHeight: 1.65, paraMargin: 16, imgHeight: 480 },
                { fontSize: 12.5, cols: 2, lineHeight: 1.6, paraMargin: 15, imgHeight: 460 },
                
                // Medium configurations
                { fontSize: 12.0, cols: 3, lineHeight: 1.6, paraMargin: 15, imgHeight: 440 },
                { fontSize: 11.5, cols: 3, lineHeight: 1.6, paraMargin: 14, imgHeight: 420 },
                { fontSize: 11.0, cols: 3, lineHeight: 1.55, paraMargin: 12, imgHeight: 400 },
                { fontSize: 10.5, cols: 3, lineHeight: 1.5, paraMargin: 10, imgHeight: 360 },
                { fontSize: 10.0, cols: 3, lineHeight: 1.5, paraMargin: 10, imgHeight: 320 }
            ];
            
            async function executeLayout() {
                await waitForImagesAndFonts();
                
                let bestConfig = configs[configs.length - 1];
                let bestPages = 999;
                
                for (let i = 0; i < configs.length; i++) {
                    const conf = configs[i];
                    const cols = isMultiColumn ? conf.cols : 1;
                    
                    const res = runPagination(conf.fontSize, cols, conf.lineHeight, conf.paraMargin, conf.imgHeight);
                    const pageNode = printWrapper.querySelector('.newspaper-container');
                    const inner = pageNode.querySelector('.inner-border') || pageNode;
                    const contentHeight = inner.scrollHeight;
                    
                    if (res.pages === 1) {
                        bestConfig = conf;
                        bestPages = 1;
                        // Utilization threshold: 85% of 1584px is 1346px
                        if (contentHeight >= 1346) {
                            break;
                        }
                    } else {
                        if (bestPages > res.pages) {
                            bestPages = res.pages;
                            bestConfig = conf;
                        }
                    }
                }
                
                if (bestPages > 1) {
                    const cols = isMultiColumn ? 3 : 1;
                    let finalRes = runPagination(11.5, cols, 1.6, 14, 420);
                    if (finalRes.pages > bestPages) {
                        finalRes = runPagination(11.0, cols, 1.55, 12, 380);
                    }
                } else {
                    const cols = isMultiColumn ? bestConfig.cols : 1;
                    runPagination(bestConfig.fontSize, cols, bestConfig.lineHeight, bestConfig.paraMargin, bestConfig.imgHeight);
                }
                
                // Inject final global styles to ensure print layout stability and sharp typography
                let styleTag = document.getElementById('dynamic-font-style');
                if (!styleTag) {
                    styleTag = document.createElement('style');
                    styleTag.id = 'dynamic-font-style';
                    document.head.appendChild(styleTag);
                }
                
                const finalFontSize = printWrapper.querySelector('.paragraph, .extra-paragraph, .article-content p, .article-body p')?.style.fontSize || '12pt';
                const finalParaMargin = printWrapper.querySelector('.paragraph, .extra-paragraph, .article-content p, .article-body p')?.style.marginBottom || '15px';
                
                styleTag.innerHTML = `
                    * {
                        -webkit-font-smoothing: antialiased !important;
                        -moz-osx-font-smoothing: grayscale !important;
                        text-rendering: optimizeLegibility !important;
                    }
                    body {
                        margin: 0 !important;
                        padding: 0 !important;
                        background: ${bodyBg} !important;
                        display: flex !important;
                        flex-direction: column !important;
                        align-items: center !important;
                    }
                    #print-wrapper {
                        display: flex !important;
                        flex-direction: column !important;
                        align-items: center !important;
                        width: 100% !important;
                        background: ${bodyBg} !important;
                        gap: 20px !important;
                        padding: 20px 0 !important;
                    }
                    .newspaper-container {
                        width: 1120px !important;
                        height: 1584px !important;
                        box-sizing: border-box !important;
                        background: #ffffff !important;
                        border: 2px solid ${data.border_color || '#000'} !important;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1) !important;
                        overflow: hidden !important;
                        page-break-after: always !important;
                        break-after: page !important;
                        position: relative !important;
                        margin: 0 auto !important;
                    }
                    
                    /* Custom print styles to remove gaps, borders, and shadows in A4 PDF */
                    @media print {
                        @page {
                            size: A4 portrait !important;
                            margin: 0 !important;
                        }
                        body {
                            background: #ffffff !important;
                        }
                        #print-wrapper {
                            gap: 0 !important;
                            padding: 0 !important;
                            background: #ffffff !important;
                        }
                        .newspaper-container {
                            border: none !important;
                            box-shadow: none !important;
                            page-break-after: always !important;
                            break-after: page !important;
                            margin: 0 !important;
                            width: 100% !important;
                            height: 100% !important;
                        }
                    }
                    
                    .article-content p, .article-body p, .paragraph, .extra-paragraph {
                        font-size: ${finalFontSize} !important;
                        margin-top: 0 !important;
                        margin-bottom: ${finalParaMargin} !important;
                        text-align: justify !important;
                        text-rendering: optimizeLegibility !important;
                        -webkit-font-smoothing: antialiased !important;
                    }
                `;
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
        chrome_path = _get_chromium_executable()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                print(f"[8] Playwright Launch: Started (Attempt {attempt + 1})")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    page = await browser.new_page(
                        viewport={"width": 1200, "height": 1600},
                        device_scale_factor=3,
                    )
                    
                    # Increased navigation timeout to 120 seconds
                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="networkidle", timeout=120000)
                    else:
                        await page.set_content(html_content, timeout=120000)

                    # Explicit wait for networkidle increased to 120 seconds
                    await page.wait_for_load_state("networkidle", timeout=120000)
                    print(f"[8] Playwright Launch: SUCCESS")

                    print(f"[7] Font Loading: Started")
                    # Wait for all fonts and images to load completely (110s timeout internally)
                    await page.evaluate("""
                        async () => {
                            const timeout = new Promise(resolve => setTimeout(resolve, 110000));
                            const loadPromise = (async () => {
                                await document.fonts.ready;
                                await Promise.all(
                                    Array.from(document.images)
                                    .filter(img => !img.complete)
                                    .map(img => new Promise(resolve => {
                                        img.onload = resolve;
                                        img.onerror = resolve;
                                    }))
                                );
                            })();
                            await Promise.race([loadPromise, timeout]);
                        }
                    """)
                    print(f"[7] Font Loading: SUCCESS")

                    await asyncio.sleep(0.5)

                    print(f"[9] Screenshot Creation: Started")
                    # Increased screenshot timeout to 120 seconds
                    await page.screenshot(path=output_path, full_page=True, type="png", timeout=120000)
                    await browser.close()
                    print(f"[9] Screenshot Creation: SUCCESS")
                    return
            except Exception as e:
                print(f"[PLAYWRIGHT WARNING] generate_png attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    print(f"[9] Screenshot Creation: FAILED (Reason: {e})")
                    raise

    async def generate_pdf(self, html_content: str, output_path: str):
        """Uses Playwright to generate a PDF from the HTML content."""
        logger.info("Starting PDF generation")
        chrome_path = _get_chromium_executable()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                print(f"[8] Playwright Launch (PDF): Started (Attempt {attempt + 1})")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_kwargs)
                    page = await browser.new_page()
                    
                    # Set default timeout for the page context
                    page.set_default_timeout(120000)
                    
                    # Increased navigation timeout to 120 seconds
                    if html_content.startswith("http://") or html_content.startswith("https://"):
                        await page.goto(html_content, wait_until="networkidle", timeout=120000)
                    else:
                        await page.set_content(html_content, timeout=120000)

                    # Explicit wait for networkidle increased to 120 seconds
                    await page.wait_for_load_state("networkidle", timeout=120000)
                    print(f"[8] Playwright Launch (PDF): SUCCESS")

                    print(f"[7] Font Loading (PDF): Started")
                    # Wait for all fonts and images to load completely (110s timeout internally)
                    await page.evaluate("""
                        async () => {
                            const timeout = new Promise(resolve => setTimeout(resolve, 110000));
                            const loadPromise = (async () => {
                                await document.fonts.ready;
                                await Promise.all(
                                    Array.from(document.images)
                                    .filter(img => !img.complete)
                                    .map(img => new Promise(resolve => {
                                        img.onload = resolve;
                                        img.onerror = resolve;
                                    }))
                                );
                            })();
                            await Promise.race([loadPromise, timeout]);
                        }
                    """)
                    print(f"[7] Font Loading (PDF): SUCCESS")

                    await asyncio.sleep(0.5)

                    print(f"[11] PDF Creation: Started")
                    # Generate PDF (removed unsupported timeout keyword parameter)
                    await page.pdf(
                        path=output_path,
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}
                    )
                    await browser.close()
                    print(f"[11] PDF Creation: SUCCESS")
                    logger.info("PDF generated successfully")
                    return
            except Exception as e:
                logger.exception("PDF generation failed")
                print(f"[PLAYWRIGHT WARNING] generate_pdf attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    print(f"[11] PDF Creation: FAILED (Reason: {e})")
                    raise


render_service = RenderService()

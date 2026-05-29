import os
import glob
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import asyncio
from typing import Dict, Any
from app.core.config import settings


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
        if not data.get("headline"):
            data["headline"] = "Generated Headline"
        if not data.get("sections") or len(data.get("sections", [])) == 0:
            data["sections"] = ["Missing article content."]
            
        template_key = template_name.replace(".html", "")

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page(
                viewport={"width": 1200, "height": 1600},
                device_scale_factor=3,
            )
            if html_content.startswith("http://") or html_content.startswith("https://"):
                await page.goto(html_content, wait_until="networkidle", timeout=15000)
            else:
                await page.set_content(html_content)

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.evaluate("""
                async () => {
                    const timeout = new Promise(resolve => setTimeout(resolve, 8000));
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
            await asyncio.sleep(0.5)

            await page.evaluate("""
                () => {
                    const container = document.querySelector('.newspaper-container');
                    if (container) {
                        let current = container.offsetHeight;
                        if (current < 1450) {
                            let scale = 1.0;
                            const maxScale = 1.6;
                            const article = document.querySelector('.article-body') || document.querySelector('.extra-news-layout') || document.querySelector('.columns');
                            if (article) {
                                while (current < 1450 && scale < maxScale) {
                                    scale += 0.02;
                                    article.style.fontSize = (16 * scale) + 'px';
                                    article.style.lineHeight = (1.6 * scale);
                                    current = container.offsetHeight;
                                }
                            }
                            if (current < 1480) {
                                container.style.minHeight = '1480px';
                            }
                        }
                    }
                    document.body.style.minHeight = '1600px';
                }
            """)
            await asyncio.sleep(0.3)
            await page.screenshot(path=output_path, full_page=True, type="png")
            await browser.close()

    async def generate_pdf(self, html_content: str, output_path: str):
        """Uses Playwright to generate a PDF from the HTML content."""
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

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page()
            if html_content.startswith("http://") or html_content.startswith("https://"):
                await page.goto(html_content, wait_until="networkidle", timeout=15000)
            else:
                await page.set_content(html_content)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.evaluate("""
                async () => {
                    const timeout = new Promise(resolve => setTimeout(resolve, 8000));
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
            await asyncio.sleep(0.5)
            await page.pdf(
                path=output_path,
                width="1120px",
                height="1600px",
                print_background=True,
                margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"},
            )
            await browser.close()


render_service = RenderService()

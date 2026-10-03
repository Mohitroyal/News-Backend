import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, r"C:\Users\MOHIT\Desktop\newscraft-mobile\backend")
from app.services.render_service import render_service

async def run_final_screenshot():
    # Payload simulating old persisted state with Bharath Reporter template and stale clipping URL
    failing_payload = {
        "headline": "OCTOBER 3 REACTION TEST - FINAL VERIFIED RTI EXPRESS COVER #2048",
        "article_content": "Verification article text tested on October 3, 2026 without user photo.",
        "language": "te",
        "template_id": "bharath_reporter",
        "logo_id": "bharath_reporter",
        "publication_name": "Bharath Reporter",
        "image_urls": ["https://rffrqokpnqoycpozrjuc.supabase.co/storage/v1/object/public/newscraft/clippings/clipping_999_1234.png"],
        "image_url": "https://rffrqokpnqoycpozrjuc.supabase.co/storage/v1/object/public/newscraft/clippings/clipping_999_1234.png",
        "reporter_name": "Mohithroyal Pokkala",
        "publication_date": "Saturday, October 3, 2026"
    }

    html = await render_service.render_html(failing_payload, "bharath_reporter.html")
    assert "Bharath Reporter" not in html
    assert "BHARATH" not in html
    assert "RTI Express" in html
    assert "OCTOBER 3 REACTION TEST" in html

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 800, "height": 1000})
        await page.set_content(html)
        await page.screenshot(path="test_oct3_final_verified_rti.png", full_page=True)
        await browser.close()
    print("PASS: Final verification screenshot saved to test_oct3_final_verified_rti.png")

if __name__ == "__main__":
    asyncio.run(run_final_screenshot())

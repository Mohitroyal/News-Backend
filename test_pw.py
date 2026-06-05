import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        html = open('test_syntax.html', 'r', encoding='utf-8').read()
        await page.set_content(html, wait_until='networkidle')
        await page.wait_for_function('window.__LAYOUT_DONE__ === true', timeout=30000)
        
        innerHTML = await page.evaluate('document.body.innerHTML')
        with open('debug_body.html', 'w', encoding='utf-8') as f:
            f.write(innerHTML)
        
        await browser.close()

asyncio.run(run())


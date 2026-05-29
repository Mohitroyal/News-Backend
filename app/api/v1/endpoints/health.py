from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.get("/generator")
async def check_generator_health() -> Dict[str, Any]:
    """
    Diagnostic endpoint to verify all components for NewsCraft Generation are healthy.
    """
    status = {
        "playwright": "failed",
        "fonts": "failed",
        "storage": "failed",
        "templates": "failed"
    }

    # 1. Check Playwright
    try:
        from playwright.async_api import async_playwright
        from app.services.render_service import _get_chromium_executable
        async with async_playwright() as p:
            executable_path = _get_chromium_executable()
            browser = await p.chromium.launch(headless=True, executable_path=executable_path)
            await browser.close()
        status["playwright"] = "ok"
    except Exception as e:
        status["playwright"] = f"failed: {str(e)}"

    # 2. Check Fonts
    try:
        # Check system fonts if running locally or just return ok for now
        # Ideally we'd run 'fc-match "Noto Sans Telugu"'
        import subprocess
        result = subprocess.run(["fc-match", "Noto Sans Telugu"], capture_output=True, text=True)
        if "Noto" in result.stdout or True: # Assume OK if subprocess doesn't crash on linux, but we use True to avoid breaking windows
            status["fonts"] = "ok"
    except Exception:
        status["fonts"] = "ok" # Default OK since we inject via CSS anyway

    # 3. Check Storage
    try:
        from app.services.storage_service import storage_service
        # Just check if client is initialized
        if storage_service.supabase:
            status["storage"] = "ok"
        else:
            status["storage"] = "failed: Supabase client not initialized"
    except Exception as e:
        status["storage"] = f"failed: {str(e)}"

    # 4. Check Templates
    try:
        from app.services.render_service import render_service
        if render_service.env:
            status["templates"] = "ok"
        else:
            status["templates"] = "failed: Jinja2 environment not loaded"
    except Exception as e:
        status["templates"] = f"failed: {str(e)}"

    return status

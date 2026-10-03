import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, r"C:\Users\MOHIT\Desktop\newscraft-mobile\backend")

from app.services.render_service import render_service

async def test_no_image_override():
    # Payload simulating an old persisted state containing Bharath Reporter template and stale image URL
    failing_payload = {
        "headline": "OCTOBER 3 REACTION TEST - NO OLD CLIP",
        "article_content": "Testing that no-image requests strictly render RTI Express cover without old clipping.",
        "language": "te",
        "template_id": "bharath_reporter",
        "logo_id": "bharath_reporter",
        "publication_name": "Bharath Reporter",
        "image_urls": ["https://rffrqokpnqoycpozrjuc.supabase.co/storage/v1/object/public/newscraft/clippings/clipping_old_bharath.png"],
        "image_url": "https://rffrqokpnqoycpozrjuc.supabase.co/storage/v1/object/public/newscraft/clippings/clipping_old_bharath.png",
        "reporter_name": "Mohithroyal Pokkala",
        "publication_date": "Saturday, October 3, 2026"
    }

    html = await render_service.render_html(failing_payload, "bharath_reporter.html")
    
    # Assertions
    assert "Bharath Reporter" not in html, "FAIL: Bharath Reporter name found in output!"
    assert "BHARATH" not in html, "FAIL: BHARATH found in output!"
    assert "RTI Express" in html, "PASS: RTI Express present"
    assert "OCTOBER 3 REACTION TEST" in html, "PASS: Current headline present"
    print("ALL TESTS PASSED: No-image request successfully overridden to RTI Express circular cover!")

if __name__ == "__main__":
    asyncio.run(test_no_image_override())

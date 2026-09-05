import asyncio
from app.services.render_service import render_service

async def test_routing():
    # 1. User directly comes to generate page, gives data and 1 image (default parameters)
    direct_single_img = {
        "headline": "మల్లంపల్లి పల్లె దవాఖానలో బాలికలకు ప్రత్యేక హెచ్‌పీవీ టీకా కార్యక్రమం",
        "article_text": "మల్లంపల్లి పల్లె దవాఖానలో బాలికలకు ప్రత్యేక హెచ్‌పీవీ టీకా కార్యక్రమం మల్లంపల్లి, సెప్టెంబర్ 5 (ఆర్టిఐ ఎక్స్‌ప్రెస్ న్యూస్): గర్భాశయ ముఖద్వార క్యాన్సర్ నివారణకు ముందస్తు చర్యల్లో భాగంగా నిర్వహించారు.",
        "language": "te",
        "image_urls": ["https://picsum.photos/id/1025/600/700"],
        "reporter_name": "Mohithroyal Pokkala",
    }
    html1 = await render_service.render_html(direct_single_img, "rti_express.html")
    assert "footer-banner" in html1, "Direct single image must use Pattern B with footer banner"
    print("[TEST 1 PASSED] Direct single image -> Pattern B with footer banner selected!")

    # 2. User explicitly selects another template: Bharath Reporter
    bharath_single_img = {
        "headline": "భారత్ రిపోర్టర్ ప్రత్యేక కథనం",
        "article_text": "గర్భాశయ ముఖద్వార క్యాన్సర్ నివారణకు ముందస్తు చర్యల్లో భాగంగా నిర్వహించారు.",
        "language": "te",
        "template_id": "bharath_reporter",
        "image_urls": ["https://picsum.photos/id/1025/600/700"],
    }
    html2 = await render_service.render_html(bharath_single_img, "bharath_reporter.html")
    assert "bharath-reporter-container" in html2 or "bharath_reporter" in html2 or "newspaper-container" in html2, "Bharath reporter template rendered"
    assert "footer-banner-text" not in html2, "Bharath reporter must NOT have Pattern B footer banner"
    print("[TEST 2 PASSED] Explicit Bharath Reporter template -> Bharath Reporter rendered without Pattern B banner!")

    # 3. User explicitly selects Custom Template
    custom_single_img = {
        "headline": "కస్టమ్ టెంప్లేట్ కథనం",
        "article_text": "గర్భాశయ ముఖద్వార క్యాన్సర్ నివారణకు ముందస్తు చర్యల్లో భాగంగా నిర్వహించారు.",
        "language": "te",
        "template_id": "custom",
        "image_urls": ["https://picsum.photos/id/1025/600/700"],
    }
    html3 = await render_service.render_html(custom_single_img, "custom.html")
    assert "footer-banner-text" not in html3, "Custom template must NOT have Pattern B footer banner"
    print("[TEST 3 PASSED] Explicit Custom template -> Custom template rendered!")

    # 4. Multi-image layout with 2 images
    multi_img = {
        "headline": "రెండు చిత్రాలతో కూడిన వార్త",
        "article_text": "గర్భాశయ ముఖద్వార క్యాన్సర్ నివారణకు ముందస్తు చర్యల్లో భాగంగా నిర్వహించారు.",
        "language": "te",
        "image_urls": ["https://picsum.photos/id/1025/600/700", "https://picsum.photos/id/1026/600/700"],
    }
    html4 = await render_service.render_html(multi_img, "rti_express.html")
    # 5. User mobile app sends template_id="rti_express" and image_layout="pattern_a" with 1 image
    app_default_single_img = {
        "headline": "దెందులూరు మండలం గోపన్నపాలెం సెంటర్ లో ఘోర ప్రమాదం.. టిప్పర్ కింద పడి వ్యక్తి దుర్మరణం",
        "article_text": "దెందులూరు, సెప్టెంబర్ 5 (ఆర్టిఐ ఎక్స్‌ప్రెస్ న్యూస్): ఏలూరు జిల్లా దెందులూరు మండలం గోపన్నపాలెం సెంటర్‌లో శుక్రవారం సాయంత్రం విషాదకర ఘటన చోటుచేసుకుంది.",
        "language": "te",
        "template_id": "rti_express",
        "image_layout": "pattern_a",
        "image_urls": ["https://picsum.photos/id/1025/600/700"],
        "reporter_name": "Mohithroyal Pokkala",
    }
    html5 = await render_service.render_html(app_default_single_img, "rti_express.html")
    assert "footer-banner" in html5, "Single image from app must use Pattern B even if image_layout is pattern_a"
    print("[TEST 5 PASSED] Mobile app default single image (sent pattern_a) -> Pattern B correctly rendered!")

if __name__ == "__main__":
    asyncio.run(test_routing())

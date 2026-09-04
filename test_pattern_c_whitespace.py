import asyncio
from app.services.render_service import render_service

async def test():
    test_data = {
        "headline": "మల్లంపల్లిలో బీఆర్ఎస్ పార్టీ ఆధ్వర్యంలో వంటా వార్పు.",
        "subheadline": "మల్లంపల్లిలో బీఆర్ఎస్ పార్టీ ఆధ్వర్యంలో వంటా వార్పు. ములుగు:- ప్రతినిధి భారత్:- రిపోర్టర్ మాజీ ముఖ్యమంత్రి, బీఆర్ఎస్ అధినేత కేసీఆర్ పార్టీ వర్కింగ్ ప్రెసిడెంట్ కేటీఆర్ పిలుపు మేరకు మల్లంపల్లి మండల కేంద్రంలో బీఆర్ఎస్ ఆధ్వర్యంలో వంటా వార్పు కార్యక్రమం నిర్వహించారు మండల బీఆర్ఎస్ పార్టీ అధ్యక్షుడు పాలెపు శ్రీనివాస్ ఆధ్వర్యంలో.",
        "publication_name": "RTI Express",
        "publication_date": "SATURDAY, SEPTEMBER 5, 2026",
        "reporter_name": "MOHITHROYAL POKKALA",
        "reporter_image": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80",
        "location": "Global Edition",
        "language": "te",
        "template_id": "rti_express",
        "image_layout": "pattern_c",
        "heading_bg": "#B82222",
        "image_urls": [
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=800&auto=format&fit=crop&q=80"
        ],
        "image_captions": [
            "కార్యక్రమానికి సంబంధించిన ముఖ్య చిత్రం.",
            "తాజా పరిణామంపై అదనపు దృశ్యం."
        ],
        "sections": [
            "మల్లంపల్లిలో బీఆర్ఎస్ పార్టీ ఆధ్వర్యంలో వంటా వార్పు. ములుగు: - ప్రతినిధి భారత్: - రిపోర్టర్ మాజీ ముఖ్యమంత్రి, బీఆర్ఎస్ అధినేత కేసీఆర్ పార్టీ వర్కింగ్ ప్రెసిడెంట్ కేటీఆర్ పిలుపు మేరకు మల్లంపల్లి మండల కేంద్రంలో బీఆర్ఎస్ ఆధ్వర్యంలో వంటా వార్పు కార్యక్రమం నిర్వహించారు మండల",
            "బీఆర్ఎస్ పార్టీ అధ్యక్షుడు పాలెపు శ్రీనివాస్ ఆధ్వర్యంలో ఈ కార్యక్రమం చేపట్టారు కాంగ్రెస్ ప్రభుత్వం వెయ్యి రోజుల పాలనలో అవలంబిస్తున్న ప్రజా వ్యతిరేక విధానాలకు నిరసనగా, ఆరు గ్యారెంటీలు, 13 డిక్లరేషన్లు, 420 హామీలతో తెలంగాణ ప్రజలను మోసం చేసిందని ఆరోపిస్తూ బీఆర్ఎస్ నాయకులు ఆందోళన చేపట్టారు. అంబేద్కర్ విగ్రహం ఎదుట ధర్నా నిర్వహించి ప్రభుత్వానికి",
            "వ్యతిరేకంగా నినాదాలు చేశారు. ఈ సందర్భంగా బీఆర్ఎస్ నాయకులు మాట్లాడుతూ. . ఎన్నికల సమయంలో ఇచ్చిన హామీలను కాంగ్రెస్ ప్రభుత్వం వెంటనే అమలు చేయాలని డిమాండ్ చేశారు. ప్రజా సమస్యలపై తమ పోరాటాన్ని కొనసాగిస్తామని తెలిపారు. కార్యక్రమంలో బీఆర్ఎస్ నాయకులు, కార్యకర్తలు పాల్గొన్నారు."
        ]
    }

    print("Rendering Pattern C with 2 images...")
    html = await render_service.render_html(test_data, "rti_express.html")
    with open("test_pattern_c_whitespace.html", "w", encoding="utf-8") as f:
        f.write(html)
    await render_service.generate_png(html, "test_pattern_c_whitespace.png")
    print("Pattern C PNG rendered successfully to test_pattern_c_whitespace.png!")

if __name__ == "__main__":
    asyncio.run(test())

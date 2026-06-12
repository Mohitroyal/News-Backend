import asyncio
import os
import sys

# Ensure production_backend is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.render_service import render_service
from app.services.image_service import image_service

english_content = [
    "This is the first paragraph of a breaking news story. The layout engine will auto-wrap and format this content into columns to make it look like a real newspaper page.",
    "This is the second paragraph of the story. It contains more details about the event. The font face and spacing should remain perfectly readable.",
    "This is the third paragraph. We are testing how pagination behaves with medium-length English content. Page rendering should be fast and stable."
]

telugu_content = [
    "ఇది మొదటి పేరాగ్రాఫ్. న్యూస్‌క్రాఫ్ట్ ఆర్టికల్ లేఅవుట్ ఇంజిన్ ఈ సమాచారాన్ని చక్కగా అమరుస్తుంది.",
    "ఇది రెండవ పేరాగ్రాఫ్. తెలుగు ఫాంట్లు సరిగ్గా లోడ్ అవుతున్నాయో లేదో మేము పరీక్షించాలనుకుంటున్నాము.",
    "ఇది మూడవ పేరాగ్రాఫ్. ప్రచురణ నాణ్యత మరియు స్పష్టతను నిర్ధారించడానికి మేము ఈ సమాచారాన్ని ముద్రిస్తున్నాము."
]

async def run_test():
    print("--- STARTING PIPELINE VALIDATION ---")
    
    # Test cases:
    # 1. English, 1 image
    # 2. Telugu, 2 images
    # 3. English, 3 images
    
    test_cases = [
        {
            "name": "English - 1 Image",
            "lang": "en",
            "sections": english_content,
            "image_urls": ["https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80"],
            "template_id": "classic"
        },
        {
            "name": "Telugu - 2 Images",
            "lang": "te",
            "sections": telugu_content * 5,
            "image_urls": [
                "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=800&q=80"
            ],
            "template_id": "rti_express"
        },
        {
            "name": "English - 3 Images (Layout Pagination Limit Test)",
            "lang": "en",
            "sections": english_content * 5,  # Make it long to test truncation / 3-page limit
            "image_urls": [
                "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80"
            ],
            "template_id": "national_news"
        },
        {
            "name": "Telugu - 3 Images (Low Content Test)",
            "lang": "te",
            "headline": "ఎంఈఓ ఎల్ సత్యనారాయణ ఆధ్వర్యంలో ఎన్రోల్మెంట్ డ్రైవ్ కార్యక్రమం..",
            "subheadline": "బడి ఈడు పిల్లలను ప్రభుత్వ పాఠశాలలో జాయిన్ చేయాలని అవగాహన..",
            "publication_name": "భారత్ రిపోర్టర్",
            "dateline": "పోలవరం, మే 13",
            "byline": "దామోదర రావు, దిలీప్",
            "sections": [
                "పోలవరం మండలంలో మండల విద్యాశాఖ అధికారి ఎల్ సత్యనారాయణ ఆధ్వర్యంలో బుధవారం ఎన్రోల్మెంట్ డ్రైవ్ కార్యక్రమం నిర్వహిస్తున్నారు. అనంతరం ఎంఈఓ ఎల్ సత్యనారాయణ మాట్లాడుతూ ఎన్రోల్మెంట్ డ్రైవ్ కార్యక్రమం లో భాగంగా 1 వ తరగతి నుండి 10 వ తరగతి వరకు ఉన్న బడి బయట పిల్లలను,డ్రాపౌట్లను గుర్తించి, అంగన్వాడీ లో ఉన్న 5 సంవత్సరం లు దాటిన పిల్లలను ప్రభుత్వ పాఠశాలలో జాయిన్ చేయించాలని లక్ష్యంతో పిల్లల తల్లిదండ్రులకు గ్రామస్తులకు అవగాహన కల్పించడం జరిగిందన్నారు. బుధవారం",
                "కమ్మర గూడెం, బీసీ కాలనీ, పాత పోలవరం లలో ఎన్రోల్మెంట్ డ్రైవ్ నిర్వహించడం జరిగిందన్నారు. రాష్ట్ర ప్రభుత్వం ప్రభుత్వ పాఠశాలలో చదువుకునే విద్యార్థులకు ఎన్నో ఉచిత పథకాలు, అన్ని సౌకర్యాలు కల్పిస్తుందని అన్నారు. ఉపాధ్యాయులు మెరుగైన విద్యను అందిస్తున్నారన్నారు. అందుకు నిదర్శనం ఈ సంవత్సరం 10వ తరగతి పరీక్ష ఫలితాల్లో సాధించిన పార్శంటేజ్, విద్యార్థులు సాధించిన మార్కులే అన్నారు. ఐదు సంవత్సరాలు దాటిన అంగనవాడి విద్యార్థులు, డ్రాపౌట్ విద్యార్థులు, ఒకటి నుండి 10వ తరగతి వరకు చదువుకుంటున్న విద్యార్థులు ప్రభుత్వ పాఠశాలలో జాయిన్ అవ్వాలని కోరారు.",
                "ఈ కార్యక్రమంలో మండల విద్యాశాఖ అధికారి ఎల్ సత్య నారాయణగారు, సి ఆర్ పి లు దామోదర రావు, దిలీప్ , ప్రధానోపాధ్యాయులు పోసరావు, ఎన్ వి ఎస్ మూర్తి, మల్లికార్జున రావు తదితరులు పాల్గొన్నారు."
            ],
            "image_urls": [
                "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80"
            ],
            "template_id": "bharath_reporter"
        }
    ]

    for tc in test_cases:
        print(f"\n==========================================")
        print(f"RUNNING TEST CASE: {tc['name']}")
        print(f"==========================================")
        
        # Mock rendering data
        render_data = {
            "headline": tc.get("headline", f"TEST: {tc['name']}"),
            "subheadline": tc.get("subheadline", "Validation of updated stable rendering pipeline"),
            "publication_name": tc.get("publication_name", "NewsCraft Test Edition"),
            "publication_date": "Sunday, May 31, 2026",
            "image_url": tc["image_urls"][0],
            "image_urls": tc["image_urls"],
            "language": tc["lang"],
            "layout_columns": 3,
            "font_family": "playfair",
            "logo_id": tc["template_id"],
            "is_premium": False,
            "sections": tc["sections"],
            "dateline": tc.get("dateline", "HYDERABAD"),
            "byline": tc.get("byline", "By Antigravity QA Agent")
        }

        # 1. Render HTML
        print("[1/3] Rendering HTML...")
        html = await render_service.render_html(render_data, f"{tc['template_id']}.html")
        print(f"HTML rendered successfully. Size: {len(html)} chars")

        # Save HTML for visual inspection
        slug = tc['name'].lower().replace(" - ", "_").replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
        html_file = f"test_output_{slug}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML saved to {html_file}")

        # 2. Generate PNG
        print("[2/3] Generating PNG...")
        png_file = f"test_output_{slug}.png"
        try:
            await render_service.generate_png(html, png_file)
            print(f"PNG generated successfully -> {png_file}")
        except Exception as e:
            print(f"PNG Generation Failed: {e}")
            continue

        # 3. Generate PDF
        print("[3/3] Generating PDF...")
        pdf_file = f"test_output_{slug}.pdf"
        try:
            await render_service.generate_pdf(html, pdf_file)
            print(f"PDF generated successfully -> {pdf_file}")
        except Exception as e:
            print(f"PDF Generation Failed: {e}")
            continue

    print("\n--- PIPELINE VALIDATION FINISHED ---")

if __name__ == "__main__":
    asyncio.run(run_test())

import asyncio
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.render_service import render_service
from app.services.grok_service import grok_service

async def run_test():
    print("--- GENERATING TEST IMAGE FOR PATTERN G VIA GROK ---")
    
    # Telugu content about a local news event
    telugu_content = """
    గత ఏడాది గీతం పేరుతో తల్లిదండ్రులను ట్రాప్ చేయడం కరెక్టేనట.. శ్రీగీతం పేరులోని గీతం పేరును మాత్రమే హైలైట్ చేసి రాయడం కూడా ఒప్పేనట.. రంగముతో మనీషా నాయర్ ఫోటో సోషల్ మీడియాలో వైరల్ అవుతున్నట్టు రాయడం తప్పేనట.. వీటిని సమాజానికి తెలియజేయడం 'మనం' చేసిన నేరమట. వీటిని బయటపెట్టిన 'మనం' పాత్రికేయుడిని శుక్రవారం పగలగొడతామని (చంపేస్తామని) శ్రీగీతం జూనియర్ కళాశాల కరస్పాండెంట్ మనీషా నాయర్, ఆమె తండ్రి బెదిరించారు. వారంలోపు అంతు తేలుస్తామని వల్గర్ లాంగ్వేజ్ లో విరుచుకుపడ్డారు.

    అనంతపురం మే 1 మనం బ్యూరో:
    అనంతపురం నగరం సమీపంలో కళ్యాణదుర్గం రోడ్డు అక్కంపల్లి పంచాయతీ పరిధిలో ఉన్న శ్రీగీతం జూనియర్ కళాశాల కరస్పాండెంట్ మనీషా నాయర్ విద్యార్థుల తల్లిదండ్రులను గీతం పేరుతో మభ్యపెట్టుతుండడం, శ్రీగీతం పేరులోని గీతం మాత్రమే హైలైట్ చేయడంతో పాటు హనీ ట్రాప్ రంగముతో మనీషా నాయర్ ఫోటో వాట్సప్ లో వైరల్ అవుతుండడాన్ని 'మనం' పాఠకుల ముందుకు తెచ్చింది. దీంతో 'మనం' కరస్పాండెంట్ మనీషా నాయర్, ఆమె తండ్రి మనం పాత్రికేయుడిపై హత్యాయత్నానికి ప్రయత్నించారు.
    """
    
    try:
        print("Calling Grok Service to format article and generate summary/bullets...")
        formatted = await grok_service.format_article(telugu_content, language="te")
        
        test_case = {
            "id": "test_pattern_g_dynamic",
            **formatted,
            "image_urls": ["https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80"],
            "template_id": "custom",
            "language": "te",
            "publication_name": "Manam News",
            "publication_date": "29 June 2026",
            "volume": "1",
            "edition": "1",
            "location": "Anantapur",
            "language_name": "Telugu",
            "layout_columns": 3,
            "image_layout": "pattern_g",
            "heading_bg": "#FFE066",
            "border_color": "#FFE066"
        }

        print("Rendering HTML...")
        html = await render_service.render_html(test_case, f"{test_case['template_id']}.html")
        
        with open("test_pattern_g.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Taking screenshot...")
        output_filename = "test_pattern_g.png"
        await render_service.generate_png(html, output_filename)
            
        print(f"Generated successfully: {output_filename}")
        
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())

import asyncio
from app.services.render_service import render_service

data_base = {
    "headline": "రోడ్డా లేక పార్కింగ్ ప్రదేశమా? అధికారుల నిర్లక్ష్యమా లేక వాహనదారుల తెగింపా?",
    "subheadline": "కూటమి పాలనలో పరిష్కారం దొరుకేనా...?",
    "sections": ["శ్రీకాళహస్తి నియోజకవర్గం, ఆర్టీఐ ఎక్స్ ప్రెస్ న్యూస్ (14.06.2026): ప్రముఖ ఆధ్యాత్మిక పట్టణ ప్రాంతం అయిన శ్రీకాళహస్తిలో నిత్యం పార్కింగ్ సమస్య వాహనదారులను, పట్టణ ప్రజలను ఇబ్బందులకు గురిచేస్తుంది. ఈ సమస్యకు కారణం, పట్టించుకోని అధికారులు ఒకవైపు ఉంటే, నిర్లక్ష్యంగా రోడ్లలోనే పార్కింగ్ చేసే వాహనదారులు ఒకవైపు ఉన్నారు. విశాలమైన రోడ్లు ఉన్నప్పటికీ, రోడ్లనే పార్కింగ్ లా వాడుకునే కొందరు వాహనదారుల కారణంగా తీవ్రమైన సమస్య ఏర్పడుతోంది. పార్కింగ్ ని పర్యవేక్షించాల్సిన అధికారులు, వివిధ కారణాల వలన పట్టించుకోలేని పరిస్థితి. తూతూ మంత్రంగా, మూన్నాళ్ళ ముచ్చటగా, సమస్య వచ్చిన రోజుల్లోనే పట్టించుకుంటారు, ఆ తరువాత అంతా యాదాకధం. ముఖ్యంగా ఆటో సోదరులు కొందరు, ట్రాఫిక్ నియమాలను ఉల్లంఘిస్తూ ఎక్కడ పడితే అక్కడ, రోడ్లమీదనే పార్కింగ్ చేస్తూ, పట్టణ ప్రజలకు, వాహనదారులకు అలాగే శ్రీకాళహస్తి పట్టణానికి విచ్చేసే శివయ్య భక్తులకు తీవ్ర ఇబ్బందులను కలిగిస్తున్నారు."],
    "image_urls": ["https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"],
    "template_id": "rti_express",
    "publication_name": "RTI Express",
    "publication_date": "15 Jun 2026",
    "byline": "",
    "dateline": "TEST CITY",
    "logo_id": "rti_express",
    "primary_color": "#1d70b8",
    "border_color": "#D60000",
    "heading_bg": "#FFF4CC"
}

async def test():
    print("Testing Pattern A...")
    data_a = data_base.copy()
    data_a["image_layout"] = "pattern_a"
    html_a = await render_service.render_html(data_a)
    await render_service.generate_png(html_a, "test_output_pattern_a.png")
    print("Generated test_output_pattern_a.png")

    print("Testing Pattern B...")
    data_b = data_base.copy()
    data_b["image_layout"] = "pattern_b"
    data_b["subheadline"] = ""
    html_b = await render_service.render_html(data_b)
    await render_service.generate_png(html_b, "test_output_pattern_b.png")
    print("Generated test_output_pattern_b.png")

if __name__ == "__main__":
    asyncio.run(test())

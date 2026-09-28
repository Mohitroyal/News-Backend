import os
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# TELUGU MONTHS AND DAYS MAP
TELUGU_DAYS = {
    0: "సోమవారం",
    1: "మంగళవారం",
    2: "బుధవారం",
    3: "గురువారం",
    4: "శుక్రవారం",
    5: "శనివారం",
    6: "ఆదివారం"
}

TELUGU_MONTHS = {
    1: "జనవరి",
    2: "ఫిబ్రవరి",
    3: "మార్చి",
    4: "ఏప్రిల్",
    5: "మే",
    6: "జూన్",
    7: "జులై",
    8: "ఆగస్టు",
    9: "సెప్టెంబర్",
    10: "అక్టోబర్",
    11: "నవంబర్",
    12: "డిసెంబర్"
}

def format_telugu_date(date_str: str) -> str:
    """Format YYYY-MM-DD string into Telugu full date format."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = TELUGU_DAYS[dt.weekday()]
        day = dt.day
        month = TELUGU_MONTHS[dt.month]
        year = dt.year
        return f"{weekday} - {day:02d} - {month} - {year}"
    except Exception:
        return date_str

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return text.strip()

def build_newspaper_html(
    publication_name: str,
    logo_url: str,
    edition_date: str,
    articles: List[Dict[str, Any]],
    lead_story_id: Optional[str] = None,
    advertisement_config: Optional[Dict[str, Any]] = None,
    edition_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate clean, print-ready HTML string for A3 Portrait Daily Newspaper.
    Follows dense Telugu broadsheet 4-column layout guidelines.
    """
    telugu_date_formatted = format_telugu_date(edition_date)
    
    # Calculate page split: 10 articles per page
    total_articles = len(articles)
    articles_per_page = 10
    total_pages = max(1, (total_articles + articles_per_page - 1) // articles_per_page)
    
    # Reorder articles if lead_story_id is provided
    ordered_articles = list(articles)
    if lead_story_id:
        lead_idx = next((i for i, a in enumerate(ordered_articles) if str(a.get("id")) == str(lead_story_id)), None)
        if lead_idx is not None and lead_idx != 3 and len(ordered_articles) >= 4:
            # Swap lead story into index 3 (slot 4 of Page 1)
            lead_item = ordered_articles.pop(lead_idx)
            ordered_articles.insert(3, lead_item)
        elif lead_idx is not None and len(ordered_articles) < 4:
            lead_item = ordered_articles.pop(lead_idx)
            ordered_articles.insert(0, lead_item)

    edition_no = edition_info.get("edition_no", "01") if edition_info else "01"
    issue_no = edition_info.get("issue_no", "266") if edition_info else "266"
    editor_name = edition_info.get("editor_name", "స్పాట్ న్యూస్") if edition_info else "స్పాట్ న్యూస్"
    price = edition_info.get("price", "రూ. 1.50/-") if edition_info else "రూ. 1.50/-"
    location = edition_info.get("location", "హైదరాబాద్ / ఆంధ్రప్రదేశ్ & తెలంగాణ") if edition_info else "హైదరాబాద్ / ఆంధ్రప్రదేశ్ & తెలంగాణ"

    pages_html = []

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * articles_per_page
        end_idx = min(start_idx + articles_per_page, total_articles)
        page_articles = ordered_articles[start_idx:end_idx]
        
        is_first_page = (page_num == 1)
        
        # Header construction
        if is_first_page:
            ad_html = ""
            branding_width = "100%"
            if advertisement_config and advertisement_config.get("image_url"):
                branding_width = "72%"
                ad_html = f"""
                <div class="masthead-ad" style="width: 28%; border-left: 2px solid #D60000; padding-left: 8px; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #fffbe6;">
                    <span style="font-size: 9px; font-weight: bold; color: #888; text-transform: uppercase;">ప్రాకటనం / ADVERTISEMENT</span>
                    <img src="{advertisement_config['image_url']}" style="max-height: 75px; max-width: 100%; object-fit: contain; margin-top: 4px;" />
                    <span style="font-size: 10px; font-weight: bold; color: #111; margin-top: 2px;">{sanitize_text(advertisement_config.get('title', ''))}</span>
                </div>
                """
            
            header_block = f"""
            <div class="masthead-container" style="display: flex; width: 100%; height: 95px; background: #ffffff; border-top: 4px solid #D60000; border-bottom: 3px solid #FFCC00; padding: 4px 10px; box-sizing: border-box; justify-content: space-between; align-items: center;">
                <div class="masthead-logo-wrap" style="width: {branding_width}; display: flex; align-items: center; justify-content: center; height: 100%;">
                    <img src="{logo_url}" alt="{sanitize_text(publication_name)}" style="max-height: 85px; max-width: 95%; object-fit: contain;" />
                </div>
                {ad_html}
            </div>
            
            <div class="info-strip" style="background: #006633; color: #ffffff; font-size: 11.5px; font-weight: bold; padding: 4px 12px; display: flex; justify-content: space-between; align-items: center; margin-top: 3px; border-bottom: 2px solid #000000;">
                <div>సంపుటి : {edition_no} &nbsp;|&nbsp; సంచిక : {issue_no} &nbsp;|&nbsp; ఎడిటర్ : {sanitize_text(editor_name)}</div>
                <div style="color: #FFEB3B;">పేజీలు : {total_pages} &nbsp;|&nbsp; వెల : {price}</div>
                <div>{telugu_date_formatted}</div>
            </div>
            """
        else:
            header_block = f"""
            <div class="continuation-header" style="display: flex; width: 100%; height: 45px; background: #ffffff; border-bottom: 2px solid #006633; padding: 4px 10px; box-sizing: border-box; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <img src="{logo_url}" alt="{sanitize_text(publication_name)}" style="max-height: 38px; object-fit: contain;" />
                    <span style="font-size: 13px; font-weight: bold; color: #006633;">{sanitize_text(publication_name)} — దినపత్రిక</span>
                </div>
                <div style="font-size: 11px; font-weight: bold; color: #333;">{telugu_date_formatted} &nbsp;|&nbsp; పేజీ {page_num} of {total_pages}</div>
            </div>
            """

        # Build grid slots for articles
        grid_items_html = []
        count_in_page = len(page_articles)

        # Headline color hierarchy
        headline_colors = ["#D60000", "#003399", "#8B0055", "#006600", "#111111", "#003399", "#D60000"]

        for idx, art in enumerate(page_articles):
            slot_num = idx + 1
            headline = sanitize_text(art.get("headline") or art.get("title") or "ముఖ్యాంశం")
            subheadline = sanitize_text(art.get("subheadline") or "")
            kicker = sanitize_text(art.get("kicker") or "")
            content = sanitize_text(art.get("content") or art.get("summary") or "")
            reporter = sanitize_text(art.get("reporter_name") or art.get("byline") or "రిపోర్టర్")
            loc = sanitize_text(art.get("location") or art.get("district") or "")
            
            # Photos
            imgs = art.get("image_urls") or []
            if not imgs and art.get("image_url"):
                imgs = [art.get("image_url")]
            
            # Custom slot layout rules based on position in 10-article page
            grid_style = "grid-column: span 1; grid-row: span 1;"
            is_lead = False
            is_feature = False
            title_color = headline_colors[idx % len(headline_colors)]

            if count_in_page == 10:
                if slot_num in (1, 2):
                    grid_style = "grid-column: span 2;"
                elif slot_num == 3:
                    grid_style = "grid-column: span 1;"
                elif slot_num == 4:
                    grid_style = "grid-column: span 2; background: #fffdf5; border: 2px solid #D60000;"
                    is_lead = True
                    title_color = "#D60000"
                elif slot_num == 5:
                    grid_style = "grid-column: span 1;"
                elif slot_num in (6, 7):
                    grid_style = "grid-column: span 1;"
                elif slot_num == 8:
                    grid_style = "grid-column: span 2;"
                elif slot_num == 9:
                    grid_style = "grid-column: span 3; background: #f5f9ff;"
                    is_feature = True
                    title_color = "#003399"
                elif slot_num == 10:
                    grid_style = "grid-column: span 1;"
            else:
                # Dynamic rebalancing for partially filled pages
                if count_in_page == 1:
                    grid_style = "grid-column: span 4;"
                    is_lead = True
                elif count_in_page == 2:
                    grid_style = "grid-column: span 2;"
                elif count_in_page == 3:
                    grid_style = "grid-column: span 4;" if idx == 0 else "grid-column: span 2;"
                elif count_in_page == 4:
                    grid_style = "grid-column: span 2;"
                elif count_in_page == 5:
                    grid_style = "grid-column: span 2;" if idx < 2 else ("grid-column: span 2;" if idx == 2 else "grid-column: span 1;")
                elif count_in_page in (6, 7, 8, 9):
                    if idx == 0:
                        grid_style = "grid-column: span 2;"
                    elif idx == 1:
                        grid_style = "grid-column: span 2;"
                    elif idx == 2 and count_in_page >= 7:
                        grid_style = "grid-column: span 2;"
                    else:
                        grid_style = "grid-column: span 1;"

            # Image markup
            img_html = ""
            if imgs and len(imgs) > 0:
                first_img = imgs[0]
                img_height = "180px" if is_lead else ("150px" if is_feature else "120px")
                img_html = f"""
                <div style="margin: 6px 0; text-align: center;">
                    <img src="{first_img}" style="width: 100%; max-height: {img_height}; object-fit: cover; border: 1px solid #ddd; display: block;" />
                </div>
                """

            # Kicker markup
            kicker_html = f'<div style="font-size: 10px; font-weight: 800; color: #D60000; text-transform: uppercase; margin-bottom: 2px;">{kicker}</div>' if kicker else ""
            subhead_html = f'<div style="font-size: 12px; font-weight: 700; color: #333; margin-top: 3px; line-height: 1.25;">{subheadline}</div>' if subheadline else ""

            # Highlights list
            highlights_html = ""
            hl_list = art.get("highlight_list") or []
            if hl_list:
                items = "".join([f'<li style="margin-bottom: 2px;"><span style="color: #D60000; margin-right: 4px;">▶</span>{sanitize_text(h)}</li>' for h in hl_list])
                highlights_html = f'<ul style="list-style: none; padding-left: 0; margin: 6px 0; font-size: 10.5px; font-weight: bold; background: #fff5f5; padding: 4px 6px; border-left: 3px solid #D60000;">{items}</ul>'

            # Headline size
            h_size = "22px" if is_lead else ("18px" if is_feature else ("15px" if "span 2" in grid_style or "span 3" in grid_style else "13.5px"))
            h_weight = "900" if is_lead else "800"

            byline_str = f"{loc} &nbsp;|&nbsp; {reporter}" if loc and reporter else (loc or reporter)

            item_html = f"""
            <div class="article-cell" style="{grid_style} border: 1px solid #b0b0b0; padding: 6px 8px; box-sizing: border-box; display: flex; flex-direction: column; overflow: hidden; background: #ffffff;">
                {kicker_html}
                <h2 style="font-size: {h_size}; font-weight: {h_weight}; color: {title_color}; margin: 0; line-height: 1.2; letter-spacing: -0.2px;">
                    {headline}
                </h2>
                {subhead_html}
                {img_html}
                <div style="font-size: 9.5px; font-weight: bold; color: #666; margin: 3px 0 4px 0; border-bottom: 1px solid #eee; padding-bottom: 2px;">
                    {byline_str}
                </div>
                {highlights_html}
                <div style="font-size: 10.5px; line-height: 1.36; color: #111; text-align: justify; flex: 1;">
                    {content}
                </div>
            </div>
            """
            grid_items_html.append(item_html)

        grid_content = "".join(grid_items_html)

        page_markup = f"""
        <div class="page-container">
            {header_block}
            <div class="articles-grid">
                {grid_content}
            </div>
            <div class="footer-strip">
                <span>{sanitize_text(publication_name)} — TELUGU DAILY</span>
                <span>{telugu_date_formatted}</span>
                <span>PAGE {page_num} OF {total_pages}</span>
            </div>
        </div>
        """
        pages_html.append(page_markup)

    full_body = "".join(pages_html)

    html = f"""<!DOCTYPE html>
<html lang="te">
<head>
    <meta charset="UTF-8">
    <title>{sanitize_text(publication_name)} - {edition_date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+Telugu:wght@400;600;700;800;900&family=Mandali&family=Cinzel:wght@700&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: 297mm 420mm; /* A3 Portrait */
            margin: 8mm 10mm 10mm 10mm;
        }}
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        html, body {{
            background: #ffffff;
            color: #000000;
            font-family: 'Noto Serif Telugu', serif;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .page-container {{
            width: 277mm;
            height: 402mm;
            box-sizing: border-box;
            page-break-after: always;
            page-break-inside: avoid;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: #ffffff;
            position: relative;
        }}
        .articles-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: auto;
            gap: 6px;
            flex: 1;
            margin-top: 4px;
            box-sizing: border-box;
        }}
        .footer-strip {{
            height: 20px;
            border-top: 1.5px solid #000000;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 9.5px;
            font-weight: bold;
            color: #444;
            padding: 0 4px;
            margin-top: 4px;
            font-family: sans-serif;
        }}
    </style>
</head>
<body>
    {full_body}
</body>
</html>
"""
    return html

def render_html_to_pdf(html_content: str, output_path: str) -> bool:
    """Render HTML string to A3 PDF file using Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A3",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            browser.close()
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"Playwright PDF rendering error: {e}")
        print(f"Playwright PDF rendering error: {e}")
        return False

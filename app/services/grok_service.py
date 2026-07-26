import json
import httpx
import re
from typing import Dict, Any, List
from app.core.config import settings

class GrokService:
    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        # Auto-detect Groq keys starting with gsk_
        if self.api_key and self.api_key.startswith("gsk_"):
            self.base_url = "https://api.groq.com/openai/v1/chat/completions"
            self.model = "llama-3.3-70b-versatile"
        else:
            self.base_url = "https://api.x.ai/v1/chat/completions"
            self.model = "grok-beta"
            
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def format_article(self, content: str, language: str = "en") -> Dict[str, Any]:
        """
        Rewrites a raw article into a newspaper-style format with headline, 
        subheadings, and body paragraphs optimized for a clipping layout.
        """
        language_map = {
            "en": "English",
            "te": "Telugu",
            "hi": "Hindi",
            "kn": "Kannada",
            "ta": "Tamil",
            "ml": "Malayalam"
        }
        full_lang = language_map.get(language.lower(), language)
        
        prompt = f"""
        Act as a professional JSON formatter. You must format the following content into a newspaper JSON structure.
        
        CRITICAL REQUIREMENT 1: LANGUAGE ENFORCEMENT. You MUST output ALL content strictly in {full_lang}. If the original content is NOT in {full_lang}, you MUST translate every single word into {full_lang}. Do NOT output in the original language unless it is already {full_lang}.
        
        CRITICAL REQUIREMENT 2: PRESERVE MEANING. While translating to {full_lang}, you MUST preserve 100% of the original meaning and facts. Every paragraph must be kept intact in the "sections" array. Do not summarize or shorten.
        
        CRITICAL REQUIREMENT 3: Extract the reporter/author name from the content if provided. DO NOT INVENT AUTHORS. If no author is found, set "byline" to "" (empty string).
        
        CRITICAL REQUIREMENT 4: Provide image captions based on the context in an "image_captions" array. Do not output "Uploaded image" or "Photo shown". Ensure there are up to 8 professional captions provided.
        
        CRITICAL REQUIREMENT 5: Generate a concise, engaging summary paragraph based on the content in {full_lang}.
        
        CRITICAL REQUIREMENT 6: Generate an array of 3-5 short bullet points summarizing the key takeaways from the article in {full_lang}.
        
        The response MUST be a JSON object with the following keys:
        - headline: A catchy, professional newspaper headline strictly in {full_lang}.
        - subheadline: A brief summary line strictly in {full_lang}.
        - sections: An array of strings, where each string is a well-formatted paragraph strictly translated to {full_lang}. Ensure NO description is omitted.
        - dateline: A standard newspaper dateline (e.g., location and date) strictly in {full_lang}.
        - byline: The extracted author name strictly in {full_lang}, or "" if none.
        - image_captions: An array of strings containing professional captions strictly in {full_lang}.
        - summary: A concise summary paragraph strictly in {full_lang}.
        - bullet_points: An array of strings containing 3-5 key takeaways strictly in {full_lang}.
        
        Original Content:
        {content}
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor. You MUST translate and write EVERYTHING strictly in {full_lang}. Do NOT use any other language. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions, summary, bullet_points."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2500
        }

        last_error = ""
        import asyncio
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(self.base_url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    raw_content = result["choices"][0]["message"]["content"]
                    if raw_content.startswith("```"):
                        raw_content = raw_content.strip("` \n")
                        if raw_content.lower().startswith("json"):
                            raw_content = raw_content[4:].strip()
                    ai_content = json.loads(raw_content)
                    # Normalize keys to lowercase to prevent missing data in layouts
                    normalized = {k.lower().replace(" ", "_"): v for k, v in ai_content.items()}
                    return normalized
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 413, 400) and attempt < max_retries - 1:
                    payload["max_tokens"] = 1500
                    if payload["model"] == "llama-3.3-70b-versatile":
                        payload["model"] = "llama-3.1-8b-instant"
                        print("[INFO] Rate or token limit reached on 70B model. Falling back to llama-3.1-8b-instant.")
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                last_error = f"HTTP Error {e.response.status_code}: {e.response.text}"
                print(f"[WARNING] Grok API call failed (attempt {attempt+1}), using graceful fallback: {repr(e)}. Response Body: {e.response.text}")
                break
            except Exception as e:
                last_error = f"Error: {repr(e)}"
                print(f"[WARNING] Grok API call failed, using graceful fallback: {repr(e)}")
                break

        # Fallback to local parsing of content if all retries fail
        sections = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not sections:
            sections = [content]
            
        headline_fallback = sections[0][:60] + "..." if len(sections[0]) > 60 else sections[0]
        subheadline_fallback = ""
        body_sections = sections
        
        # Smart fallback: if there are multiple paragraphs, treat the first as headline, second as subheadline
        if len(sections) > 1 and len(sections[0]) < 150:
            headline_fallback = sections[0]
            if len(sections) > 2 and len(sections[1]) < 200:
                subheadline_fallback = sections[1]
                body_sections = sections[2:]
            else:
                body_sections = sections[1:]

        # Smart extraction of summary and key takeaways directly from article content (NO ERROR STRINGS)
        summary_fallback, bullet_points_fallback = self._extract_summary_and_bullets(content)

        # Localized image captions fallback
        caption_fallbacks = {
            "te": ["ఈవెంట్ యొక్క ముఖ్య క్షణాన్ని బంధించే ఫోటో.", "తాజా పరిణామంపై అదనపు దృశ్యం."],
            "hi": ["इवेंट के मुख्य क्षण की फोटो।", "नवीनतम विकास पर अतिरिक्त दृष्टिकोण।"],
            "kn": ["ಕಾರ್ಯಕ್ರಮದ ಪ್ರಮುಖ ಕ್ಷಣವನ್ನು ಸೆರೆಹಿಡಿಯುವ ಫೋಟೋ.", "ಇತ್ತೀಚಿನ ಬೆಳವಣಿಗೆಯ ಕುರಿತು ಹೆಚ್ಚುವರಿ ನೋಟ."],
            "ta": ["நிகழ்வின் முக்கிய தருணத்தை படம்பிடிக்கும் புகைப்படம்.", "சமீபத்திய வளர்ச்சியின் கூடுதல் பார்வை."],
            "ml": ["ഇവന്റിന്റെ പ്രധാന നിമിഷം പകർത്തുന്ന ഫോട്ടോ.", "സമീപകാല വികസനത്തെക്കുറിച്ചുള്ള അധിക കാഴ്ചപ്പാട്."],
            "en": ["Photo capturing the key moment of the event.", "Additional perspective on the recent development."]
        }
        
        lang_key = language.lower()
        reverse_map = {v.lower(): k for k, v in language_map.items()}
        if lang_key in reverse_map:
            lang_key = reverse_map[lang_key]
        if lang_key not in caption_fallbacks:
            lang_key = "en"
            
        return {
            "headline": headline_fallback,
            "subheadline": subheadline_fallback,
            "sections": body_sections,
            "dateline": "",
            "byline": "",
            "image_captions": caption_fallbacks[lang_key],
            "summary": summary_fallback,
            "bullet_points": bullet_points_fallback
        }

    def _extract_summary_and_bullets(self, content: str) -> tuple:
        """Extracts clean, non-error summary and key takeaways from raw content."""
        paragraphs = [p.strip() for p in content.replace("\r", "\n").split("\n") if p.strip()]
        
        sentences = []
        for p in paragraphs:
            chunks = re.split(r'[\.!\?।]+', p)
            for c in chunks:
                cleaned = c.strip()
                if len(cleaned) > 15:
                    sentences.append(cleaned)
                    
        if not sentences:
            clean_content = content.strip()
            if clean_content:
                sentences = [clean_content[:150]]
            else:
                sentences = ["తాజా సమాచారం ప్రకారం వివరాలు సిద్ధమవుతున్నాయి."]

        # 1. Build summary paragraph (first 1-2 clean sentences)
        if len(sentences) >= 2:
            summary = f"{sentences[0]}. {sentences[1]}."
        else:
            summary = f"{sentences[0]}."
            
        if len(summary) > 250:
            summary = summary[:247] + "..."

        # 2. Build 3 key takeaway bullets from content sentences
        bullets = []
        for s in sentences:
            bullet_text = s[:120].strip()
            if bullet_text and bullet_text not in bullets:
                bullets.append(bullet_text if bullet_text.endswith(('.', '।')) else bullet_text + ".")
            if len(bullets) == 3:
                break
                
        # Fill to 3 bullets if content is short
        while len(bullets) < 3:
            if bullets:
                last = bullets[-1]
                if len(last) > 40:
                    split_idx = len(last) // 2
                    bullets.append(last[split_idx:].strip())
                else:
                    bullets.append(bullets[0])
            else:
                bullets.append(summary[:80] + "...")

        return summary, bullets[:3]

grok_service = GrokService()


import json
import httpx
import re
from typing import Dict, Any, List
from app.core.config import settings

class GrokService:
    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        # Auto-detect Groq keys starting with gsk_
        # Auto-detect Groq keys starting with gsk_
        if self.api_key and self.api_key.startswith("gsk_"):
            self.base_url = "https://api.groq.com/openai/v1/chat/completions"
            self.model = "llama-3.1-8b-instant"
        else:
            self.base_url = "https://api.x.ai/v1/chat/completions"
            self.model = "grok-2-latest"
            
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
        
        CRITICAL REQUIREMENT 4: Provide image captions based on the context in an "image_captions" array. Do not output "Uploaded image" or "Photo shown". Ensure there are up to 8 professional captions provided strictly in {full_lang}.
        
        CRITICAL REQUIREMENT 5: Generate a detailed, informative summary paragraph (3-4 complete sentences, ~350-450 characters) based on the content strictly in {full_lang}. DO NOT USE ENGLISH for summary if {full_lang} is not English.
        
        CRITICAL REQUIREMENT 6: Generate an array of 4-5 complete, informative bullet points summarizing the key takeaways from the article strictly in {full_lang}. DO NOT USE ENGLISH for bullet points if {full_lang} is not English.
        
        The response MUST be a JSON object with the following keys:
        - headline: A catchy, professional newspaper headline strictly in {full_lang}.
        - subheadline: A brief summary line strictly in {full_lang}.
        - sections: An array of strings, where each string is a well-formatted paragraph strictly translated to {full_lang}. Ensure NO description is omitted.
        - dateline: A standard newspaper dateline (e.g., location and date) strictly in {full_lang}.
        - byline: The extracted author name strictly in {full_lang}, or "" if none.
        - image_captions: An array of strings containing professional captions strictly in {full_lang}.
        - summary: A detailed summary paragraph strictly in {full_lang}.
        - bullet_points: An array of strings containing 4-5 key takeaways strictly in {full_lang}.
        
        Original Content:
        {content}
        """
        
        payload = {
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor. You MUST translate and write EVERYTHING strictly in {full_lang}. Do NOT use any other language for any field. Summary and bullet_points MUST be written in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions, summary, bullet_points."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2500
        }

        if self.api_key and self.api_key.startswith("gsk_"):
            models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        else:
            models_to_try = ["grok-2-latest", "grok-2", "grok-beta"]

        normalized = None
        import asyncio
        for model in models_to_try:
            payload["model"] = model
            url = "https://api.groq.com/openai/v1/chat/completions" if "llama" in model else self.base_url
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    raw_content = result["choices"][0]["message"]["content"]
                    if raw_content.startswith("```"):
                        raw_content = raw_content.strip("` \n")
                        if raw_content.lower().startswith("json"):
                            raw_content = raw_content[4:].strip()
                    ai_content = json.loads(raw_content)
                    normalized = {k.lower().replace(" ", "_"): v for k, v in ai_content.items()}
                    break # Success!
            except Exception as e:
                print(f"[WARNING] Model {model} failed: {e}")
                await asyncio.sleep(0.3)

        if not normalized:
            # Fallback to local parsing of content if AI calls fail
            clean_sum, clean_bps = self._extract_summary_and_bullets(content)
            sections = [p.strip() for p in content.split("\n\n") if p.strip()] or [content]
            return {
                "headline": sections[0][:60] + "..." if len(sections[0]) > 60 else sections[0],
                "subheadline": "",
                "sections": sections,
                "dateline": "",
                "byline": "",
                "image_captions": ["ఈవెంట్ యొక్క ముఖ్య క్షణాన్ని బంధించే ఫోటో.", "తాజా పరిణామంపై అదనపు దృశ్యం."],
                "summary": clean_sum,
                "bullet_points": clean_bps
            }

        # Post-process target language compliance
        lang_key = language.lower()
        reverse_map = {v.lower(): k for k, v in language_map.items()}
        if lang_key in reverse_map:
            lang_key = reverse_map[lang_key]
            
        if lang_key != "en":
            sec_list = normalized.get("sections", [])
            sec_text = "\n\n".join(sec_list) if isinstance(sec_list, list) else str(sec_list)
            if not sec_text.strip():
                sec_text = content
                
            sum_val = normalized.get("summary", "")
            bp_val = normalized.get("bullet_points", [])
            
            if self._is_mostly_english(sum_val) or self._is_mostly_english(bp_val):
                clean_sum, clean_bps = self._extract_summary_and_bullets(sec_text)
                if self._is_mostly_english(sum_val):
                    normalized["summary"] = clean_sum
                if self._is_mostly_english(bp_val):
                    normalized["bullet_points"] = clean_bps

        return normalized

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

    def _is_mostly_english(self, data: Any) -> bool:
        """Returns True if the data contains 3 or more English words."""
        if isinstance(data, list):
            text = " ".join(str(item) for item in data)
        else:
            text = str(data or "")
        if not text.strip():
            return False
        english_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        return len(english_words) >= 3

    def _extract_summary_and_bullets(self, content: str) -> tuple:
        """Extracts clean, non-error summary and key takeaways from raw content without breaking abbreviations."""
        raw_text = content.replace("\r", "\n").strip()
        
        # Protect abbreviation dots (e.g., ఆర్., టి., ఐ., శ్రీ., డా., బి., 26.07)
        protected_text = re.sub(r'(\b[^\s\.]{1,4})\.\s+', r'\1_DOT_ ', raw_text)
        protected_text = re.sub(r'(\d+)\.(\d+)', r'\1_NUMDOT_\2', protected_text)
        
        # Split by actual sentence endings (. or । or ? or ! or \n)
        chunks = [c.replace('_DOT_', '.').replace('_NUMDOT_', '.').strip() for c in re.split(r'[\.!\?।\n]+', protected_text) if c.strip()]
        
        sentences = [c for c in chunks if len(c) > 15]
        if not sentences:
            clean_content = content.strip()
            if clean_content:
                sentences = [clean_content[:150]]
            else:
                sentences = ["తాజా సమాచారం ప్రకారం వివరాలు సిద్ధమవుతున్నాయి."]

        # 1. Build rich summary paragraph (up to ~450 chars)
        summary_sentences = sentences[:3]
        summary = " ".join(s.rstrip('.') + '.' for s in summary_sentences)
        if len(summary) > 480:
            summary = summary[:477] + "..."

        # 2. Extract clauses for 4-5 key takeaway bullet points
        clauses = []
        for s in sentences:
            if len(s) > 120 and ',' in s:
                parts = [p.strip() for p in s.split(',') if len(p.strip()) > 15]
                clauses.extend(parts)
            else:
                clauses.append(s)
                
        bullets = []
        for c in clauses:
            clean_c = c.strip()
            if clean_c and clean_c not in bullets:
                if not clean_c.endswith(('.', '।')):
                    clean_c += "."
                bullets.append(clean_c)
            if len(bullets) == 5:
                break
                
        # Fill to 4 bullets if content is short
        while len(bullets) < 4:
            if bullets:
                last = bullets[-1]
                if len(last) > 50:
                    split_idx = len(last) // 2
                    bullets.append(last[split_idx:].strip())
                else:
                    bullets.append(bullets[0])
            else:
                bullets.append(summary[:100] + "...")

        return summary, bullets[:5]

grok_service = GrokService()




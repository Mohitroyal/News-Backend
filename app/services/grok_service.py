import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional

language_map = {
    "te": "Telugu",
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
    "ml": "Malayalam",
    "en": "English",
    "telugu": "Telugu",
    "hindi": "Hindi",
    "kannada": "Kannada",
    "tamil": "Tamil",
    "malayalam": "Malayalam",
    "english": "English"
}

class GrokService:
    def __init__(self):
        self.api_key = os.getenv("GROK_API_KEY") or os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def format_article(self, content: str, language: str = "te", image_count: int = 1) -> Dict[str, Any]:
        """Formats and structures news article text."""
        return await self.process_text_with_grok(content, language, image_count)

    async def process_text_with_grok(self, content: str, language: str = "te", image_count: int = 1) -> Dict[str, Any]:
        """
        Processes news text to extract structured fields and translate if needed.
        """
        full_lang = language_map.get(language.lower(), "Telugu")
        
        prompt = f"""
        Analyze the following raw news article and reformat it into a structured newspaper layout object.
        Language required for output: {full_lang}.
        
        CRITICAL CONTENT PRESERVATION RULES:
        1. "sections": Array of body text paragraphs (in {full_lang}). You MUST preserve 100% of the raw article text! Do NOT summarize, shorten, condense, or omit any sentences, names, figures (e.g. 8000 కోట్లు), or facts. Split the COMPLETE text into 3 to 5 logical paragraphs without deleting any original words.
        2. "headline": Catchy, impactful main headline (in {full_lang}, maximum 120 characters).
        3. "subheadline": Subheading or context tag (in {full_lang}, maximum 90 characters).
        4. "dateline": Location/Date tag (e.g., "సంగారెడ్డి:").
        5. "byline": Reporter/Source tag (e.g., "భారత్ రిపోర్టర్").
        6. "image_captions": Array of {image_count} photo captions (in {full_lang}, 1 caption per image).
        7. "summary": A comprehensive 2-3 sentence executive summary of the article (in {full_lang}, ~250-350 characters).
        8. "bullet_points": Array of exactly 4 to 5 concise key takeaways/highlights from the article (in {full_lang}, max 85 chars per point).

        Raw Article Text:
        {content}
        """
        
        payload = {
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor. You MUST preserve 100% of the user's raw article text inside 'sections' without summarizing, omitting, or deleting any text. Translate and write EVERYTHING strictly in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions, summary, bullet_points."},
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
            
            caption_fallbacks = {
                "te": ["కార్యక్రమానికి సంబంధించిన ముఖ్య చిత్రం.", "తాజా పరిణామంపై అదనపు దృశ్యం."],
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
            caps = caption_fallbacks.get(lang_key, caption_fallbacks["en"])

            return {
                "headline": sections[0][:60] + "..." if len(sections[0]) > 60 else sections[0],
                "subheadline": "",
                "sections": sections,
                "dateline": "",
                "byline": "",
                "image_captions": caps,
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
            
            if self._is_mostly_english(sum_val, lang_key) or self._is_mostly_english(bp_val, lang_key):
                clean_sum, clean_bps = self._extract_summary_and_bullets(sec_text)
                if self._is_mostly_english(sum_val, lang_key):
                    normalized["summary"] = clean_sum
                if self._is_mostly_english(bp_val, lang_key):
                    normalized["bullet_points"] = clean_bps

        return normalized

    def _is_mostly_english(self, data: Any, target_lang: str = "en") -> bool:
        """Returns True ONLY if Latin ASCII characters overwhelmingly dominate the text for a non-English target language."""
        if target_lang.lower() in ["en", "english"]:
            return False
        if isinstance(data, list):
            text = " ".join(str(item) for item in data)
        else:
            text = str(data or "")
        text = text.strip()
        if not text:
            return False
        
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        non_latin_chars = len(re.findall(r'[^\x00-\x7F]', text))
        
        if non_latin_chars == 0:
            return latin_chars > 8
            
        return latin_chars > (non_latin_chars * 2)

    def _extract_summary_and_bullets(self, content: str) -> tuple:
        """Extracts clean, meaningful summary and key takeaways by filtering out header artifacts, equals lines and datelines."""
        raw_text = content.replace("\r", "\n").strip()
        
        # 1. Clean out divider lines, equals signs, datelines and empty artifacts
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        clean_paragraphs = []
        
        for l in lines:
            if re.search(r'^[=\-_.\s]{3,}$', l):
                continue
            clean_l = re.sub(r'[=\-_]{2,}', '', l).strip()
            if len(clean_l) < 30 and ("ప్రతినిధి" in clean_l or "రిపోర్టర్" in clean_l or "నాయక్" in clean_l):
                continue
            if clean_l:
                clean_paragraphs.append(clean_l)

        full_clean_text = " ".join(clean_paragraphs)
        
        # Protect abbreviation dots
        protected_text = re.sub(r'(\b[^\s\.]{1,4})\.\s+', r'\1_DOT_ ', full_clean_text)
        protected_text = re.sub(r'(\d+)\.(\d+)', r'\1_NUMDOT_\2', protected_text)
        
        raw_chunks = [c.replace('_DOT_', '.').replace('_NUMDOT_', '.').strip() for c in re.split(r'[\.!\?।\n]+', protected_text) if c.strip()]
        sentences = []
        for s in raw_chunks:
            clean_s = re.sub(r'[=\-_]{2,}', '', s).strip()
            if len(clean_s) > 25 and not clean_s.startswith("సంగారెడ్డి జిల్లా : ప్రతినిధి"):
                sentences.append(clean_s)
                
        if not sentences:
            sentences = [full_clean_text[:150]] if full_clean_text else ["తాజా సమాచారం ప్రకారం వివరాలు సిద్ధమవుతున్నాయి."]

        # Summary: Take substantial body sentences (up to ~300 chars)
        summary_sentences = []
        total_len = 0
        for s in sentences:
            if total_len + len(s) <= 320:
                summary_sentences.append(s.rstrip('.') + '.')
                total_len += len(s)
            else:
                if not summary_sentences:
                    summary_sentences.append(s[:315].rsplit(' ', 1)[0] + '...')
                break
                
        summary = " ".join(summary_sentences)

        # Bullet Points: Extract 4-5 concise key takeaway clauses (max 85 chars each)
        bullets = []
        for s in sentences:
            sub_parts = re.split(r'[,;—–-]', s)
            for p in sub_parts:
                clean_p = p.strip()
                clean_p = re.sub(r'^[•\-\*\d\.\s]+', '', clean_p)
                if 20 <= len(clean_p) <= 85:
                    if not clean_p.endswith(('.', '।')):
                        clean_p += "."
                    if clean_p not in bullets:
                        bullets.append(clean_p)
                elif len(clean_p) > 85:
                    truncated = clean_p[:82].rsplit(' ', 1)[0] + "..."
                    if truncated not in bullets:
                        bullets.append(truncated)
                if len(bullets) >= 5:
                    break
            if len(bullets) >= 5:
                break

        # Fallback to ensure 4 to 5 bullet points
        if len(bullets) < 4:
            for s in sentences:
                clean_s = s.strip()
                clean_s = re.sub(r'^[•\-\*\d\.\s]+', '', clean_s)
                if len(clean_s) > 85:
                    clean_s = clean_s[:82].rsplit(' ', 1)[0] + "..."
                if clean_s and clean_s not in bullets:
                    bullets.append(clean_s)
                if len(bullets) >= 4:
                    break

        return summary, bullets[:5]

grok_service = GrokService()

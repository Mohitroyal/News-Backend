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
        
        CRITICAL CONTENT PRESERVATION & FULL KEY TAKEAWAYS RULES:
        1. "sections": Array of body text paragraphs (in {full_lang}). You MUST preserve 100% of the raw article text! Do NOT summarize, shorten, condense, or omit any sentences, names, figures (e.g. 8000 కోట్లు), or facts. Split the COMPLETE raw text into 3 to 5 logical paragraphs without deleting any original words or content.
        2. "headline": Catchy, impactful main headline (in {full_lang}, maximum 120 characters).
        3. "subheadline": Subheading or context tag (in {full_lang}, maximum 90 characters).
        4. "dateline": Location/Date tag (e.g., "సంగారెడ్డి:").
        5. "byline": Reporter/Source tag (e.g., "భారత్ రిపోర్టర్").
        6. "image_captions": Array of {image_count} photo captions (in {full_lang}, 1 caption per image).
        7. "summary": A comprehensive 2-3 sentence executive summary of the article (in {full_lang}, ~250-350 characters).
        8. "bullet_points": Array of exactly 4 to 5 complete, clear key takeaways/highlights from the article (in {full_lang}, max 130 chars per point). Each key takeaway point MUST be a complete, meaningful sentence.

        ABSOLUTE MANDATE: You MUST include BOTH the 100% complete body text inside 'sections' AND 4 to 5 complete key takeaways inside 'bullet_points'. NEVER omit or reduce 'sections' text to make room for bullet points, and NEVER omit or shorten key takeaways when providing body content.

        Raw Article Text:
        {content}
        """
        
        payload = {
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor. You MUST preserve 100% of the user's raw article text inside 'sections' without summarizing, omitting, or deleting any text, AND generate 4 to 5 complete key takeaways inside 'bullet_points'. Translate and write EVERYTHING strictly in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions, summary, bullet_points."},
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

        # Post-process target language compliance & ensure 4-5 bullet points
        lang_key = language.lower()
        reverse_map = {v.lower(): k for k, v in language_map.items()}
        if lang_key in reverse_map:
            lang_key = reverse_map[lang_key]
            
        sec_list = normalized.get("sections", [])
        sec_text = "\n\n".join(sec_list) if isinstance(sec_list, list) else str(sec_list)
        raw_clean = content.replace("\r", "\n").strip()

        # Enforce 100% raw content preservation if AI omitted sentences from sections
        if len(sec_text.strip()) < len(raw_clean) * 0.90:
            print(f"[PRESERVATION ENFORCER] AI model omitted text ({len(sec_text.strip())} < {len(raw_clean)} chars). Restoring 100% raw content.")
            raw_paras = [p.strip() for p in raw_clean.split("\n\n") if p.strip()]
            if len(raw_paras) <= 1:
                s_chunks = [s.strip() for s in re.split(r'[\.!\?।]+', raw_clean) if s.strip()]
                new_paras = []
                chunk_size = max(2, len(s_chunks) // 3)
                for i in range(0, len(s_chunks), chunk_size):
                    piece = ". ".join(s_chunks[i:i+chunk_size]).strip()
                    if piece:
                        new_paras.append(piece + ".")
                normalized["sections"] = new_paras if new_paras else [raw_clean]
            else:
                normalized["sections"] = raw_paras
            sec_text = "\n\n".join(normalized["sections"])
            
        sum_val = normalized.get("summary", "")
        bp_val = normalized.get("bullet_points", [])
        
        if not isinstance(bp_val, list) or len(bp_val) < 4:
            clean_sum, clean_bps = self._extract_summary_and_bullets(sec_text or content)
            normalized["bullet_points"] = clean_bps
            if not sum_val:
                normalized["summary"] = clean_sum
        elif lang_key != "en":
            if self._is_mostly_english(sum_val, lang_key) or self._is_mostly_english(bp_val, lang_key):
                clean_sum, clean_bps = self._extract_summary_and_bullets(sec_text or content)
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
        
        # 1. Clean out divider lines, equals signs, and dateline artifacts
        clean_text = re.sub(r'[=\-_]{2,}', '', raw_text).strip()
        clean_text_no_header = re.sub(r'^.*?ప్రతినిధి\s*\([^)]*\)\s*\d*\s*[^\s]*\s*', '', clean_text)
        if not clean_text_no_header.strip():
            clean_text_no_header = clean_text

        # Protect decimal numbers and single-letter/known abbreviations (e.g. M. Rajeshwar, 14.06.2026)
        protected_text = re.sub(r'(\d+)\.(\d+)', r'\1_NUMDOT_\2', clean_text_no_header)
        protected_text = re.sub(r'(\b[A-Za-zఅ-హ]\.)\s*', r'\1_DOT_ ', protected_text)
        protected_text = re.sub(r'\b(Dr|Mr|Mrs|Prof|No|Vol|vs|శ్రీ)\.\s*', r'\1_DOT_ ', protected_text, flags=re.IGNORECASE)
        
        # Split strictly into whole sentences (by period, question mark, exclamation mark, purna viram, or newline)
        raw_chunks = [c.replace('_DOT_', '.').replace('_NUMDOT_', '.').strip() for c in re.split(r'[\.!\?।\n]+', protected_text) if c.strip()]
        sentences = []
        for s in raw_chunks:
            clean_s = re.sub(r'[=\-_]{2,}', '', s).strip()
            if len(clean_s) >= 15:
                sentences.append(clean_s)
                
        if not sentences:
            sentences = [clean_text_no_header[:150]] if clean_text_no_header else ["తాజా సమాచారం ప్రకారం వివరాలు సిద్ధమవుతున్నాయి."]

        # Summary: Take first 2-3 substantial sentences (up to ~350 chars)
        summary_sentences = []
        total_len = 0
        for s in sentences:
            clean_stmt = s.rstrip('.') + '.'
            if total_len + len(clean_stmt) <= 350:
                summary_sentences.append(clean_stmt)
                total_len += len(clean_stmt)
            else:
                if not summary_sentences:
                    summary_sentences.append(clean_stmt)
                break
                
        summary = " ".join(summary_sentences)

        # Bullet Points: Use complete, clean sentences as bullet points (4 to 5 points)
        bullets = []
        for s in sentences:
            clean_b = s.strip()
            clean_b = re.sub(r'^[•\-\*\d\.\s]+', '', clean_b)
            clean_b = re.sub(r'^[:\s]+', '', clean_b)
            if len(clean_b) >= 15:
                if len(clean_b) > 130:
                    clean_b = clean_b[:127].rsplit(' ', 1)[0] + "..."
                elif not clean_b.endswith(('.', '।')):
                    clean_b += "."
                if clean_b not in bullets:
                    bullets.append(clean_b)
                if len(bullets) >= 4:
                    break

        # Fallback if fewer than 4 bullet points (e.g. text only had 1-2 long sentences):
        if len(bullets) < 4:
            raw_clauses = re.split(r'[;—–\n]', clean_text_no_header)
            for c in raw_clauses:
                clean_c = c.strip()
                clean_c = re.sub(r'^[•\-\*\d\.\s]+', '', clean_c)
                clean_c = re.sub(r'^[:\s]+', '', clean_c)
                if len(clean_c) >= 15:
                    if len(clean_c) > 130:
                        clean_c = clean_c[:127].rsplit(' ', 1)[0] + "..."
                    elif not clean_c.endswith(('.', '।')):
                        clean_c += "."
                    if clean_c not in bullets:
                        bullets.append(clean_c)
                    if len(bullets) >= 4:
                        break

        return summary, bullets[:4]

grok_service = GrokService()

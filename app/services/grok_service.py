import json
import httpx
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
            self.model = "grok-2-1212"
            
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
        Act as a professional newspaper editor and translator. Rewrite the following content in a high-quality newspaper style.
        
        CRITICAL REQUIREMENT 1: You MUST translate the ENTIRE output strictly into the '{full_lang}' language using the native '{full_lang}' script.
        DO NOT mix languages. DO NOT use Hindi letters or words if the requested language is Telugu. DO NOT use English letters (transliteration).
        The headline, subheadline, sections, dateline, and byline MUST ALL be strictly in native {full_lang}.
        
        CRITICAL REQUIREMENT 2: DO NOT SUMMARIZE OR SHORTEN. You MUST translate and include EVERY SINGLE WORD, FACT, and DETAIL from the original text into your rewritten {full_lang} article. If the original text is long, your output MUST be equally long. 
        When converting to {full_lang}, do NOT skip any part of the description. Check that 100% of the original information is present in your response.
        
        The response MUST be a JSON object with the following keys:
        - headline: A catchy, professional newspaper headline strictly in {full_lang}.
        - subheadline: A brief summary line strictly in {full_lang}.
        - sections: An array of strings, where each string is a well-formatted paragraph strictly in {full_lang}. Ensure NO description is omitted.
        - dateline: A standard newspaper dateline (e.g., location and date) strictly in {full_lang}.
        - byline: A creative author name strictly in {full_lang}.
        
        Original Content:
        {content}
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor writing strictly in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, ALL written in {full_lang}."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        import asyncio
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(self.base_url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract content from response
                    ai_content = json.loads(result["choices"][0]["message"]["content"])
                    return ai_content
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                print(f"[WARNING] Grok API call failed (attempt {attempt+1}), using graceful fallback: {repr(e)}. Response Body: {e.response.text}")
                break
            except Exception as e:
                print(f"[WARNING] Grok API call failed, using graceful fallback: {repr(e)}")
                break

        # Fallback to local parsing of content if all retries fail
        sections = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not sections:
            sections = [content]
        headline_fallback = sections[0][:60] + "..." if len(sections[0]) > 60 else sections[0]
        return {
            "headline": headline_fallback,
            "subheadline": "Generated offline with local backup layout parser",
            "sections": sections,
            "dateline": "NEW DELHI",
            "byline": "NewsCraft Bureau"
        }

grok_service = GrokService()

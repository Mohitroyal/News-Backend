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
        Act as a professional JSON formatter. You must format the following content into a newspaper JSON structure.
        
        CRITICAL REQUIREMENT 1: DO NOT REWRITE, MODIFY, OR CHANGE THE ORIGINAL CONTENT. You must keep the full content exactly as provided. Do not change any words, phrases, or sentences.
        
        CRITICAL REQUIREMENT 2: DO NOT SUMMARIZE OR SHORTEN. You MUST preserve 100% of the original content. Every single sentence and paragraph from the original article must be kept exactly in the "sections" array verbatim.
        
        CRITICAL REQUIREMENT 3: If the original content is in a different language than '{full_lang}', ONLY translate it. If it is already in '{full_lang}', DO NOT change it at all.
        
        CRITICAL REQUIREMENT 4: Keep the paragraphs exactly as they are provided in the source text. Do not merge or split paragraphs unnecessarily. Just return the full content unmodified.
        
        CRITICAL REQUIREMENT 5: Extract the reporter/author name from the content if provided. DO NOT INVENT AUTHORS. If no author is found, set "byline" to "" (empty string).
        
        CRITICAL REQUIREMENT 5: Provide image captions based on the context in an "image_captions" array. Do not output "Uploaded image" or "Photo shown". Ensure there are up to 8 professional captions provided.
        
        The response MUST be a JSON object with the following keys:
        - headline: A catchy, professional newspaper headline strictly in {full_lang}.
        - subheadline: A brief summary line strictly in {full_lang}.
        - sections: An array of strings, where each string is a well-formatted paragraph strictly in {full_lang}. Ensure NO description is omitted.
        - dateline: A standard newspaper dateline (e.g., location and date) strictly in {full_lang}.
        - byline: The extracted author name strictly in {full_lang}, or "" if none.
        - image_captions: An array of strings containing professional captions.
        
        Original Content:
        {content}
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor writing strictly in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions."},
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
                
        return {
            "headline": headline_fallback,
            "subheadline": subheadline_fallback,
            "sections": body_sections,
            "dateline": "",
            "byline": "",
            "image_captions": ["Photo capturing the key moment of the event.", "Additional perspective on the recent development."]
        }

grok_service = GrokService()

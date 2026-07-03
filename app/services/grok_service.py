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
        
        CRITICAL REQUIREMENT 6: Generate a concise, engaging summary paragraph based on the content.
        
        CRITICAL REQUIREMENT 7: Generate an array of 3-5 short bullet points summarizing the key takeaways from the article.
        
        The response MUST be a JSON object with the following keys:
        - headline: A catchy, professional newspaper headline strictly in {full_lang}.
        - subheadline: A brief summary line strictly in {full_lang}.
        - sections: An array of strings, where each string is a well-formatted paragraph strictly in {full_lang}. Ensure NO description is omitted.
        - dateline: A standard newspaper dateline (e.g., location and date) strictly in {full_lang}.
        - byline: The extracted author name strictly in {full_lang}, or "" if none.
        - image_captions: An array of strings containing professional captions.
        - summary: A concise summary paragraph strictly in {full_lang}.
        - bullet_points: An array of strings containing 3-5 key takeaways strictly in {full_lang}.
        
        Original Content:
        {content}
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"You are a professional newspaper layout editor writing strictly in {full_lang}. You must respond with a JSON object containing keys: headline, subheadline, sections, dateline, byline, image_captions, summary, bullet_points."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 8000
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
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    # Fallback from 70B to 8B if daily token limit is reached
                    if payload["model"] == "llama-3.3-70b-versatile" and "tokens" in e.response.text.lower():
                        payload["model"] = "llama-3.1-8b-instant"
                        print("[INFO] Daily token rate limit exceeded on 70B model. Falling back to llama-3.1-8b-instant.")
                        continue
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
                
        # Localized fallbacks
        fallbacks = {
            "te": {
                "captions": ["ఈవెంట్ యొక్క ముఖ్య క్షణాన్ని బంధించే ఫోటో.", "తాజా పరిణామంపై అదనపు దృశ్యం."],
                "summary": "AI సేవలో లోపం లేదా రేట్ పరిమితి కారణంగా ఈ ఫాల్‌బ్యాక్ సారాంశం రూపొందించబడింది.",
                "bullets": ["AI సృష్టి తాత్కాలికంగా అందుబాటులో లేదు.", "దయచేసి క్లిప్పింగ్‌ను మళ్లీ సృష్టించడానికి ప్రయత్నించండి.", "మీ Grok API కీ మరియు పరిమితులను ధృవీకరించండి."]
            },
            "hi": {
                "captions": ["इवेंट के मुख्य क्षण की फोटो।", "नवीनतम विकास पर अतिरिक्त दृष्टिकोण।"],
                "summary": "यह एक फ़ॉलबैक सारांश है क्योंकि एआई सेवा में त्रुटि या दर सीमा थी।",
                "bullets": ["एआई जनरेशन अस्थायी रूप से अनुपलब्ध है।", "कृपया क्लिपिंग फिर से बनाने का प्रयास करें।", "अपनी Grok API कुंजी और सीमाएँ सत्यापित करें।"]
            },
            "kn": {
                "captions": ["ಕಾರ್ಯಕ್ರಮದ ಪ್ರಮುಖ ಕ್ಷಣವನ್ನು ಸೆರೆಹಿಡಿಯುವ ಫೋಟೋ.", "ಇತ್ತೀಚಿನ ಬೆಳವಣಿಗೆಯ ಕುರಿತು ಹೆಚ್ಚುವರಿ ನೋಟ."],
                "summary": "AI ಸೇವೆಯಲ್ಲಿ ದೋಷ ಅಥವಾ ದರ ಮಿತಿಯನ್ನು ಎದುರಿಸಿದ ಕಾರಣ ಈ ಫಾಲ್‌ಬ್ಯಾಕ್ ಸಾರಾಂಶವನ್ನು ರಚಿಸಲಾಗಿದೆ.",
                "bullets": ["AI ಸೃಷ್ಟಿ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ.", "ದಯವಿಟ್ಟು ಕ್ಲಿಪ್ಪಿಂಗ್ ಅನ್ನು ಮರುಸೃಷ್ಟಿಸಲು ಪ್ರಯತ್ನಿಸಿ.", "ನಿಮ್ಮ Grok API ಕೀ ಮತ್ತು ಮಿತಿಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."]
            },
            "ta": {
                "captions": ["நிகழ்வின் முக்கிய தருணத்தை படம்பிடிக்கும் புகைப்படம்.", "சமீபத்திய வளர்ச்சியின் கூடுதல் பார்வை."],
                "summary": "AI சேவையில் பிழை அல்லது விகித வரம்பு ஏற்பட்டதால் இந்த மாற்று சுருக்கம் உருவாக்கப்பட்டது.",
                "bullets": ["AI உருவாக்கம் தற்காலிகமாக கிடைக்கவில்லை.", "கிளிப்பிங்கை மீண்டும் உருவாக்க முயற்சிக்கவும்.", "உங்கள் Grok API விசை மற்றும் வரம்புகளை சரிபார்க்கவும்."]
            },
            "ml": {
                "captions": ["ഇവന്റിന്റെ പ്രധാന നിമിഷം പകർത്തുന്ന ഫോട്ടോ.", "സമീപകാല വികസനത്തെക്കുറിച്ചുള്ള അധിക കാഴ്ചപ്പാട്."],
                "summary": "AI സേവനത്തിൽ ഒരു പിശകോ നിരക്ക് പരിധിയോ ഉണ്ടായതിനാൽ ഈ താൽക്കാലിക സംഗ്രഹം സൃഷ്ടിച്ചു.",
                "bullets": ["AI നിർമ്മാണം താൽക്കാലികമായി ലഭ്യമല്ല.", "ക്ലിപ്പിംഗ് വീണ്ടും സൃഷ്ടിക്കാൻ ശ്രമിക്കുക.", "നിങ്ങളുടെ Grok API കീയും പരിധികളും പരിശോധിക്കുക."]
            },
            "en": {
                "captions": ["Photo capturing the key moment of the event.", "Additional perspective on the recent development."],
                "summary": "This is a fallback summary generated because the AI service encountered an error or rate limit.",
                "bullets": ["AI generation temporarily unavailable.", "Please try generating the clipping again.", "Verify your Grok API key and limits."]
            }
        }
        
        lang_key = language.lower()
        
        # If the input was the full name (e.g. "telugu"), convert it back to the short key
        reverse_map = {v.lower(): k for k, v in language_map.items()}
        if lang_key in reverse_map:
            lang_key = reverse_map[lang_key]
            
        if lang_key not in fallbacks:
            lang_key = "en"
            
        summary_text = fallbacks[lang_key]["summary"]
        if last_error:
            summary_text += f"\n\nError details: {last_error}"
            
        return {
            "headline": headline_fallback,
            "subheadline": subheadline_fallback,
            "sections": body_sections,
            "dateline": "",
            "byline": "",
            "image_captions": fallbacks[lang_key]["captions"],
            "summary": summary_text,
            "bullet_points": fallbacks[lang_key]["bullets"]
        }

grok_service = GrokService()

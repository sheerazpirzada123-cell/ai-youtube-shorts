from google import genai
import json
import random

FACT_TOPICS = [
    "Wahiyat aur Ajeeb Facts",
    "Insaan ke Jism ke Mind-Blowing Sach",
    "Janwaro ki Shocking Duniya",
    "Antariksh ke Khaufnak Facts",
    "Psychology ke Magical Facts"
]

def generate_fact_script(api_key):
    client = genai.Client(api_key=api_key)
    selected_topic = random.choice(FACT_TOPICS)
    
    prompt = f"""
    Tum ek viral YouTube Shorts content strategist aur scriptwriter ho (jaise "Facts Mine", "Bright Side" jaise channels).
    Topic: "{selected_topic}" par ek engaging 30-second Hindi facts script aur uske saath YouTube ke liye
    trending/SEO-optimized metadata bhi banao.

    RULES FOR SCRIPT:
    1. Language MUST BE natural spoken Hindi (Devanagari script).
    2. Directly start with an energetic hook (first 2 seconds mein curiosity create karo - "Kya aapko pata hai...", "Ye sunke aap...")
    3. Har fact short aur punchy sentences mein ho, taake retention high rahe.
    4. End mein ek chhota CTA ho (jaise "Aise hi Hindi facts ke liye follow karo").

    RULES FOR YOUTUBE METADATA (trending/discoverability ke liye):
    1. "title": Clickbait-style lekin honest hook, emoji ke saath, 60-70 characters, curiosity gap create kare
       (jaise "🤯 Insaan ke Jism ka Ye Sach Aapko Hilaa Dega!"). Hashtag titles mein mat daalo.
    2. "description": 2-3 lines mein fact ka summary + curiosity hook, phir niche 10-15 relevant hashtags
       (mix of broad trending tags jaise #shorts #facts #viral #trending aur specific tags related to topic,
       jaise #hindifacts #amazingfacts #didyouknow #factsinhindi #mindblowingfacts).
    3. "tags": Ek JSON array of 15-20 individual SEO keywords (bina # ke, YouTube tags field ke liye) jo
       is video ko search/suggested mein rank karwayein - mix karo broad high-search-volume keywords
       (jaise "facts", "hindi facts", "amazing facts", "shorts", "viral shorts", "did you know") aur
       specific topic-related keywords.

    Output STRICTLY in this JSON format, bina markdown codeblocks ke:
    {{
        "title": "Title with emoji here",
        "script": "Hindi spoken content...",
        "description": "Description with hashtags here",
        "tags": ["tag1", "tag2", "tag3", "..."]
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

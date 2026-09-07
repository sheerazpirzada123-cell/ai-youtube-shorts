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
    Tum ek viral YouTube Shorts content strategist, scriptwriter, aur video editor ho (jaise "Facts Mine",
    "Bright Side" jaise channels). Topic: "{selected_topic}" par ek engaging 30-40 second Hindi facts
    Short banao, jo SCENE-BY-SCENE structure mein ho (taake har scene ke liye alag matching stock footage
    lagayi ja sake, jaisa professional facts channels karte hain).

    RULES FOR SCENES:
    1. Poori script ko 6-8 chhoti scenes mein todo. Har scene sirf 1 fact/idea cover kare aur bolne mein
       3-5 second ki ho (roughly 8-15 Hindi words).
    2. Language MUST BE natural spoken Hindi (Devanagari script), energetic aur punchy.
    3. Pehli scene ek strong hook ho ("Kya aapko pata hai...", "Ye sunke aap chauk jaoge...").
    4. Aakhri scene mein chhota CTA ho ("Aise hi Hindi facts ke liye follow karo").
    5. Har scene ke liye ek "visual_keyword" do - ye ENGLISH mein 2-4 simple words ka stock-footage search
       term hoga jo us scene ke fact se DIRECTLY match kare (jaise agar scene insaan ke dimaag ke baare
       mein hai to "human brain closeup", agar scene samandar ke baare mein hai to "deep ocean waves").
       Generic/broad keywords use karo taake Pexels par asaani se milein - koi specific brand/person naam
       mat do.

    RULES FOR YOUTUBE METADATA (trending/discoverability ke liye):
    1. "title": Clickbait-style lekin honest hook, emoji ke saath, 60-70 characters, curiosity gap create kare.
       Hashtag titles mein mat daalo.
    2. "description": 2-3 lines mein fact ka summary + curiosity hook, phir niche 10-15 relevant hashtags
       (mix of broad trending tags jaise #shorts #facts #viral #trending aur specific tags related to topic,
       jaise #hindifacts #amazingfacts #didyouknow #factsinhindi #mindblowingfacts).
    3. "tags": Ek JSON array of 15-20 individual SEO keywords (bina # ke) jo is video ko search/suggested
       mein rank karwayein - mix karo broad high-search-volume keywords (jaise "facts", "hindi facts",
       "amazing facts", "shorts", "viral shorts", "did you know") aur specific topic-related keywords.

    Output STRICTLY in this JSON format, bina markdown codeblocks ke:
    {{
        "title": "Title with emoji here",
        "description": "Description with hashtags here",
        "tags": ["tag1", "tag2", "..."],
        "scenes": [
            {{"narration": "Hindi text for scene 1...", "visual_keyword": "english search term"}},
            {{"narration": "Hindi text for scene 2...", "visual_keyword": "english search term"}}
        ]
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

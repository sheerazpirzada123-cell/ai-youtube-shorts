from google import genai
import json
import random

FACT_TOPICS = [
    "Wahiyat aur Ajeeb Facts",
    "Insaan ke Jism ke Mind-Blowing Sach",
    "Janwaro ki Shocking Duniya",
    "Antariksh ke Khaufnak Facts",
    "Psychology ke Magical Facts",
    "History ke Chaunka Dene Wale Raaz",
    "Crime aur Mystery Facts",
    "Food aur Khane-Peene ke Ajeeb Sach",
    "Technology ke Hairat-Angez Facts",
    "Duniya ke Ajeeb Kanoon aur Riwaj",
    "Paisa aur Ameer Logo ke Facts",
    "Sapno aur Neend ke Raaz",
    "Prachin Sabhyata aur Khazano ke Raaz",
    "Samandar aur Uski Gehraiyon ke Raaz",
    "Dimaag ko Hila Dene Wale Science Facts",
    "Bollywood aur Entertainment ke Anjaane Facts",
    "Sports ki Duniya ke Shocking Facts",
    "Haiwano aur Insaano ke Ajeeb Rishtey"
]

def generate_fact_script(api_key):
    client = genai.Client(api_key=api_key)
    selected_topic = random.choice(FACT_TOPICS)
    
    # Har run mein Gemini ko ek chhota random "angle" bhi diya jata hai taake wahi ghisay-pitay
    # facts baar baar repeat na ho aur topic ke andar bhi variety aaye.
    angle_pool = [
        "koi kam-jaana (less popular/underrated) fact chuno, sabse obvious/common wala fact mat lena",
        "kisi recent (last few years) discovery ya event se related fact chuno",
        "kisi historical/purani ghatna se juda hua surprising fact chuno",
        "ek aisa fact chuno jo counter-intuitive ho (jo sunke log 'sach mein?' bolein)",
        "kisi number/statistic based shocking fact chuno",
        "kisi desi/India-related angle wala fact chuno agar topic allow kare"
    ]
    selected_angle = random.choice(angle_pool)

    prompt = f"""
    Tum ek viral YouTube Shorts content strategist, scriptwriter, aur video editor ho (jaise "Facts Mine",
    "Bright Side" jaise channels). Topic: "{selected_topic}" par ek engaging 30-40 second Hindi facts
    Short banao, jo SCENE-BY-SCENE structure mein ho (taake har scene ke liye alag matching stock footage
    lagayi ja sake, jaisa professional facts channels karte hain).

    VARIETY REQUIREMENT (bahut zaroori): Is baar {selected_angle}. Har baar generate hone par facts
    HAMESHA naye aur different hone chahiye - kabhi bhi wahi ghisa-pita/sabse common fact repeat mat karo
    jo is topic par sabse pehle dimaag mein aata hai. Kuch unexpected/unique chuno jo genuinely interesting ho.

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

    RULES FOR TTS-FRIENDLY NARRATION (bahut zaroori, is se pronunciation mistakes hoti hain):
    1. "narration" field mein KABHI bhi digits/numerals (0-9) use mat karo - har number ko Hindi
       Devanagari words mein likho (jaise "100" ki jagah "sau", "2024" ki jagah "do hazaar chaubees",
       "50%" ki jagah "pachaas pratishat").
    2. "narration" field mein English words/acronyms bilkul mat mix karo (koi bhi English mein likha
       hua word Hindi TTS engine ghalat pronounce karta hai) - sirf un English words ki ijazat hai jo
       Hindi mein itne common ho chuke hain ke Devanagari mein likhe ja sakein (jaise "internet",
       "mobile", "video") - wo bhi Devanagari script mein hi likho, Roman/English letters mein nahi.
       Koi bhi brand naam, technical term ya abbreviation (jaise "DNA", "NASA", "AI") ho to uska
       Hindi-pronunciation wala Devanagari spelling likho (jaise "NASA" → "नासा", "DNA" → "डीएनए").
    3. Symbols (%, +, &, /, etc.) bilkul use mat karo narration mein - har symbol ko poora Hindi
       word mein likho.
    4. "visual_keyword" field is rule se exempt hai - wo hamesha plain English mein hi rahega
       (kyunki wo sirf stock-footage search ke liye hai, bola nahi jayega).

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

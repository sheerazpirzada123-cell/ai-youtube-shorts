import os
import json
import time
import re
import random
import shutil
import requests
import asyncio
import edge_tts
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from google.genai.errors import APIError

from modules.composer import ShortsComposer
from modules.youtube_uploader import (
    upload_video,
    set_thumbnail,
    add_to_playlist,
)
from modules.tiktok_uploader import upload_to_tiktok
from modules.asset_manager import (
    fetch_scene_video,
    prepare_background_audio,
    prepare_all_assets,
)
from modules.audio import _trim_silence

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_PLAYLIST_ID = os.getenv("YOUTUBE_PLAYLIST_ID", "")

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

USED_TOPICS_FILE = "used_topics.json"
TOPIC_COOLDOWN_DAYS = 21

client = genai.Client(api_key=GEMINI_API_KEY)

ASSETS_DIR = "assets"
TEMP_VIDEO_DIR = os.path.join(ASSETS_DIR, "video_clips")
TEMP_AUDIO_DIR = os.path.join(ASSETS_DIR, "audio_clips")
SCENE_CLIP_DIR = os.path.join(ASSETS_DIR, "scene_clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "final")

for directory in [TEMP_VIDEO_DIR, TEMP_AUDIO_DIR, SCENE_CLIP_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

KEYWORD_MAP = {
    "hot cheetos": "spicy chips snacks",
    "chips": "potato chips snack",
    "water": "water glass drinking",
    "paani": "water glass drinking",
    "chai": "tea cup hot",
    "coffee": "coffee cup hot",
    "namak": "salt shaker kitchen",
    "sugar": "sugar cubes sweet",
    "chocolate": "chocolate bar sweet",
    "banana": "banana fruit",
    "apple": "red apple fruit",
    "energy drink": "energy drink can",
    "soda": "soda can fizzy",
    "ice cream": "ice cream cone",
    "brain": "human brain animation",
    "dimaag": "human brain animation",
    "heart": "human heart beating",
    "dil": "human heart beating",
    "eye": "human eye closeup",
    "aankh": "human eye closeup",
    "lion": "lion wildlife",
    "sher": "lion wildlife",
    "wolf": "wolf wildlife",
    "shark": "shark underwater",
    "snake": "snake wildlife",
    "elephant": "elephant wildlife",
    "spider": "spider web insect",
    "ant": "ants colony insect",
    "bee": "bees hive insect",
    "dinosaur": "dinosaur skeleton museum",
    "bomb": "explosion fire",
    "volcano": "volcano eruption lava",
    "earthquake": "earthquake crack ground",
    "tsunami": "tsunami wave ocean",
    "lightning": "lightning storm sky",
    "tornado": "tornado storm clouds",
    "diamond": "diamond jewel shiny",
    "gold": "gold coins treasure",
    "money": "money cash dollars",
    "paisa": "money cash dollars",
}

TOPIC_POOL = [
    "kitne chips khaane se aap mar sakte ho",
    "kitna paani peene se aap bebaak ho sakte ho",
    "kitni chai peene se aapka dil ruk sakta hai",
    "kitna namak khaane se aapki maut ho sakti hai",
    "kitni coffee peene se aapko heart attack aa sakta hai",
    "kitni sugar khaane se aap coma mein ja sakte ho",
    "kitni chocolate khaane se aap mar sakte ho",
    "kitne energy drinks peene se aapki death ho sakti hai",
    "kitni ice cream khaane se aapko brain freeze ho sakta hai",
    "kitne banana khaane se aapko radiation ho sakta hai",
    "agar aap sheron ke beech bade hote to kya hota",
    "agar aap wolves ke saath bade hote to kya hota",
    "agar aap ek shark ke saath tairte to kya hota",
    "agar aapke ghar mein 100 saanp hote to kya hota",
    "agar aap ek hathi ke saamne khade hote to kya hota",
    "agar aapke jism mein 1000 makdiyaan hoti to kya hota",
    "agar aap ek cheenti ke size ke hote to kya hota",
    "agar aap jungle mein akela raat bitate to kya hota",
    "agar aaj ka insaan dinosaur ke saamne khada ho jaye",
    "agar aaj ka bomb ancient egypt pe gire",
    "agar aaj ka mobile 100 saal pehle le jaaye",
    "agar aaj ki bijli ancient rome mein aaye",
    "agar aaj ka internet 1950 mein aaye",
    "agar aap 100 din tak so na paayein to kya hoga",
    "agar aap 100 din tak kuch na khaayein to kya hoga",
    "agar aap 100 din tak paani na piyein to kya hoga",
    "agar aapka dil 1 minute ke liye ruk jaye to kya hoga",
    "agar aapka dimaag 10 second ke liye band ho jaye to kya hoga",
    "agar aap volcano ke andar gir jayein to kya hoga",
    "agar aap tsunami ke saamne khade ho jayein to kya hoga",
    "agar aap bijli ke girne wali jagah pe khade ho jayein to kya hoga",
    "agar aap tornado ke andar chale jayein to kya hoga",
    "agar aap earthquake ke center mein ho to kya hoga",
    "agar aap duniya ke sabse ameer insaan ban jayein to kya hoga",
    "agar aapke paas 100 crore rupaye aa jayein to kya hoga",
    "agar aap saari duniya ki gold le lein to kya hoga",
    "agar aap 1 din mein 1 arab rupaye kharch karein to kya hoga",
]

ANGLE_POOL = [
    "ek aise sawal se shuru karo jiska jawab koi nahi jaanta",
    "ek aisi baat batao jo sunke viewer ka dimaag ghoom jaye",
    "pehle ek ajeeb si baat batao phir uska asli reason",
    "ek aisa fact batao jo sunke viewer soche 'ye jhoot hai' phir prove karo",
    "ek aisi warning se shuru karo jo viewer ko dara de",
]

HOOK_POOL = [
    "ek aisi baat se shuru karo jo sunte hi viewer ka scroll ruk jaye",
    "ek aisa sawal poocho jiska jawab jaanne ke liye viewer ko rukna pade",
    "ek aisi warning se shuru karo jo viewer ko dara de",
    "ek aisa fact batao jo sunke viewer soche 'ye kaise possible hai'",
    "ek aisi baat batao jo poori duniya ko nahi pata lekin honi chahiye",
    "ek aisa raaz kholo jo 100 saal se chhupa tha",
]

TITLE_POOL = [
    "Ye Kaise Possible Hai? 😱",
    "Duniya Ka Sabse Bada Raaz!",
    "Scientists Bhi Confuse! 🤯",
    "Ye Sach Hai Ya Jhoot?",
    "Aapko Yakeen Nahi Hoga!",
    "Ye Cheez Real Hai!",
    "Ye Mat Karna Kabhi!",
]

BASE_TAGS = [
    "shorts", "youtubeshorts", "facts", "hindi facts", "urdu facts",
    "amazing facts", "mysteries", "viral shorts", "science facts",
    "crazy facts", "mind blowing", "unbelievable", "dangerous facts",
    "what if", "how many",
]

MIN_SCENES = 7


def notify_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message[:4000]},
            timeout=15,
        )
    except Exception as e:
        print(f"Telegram notify failed: {e}")


def load_used_topics() -> dict:
    if not os.path.exists(USED_TOPICS_FILE):
        return {}
    try:
        with open(USED_TOPICS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_used_topics(data: dict):
    try:
        with open(USED_TOPICS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"used_topics save failed: {e}")


def pick_fresh_topic() -> str:
    used = load_used_topics()
    cutoff = (datetime.utcnow() - timedelta(days=TOPIC_COOLDOWN_DAYS)).isoformat()

    fresh = [
        t for t in TOPIC_POOL
        if used.get(t, {}).get("last_used", "0") < cutoff
    ]

    if not fresh:
        fresh = sorted(
            TOPIC_POOL,
            key=lambda t: used.get(t, {}).get("last_used", "0"),
        )[:5]

    return random.choice(fresh)


def mark_topic_used(topic: str):
    used = load_used_topics()
    used[topic] = {
        "last_used": datetime.utcnow().isoformat(),
        "count": used.get(topic, {}).get("count", 0) + 1,
    }
    save_used_topics(used)


def get_optimized_search_query(text):
    text_lower = text.lower()
    for key, search_term in KEYWORD_MAP.items():
        if key in text_lower:
            return search_term
    return text


def normalize_script(data):
    if isinstance(data, list):
        data = {"scenes": data}
    if not isinstance(data, dict):
        raise ValueError("Script JSON dict/list nahi hai")

    scenes = []
    for scene in data.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        narration = str(scene.get("narration", "")).strip()
        if not narration:
            continue
        keyword = str(
            scene.get("search_keyword")
            or scene.get("visual_keyword")
            or ""
        ).strip()
        scenes.append({"narration": narration, "search_keyword": keyword})

    if len(scenes) < MIN_SCENES:
        raise ValueError(
            f"Sirf {len(scenes)} scenes mile, kam az kam {MIN_SCENES} chahiye"
        )

    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    return {
        "title": str(data.get("title", "")).strip(),
        "description": str(data.get("description", "")).strip(),
        "tags": [str(t) for t in tags],
        "scenes": scenes,
    }


def generate_script(max_retries=3, base_wait=20):
    topic = pick_fresh_topic()
    mark_topic_used(topic)
    angle = random.choice(ANGLE_POOL)
    hook_style = random.choice(HOOK_POOL)
    run_seed = f"{int(time.time())}-{random.randint(100000, 999999)}"
    print(f"Run topic: {topic}")
    print(f"   angle: {angle}")
    print(f"   hook: {hook_style}")
    print(f"   seed: {run_seed}")

    prompt = f"""
    Write a smooth, fast-paced, VIRAL YouTube Short script in simple spoken Urdu/Hindi (written in Roman letters) mixed with common English words.

    TOPIC FOR THIS SCRIPT:
    {topic}

    STYLE ANGLE: {angle}

    HOOK STYLE: {hook_style}

    ============================================================
    NICHE: "WHAT IF / HOW MANY" - PERSONAL DANGER FORMAT
    ============================================================
    Ye format viewers ko PERSONALLY touch karta hai. Viewer ko lagna chahiye:
    "Ye mere baare mein hai. Mere saath kya hoga?"

    Isliye:
    - "Aap" word use karo har scene mein
    - Direct viewer ko address karo
    - Personal danger ya personal scenario dikhao
    - Numbers aur limits batao (kitna, kitne, kitni)

    ============================================================
    HOOK RULES - 3 SECOND MEIN SCROLL ROKNA HAI
    ============================================================
    Scene 1 (hook) sirf 4-6 words ka hai. MAXIMUM 6 words.
    Har word MUST punch kare. Koi filler word nahi.

    Hook mein 3 cheezein HONI CHAHIYE:
    1. PERSONAL - "aap" ya "aapko" se shuru
    2. DANGER ya SHOCK - kuch aisa jo daraa de ya chauka de
    3. CURIOSITY GAP - aadha sach batao, poora nahi

    BEST HOOK PATTERNS:

    PATTERN 1 - "KITNA/KITNE" DANGER (SABSE STRONG):
    - "Ye 10 chips aapko maar sakti hai"
    - "Ye 5 glass paani zeher hai"
    - "Ye 3 chai aapka dil tod degi"
    - "Ye 1 cheez aapko 24 ghante mein maar degi"

    PATTERN 2 - SCARY NUMBER:
    - "Sirf 2 chammach ye cheez maut"
    - "3 saans aur aap khatam"
    - "24 ghante mein aap khatam"
    - "10 second mein sab khatam"

    PATTERN 3 - DIRECT WARNING:
    - "Ye cheez aapko maar degi"
    - "Ye galti kabhi mat karna"
    - "Ye aapke saath ho sakta hai"
    - "Aapko ye kabhi nahi pata tha"

    PATTERN 4 - IMPOSSIBLE CLAIM:
    - "Ye cheez aapke dimaag ko todti hai"
    - "Aap ye kabhi nahi soch sakte"
    - "Ye science ke against hai"

    YE HOOKS BILKUL MAT LIKHNA (DEAD):
    - "Kya aapko pata hai..." - BORING
    - "Aaj hum baat karenge..." - BORING
    - "Duniya mein ek jagah hai..." - VAGUE
    - "Scientists ne discover kiya..." - SLOW
    - "Imagine karo..." - WEAK
    - Koi bhi hook jo 6 words se lamba ho

    ============================================================
    SCRIPT STRUCTURE (8 SCENES)
    ============================================================
    Scene 1 (HOOK): 4-6 words. Personal danger ya shocking number.
    Scene 2 (LIMIT): "Ye kitna hai" - specific number ya limit batao.
    Scene 3 (REACTION): "Aapka jism kya karega" - body reaction.
    Scene 4 (SCIENCE): "Kyun aisa hota hai" - simple science.
    Scene 5 (BUILD-UP): "Aur agar aap isse zyada karein..." - escalation.
    Scene 6 (DANGER PEAK): "To kya hoga" - worst case scenario.
    Scene 7 (TWIST): Ek unexpected fact ya reveal.
    Scene 8 (CTA): 4-6 words. Loop ya question CTA.

    Har scene mein "aap" word use karo. Direct viewer ko address karo.

    ============================================================
    CTA RULES - SMART CTA (DIRECT NAHI)
    ============================================================
    CTA matlab call-to-action. LEKIN direct "like karo, subscribe karo"
    BILKUL MAT LIKHNA.

    CTA ka last scene mein 4-6 words ka hona chahiye.

    TARIKA 1 - LOOP CTA:
    - "Ye baat aapne miss kar di dobara dekho"
    - "Kya aapne ye notice kiya wapas dekho"

    TARIKA 2 - QUESTION CTA:
    - "Aapko kya lagta hai sach hai"
    - "Comment mein batao aap karenge"

    TARIKA 3 - CURIOSITY CTA:
    - "Agli baat aur bhi shocking hai"
    - "Iske baare mein aur jaanna hai to ruko"

    ============================================================
    VISUAL AVAILABILITY RULE
    ============================================================
    Pexels/Pixabay par sirf BROAD, COMMON subjects ki footage hoti hai:
    food (chips, water, tea, coffee, sugar, chocolate, banana, ice cream),
    body (brain, heart, eye, hands, stomach), animals (lion, shark, snake,
    elephant, spider, bee, wolf), nature (volcano, tsunami, lightning,
    tornado, earthquake), objects (money, gold, diamond, bomb, explosion),
    places (forest, ocean, desert, city).

    search_keyword mein kabhi specific species name, brand name,
    ya specific person ka naam mat likhna.

    ============================================================
    LANGUAGE & PRONUNCIATION RULES
    ============================================================
    1. Simple spoken Urdu/Hindi with common English words (Roman script).
    2. NO formal Hindi/Urdu words (prakriti, chattaan, rahasya, adbhut).
    3. Narration ke andar NO full stops, question marks, ya commas.
    4. Har word natural Roman Urdu/Hindi spelling mein likho.
    5. Numbers ko words mein likho: "100" nahi, "sau" likho. "24" nahi, "chaubees".
    6. Aise words avoid karo jinhe TTS galat bole.
    7. Sentences chhote rakho - 5-10 words max.
    8. URDU PRONUNCIATION: "hai" ki jagah "hai" hi rakho, "hain" use karo.
    9. Words aise likho jo Pakistani Urdu mein natural lagein.

    ============================================================
    SCENE & DURATION RULES
    ============================================================
    1. EXACTLY 8 scenes. Har scene = ek chhota sentence (5-10 words).
       Scene 1 = hook (MAX 6 words). Scene 8 = SMART CTA (4-6 words).
    2. Total: 25-35 seconds (60-80 words total).
    3. Har scene ka search_keyword ALAG ho (2-4 words, English).
    4. Hook scene ka search_keyword visually dramatic ho.
    5. Scene 2-7 mein story ko aise build karo ke viewer end tak ruke.
    6. Scene 7 mein ek chhota twist ya reveal ho.

    ============================================================
    YOUTUBE METADATA RULES
    ============================================================
    1. "title": MAX 55 characters, curiosity-based, ek emoji, NO hashtags.
    2. "description": 2-3 short lines with search keywords. No hashtags.
    3. "tags": 15-20 lowercase keywords without #.

    Return ONLY valid JSON (no markdown) in exactly this structure.

    Example JSON Output Format (FORMAT ONLY):
    {{
      "title": "Yahan title likho",
      "description": "Line one\\nLine two",
      "tags": ["tag one", "tag two"],
      "scenes": [
        {{
          "narration": "Ye 10 chips aapko maar sakti hai",
          "search_keyword": "spicy chips snacks"
        }},
        {{
          "narration": "Aapka dimaag 10 minute mein khatam ho jayega",
          "search_keyword": "human brain animation"
        }},
        {{
          "narration": "Ye baat aapne miss kar di dobara dekho",
          "search_keyword": "storm clouds dramatic"
        }}
      ]
    }}
    """

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
    ]

    for attempt in range(1, max_retries + 1):
        for model_name in models_to_try:
            try:
                print(f"[Attempt {attempt}/{max_retries}] Trying {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        top_p=0.9,
                        top_k=40,
                        response_mime_type="application/json",
                    ),
                )
                clean_json = re.sub(
                    r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", response.text
                ).strip()
                return normalize_script(json.loads(clean_json))
            except APIError as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "overloaded" in err_str.lower():
                    print(f"   {model_name} unavailable (503), trying next model...")
                    continue
                elif "429" in err_str or "quota" in err_str.lower():
                    print(f"   {model_name} quota exceeded (429), trying next model...")
                    continue
                else:
                    print(f"   {model_name} error: {e}")
                    continue
            except json.JSONDecodeError:
                print(f"   {model_name} returned invalid JSON, trying next...")
                continue
            except Exception as e:
                print(f"   {model_name} unexpected error: {e}")
                continue

        wait_time = base_wait * attempt
        print(f"All models failed. Retrying in {wait_time}s...")
        if attempt < max_retries:
            time.sleep(wait_time)
        else:
            notify_telegram(f"Script generation failed after {max_retries} attempts")
            return None

    return None


def clean_text_for_tts(text):
    text = re.sub(r"\bise\b", "isey", text, flags=re.IGNORECASE)
    text = re.sub(r"\bI\.S\.E\b", "isey", text, flags=re.IGNORECASE)
    text = re.sub(r"\bjise\b", "jisey", text, flags=re.IGNORECASE)
    text = re.sub(r"\buse\b", "usey", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwo\b", "woh", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvo\b", "woh", text, flags=re.IGNORECASE)

    text = re.sub(r"\b100\b", "sau", text)
    text = re.sub(r"\b1000\b", "hazaar", text)
    text = re.sub(r"\b50\b", "pachaas", text)
    text = re.sub(r"\b24\b", "chaubees", text)

    text = text.replace(".", " , ")
    text = text.replace("?", " , ")
    text = text.replace("!", " , ")
    text = text.replace(",", " , ")

    text = re.sub(r"\s+", " ", text).strip()
    return text


async def generate_voiceover(text, output_file):
    # Pakistani Urdu Male Voice - Energetic & Natural
    voice = "ur-PK-AsadNeural"
    cleaned_text = clean_text_for_tts(text)

    communicate = edge_tts.Communicate(
        cleaned_text,
        voice,
        rate="+15%",
        pitch="+3Hz",
        volume="+10%",
    )
    await communicate.save(output_file)


def build_scene_voiceovers(scenes):
    paths = []
    for index, scene in enumerate(scenes, start=1):
        path = os.path.join(TEMP_AUDIO_DIR, f"scene_{index:02d}.mp3")
        if os.path.exists(path):
            os.remove(path)

        for attempt in range(1, 4):
            try:
                asyncio.run(generate_voiceover(scene["narration"], path))
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    break
            except Exception as e:
                print(f"[Voice scene {index}] attempt {attempt} failed: {e}")
                time.sleep(2)
        else:
            raise RuntimeError(
                f"Scene {index} ki voiceover generate nahi ho saki."
            )

        _trim_silence(path)
        paths.append(path)
    return paths


def build_scene_clips(scenes):
    shutil.rmtree(SCENE_CLIP_DIR, ignore_errors=True)
    os.makedirs(SCENE_CLIP_DIR, exist_ok=True)

    paths = []
    for index, scene in enumerate(scenes, start=1):
        target = os.path.join(SCENE_CLIP_DIR, f"scene_{index:02d}.mp4")
        keyword = scene.get("search_keyword") or "nature landscape"
        query = get_optimized_search_query(keyword)
        print(f"Scene {index}: '{query}'")

        try:
            fetch_scene_video(query, target, min_duration=3)
            paths.append(target)
        except Exception as e:
            print(f"Scene {index} ka clip nahi mila: {e}")
            if not paths:
                raise
            paths.append(paths[-1])
    return paths


def build_metadata(script, full_narration):
    title_core = re.sub(r"#\S+", "", script.get("title", "")).strip()
    if not title_core:
        title_core = random.choice(TITLE_POOL)

    title = f"{title_core[:75].strip()} #Shorts"[:95]

    tags, seen, total_chars = [], set(), 0
    for tag in script.get("tags", []) + BASE_TAGS:
        tag = re.sub(r"[#,<>]", "", tag).strip().lower()
        if not tag or tag in seen:
            continue
        if total_chars + len(tag) + 1 > 450:
            break
        seen.add(tag)
        tags.append(tag)
        total_chars += len(tag) + 1

    hashtags, seen_h = [], set()
    candidates = ["#Shorts", "#Facts", "#HindiFacts", "#UrduFacts", "#AmazingFacts", "#CrazyFacts", "#WhatIf", "#DangerousFacts"]
    candidates += [
        "#" + re.sub(r"[^0-9a-zA-Z]", "", t)
        for t in script.get("tags", [])
    ]
    for candidate in candidates:
        key = candidate.lower()
        if len(candidate) < 3 or key in seen_h:
            continue
        seen_h.add(key)
        hashtags.append(candidate)
        if len(hashtags) >= 10:
            break

    body = script.get("description") or full_narration
    description = f"{body}\n\n{' '.join(hashtags)}"[:4900]

    return title, description, tags


def generate_thumbnail(video_path: str, output_path: str, title_text: str):
    import subprocess

    if not os.path.exists(video_path):
        return None

    frame_path = output_path + ".frame.jpg"
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", "1", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", frame_path,
        ],
        capture_output=True,
    )

    if not os.path.exists(frame_path):
        print("Thumbnail frame extract nahi ho paya.")
        return None

    safe_title = re.sub(r'[":\'\\\n\r]', "", title_text)[:40].strip()
    if not safe_title:
        safe_title = "Amazing Fact"

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    font_file = next((f for f in font_candidates if os.path.exists(f)), None)

    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
    ]

    if font_file:
        vf_parts.append(
            f"drawtext=text='{safe_title}':"
            f"fontcolor=white:fontsize=72:"
            f"box=1:boxcolor=black@0.7:boxborderw=20:"
            f"x=(w-text_w)/2:y=h*0.75:"
            f"fontfile={font_file}"
        )

    cmd = [
        "ffmpeg", "-y", "-i", frame_path,
        "-vf", ",".join(vf_parts),
        "-frames:v", "1", "-q:v", "2",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(frame_path):
        os.remove(frame_path)

    if result.returncode == 0 and os.path.exists(output_path):
        return output_path

    print(f"Thumbnail generate nahi hua: {result.stderr[-300:]}")
    return None


def main():
    print("Starting Automated Short Pipeline...")
    start_time = time.time()

    print("\nPreparing SFX library...")
    try:
        prepare_background_audio()
    except Exception as e:
        print(f"SFX preparation failed (skip): {e}")

    print("\nGenerating 30-40s Short script...")
    script = generate_script()
    if not script:
        print("Script generation failed.")
        notify_telegram("Pipeline failed: script generation returned None")
        return

    scenes = script["scenes"]
    full_narration = " ".join(s["narration"] for s in scenes)
    print(f"{len(scenes)} scenes | Hook: {scenes[0]['narration']}")

    print("\nGenerating scene-wise Voiceover (Pakistani Urdu Male - Asad)...")
    try:
        voice_paths = build_scene_voiceovers(scenes)
    except Exception as e:
        print(f"Voiceover failed: {e}")
        notify_telegram(f"Voiceover generation failed: {e}")
        return

    print("\nDownloading a different Stock Video for every scene...")
    try:
        clip_paths = build_scene_clips(scenes)
    except Exception as e:
        print(f"Video download failed: {e}")
        notify_telegram(f"Video download failed: {e}")
        return

    print("\nMerging Video & Audio...")
    composer = ShortsComposer(output_dir=OUTPUT_DIR)

    bg_music_path = None
    for candidate in [
        os.path.join("assets", "bgm"),
        os.path.join("modules", "bg_music.mp3"),
    ]:
        if os.path.isdir(candidate):
            files = [
                f for f in os.listdir(candidate)
                if f.lower().endswith(".mp3")
            ]
            if files:
                bg_music_path = os.path.join(candidate, random.choice(files))
                print(f"BG music: {bg_music_path}")
                break
        elif os.path.isfile(candidate):
            bg_music_path = candidate
            print(f"BG music: {bg_music_path}")
            break

    try:
        final_video_path = composer.create_multi_scene_short(
            clip_paths=clip_paths,
            voiceover_paths=voice_paths,
            output_filename="final_short.mp4",
            bg_music_path=bg_music_path,
            scene_narrations=[s["narration"] for s in scenes],
        )
    except Exception as e:
        print(f"Composition failed: {e}")
        notify_telegram(f"Video composition failed: {e}")
        return

    if not os.path.exists(final_video_path):
        print("Final video file create nahi hui.")
        notify_telegram("Final video file not created")
        return

    print("\nGenerating thumbnail...")
    thumb_path = os.path.join(OUTPUT_DIR, "thumbnail.jpg")
    generate_thumbnail(
        final_video_path,
        thumb_path,
        script.get("title", "Amazing Fact"),
    )

    print("\nUploading Video to YouTube...")
    title, description, tags = build_metadata(script, full_narration)
    print(f"Title: {title}")
    print(f"Tags: {len(tags)} tags")

    video_id = None
    try:
        video_id = upload_video(
            video_path=final_video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status="public",
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            refresh_token=YOUTUBE_REFRESH_TOKEN,
        )
        print(f"Video uploaded! ID: {video_id}")
        print(f"https://youtube.com/shorts/{video_id}")

        if os.path.exists(thumb_path):
            print("\nSetting thumbnail...")
            set_thumbnail(
                video_id,
                thumb_path,
                YOUTUBE_CLIENT_ID,
                YOUTUBE_CLIENT_SECRET,
                YOUTUBE_REFRESH_TOKEN,
            )

        if YOUTUBE_PLAYLIST_ID:
            print("\nAdding to playlist...")
            add_to_playlist(
                video_id,
                YOUTUBE_PLAYLIST_ID,
                YOUTUBE_CLIENT_ID,
                YOUTUBE_CLIENT_SECRET,
                YOUTUBE_REFRESH_TOKEN,
            )

        elapsed = time.time() - start_time
        notify_telegram(
            f"Video uploaded!\n"
            f"{title}\n"
            f"https://youtube.com/shorts/{video_id}\n"
            f"{elapsed:.0f}s"
        )

    except Exception as e:
        print(f"YouTube Upload Failed: {e}")
        notify_telegram(f"YouTube upload failed: {e}")

    if TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET and TIKTOK_REFRESH_TOKEN:
        print("\nUploading Video to TikTok (draft)...")
        try:
            tiktok_publish_id = upload_to_tiktok(
                video_path=final_video_path,
                title=title,
                client_key=TIKTOK_CLIENT_KEY,
                client_secret=TIKTOK_CLIENT_SECRET,
                refresh_token=TIKTOK_REFRESH_TOKEN,
            )
            print(f"TikTok upload complete! Publish ID: {tiktok_publish_id}")

            notify_telegram(
                f"TikTok draft uploaded!\n"
                f"{title}\n"
                f"Publish ID: {tiktok_publish_id}\n"
                f"Open TikTok app to post manually"
            )
        except Exception as e:
            print(f"TikTok Upload Failed: {e}")
            notify_telegram(f"TikTok upload failed: {e}")
    else:
        print("\nTikTok credentials missing - skipping TikTok upload.")

    elapsed = time.time() - start_time
    print(f"\nPipeline complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

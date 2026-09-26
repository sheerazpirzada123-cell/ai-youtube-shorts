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
from modules.asset_manager import fetch_scene_video, prepare_background_audio
from modules.audio import _trim_silence

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# Keyword map — broad categories only
# ---------------------------------------------------------------
KEYWORD_MAP = {
    "blood falls": "antarctica red waterfall glacier",
    "dancing forest": "twisted pine trees forest",
    "eternal flame": "waterfall cave fire",
    "antarctica": "antarctica glacier ice landscape",
    "bermuda triangle": "ocean storm dark",
    "surtsey island": "volcano island sea ocean lava",
    "sphinx": "ancient egypt pyramid statue desert",
    "bermuda": "ocean storm dark water aerial",
    "mantis shrimp": "ocean underwater colorful",
    "pistol shrimp": "ocean underwater colorful",
    "axolotl": "underwater aquarium fish",
    "tardigrade": "microscope laboratory science",
    "anglerfish": "deep sea underwater dark",
    "corpse flower": "tropical jungle plant",
    "rafflesia": "tropical jungle flower",
    "box jellyfish": "underwater jellyfish ocean",
    "immortal jellyfish": "underwater jellyfish ocean",
    "blue whale": "ocean whale underwater",
    "giant squid": "deep sea underwater dark",
}

# ---------------------------------------------------------------
# TOPIC POOL — sirf broad, relatable, no-specific-person topics
# ---------------------------------------------------------------
TOPIC_POOL = [
    # Ocean / deep sea mysteries
    "samundar ki sabse gehri jagah mein kya chhupa hai",
    "samundar mein aisi awaaz jo sunke scientists bhi darr gaye",
    "samundar mein aisi cheez jo 100 saal se padi hai",
    "deep sea mein aisi roshni jo koi samajh nahi paya",
    "samundar mein aisi jagah jahan koi nahi ja sakta",

    # Space mysteries
    "space mein aisi cheez jo koi dekh nahi sakta",
    "space mein aisi awaaz jo sunke scientists hairan hain",
    "kisi planet par aisa toofan jo poori duniya ko nigal sakta hai",
    "space mein aisa black hole jiske baare mein koi nahi jaanta",
    "chaand par aisi cheez jo insaan ne chhod di",

    # Geography / places
    "aisi jagah jahan pani ulta girta hai aur koi nahi samajh paya",
    "aisi jagah jo duniya ke map se gayab ho gayi",
    "aisi jagah jahan log jaate hain lekin wapas nahi aate",
    "aisi jagah jahan dhoop kabhi nahi pahunchti",
    "duniya ka sabse bada waterfall ya glacier",

    # Natural phenomena
    "aisi natural disaster jo 100 saal mein ek baar aati hai",
    "aisa phenomenon jahan electricity aasman se girti hai",
    "duniya ki sabse ajeeb weather condition",
    "aisi cheez jo aasman se gir rahi hai aur koi nahi jaanta kyun",
    "duniya ka sabse khatarnak ocean current",

    # Science / physics
    "koi aisa fact jo physics ke saare rules todta hai",
    "duniya ka sabse purana ya sabse bada kuch",
    "aisa experiment jo bhool kar bhi nahi karna chahiye",
    "aisi cheez jo kabhi khatam nahi hoti",
    "koi aisa number jo poori duniya ko confuse karta hai",

    # History / mysteries (no specific person)
    "koi purani civilization ka aisa raaz jo aaj tak solve nahi hua",
    "koi aisa raaz jo 100 saal se chhupa hua tha",
    "duniya ka sabse bada jhoot jo sab ne maan liya",
    "aisa technology jo 100 saal aage ki lagti hai",
    "koi aisa raaz jo Google bhi nahi jaanta",

    # Nature records
    "duniya ki sabse purani cheez jo aaj bhi zinda hai",
    "duniya ka sabse bada jaanwar jo aaj bhi zinda hai",
    "aisi cheez jo samundar mein 100 saal se padi hai",
    "duniya ki sabse gehri jagah jahan insaan gaya hai",
    "aisa toofan jo poori duniya ko hila de",

    # Human body (broad, no specific person)
    "insani jism ka koi aisa fact jo zyadatar log nahi jante",
    "dimagh aur memory se juda koi mind blowing fact",
    "insani jism mein aisi cheez jo kabhi nahi rukti",
    "insaan ki aankh mein aisa raaz jo koi nahi jaanta",
]

ANGLE_POOL = [
    "ek aise sawal se shuru karo jiska jawab koi nahi jaanta",
    "ek aisi baat batao jo sunke viewer ka dimaag ghoom jaye",
    "pehle ek ajeeb si baat batao phir uska asli reason",
    "ek aisi kahani sunao jo sach lagti hai lekin impossible hai",
    "ek aisa fact batao jo sunke viewer soche 'ye jhoot hai' phir prove karo",
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
    "100 Saal Se Chhupa Raaz!",
    "Aapko Yakeen Nahi Hoga!",
    "Ye Cheez Real Hai!",
]

BASE_TAGS = [
    "shorts", "youtubeshorts", "facts", "hindi facts", "urdu facts",
    "amazing facts", "mysteries", "viral shorts", "science facts",
    "crazy facts", "mind blowing", "unbelievable",
]

MIN_SCENES = 7


# ---------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------
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
        print(f"⚠️ Telegram notify failed: {e}")


# ---------------------------------------------------------------
# Topic deduplication
# ---------------------------------------------------------------
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
        print(f"⚠️ used_topics save failed: {e}")


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


# ---------------------------------------------------------------
# Search query optimization
# ---------------------------------------------------------------
def get_optimized_search_query(text):
    text_lower = text.lower()
    for key, search_term in KEYWORD_MAP.items():
        if key in text_lower:
            return search_term
    return text


# ---------------------------------------------------------------
# Script normalization
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------
def generate_script(max_retries=3, base_wait=20):
    topic = pick_fresh_topic()
    mark_topic_used(topic)
    angle = random.choice(ANGLE_POOL)
    hook_style = random.choice(HOOK_POOL)
    run_seed = f"{int(time.time())}-{random.randint(100000, 999999)}"
    print(f"🎲 Run topic: {topic}")
    print(f"   angle: {angle}")
    print(f"   hook: {hook_style}")
    print(f"   seed: {run_seed}")

    prompt = f"""
    Write a smooth, fast-paced, VIRAL YouTube Short script in simple spoken Hindi/Urdu (written in Roman letters) mixed with common English words.

    TOPIC FOR THIS SCRIPT (must be about this, pick ONE specific real example of it):
    {topic}

    STYLE ANGLE FOR THIS SCRIPT: {angle}

    HOOK STYLE FOR SCENE 1: {hook_style}

    ============================================================
    SABSE ZAROORI RULE — NO SPECIFIC PERSON
    ============================================================
    Script mein KISI BHI SPECIFIC INSAAN ka zikr NAHI hona chahiye.
    Na koi real naam, na koi specific story, na koi personal event.

    YE BILKUL MAT LIKHNA:
    - Kisi insaan ka naam
    - Kisi specific insaan ki kahani
    - Kisi specific person ka record
    - Kisi celebrity, athlete, ya famous log ke baare mein

    YE LIKHNA HAI:
    - Natural phenomena (samundar ki awaaz, space ki cheez, weather)
    - Places (jagah, sheher, pahaad, samundar, jungle)
    - Science facts (physics, chemistry, biology)
    - Nature records (sabse bada, sabse purana, sabse gehri)
    - Broad categories (insani jism, dimagh, aankh — bina kisi specific person ke)

    ============================================================
    HOOK RULES — VIEWER 3 SECOND MEIN DECIDE KARTA HAI
    ============================================================
    Scene 1 (hook) sirf 6-8 words ka hai. MAXIMUM 8 words.

    Hook aisa hona chahiye jo turant SHOCK ya CURIOSITY paida kare.

    YE HOOKS BILKUL MAT LIKHNA:
    - "Kya aapko pata hai..." — bahut slow, bahut common
    - "Aaj hum baat karenge..." — boring
    - "Duniya mein ek jagah hai..." — bahut vague
    - 8 words se lamba koi bhi hook

    YE HOOK PATTERNS USE KARO (ek chuno):
    1. UNBELIEVABLE CLAIM: "Ye jagah duniya se gayab ho gayi"
    2. SHOCKING WARNING: "Yahan jaana aapki maut ho sakti hai"
    3. IMPOSSIBLE QUESTION: "Kaise possible hai ke pani ulta girta hai"
    4. DEADLY SECRET: "Ye cheez aapko 24 ghante mein maar sakti hai"
    5. SCARY FACT: "Is jagah se koi wapas nahi aaya"

    Hook aisa hona chahiye ke viewer soche: "WAIT WHAT? MUJHE AUR JAANNA HAI!"
    Scene 2 turant hook ka jawab dena shuru kare.

    ============================================================
    CTA RULES — SABSE ZAROORI (SMART CTA, DIRECT NAHI)
    ============================================================
    CTA matlab call-to-action. LEKIN direct "like karo, subscribe karo, share karo"
    BILKUL MAT LIKHNA. Ye boring hai, log ignore kar dete hain.

    LAST SCENE mein SMART CTA likhna hai. Ye 3 tarike use karo:

    TARIKA 1 — CURIOSITY-BASED:
    Aisa sawal ya promise jisse viewer next video dekhne ke liye
    like ya subscribe kare. Example:
    - "Agli baat aur bhi shocking hai"
    - "Ye toh kuch bhi nahi, aage kya hai wo dekho"
    - "Iske baare mein aur jaanne ke liye ruko"
    - "Aage wali baat sunke aap hairan reh jaoge"

    TARIKA 2 — QUESTION-BASED:
    Aisa sawal jo viewer ko soche aur comment ya like kare. Example:
    - "Aapko kya lagta hai ye sach hai"
    - "Ye possible hai ya nahi apna jawab do"
    - "Kaun jeeta is race mein aap batao"

    TARIKA 3 — SUBTLE HINT:
    Halka sa hint jo like ya subscribe ko natural bana de. Example:
    - "Aise facts roz dekhne hain to ruk jao"
    - "Ye sirf shuruaat hai"

    YE CTA BILKUL MAT LIKHNA:
    - "Like karo, share karo, subscribe karo"
    - "Channel ko subscribe karo"
    - "Video ko like kare"
    - "Bell icon dabao"
    - Koi bhi direct order jo boring lage

    Last scene 6-10 words ka hona chahiye.

    ============================================================
    VISUAL AVAILABILITY RULE
    ============================================================
    Pexels/Pixabay par sirf BROAD, COMMON subjects ki footage hoti hai:
    space, ocean, forest, mountains, desert, city, common animals (dog/cat/lion/shark/bird),
    human body (eyes/brain/heart/hands), laboratory, technology, money, ruins, fire, ice, volcano,
    books, kitchen, clock, astronaut.

    search_keyword mein kabhi specific species name, flower name, fish name,
    ya specific person ka naam mat likhna.

    ============================================================
    LANGUAGE & PRONUNCIATION RULES
    ============================================================
    1. Simple spoken Hindi/Urdu with common English words.
    2. NO formal Hindi words (prakriti, chattaan, rahasya, adbhut).
    3. Narration ke andar NO full stops (.), question marks (?), ya commas (,).
    4. Har word ko aise likho jaise koi insaan bolta hai — natural Roman Hindi spelling.
    5. Numbers ko words mein likho: "100" nahi, "sau" likho. "24" nahi, "chaubees".
    6. Aise words avoid karo jinhe TTS galat bole.

    ============================================================
    SCENE & DURATION RULES
    ============================================================
    1. EXACTLY 8 scenes. Har scene = ek chhota sentence (7-12 words).
       Scene 1 = hook (MAX 8 words). Scene 8 = SMART CTA.
    2. Total: 30-38 seconds (75-90 words total).
    3. Har scene ka search_keyword ALAG ho (2-4 words, English).
    4. Hook scene ka search_keyword visually dramatic ho.

    ============================================================
    YOUTUBE METADATA RULES
    ============================================================
    1. "title": MAX 55 characters, curiosity-based, ek emoji, NO hashtags.
    2. "description": 2-3 short lines with search keywords. No hashtags.
    3. "tags": 15-20 lowercase keywords without #.

    Return ONLY valid JSON (no markdown) in exactly this structure.

    Example JSON Output Format (FORMAT ONLY):
    {{
      "title": "Yahan title likho 🔥",
      "description": "Line one\\nLine two",
      "tags": ["tag one", "tag two"],
      "scenes": [
        {{
          "narration": "Ye jagah duniya se gayab ho gayi",
          "search_keyword": "abandoned city fog"
        }},
        {{
          "narration": "Scientists ne wahan jaake kuch ajeeb dekha",
          "search_keyword": "scientist laboratory"
        }},
        {{
          "narration": "Aage wali baat aur bhi shocking hai",
          "search_keyword": "storm clouds dramatic"
        }}
      ]
    }}
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
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
            wait_time = base_wait * attempt
            print(
                f"[Attempt {attempt}/{max_retries}] API Error: {e}. "
                f"Retrying in {wait_time}s..."
            )
            if attempt < max_retries:
                time.sleep(wait_time)
            else:
                print("Max retries reached. Giving up on script generation.")
                notify_telegram(
                    f"❌ Script generation failed after {max_retries} attempts: {e}"
                )
                return None
        except Exception as e:
            print(
                f"[Attempt {attempt}/{max_retries}] Error parsing script JSON: {e}"
            )
            if attempt < max_retries:
                time.sleep(5)

    return None


# ---------------------------------------------------------------
# TTS text cleanup
# ---------------------------------------------------------------
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
    voice = "hi-IN-MadhurNeural"
    cleaned_text = clean_text_for_tts(text)
    communicate = edge_tts.Communicate(
        cleaned_text,
        voice,
        rate="+8%",
        pitch="-1Hz",
    )
    await communicate.save(output_file)


# ---------------------------------------------------------------
# Scene-wise voiceovers
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# Scene-wise video clips
# ---------------------------------------------------------------
def build_scene_clips(scenes):
    shutil.rmtree(SCENE_CLIP_DIR, ignore_errors=True)
    os.makedirs(SCENE_CLIP_DIR, exist_ok=True)

    paths = []
    for index, scene in enumerate(scenes, start=1):
        target = os.path.join(SCENE_CLIP_DIR, f"scene_{index:02d}.mp4")
        keyword = scene.get("search_keyword") or "nature landscape"
        query = get_optimized_search_query(keyword)
        print(f"🎥 Scene {index}: '{query}'")

        try:
            fetch_scene_video(query, target, min_duration=3)
            paths.append(target)
        except Exception as e:
            print(f"⚠️ Scene {index} ka clip nahi mila: {e}")
            if not paths:
                raise
            paths.append(paths[-1])
    return paths


# ---------------------------------------------------------------
# YouTube metadata builder
# ---------------------------------------------------------------
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
    candidates = ["#Shorts", "#Facts", "#HindiFacts", "#UrduFacts", "#AmazingFacts", "#CrazyFacts"]
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


# ---------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------
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
        print("⚠️ Thumbnail frame extract nahi ho paya.")
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

    print(f"⚠️ Thumbnail generate nahi hua: {result.stderr[-300:]}")
    return None


# ---------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------
def main():
    print("🚀 Starting Automated Short Pipeline...")
    start_time = time.time()

    print("\n📝 Generating 30-40s Short script...")
    script = generate_script()
    if not script:
        print("❌ Script generation failed.")
        notify_telegram("❌ Pipeline failed: script generation returned None")
        return

    scenes = script["scenes"]
    full_narration = " ".join(s["narration"] for s in scenes)
    print(f"📝 {len(scenes)} scenes | Hook: {scenes[0]['narration']}")

    print("\n🎙️ Generating scene-wise Voiceover...")
    try:
        voice_paths = build_scene_voiceovers(scenes)
    except Exception as e:
        print(f"❌ Voiceover failed: {e}")
        notify_telegram(f"❌ Voiceover generation failed: {e}")
        return

    print("\n🎥 Downloading a different Stock Video for every scene...")
    try:
        clip_paths = build_scene_clips(scenes)
    except Exception as e:
        print(f"❌ Video download failed: {e}")
        notify_telegram(f"❌ Video download failed: {e}")
        return

    print("\n🎬 Merging Video & Audio...")
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
                print(f"🎵 BG music: {bg_music_path}")
                break
        elif os.path.isfile(candidate):
            bg_music_path = candidate
            print(f"🎵 BG music: {bg_music_path}")
            break

    try:
        final_video_path = composer.create_multi_scene_short(
            clip_paths=clip_paths,
            voiceover_paths=voice_paths,
            output_filename="final_short.mp4",
            bg_music_path=bg_music_path,
        )
    except Exception as e:
        print(f"❌ Composition failed: {e}")
        notify_telegram(f"❌ Video composition failed: {e}")
        return

    if not os.path.exists(final_video_path):
        print("❌ Final video file create nahi hui.")
        notify_telegram("❌ Final video file not created")
        return

    print("\n🖼️ Generating thumbnail...")
    thumb_path = os.path.join(OUTPUT_DIR, "thumbnail.jpg")
    generate_thumbnail(
        final_video_path,
        thumb_path,
        script.get("title", "Amazing Fact"),
    )

    print("\n⬆️ Uploading Video to YouTube...")
    title, description, tags = build_metadata(script, full_narration)
    print(f"📹 Title: {title}")
    print(f"🏷️ Tags: {len(tags)} tags")

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
        print(f"🎉 Video uploaded! ID: {video_id}")
        print(f"🔗 https://youtube.com/shorts/{video_id}")

        if os.path.exists(thumb_path):
            print("\n🖼️ Setting thumbnail...")
            set_thumbnail(
                video_id,
                thumb_path,
                YOUTUBE_CLIENT_ID,
                YOUTUBE_CLIENT_SECRET,
                YOUTUBE_REFRESH_TOKEN,
            )

        if YOUTUBE_PLAYLIST_ID:
            print("\n📂 Adding to playlist...")
            add_to_playlist(
                video_id,
                YOUTUBE_PLAYLIST_ID,
                YOUTUBE_CLIENT_ID,
                YOUTUBE_CLIENT_SECRET,
                YOUTUBE_REFRESH_TOKEN,
            )

        elapsed = time.time() - start_time
        notify_telegram(
            f"✅ Video uploaded!\n"
            f"📹 {title}\n"
            f"🔗 https://youtube.com/shorts/{video_id}\n"
            f"⏱️ {elapsed:.0f}s"
        )

    except Exception as e:
        print(f"❌ YouTube Upload Failed: {e}")
        notify_telegram(f"❌ YouTube upload failed: {e}")

    if TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET and TIKTOK_REFRESH_TOKEN:
        print("\n⬆️ Uploading Video to TikTok (draft)...")
        try:
            tiktok_publish_id = upload_to_tiktok(
                video_path=final_video_path,
                title=title,
                client_key=TIKTOK_CLIENT_KEY,
                client_secret=TIKTOK_CLIENT_SECRET,
                refresh_token=TIKTOK_REFRESH_TOKEN,
            )
            print(f"🎉 TikTok upload complete! Publish ID: {tiktok_publish_id}")
            print(f"📱 Open TikTok app to manually post the draft")

            notify_telegram(
                f"✅ TikTok draft uploaded!\n"
                f"📹 {title}\n"
                f"🆔 Publish ID: {tiktok_publish_id}\n"
                f"📱 Open TikTok app to post manually"
            )
        except Exception as e:
            print(f"❌ TikTok Upload Failed: {e}")
            notify_telegram(f"❌ TikTok upload failed: {e}")
    else:
        print("\n⚠️ TikTok credentials missing — skipping TikTok upload.")

    elapsed = time.time() - start_time
    print(f"\n✨ Pipeline complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

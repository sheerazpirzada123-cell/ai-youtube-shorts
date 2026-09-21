import os
import json
import time
import re
import random
import shutil
import requests
import asyncio
import edge_tts
from google import genai
from google.genai import types
from google.genai.errors import APIError

from modules.composer import ShortsComposer
from modules.youtube_uploader import upload_video
from modules.asset_manager import fetch_scene_video
from modules.audio import _trim_silence

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

# New Client Initialization
client = genai.Client(api_key=GEMINI_API_KEY)

ASSETS_DIR = "assets"
TEMP_VIDEO_DIR = os.path.join(ASSETS_DIR, "video_clips")
TEMP_AUDIO_DIR = os.path.join(ASSETS_DIR, "audio_clips")
SCENE_CLIP_DIR = os.path.join(ASSETS_DIR, "scene_clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "final")

for directory in [TEMP_VIDEO_DIR, TEMP_AUDIO_DIR, SCENE_CLIP_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

KEYWORD_MAP = {
    "blood falls": "Antarctica red waterfall blood falls glacier",
    "dancing forest": "Kaliningrad curved twisted pine trees forest",
    "eternal flame": "New York eternal flame waterfall cavern cave fire",
    "antarctica": "antarctica glacier ice freeze landscape",
    "bermuda triangle": "bermuda triangle ocean storm dark water",
    "surtsey island": "volcano island emergence sea ocean lava"
}

# Har run par naya topic chuna jata hai. Pehle prompt fixed tha aur uska example
# bhi "Eternal Flame Falls" wala tha, is liye Gemini bar bar wohi script de raha
# tha. Ab topic + angle random hote hain aur temperature bhi upar hai.
TOPIC_POOL = [
    "duniya ki sabse ajeeb jagah jahan science bhi confuse ho jata hai",
    "samundar ke andar chupi hui koi hairan kar dene wali cheez",
    "koi aisa island jahan jana mana hai",
    "space aur planets ke bare mein koi weird fact",
    "insani jism ka koi aisa fact jo zyadatar log nahi jante",
    "koi purani civilization ka aisa raaz jo aaj tak solve nahi hua",
    "jaanwaron ki koi aisi power jo bilkul unbelievable hai",
    "duniya ka sabse khatarnak natural phenomenon",
    "koi aisi jagah jahan waqt ya gravity ajeeb behave karti hai",
    "abandoned city ya ghost town ki kahani",
    "koi aisi purani technology jo apne waqt se decades aage thi",
    "desert, glacier ya volcano se juda koi shocking fact",
    "koi aisa plant ya khana jo duniya ka sabse ajeeb hai",
    "deep sea creatures aur unki ajeeb duniya",
    "mausam ka koi aisa record jo sunn kar yaqeen na aaye",
    "koi aam cheez jiski asli kahani hairan kar deti hai",
    "dimagh aur memory se juda koi mind blowing fact",
    "kisi mashhoor jagah ke peeche chupa hua ajeeb sach",
]

ANGLE_POOL = [
    "ek seedhe sawal se shuru karo",
    "ek shocking statement se shuru karo",
    "'zara socho' wale andaz mein samjhao",
    "pehle mystery batao phir scientists ka jawab",
    "ek chhoti si kahani ki tarah sunao",
    "'zyadatar log samajhte hain lekin asal mein' wala twist do",
]

# Pehle 3 second ka HOOK - har run par alag style.
HOOK_POOL = [
    "ek shocking claim se shuru karo jo sunte hi impossible lage",
    "ek khaufnak ya dangerous warning se shuru karo",
    "aisa sawal poocho jiska jawab jaanne ke liye viewer ruk jaye",
    "ek unbelievable number ya record se shuru karo",
    "aisi baat se shuru karo jo viewer ki soch ko challenge kare",
    "ek adhoori baat se shuru karo jo jawab dene se pehle ruk jaye",
]

TITLE_POOL = [
    "Unbelievable Mystery Revealed!",
    "You Won't Believe This Exists!",
    "This Place Broke Science!",
    "Nobody Can Explain This!",
    "The Craziest Fact Ever!",
    "Scientists Are Still Confused!",
    "This Sounds Fake But It's Real!",
    "Wait Till You See This!",
]

BASE_TAGS = [
    "shorts", "youtubeshorts", "facts", "hindi facts", "urdu facts",
    "amazing facts", "mysteries", "viral shorts", "science facts",
]

MIN_SCENES = 5


def get_optimized_search_query(text):
    text_lower = text.lower()
    for key, search_term in KEYWORD_MAP.items():
        if key in text_lower:
            return search_term
    return text


def normalize_script(data):
    """Gemini ka output (dict ya purani list) ko ek standard dict mein badalta hai."""
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
        keyword = str(scene.get("search_keyword") or scene.get("visual_keyword") or "").strip()
        scenes.append({"narration": narration, "search_keyword": keyword})

    if len(scenes) < MIN_SCENES:
        raise ValueError(f"Sirf {len(scenes)} scenes mile, kam az kam {MIN_SCENES} chahiye")

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
    topic = random.choice(TOPIC_POOL)
    angle = random.choice(ANGLE_POOL)
    hook_style = random.choice(HOOK_POOL)
    run_seed = f"{int(time.time())}-{random.randint(100000, 999999)}"
    print(f"🎲 Run topic: {topic} | angle: {angle} | hook: {hook_style} | seed: {run_seed}")

    prompt = f"""
    Write a smooth, fast-paced, VIRAL YouTube Short script in simple spoken Hindi/Urdu (written in Roman letters) mixed with common English words.

    TOPIC FOR THIS SCRIPT (must be about this, pick ONE specific real example of it):
    {topic}

    STYLE ANGLE FOR THIS SCRIPT: {angle}

    HOOK STYLE FOR SCENE 1: {hook_style}

    FRESHNESS RULES (VERY IMPORTANT):
    1. The JSON example below is ONLY a format sample. DO NOT write about Eternal Flame Falls,
       New York, or any topic shown in the example.
    2. Pick a specific, concrete subject that fits the topic above and build the whole script on it.
    3. Uniqueness seed (do not mention it in the output, just make sure the wording and the chosen
       subject are different from any previous script): {run_seed}
    4. Facts must be real and credible. Do not invent anything.

    HOOK RULES (MOST IMPORTANT - viewers decide in the first 3 seconds):
    1. Scene 1 is ONLY the hook. Maximum 9 words (about 3 seconds when spoken).
    2. The hook must create a curiosity gap - make the viewer NEED the answer - but must NOT reveal the answer.
    3. No greeting. Do NOT start with "Namaste", "Hello", "Doston" or "Kya aapko pata hai".
    4. Scene 2 must immediately start paying off the hook. Add one small twist line around the middle
       (like "lekin asli baat ye hai") so people keep watching.
    5. The LAST scene is a short punchy closing line that makes people want to watch again
       (it can connect back to the opening question). No long "like subscribe" speech.

    STRICT LANGUAGE & STYLE RULES:
    1. NO hard or formal Hindi words (Strictly avoid: prakriti, chattaan, rahasya, adbhut, drishya, etc.).
    2. Use simple daily conversational Hindi/Urdu with simple English words (waterfall, fire, mystery, natural gas, place, dangerous, scientists).
    3. VERY IMPORTANT FOR CONTINUOUS FLOW: DO NOT use full stops (.), question marks (?), or commas (,) inside the narration text so there are NO LONG PAUSES OR GAPS between words. Keep every scene as ONE connected sentence.

    SCENE & DURATION RULES:
    1. Split the script into 8 to 10 scenes. Each scene = exactly ONE short sentence (6 to 12 words).
       Scene 1 is the hook (max 9 words).
    2. Total length MUST be 30 to 40 seconds (70-85 words total across all scenes).
    3. Every scene gets its OWN stock video clip, so every scene needs a DIFFERENT "search_keyword".
       Never repeat the same keyword or the same visual in two scenes.
    4. "search_keyword" = English stock-footage search words, 2 to 4 words, that visually match THAT scene's sentence.
       Use common, easy-to-find footage subjects (ocean, forest, volcano, desert, space, city, animals,
       laboratory, ruins, fire, ice, storm, clouds, waterfall, night sky, etc.). Do not use people's names
       or brand names. If the real subject is too rare/specific for stock sites, use the closest broad
       category instead.

    YOUTUBE METADATA RULES:
    1. "title": maximum 60 characters, curiosity-based, includes the main keyword of the fact,
       one emoji, Roman Hindi/Urdu + English mix, NO hashtags.
    2. "description": 2 to 3 short lines, engaging, and rich with search keywords people would type
       (for example: amazing facts in hindi, urdu facts, mysterious places, the topic keywords).
       NO hashtags in it (they are added separately).
    3. "tags": 15 to 20 lowercase search keywords WITHOUT the # sign. Mix English and Roman Hindi/Urdu,
       broad ones (facts, hindi facts, urdu facts, amazing facts, shorts) and topic-specific ones.

    Return ONLY valid JSON (no markdown) in exactly this structure.

    Example JSON Output Format (FORMAT ONLY - do not reuse this content):
    {{
      "title": "Yahan title likho 🔥",
      "description": "Line one\\nLine two",
      "tags": ["tag one", "tag two"],
      "scenes": [
        {{
          "narration": "Ye jagah duniya ke naqshe se kyun mita di gayi",
          "search_keyword": "old map ocean"
        }},
        {{
          "narration": "Scientists ko wahan pahunchte hi kuch ajeeb mehsoos hua",
          "search_keyword": "scientist laboratory"
        }}
      ]
    }}
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                # Default sampling was too deterministic and kept returning the
                # same script every run.
                config=types.GenerateContentConfig(
                    temperature=1.3,
                    top_p=0.95,
                    response_mime_type="application/json",
                ),
            )
            clean_json = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', response.text).strip()
            return normalize_script(json.loads(clean_json))
        except APIError as e:
            wait_time = base_wait * attempt
            print(f"[Attempt {attempt}/{max_retries}] API Error: {e}. Retrying in {wait_time}s...")
            if attempt < max_retries:
                time.sleep(wait_time)
            else:
                print("Max retries reached. Giving up on script generation.")
                return None
        except Exception as e:
            print(f"[Attempt {attempt}/{max_retries}] Error parsing script JSON: {e}")
            if attempt < max_retries:
                time.sleep(5)

    return None


def clean_text_for_tts(text):
    text = re.sub(r'\bise\b', 'isey', text, flags=re.IGNORECASE)
    text = re.sub(r'\bI\.S\.E\b', 'isey', text, flags=re.IGNORECASE)
    text = re.sub(r'\bjise\b', 'jisey', text, flags=re.IGNORECASE)
    text = re.sub(r'\buse\b', 'usey', text, flags=re.IGNORECASE)
    text = text.replace(".", " ").replace("?", " ").replace("!", " ").replace(",", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def generate_voiceover(text, output_file):
    voice = "hi-IN-MadhurNeural"
    cleaned_text = clean_text_for_tts(text)
    communicate = edge_tts.Communicate(cleaned_text, voice, rate="+5%")
    await communicate.save(output_file)


def build_scene_voiceovers(scenes):
    """Har scene ki apni voice file (taake clip ki length voice se match ho)."""
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
            raise RuntimeError(f"Scene {index} ki voiceover generate nahi ho saki.")

        _trim_silence(path)  # scene ke start/end ki extra khamoshi hatao
        paths.append(path)
    return paths


def build_scene_clips(scenes):
    """Har scene ke liye alag stock clip (Pexels -> Pixabay -> AI image fallback)."""
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
            paths.append(paths[-1])  # pichla clip dobara (composer alag hissa lega)
    return paths


def build_metadata(script, full_narration):
    """Title, description (keywords + hashtags) aur tags tayyar karta hai."""
    title_core = re.sub(r'#\S+', '', script.get("title", "")).strip()
    if not title_core:
        title_core = random.choice(TITLE_POOL)
    title = f"{title_core[:88].strip()} #Shorts"[:100]

    # Tags: Gemini ke topic tags + base tags (dedupe, total 450 chars se kam)
    tags, seen, total_chars = [], set(), 0
    for tag in script.get("tags", []) + BASE_TAGS:
        tag = re.sub(r'[#,<>]', '', tag).strip().lower()
        if not tag or tag in seen:
            continue
        if total_chars + len(tag) + 1 > 450:
            break
        seen.add(tag)
        tags.append(tag)
        total_chars += len(tag) + 1

    # Hashtags: YouTube 15 se zyada hashtags ko ignore kar deta hai, is liye max 12
    hashtags, seen_h = [], set()
    for candidate in ["#Shorts", "#Facts", "#HindiFacts", "#UrduFacts"] + [
        "#" + re.sub(r'[^0-9a-zA-Z]', '', t) for t in script.get("tags", [])
    ]:
        key = candidate.lower()
        if len(candidate) < 3 or key in seen_h:
            continue
        seen_h.add(key)
        hashtags.append(candidate)
        if len(hashtags) >= 12:
            break

    body = script.get("description") or full_narration
    description = f"{body}\n\n{' '.join(hashtags)}"[:4900]

    return title, description, tags


def main():
    print("🚀 Starting Automated Short Pipeline...")

    print("Generating 30-40s Short script...")
    script = generate_script()

    if not script:
        print("❌ Script generation failed.")
        return

    scenes = script["scenes"]
    full_narration = " ".join(scene["narration"] for scene in scenes)
    print(f"📝 {len(scenes)} scenes | Hook: {scenes[0]['narration']}")

    print("🎙️ Generating scene-wise Voiceover...")
    voice_paths = build_scene_voiceovers(scenes)

    print("🎥 Downloading a different Stock Video for every scene...")
    try:
        clip_paths = build_scene_clips(scenes)
    except Exception as e:
        print(f"❌ Video download failed: {e}")
        return

    print("🎬 Merging Video & Audio...")
    composer = ShortsComposer(output_dir=OUTPUT_DIR)
    bg_music_path = os.path.join("modules", "bg_music.mp3")

    final_video_path = composer.create_multi_scene_short(
        clip_paths=clip_paths,
        voiceover_paths=voice_paths,
        output_filename="final_short.mp4",
        bg_music_path=bg_music_path
    )

    if os.path.exists(final_video_path):
        print("⬆️ Uploading Video to YouTube...")
        title, description, tags = build_metadata(script, full_narration)
        print(f"Title: {title}")

        try:
            video_id = upload_video(
                video_path=final_video_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status="public",
                client_id=YOUTUBE_CLIENT_ID,
                client_secret=YOUTUBE_CLIENT_SECRET,
                refresh_token=YOUTUBE_REFRESH_TOKEN
            )
            print(f"🎉 Process Complete! Video uploaded successfully with ID: {video_id}")
        except Exception as e:
            print(f"❌ YouTube Upload Failed: {e}")


if __name__ == "__main__":
    main()

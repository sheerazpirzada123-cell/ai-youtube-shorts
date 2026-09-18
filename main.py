import os
import json
import time
import requests
import asyncio
import edge_tts
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from modules.composer import ShortsComposer
from modules.youtube_uploader import upload_video

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)

ASSETS_DIR = "assets"
TEMP_VIDEO_DIR = os.path.join(ASSETS_DIR, "video_clips")
TEMP_AUDIO_DIR = os.path.join(ASSETS_DIR, "audio_clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "final")

for directory in [TEMP_VIDEO_DIR, TEMP_AUDIO_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

KEYWORD_MAP = {
    "blood falls": "Antarctica red waterfall blood falls glacier",
    "dancing forest": "Kaliningrad curved twisted pine trees forest",
    "eternal flame": "New York eternal flame waterfall cavern cave fire",
    "antarctica": "antarctica glacier ice freeze landscape",
    "bermuda triangle": "bermuda triangle ocean storm dark water",
    "surtsey island": "volcano island emergence sea ocean lava"
}

def get_optimized_search_query(text):
    text_lower = text.lower()
    for key, search_term in KEYWORD_MAP.items():
        if key in text_lower:
            return search_term
    return text

def generate_script(max_retries=3, base_wait=20):
    prompt = """
    Create an engaging, mysterious YouTube Short script in Hindi/Urdu.
    
    STRICT RULES:
    1. Duration: MUST be between 30 to 45 seconds (around 70 to 85 words max).
    2. Focus: Pick ONLY 1 or 2 specific mysteries or places per video (e.g., Blood Falls or Eternal Flame Falls) so the context is detailed and focused.
    3. Formatting: Return a valid JSON list where each object has "narration" and "search_keyword".
    
    Example Output Format:
    [
      {
        "narration": "Kya aapne kabhi zameen ke neeche pani mein jalti hui aag dekhi hai?",
        "search_keyword": "New York eternal flame waterfall cavern cave fire"
      },
      {
        "narration": "Antarctica mein ek aisi jagah hai jahan barf ke beech se laal rang ka paani behta hai, jise Blood Falls kehte hain.",
        "search_keyword": "Antarctica red waterfall blood falls glacier"
      }
    ]
    """

    model = genai.GenerativeModel("gemini-2.5-flash")

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            script_data = json.loads(clean_json)
            return script_data
        except ResourceExhausted as e:
            wait_time = base_wait * attempt
            print(f"[Attempt {attempt}/{max_retries}] Quota limit hit (429). Retrying in {wait_time}s...")
            if attempt < max_retries:
                time.sleep(wait_time)
            else:
                print("Max retries reached. Giving up on script generation.")
                return []
        except Exception as e:
            print(f"Error parsing script JSON: {e}")
            return []

    return []

def download_broll_video(query, save_path):
    optimized_query = get_optimized_search_query(query)
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={optimized_query}&per_page=5&orientation=portrait"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("videos"):
            videos = data["videos"]
            selected_video = max(videos, key=lambda v: v.get("duration", 0))
            video_files = selected_video["video_files"]
            video_url = video_files[0]["link"]
            
            v_res = requests.get(video_url, stream=True)
            if v_res.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in v_res.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                return True

    print(f"No video found for: {optimized_query}")
    return False

async def generate_voiceover(text, output_file):
    voice = "ur-PK-AsadNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def main():
    print("🚀 Starting Automated Short Pipeline...")
    
    print("Generating 30-45s Short script...")
    script_data = generate_script()
    
    if not script_data:
        print("❌ Script generation failed.")
        return

    full_narration = " ".join([scene.get("narration", "") for scene in script_data])
    first_keyword = script_data[0].get("search_keyword", "mysterious place") if script_data else "mysterious place"

    audio_path = os.path.join(TEMP_AUDIO_DIR, "narration.mp3")
    print("🎙️ Generating Voiceover...")
    asyncio.run(generate_voiceover(full_narration, audio_path))

    video_path = os.path.join(TEMP_VIDEO_DIR, "broll.mp4")
    print("🎥 Downloading Stock Video...")
    success = download_broll_video(first_keyword, video_path)
    
    if not success:
        print("❌ Video download failed.")
        return

    print("🎬 Merging Video & Audio...")
    composer = ShortsComposer(output_dir=OUTPUT_DIR)
    bg_music_path = os.path.join("modules", "bg_music.mp3")
    
    final_video_path = composer.create_short(
        video_path=video_path,
        voiceover_path=audio_path,
        output_filename="final_short.mp4",
        bg_music_path=bg_music_path
    )

    if os.path.exists(final_video_path):
        print("⬆️ Uploading Video to YouTube...")
        title = f"Unbelievable Mystery Revealed! #Shorts #{first_keyword.replace(' ', '')}"
        description = f"{full_narration}\n\n#Shorts #Viral #Mysteries"
        
        try:
            video_id = upload_video(
                video_path=final_video_path,
                title=title[:100],
                description=description,
                tags=["shorts", "mysteries", "facts", "youtubeshorts"],
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

import os
import re
import sys
import time
import requests
import subprocess
from gtts import gTTS

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# --- YouTube auto-upload (free, YouTube Data API v3) --------------------
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")

NUM_SCENES = int(os.getenv("NUM_SCENES", "5"))

# ElevenLabs keys fallback list
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_story_script():
    """Generates an NUM_SCENES-scene facts script with visual keywords for Pexels/Pixabay."""
    print("Generating Unique Facts Script via Gemini...")

    if not gemini_client:
        print("Gemini client not available, using default script.")
        return {"scenes": [
            {"keyword": "galaxy space stars", "script": "Kya aapko pata hai, hamari galaxy mein taron ki sankhya samandar ki reti ke kano se bhi zyada hai!"},
            {"keyword": "deep ocean waves", "script": "Duniya ka sabse gehra hissa itna andhera hai ke wahan rooh kaanp jaye!"}
        ]}

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]

    format_lines = []
    for i in range(1, NUM_SCENES + 1):
        format_lines.append(f"SCENE {i} KEYWORD: [Pexels search keyword in English]")
        format_lines.append(f"SCENE {i} SCRIPT: [Hindi voiceover line]")
    format_block = "\n".join(format_lines)

    prompt_text = (
        f"Create a viral facts YouTube Short script with {NUM_SCENES} scenes in Hindi. "
        "Each scene must have a short English search keyword for downloading stock videos (like Pexels) "
        "and 1 engaging Hindi dialogue line.\n\n"
        "STRICT FORMAT (no extra text before/after):\n" + format_block
    )

    for model_name in models_to_try:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            raw_text = (response.text or "").strip()

            scenes = []
            keywords = re.findall(r'SCENE \d+ KEYWORD:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(keywords) >= NUM_SCENES and len(scripts) >= NUM_SCENES:
                for i in range(NUM_SCENES):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_keyword = keywords[i].strip()
                    if clean_script and clean_keyword:
                        scenes.append({"keyword": clean_keyword, "script": clean_script})
                if len(scenes) == NUM_SCENES:
                    return {"scenes": scenes}
        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return {"scenes": [
        {"keyword": "galaxy space stars", "script": "Kya aapko pata hai, hamari galaxy mein taron ki sankhya samandar ki reti ke kano se bhi zyada hai!"},
        {"keyword": "deep ocean waves", "script": "Duniya ka sabse gehra hissa itna andhera hai ke wahan rooh kaanp jaye!"}
    ]}


def download_pexels_video(keyword, idx):
    """Pexels API se stock video download karta hai."""
    if not PEXELS_API_KEY:
        return None
    
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(keyword)}&per_page=1"
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            videos = data.get("videos", [])
            if videos:
                # HD ya vertical video files find karein
                video_files = videos[0].get("video_files", [])
                best_url = None
                for vf in video_files:
                    if vf.get("width") and vf.get("height") and vf["height"] > vf["width"]:
                        best_url = vf["link"]
                        break
                if not best_url and video_files:
                    best_url = video_files[0]["link"]
                
                if best_url:
                    vid_res = requests.get(best_url, stream=True, timeout=30)
                    if vid_res.status_code == 200:
                        out_path = f"pexels_scene_{idx}.mp4"
                        with open(out_path, "wb") as f:
                            for chunk in vid_res.iter_content(chunk_size=1024):
                                if chunk:
                                    f.write(chunk)
                        return out_path
    except Exception as e:
        print(f"Pexels download error: {e}")
    return None


def download_pixabay_video(keyword, idx):
    """Agar Pexels na mile toh Pixabay se stock video download karta hai."""
    if not PIXABAY_API_KEY:
        return None
        
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(keyword)}&per_page=3"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if hits:
                vid_url = hits[0]["videos"]["medium"]["url"]
                vid_res = requests.get(vid_url, stream=True, timeout=30)
                if vid_res.status_code == 200:
                    out_path = f"pixabay_scene_{idx}.mp4"
                    with open(out_path, "wb") as f:
                        for chunk in vid_res.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                    return out_path
    except Exception as e:
        print(f"Pixabay download error: {e}")
    return None


def get_fallback_bg_video(keyword, idx):
    """Agar Pexels/Pixabay fail ho jaye toh Pollinations se background image generate karke zoompan video bana deta hai."""
    img_prompt = requests.utils.quote(f"{keyword}, cinematic background, vertical 9:16")
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = f"fallback_{idx}.jpg"
    out_file = f"fallback_scene_{idx}.mp4"
    
    try:
        res = requests.get(img_url, timeout=30)
        if res.status_code == 200:
            with open(img_file, "wb") as f:
                f.write(res.content)
            
            zoom_cmd = [
                "ffmpeg", "-loop", "1", "-i", img_file,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.3)':d=150:s=1080x1920:fps=25",
                "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", out_file
            ]
            subprocess.run(zoom_cmd, check=True, capture_output=True, text=True)
            return out_file
    except Exception as e:
        print(f"Fallback bg generation failed: {e}")
    return None


def get_media_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def assemble_scene(keyword, script_text, idx):
    # 1. Voiceover generate karein (ElevenLabs ya gTTS)
    audio_file = f"audio_{idx}.mp3"
    eleven_success = False
    for key in ELEVEN_KEYS:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            headers = {"xi-api-key": key, "Content-Type": "application/json"}
            payload = {
                "text": script_text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.35, "similarity_boost": 0.85}
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200 and res.content:
                with open(audio_file, "wb") as f:
                    f.write(res.content)
                eleven_success = True
                break
        except Exception:
            pass

    if not eleven_success:
        try:
            tts = gTTS(text=script_text, lang="hi", slow=False)
            tts.save(audio_file)
        except Exception as e:
            print(f"gTTS failed: {e}")
            raise

    audio_duration = get_media_duration(audio_file)

    # 2. Pexels ya Pixabay se stock video uthayein
    video_file = download_pexels_video(keyword, idx)
    if not video_file:
        video_file = download_pixabay_video(keyword, idx)
    if not video_file:
        video_file = get_fallback_bg_video(keyword, idx)

    if not video_file:
        raise RuntimeError(f"Could not get video for scene {idx}")

    # 3. FFmpeg se video ko audio ke mutabiq resize aur trim karein (Vertical 9:16)
    output_clip = f"clip_{idx}.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-stream_loop", "-1", "-i", video_file, "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
        "-t", f"{audio_duration:.2f}", "-y", output_clip
    ]
    subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
    return output_clip


def merge_clips(clip_files, final_output="final_short.mp4"):
    with open("files.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    concat_cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", "files.txt", "-c", "copy", "-y", final_output
    ]
    subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
    return final_output


def upload_to_youtube(video_path, title, description):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("YouTube credentials missing, skipping upload.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return None

    creds = Credentials(
        token=None,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    try:
        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "facts", "hindi", "amazingfacts", "viral"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": YT_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
        video_id = response.get("id")
        print(f"Uploaded to YouTube: https://youtube.com/shorts/{video_id}")
        return video_id
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None


if __name__ == "__main__":
    print("=== Stock Footage Facts Short Bot Started ===")
    story = generate_story_script()
    scenes = story["scenes"]
    final_clips = []

    for idx, scene in enumerate(scenes):
        print(f"\n--- Processing Scene {idx + 1}/{len(scenes)}: {scene['keyword']} ---")
        try:
            clip = assemble_scene(scene["keyword"], scene["script"], idx)
            final_clips.append(clip)
        except Exception as e:
            print(f"Scene {idx + 1} failed: {e}")

    if final_clips:
        try:
            final_video = merge_clips(final_clips)
            total_duration = get_media_duration(final_video)
        except Exception as e:
            print(f"\nFAILED: {e}")
            sys.exit(1)
        print(f"\nSUCCESS: Short Ready: {final_video} (~{total_duration:.1f}s)")

        yt_title = "Mind Blowing Facts 🤯 #Shorts"
        yt_description = "\n".join(s["script"] for s in scenes) + "\n\n#Shorts #Facts #HindiFacts #Viral #Trending #AmazingFacts"
        upload_to_youtube(final_video, yt_title, yt_description)
    else:
        print("\nFAILED: No clips produced.")
        sys.exit(1)

import os
import re
import sys
import time
import uuid
import inspect
import itertools
import requests
import subprocess
from gtts import gTTS

# ✅ FIXED: Check for required packages
def check_dependencies():
    """Check that all required packages are installed"""
    required_packages = {
        'google': 'google-genai',
        'gtts': 'gtts',
        'pydub': 'pydub',
        'moviepy': 'moviepy',
        'PIL': 'Pillow',
        'requests': 'requests',
        'gradio_client': 'gradio-client',
        'scipy': 'scipy',
        'cv2': 'opencv-python',
        'numpy': 'numpy'
    }
    
    missing = []
    for module, package_name in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package_name)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"Run: pip install {' '.join(missing)}")
        sys.exit(1)
    print("✅ All dependencies are installed")

check_dependencies()

# Gemini Setup
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- YouTube auto-upload (free, YouTube Data API v3) --------------------
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "private")

NUM_SCENES = int(os.getenv("NUM_SCENES", "5"))

# ElevenLabs keys fallback list
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]

# Hugging Face free Spaces for base video generation
HF_TOKENS = []
if os.getenv("HF_TOKEN", "").strip():
    HF_TOKENS.append(os.getenv("HF_TOKEN").strip())
for i in range(1, 5):
    tok = os.getenv(f"HF_TOKEN_{i}", "").strip()
    if tok:
        HF_TOKENS.append(tok)
HF_TOKENS = list(dict.fromkeys(HF_TOKENS))

HF_VIDEO_SPACES = [
    s.strip() for s in os.getenv("HF_VIDEO_SPACES", "Wan-AI/Wan2.1").split(",")
    if s.strip()
]

gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Warning: {e}")


def generate_story_script():
    """Generates an NUM_SCENES-scene cute 3D cartoon style story script with dynamic unique plots every time."""
    print("Generating Unique & Cute 3D Cartoon Story Script via Gemini...")

    if not gemini_client:
        print("Gemini client not available, using default script.")
        return {"scenes": [
            {"prompt": "Cute 3D Pixar style animated fluffy cat talking with funny expressive eyes, bright cozy room background, vertical 9:16", "script": "O yaaron, aaj maine ek naya business shuru karne ka socha hai, dekhte hain kya hota hai!"},
            {"prompt": "Cute 3D Pixar style animated funny dog reacting with shocked expression, colorful cartoon park background, vertical 9:16", "script": "Arre bhai, tera naya business sunkar mere toh hosh hi udd gaye!"}
        ]}

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]

    format_lines = []
    for i in range(1, NUM_SCENES + 1):
        format_lines.append(f"SCENE {i} PROMPT: [Video prompt]")
        format_lines.append(f"SCENE {i} SCRIPT: [Hindi dialogue line]")
    format_block = "\n".join(format_lines)

    prompt_text = (
        f"Create a totally unique, random, and funny {NUM_SCENES}-scene animated Hindi short story starring cute 3D cartoon characters "
        "(like funny cats, pets, or cute cartoon creatures) with a continuing storyline. Avoid repetition. Each scene must have a "
        "visual video prompt in English describing cute actions in a vibrant 3D Pixar/Disney style (max 12 words) "
        "and 1 pure Hindi dialogue line (roughly 6-8 seconds when spoken), making the whole short about 30-40 seconds.\n\n"
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
            video_prompts = re.findall(r'SCENE \d+ PROMPT:\s*(.*)', raw_text)
            scripts = re.findall(r'SCENE \d+ SCRIPT:\s*(.*)', raw_text)

            if len(video_prompts) >= NUM_SCENES and len(scripts) >= NUM_SCENES:
                for i in range(NUM_SCENES):
                    clean_script = re.sub(r'\(.*?\)', '', scripts[i]).replace('*', '').replace('"', '').strip()
                    clean_prompt = video_prompts[i].strip() + ", cute 3D Pixar style animation, vibrant colors, bright lighting, vertical 9:16"
                    if clean_script and clean_prompt:
                        scenes.append({"prompt": clean_prompt, "script": clean_script})
                if len(scenes) == NUM_SCENES:
                    return {"scenes": scenes}
        except Exception as e:
            print(f"Gemini Story Error ({model_name}): {e}")

    return {"scenes": [
        {"prompt": "Cute 3D Pixar style animated fluffy cat talking with funny expressive eyes, bright cozy room background, vertical 9:16", "script": "O yaaron, aaj maine ek naya business shuru karne ka socha hai, dekhte hain kya hota hai!"},
        {"prompt": "Cute 3D Pixar style animated funny dog reacting with shocked expression, colorful cartoon park background, vertical 9:16", "script": "Arre bhai, tera naya business sunkar mere toh hosh hi udd gaye!"}
    ]}


def _make_hf_client(space_id, token):
    from gradio_client import Client
    kwargs = {}
    if token:
        try:
            sig_params = inspect.signature(Client.__init__).parameters
        except (TypeError, ValueError):
            sig_params = {}
        if "hf_token" in sig_params:
            kwargs["hf_token"] = token
        elif "token" in sig_params:
            kwargs["token"] = token
    return Client(space_id, **kwargs)


def generate_video_hf_spaces(prompt_text, idx):
    try:
        from gradio_client import Client  # noqa: F401
    except ImportError:
        return None

    tokens_to_try = HF_TOKENS if HF_TOKENS else [None]

    for space_id in HF_VIDEO_SPACES:
        for token_idx, token in enumerate(tokens_to_try):
            try:
                client = _make_hf_client(space_id, token)
                result = client.predict(
                    prompt_text,
                    "",          # negative_prompt
                    480,         # resolution
                    5,           # duration
                    api_name="/generate_video"
                )
            except Exception:
                continue

            video_path = result
            if isinstance(video_path, (list, tuple)) and video_path:
                video_path = video_path[0]
            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("path")

            if not video_path or not os.path.exists(video_path):
                continue

            out_file = f"scene_{idx}_hf.mp4"
            try:
                with open(video_path, "rb") as src, open(out_file, "wb") as dst:
                    dst.write(src.read())
                return out_file
            except OSError:
                continue
    return None


def generate_video_pollinations_zoom(prompt_text, idx):
    img_prompt = requests.utils.quote(f"{prompt_text}, cute 3D cartoon style, bright lighting, colorful background, vertical")
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = f"scene_{idx}_pollinations.jpg"

    try:
        res = requests.get(img_url, timeout=60)
        res.raise_for_status()
        with open(img_file, "wb") as f:
            f.write(res.content)
    except Exception as e:
        print(f"Pollinations image fetch failed: {e}")
        return None

    out_file = f"scene_{idx}_pollinations.mp4"
    zoom_cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", img_file,
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "zoompan=z='min(zoom+0.0015,1.4)':d=200:s=1080x1920:fps=25",
        "-t", "8",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y",
        out_file
    ]
    try:
        subprocess.run(zoom_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg zoompan failed: {e.stderr}")
        return None

    return {"video": out_file, "face_image": img_file}


def generate_video_any_provider(prompt_text, idx):
    providers = [
        ("HF Spaces (free)", generate_video_hf_spaces),
        ("Pollinations cute cartoon image + zoom (guaranteed fallback)", generate_video_pollinations_zoom),
    ]
    for name, func in providers:
        try:
            result = func(prompt_text, idx)
        except Exception:
            result = None
        if result:
            if isinstance(result, dict):
                return result
            return {"video": result, "face_image": None}
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


def _clone_with_retry(repo_url, dest, attempts=3, timeout_s=180):
    """Shallow-clone with a hard timeout + retries so a stalled clone can't hang the job forever."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"  # never wait for a credentials prompt
    for attempt in range(1, attempts + 1):
        if os.path.exists(dest):
            return
        try:
            print(f"Cloning {repo_url} (attempt {attempt}/{attempts})...")
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, dest],
                check=True,
                timeout=timeout_s,
                env=env,
            )
            return
        except subprocess.TimeoutExpired:
            print(f"Clone timed out after {timeout_s}s, retrying...")
            subprocess.run(["rm", "-rf", dest])
        except subprocess.CalledProcessError as e:
            print(f"Clone failed: {e}, retrying...")
            subprocess.run(["rm", "-rf", dest])
    raise RuntimeError(f"Failed to clone {repo_url} after {attempts} attempts")


def _download_with_retry(url, dest_path, min_size_bytes=1_000_000, attempts=3, timeout_s=120):
    """Stream a download to disk (no huge in-memory buffering) with retries + size sanity check."""
    for attempt in range(1, attempts + 1):
        try:
            print(f"Downloading {os.path.basename(dest_path)} (attempt {attempt}/{attempts})...")
            with requests.get(url, stream=True, timeout=timeout_s) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) >= min_size_bytes:
                return
            print(f"Downloaded file too small, retrying...")
        except (requests.RequestException, OSError) as e:
            print(f"Download failed: {e}, retrying...")
    raise RuntimeError(f"Failed to download {url} after {attempts} attempts")


def setup_wav2lip():
    _clone_with_retry("https://github.com/Rudrabha/Wav2Lip.git", "Wav2Lip")
    os.makedirs("Wav2Lip/checkpoints", exist_ok=True)
    os.makedirs("Wav2Lip/face_detection/detection/sfd", exist_ok=True)

    weights_path = "Wav2Lip/checkpoints/wav2lip.pth"
    if not (os.path.exists(weights_path) and os.path.getsize(weights_path) >= 1_000_000):
        weights_url = "https://github.com/justinjohn0306/Wav2Lip/releases/download/models/wav2lip.pth"
        _download_with_retry(weights_url, weights_path)

    s3fd_path = "Wav2Lip/face_detection/detection/sfd/s3fd.pth"
    if not (os.path.exists(s3fd_path) and os.path.getsize(s3fd_path) >= 1_000_000):
        s3fd_url = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
        _download_with_retry(s3fd_url, s3fd_path)


def apply_wav2lip_lipsync(face_file, video_file, audio_file, output_clip, idx):
    """Applies Wav2Lip local lipsync with proper fallback handling if face detection misses.
    face_file: static image (fast, single face-detection pass) if available, else same as video_file.
    video_file: always a video, used for the ffmpeg fallback if Wav2Lip fails/times out.
    """
    setup_wav2lip()
    
    # Ensure temp directory exists for Wav2Lip audio processing
    os.makedirs("temp", exist_ok=True)
    
    inference_script = "Wav2Lip/inference.py"
    checkpoint_path = "Wav2Lip/checkpoints/wav2lip.pth"
    
    cmd = [
        "python", inference_script,
        "--checkpoint_path", checkpoint_path,
        "--face", face_file,
        "--audio", audio_file,
        "--outfile", output_clip,
        "--pads", "0", "10", "0", "0",
        "--nosmooth",
        "--resize_factor", "2",
        "--face_det_batch_size", "2",
        "--wav2lip_batch_size", "16",
    ]

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"

    try:
        print(f"Running Wav2Lip lipsync for scene {idx + 1}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
        if result.returncode == 0 and os.path.exists(output_clip) and os.path.getsize(output_clip) > 1000:
            print(f"Wav2Lip successfully applied for scene {idx + 1}!")
            return output_clip
        else:
            print(f"Wav2Lip warning output: {result.stderr}")
    except subprocess.TimeoutExpired:
        print(f"Wav2Lip timed out for scene {idx + 1}, falling back...")
    except Exception as e:
        print(f"Wav2Lip execution error: {e}")
    
    print("Applying standard audio-video sync fallback for this scene...")
    audio_duration = get_media_duration(audio_file)
    fallback_cmd = [
        "ffmpeg", "-stream_loop", "-1", "-i", video_file, "-i", audio_file,
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
        "-t", f"{audio_duration:.2f}", "-y", output_clip
    ]
    subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
    return output_clip


def assemble_scene(video_file, face_image, script_text, idx):
    audio_file = f"audio_{idx}.mp3"

    eleven_success = False
    for key_idx, key in enumerate(ELEVEN_KEYS):
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
            print(f"gTTS fallback failed: {e}")
            raise

    padded_audio_file = f"audio_{idx}_padded.mp3"
    pad_cmd = [
        "ffmpeg", "-i", audio_file,
        "-af", "apad=pad_dur=0.5",
        "-y", padded_audio_file
    ]
    try:
        subprocess.run(pad_cmd, check=True, capture_output=True, text=True)
        audio_file = padded_audio_file
    except subprocess.CalledProcessError as e:
        print(f"Audio padding failed, using unpadded audio: {e.stderr}")

    output_clip = f"clip_{idx}.mp4"
    face_file = face_image if face_image else video_file
    return apply_wav2lip_lipsync(face_file, video_file, audio_file, output_clip, idx)


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
    """Improved YouTube upload with better error handling and debugging"""
    
    # Debug: Check if credentials exist
    print("\n" + "="*70)
    print("🔍 YouTube Upload Check:")
    print("="*70)
    print(f"✓ Video file: {video_path}")
    print(f"✓ YT_CLIENT_ID exists: {bool(YT_CLIENT_ID)}")
    print(f"✓ YT_CLIENT_SECRET exists: {bool(YT_CLIENT_SECRET)}")
    print(f"✓ YT_REFRESH_TOKEN exists: {bool(YT_REFRESH_TOKEN)}")
    print("="*70)
    
    # Check if all credentials are present
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("\n❌ YouTube Credentials غائب ہیں!")
        print("\n✅ حل:")
        print("1. Google Cloud Console میں OAuth credentials بنائیں")
        print("2. Refresh Token حاصل کریں (get_youtube_token.py استعمال کریں)")
        print("3. GitHub Secrets میں شامل کریں:")
        print("   - YT_CLIENT_ID")
        print("   - YT_CLIENT_SECRET")
        print("   - YT_REFRESH_TOKEN")
        print("\n📖 مکمل guide: YOUTUBE_UPLOAD_SETUP.md دیکھیں")
        return None

    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"\n❌ Video file نہیں ملی: {video_path}")
        return None

    # Try to import required libraries
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        print(f"\n❌ Required libraries missing: {e}")
        print("یہ کمانڈ چلائیں: pip install google-auth-httplib2")
        return None

    # Create credentials
    try:
        creds = Credentials(
            token=None,
            refresh_token=YT_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        print("\n✅ Credentials object بنایا گیا")
    except Exception as e:
        print(f"\n❌ Credentials object میں error: {e}")
        return None

    # Try to upload
    try:
        print("🔗 YouTube API سے connect ہو رہے ہیں...")
        youtube = build("youtube", "v3", credentials=creds)
        
        print("📝 Video metadata تیار ہو رہی ہے...")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "comedy", "hindi", "AI animation"],
                "categoryId": "23",  # Entertainment
            },
            "status": {
                "privacyStatus": YT_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        }
        
        print("📤 Video file upload ہو رہی ہے...")
        print(f"   File size: {os.path.getsize(video_path) / (1024*1024):.1f}MB")
        
        media = MediaFileUpload(
            video_path, 
            chunksize=-1, 
            resumable=True, 
            mimetype="video/mp4"
        )
        
        request = youtube.videos().insert(
            part="snippet,status", 
            body=body, 
            media_body=media
        )
        
        response = None
        retry_count = 0
        while response is None:
            status, response = request.next_chunk()
            retry_count += 1
            if status:
                progress = int(status.progress() * 100)
                print(f"   Progress: {progress}% (chunk {retry_count})")
        
        video_id = response.get("id")
        
        if video_id:
            print("\n" + "="*70)
            print("✅ SUCCESS! Video YouTube پر upload ہوگیا!")
            print("="*70)
            print(f"🎬 Video ID: {video_id}")
            print(f"🔗 Link: https://youtube.com/shorts/{video_id}")
            print("="*70)
            return video_id
        else:
            print(f"\n❌ Response میں video ID نہیں ملی")
            print(f"Response: {response}")
            return None
            
    except Exception as e:
        print(f"\n❌ YouTube upload failed:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        
        # Common error solutions
        if "invalid_grant" in str(e):
            print("\n💡 شاید Refresh Token expired ہے")
            print("   حل: get_youtube_token.py دوبارہ چلائیں")
        elif "quotaExceeded" in str(e):
            print("\n💡 YouTube API quota ختم ہو گیا")
            print("   کل: 10,000 units/day")
        elif "authenticationFailed" in str(e):
            print("\n💡 Authentication fail ہوا")
            print("   حل: Credentials صحیح ہیں؟")
        
        return None


if __name__ == "__main__":
    try:
        print("="*70)
        print("🚀 Fully Automated AI Short Bot - Starting...")
        print("="*70)
        
        # ✅ Check environment variables
        print("\n✅ Checking configuration...")
        if not GEMINI_API_KEY:
            print("⚠️  Warning: GEMINI_API_KEY not set, using default story")
        
        if YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN:
            print("✅ YouTube credentials found - videos will be uploaded")
        else:
            print("⚠️  Warning: YouTube credentials incomplete - upload will be skipped")
        
        print("\n📝 Generating story script...")
        story = generate_story_script()
        scenes = story["scenes"]
        print(f"✅ Generated {len(scenes)} scenes")
        
        final_clips = []
        for idx, scene in enumerate(scenes):
            print(f"\n--- Processing Scene {idx + 1}/{len(scenes)} ---")
            try:
                media = generate_video_any_provider(scene["prompt"], idx)
                if media:
                    clip = assemble_scene(media["video"], media["face_image"], scene["script"], idx)
                    final_clips.append(clip)
                else:
                    print(f"⚠️  Scene {idx + 1}: No video generated")
            except Exception as e:
                print(f"❌ Scene {idx + 1} failed: {e}")
                continue

        if final_clips:
            try:
                print(f"\n🎬 Merging {len(final_clips)} clips...")
                final_video = merge_clips(final_clips)
                total_duration = get_media_duration(final_video)
                print(f"✅ Video merged successfully!")
            except Exception as e:
                print(f"\n❌ FAILED to merge clips: {e}")
                sys.exit(1)
            
            print(f"\n✅ SUCCESS: Short Ready: {final_video} (~{total_duration:.1f}s)")

            # ✅ FIXED: Use ASCII-safe title to avoid encoding issues
            yt_title = "Cute AI Cartoon Story - Hindi Comedy #Shorts"
            yt_description = "Mazedaar AI-generated cartoon kahani!\n\n" + "\n".join(s["script"] for s in scenes) + "\n\n#Shorts #Comedy #Hindi #AIAnimation #CartoonStory"
            
            print("\n📤 Attempting YouTube upload...")
            upload_to_youtube(final_video, yt_title, yt_description)
        else:
            print("\n❌ FAILED: No clips produced.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

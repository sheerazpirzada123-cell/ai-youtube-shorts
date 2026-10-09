import requests
import os
import random
import subprocess
import shutil
import time


# Clip IDs already used in this run - no same footage twice in one video
_USED_IDS = set()

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")


PEXELS_SEARCH_TERMS = [
    "person thinking",
    "woman phone",
    "man stressed",
    "friends talking cafe",
    "people walking street",
    "student studying",
    "couple talking",
    "person looking mirror",
    "woman smiling",
    "man thinking",
    "child playing",
    "office people",
]


# ============================================================
# POLLINATIONS AI - PRIMARY VISUAL SOURCE (Free, no API key)
# ============================================================
def _build_image_prompt(scene_narration, keyword, scene_index=0):
    """
    Scene ki narration se ek detailed, cinematic prompt banata hai.
    Generic keyword ki jagah poori line use karta hai taake image match kare.
    """
    narration = (scene_narration or "").strip()
    keyword = (keyword or "").strip()

    # Style hints - har scene ke liye alag mood
    styles = [
        "cinematic dramatic lighting, high contrast, dark background, 9:16 vertical",
        "moody atmospheric lighting, shallow depth of field, 9:16 vertical",
        "bright clean studio lighting, sharp focus, 9:16 vertical",
        "warm golden hour lighting, soft shadows, 9:16 vertical",
        "cool blue tones, mysterious atmosphere, 9:16 vertical",
        "high contrast black and white, dramatic shadows, 9:16 vertical",
    ]
    style = styles[scene_index % len(styles)]

    # Pehle narration, phir keyword - dono se relevant image
    if narration and keyword:
        base = f"{narration}, {keyword}"
    elif narration:
        base = narration
    else:
        base = keyword or "person thinking"

    # Abstract psychology concepts ko filmable banao
    base = base.replace("brain", "human brain neurons glowing")
    base = base.replace("mind", "human head silhouette with glowing particles")
    base = base.replace("memory", "old photographs and memories floating")
    base = base.replace("emotion", "human face with emotional expression")

    prompt = f"{base}, {style}, photorealistic, detailed, professional photography"

    # Prompt ko 400 chars tak limit karo (Pollinations ke liye)
    return prompt[:400]


def fetch_pollinations_image(narration, keyword, target_path, scene_index=0,
                              width=1080, height=1920, retries=3):
    """
    Pollinations AI se scene-specific image generate karta hai.
    Koi API key nahi chahiye. Bilkul free.
    """
    if not PEXELS_API_KEY and not PIXABAY_API_KEY:
        print("Warning: No stock API keys - Pollinations will be primary")

    prompt = _build_image_prompt(narration, keyword, scene_index)
    print(f"  Pollinations prompt: {prompt[:120]}...")

    encoded_prompt = requests.utils.quote(prompt)

    # Models: flux (best quality), turbo (fastest)
    models = ["flux", "turbo"]

    for attempt in range(1, retries + 1):
        model = models[(attempt - 1) % len(models)]

        img_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&nologo=true&model={model}"
            f"&seed={random.randint(1, 999999)}"
        )

        img_file = target_path + ".jpg"

        try:
            if os.path.exists(img_file):
                os.remove(img_file)

            response = requests.get(img_url, timeout=120)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if "image" not in content_type and "octet-stream" not in content_type:
                raise ValueError(f"Unexpected content type: {content_type}")

            with open(img_file, "wb") as f:
                f.write(response.content)

            if not os.path.exists(img_file) or os.path.getsize(img_file) < 5000:
                raise ValueError("Image too small or not created")

            # Verify it's a valid image
            from PIL import Image
            with Image.open(img_file) as im:
                im.verify()

            print(f"  Pollinations image OK ({os.path.getsize(img_file)} bytes, model={model})")
            return img_file

        except Exception as e:
            print(f"  Pollinations attempt {attempt}/{retries} failed: {e}")
            if os.path.exists(img_file):
                os.remove(img_file)
            time.sleep(2 * attempt)

    return None


def animate_image_with_motion(image_path, target_path, duration=5, scene_index=0):
    """
    Static image ko zoom + pan effect ke saath video banata hai.
    Har scene ke liye alag movement direction - boring nahi lagega.
    """
    if not os.path.exists(image_path):
        raise RuntimeError(f"Image not found: {image_path}")

    if os.path.exists(target_path):
        os.remove(target_path)

    fps = 30
    total_frames = int(duration * fps)

    # Har scene ke liye alag movement - zoom in, zoom out, pan left, pan right, diagonal
    movements = [
        # 0: Slow zoom in + slight pan right
        (
            f"zoompan=z='min(zoom+0.0012,1.25)':"
            f"x='iw/2-(iw/zoom/2)+on*0.3':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
        # 1: Zoom out from slight zoom
        (
            f"zoompan=z='if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0012))':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
        # 2: Pan left to right (fixed zoom)
        (
            f"zoompan=z='1.15':"
            f"x='(iw-iw/zoom)*(on/{total_frames})':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
        # 3: Pan right to left (fixed zoom)
        (
            f"zoompan=z='1.15':"
            f"x='(iw-iw/zoom)*(1-on/{total_frames})':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
        # 4: Slow zoom in + pan down (top to bottom)
        (
            f"zoompan=z='min(zoom+0.0010,1.2)':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='(ih-ih/zoom)*(on/{total_frames})':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
        # 5: Diagonal pan (zoom in + move up-left to down-right)
        (
            f"zoompan=z='min(zoom+0.0010,1.2)':"
            f"x='(iw-iw/zoom)*(on/{total_frames})':"
            f"y='(ih-ih/zoom)*(on/{total_frames})':"
            f"d={total_frames}:s=1080x1920:fps={fps}"
        ),
    ]

    movement = movements[scene_index % len(movements)]

    # Pehle image ko upscale karo (jitter se bachne ke liye), phir zoompan, phir downscale
    vf = (
        "scale=2160:3840:force_original_aspect_ratio=increase,"
        "crop=2160:3840,"
        f"{movement},"
        "scale=1080:1920"
    )

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        "-threads", "4",
        target_path,
    ]

    result = subprocess.run(command, capture_output=True, text=True, timeout=240)

    if result.returncode != 0:
        raise RuntimeError("Image animation FFmpeg failed:\n" + result.stderr[-1500:])

    if not validate_video(target_path):
        raise RuntimeError("Animated image video is invalid.")

    print(f"  Animated image ready: {target_path}")
    return target_path


def fetch_ai_scene_clip(narration, keyword, target_path, duration=5, scene_index=0):
    """
    Pollinations image + FFmpeg motion = video clip.
    Yeh PRIMARY visual source hai.
    """
    img_path = target_path + ".ai.jpg"

    try:
        img = fetch_pollinations_image(narration, keyword, target_path, scene_index)
        if not img:
            raise RuntimeError("Pollinations image generation failed")

        animate_image_with_motion(img, target_path, duration=duration, scene_index=scene_index)

        # Cleanup
        if os.path.exists(img_path):
            os.remove(img_path)

        return target_path

    except Exception as e:
        # Cleanup on failure
        for f in [img_path, target_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        raise


# ============================================================
# VALIDATION HELPERS
# ============================================================
def validate_video(video_path):
    if not os.path.exists(video_path):
        return False

    if os.path.getsize(video_path) < 50000:
        return False

    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height",
                "-of", "default=noprint_wrappers=1",
                video_path
            ],
            capture_output=True, text=True, timeout=30
        )

        if probe.returncode != 0:
            return False

        if not probe.stdout.strip():
            return False

        decode = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-i", video_path,
                "-frames:v", "1",
                "-f", "null", "-"
            ],
            capture_output=True, text=True, timeout=30
        )

        if decode.returncode != 0:
            return False

        return True

    except Exception:
        return False


def video_brightness(video_path, at=1.0):
    """Mean brightness 0-255 of one frame, or None if it cannot be measured."""
    frame = video_path + ".probe.jpg"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", video_path,
             "-frames:v", "1", "-vf", "scale=64:-2", frame],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 or not os.path.exists(frame):
            return None
        from PIL import Image, ImageStat
        with Image.open(frame) as im:
            return ImageStat.Stat(im.convert("L")).mean[0]
    except Exception:
        return None
    finally:
        if os.path.exists(frame):
            os.remove(frame)


# ============================================================
# STOCK VIDEO HELPERS (Fallback)
# ============================================================
def normalize_video(source_path, target_path):
    temp_output = target_path + ".normalized.mp4"

    if os.path.exists(temp_output):
        os.remove(temp_output)

    command = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-map", "0:v:0",
        "-an",
        "-vf", "scale='min(1080,iw)':-2",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-threads", "4",
        temp_output
    ]

    result = subprocess.run(command, capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        raise RuntimeError("FFmpeg video normalization failed:\n" + result.stderr[-1500:])

    if not validate_video(temp_output):
        if os.path.exists(temp_output):
            os.remove(temp_output)
        raise RuntimeError("Normalized video is still invalid.")

    if os.path.exists(target_path):
        os.remove(target_path)

    shutil.move(temp_output, target_path)
    return target_path


def download_file(url, target_path, extra_headers=None, asset_type="video"):
    temp_path = target_path + ".download"

    if os.path.exists(temp_path):
        os.remove(temp_path)

    print(f"Downloading asset: {target_path}...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
        "Accept": "*/*"
    }

    if extra_headers:
        headers.update(extra_headers)

    try:
        with requests.get(url, stream=True, headers=headers, timeout=(20, 180), allow_redirects=True) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()

            if asset_type == "video":
                if "video" not in content_type and "octet-stream" not in content_type:
                    raise ValueError(f"Unexpected video content type: {content_type}")
            elif asset_type == "audio":
                if "audio" not in content_type and "octet-stream" not in content_type and "mpeg" not in content_type and "ogg" not in content_type:
                    print(f"Warning: Unexpected audio content type: {content_type}")

            with open(temp_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)

        if not os.path.exists(temp_path):
            raise RuntimeError("Downloaded file was not created.")

        min_size = 2000 if asset_type == "audio" else 50000

        if os.path.getsize(temp_path) < min_size:
            raise ValueError(f"Downloaded file is too small ({os.path.getsize(temp_path)} bytes)")

        if asset_type == "video":
            if not validate_video(temp_path):
                raise ValueError("Downloaded MP4 is corrupt or cannot be decoded.")

        if os.path.exists(target_path):
            os.remove(target_path)

        shutil.move(temp_path, target_path)
        return target_path

    except Exception as error:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(target_path):
            os.remove(target_path)
        raise RuntimeError(f"Asset download failed ({target_path}): {error}") from error


def fetch_pexels_clip(keyword, target_path, min_duration=3, min_brightness=0, alt_keyword=""):
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY set nahi hai.")

    headers = {"Authorization": PEXELS_API_KEY}
    search_url = "https://api.pexels.com/videos/search"

    keyword_words = keyword.split()
    simplified_queries = []
    if len(keyword_words) > 2:
        simplified_queries.append(" ".join(keyword_words[:2]))
        simplified_queries.append(" ".join(keyword_words[-2:]))

    queries_to_try, seen_q = [], set()
    for q in [keyword, alt_keyword] + simplified_queries + random.sample(PEXELS_SEARCH_TERMS, k=4):
        q = (q or "").strip()
        if q and q.lower() not in seen_q:
            seen_q.add(q.lower())
            queries_to_try.append(q)

    for query in queries_to_try:
        print(f"Searching Pexels for '{query}'...")

        params = {
            "query": query,
            "orientation": "portrait",
            "per_page": 30
        }

        response = requests.get(search_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        videos = [
            video
            for video in data.get("videos", [])
            if video.get("duration", 0) >= min_duration
            and video.get("id") not in _USED_IDS
        ]

        if not videos:
            continue

        videos = videos[:4]
        if len(videos) > 1 and random.random() < 0.3:
            videos[0], videos[1] = videos[1], videos[0]

        for video in videos:
            files = [
                file
                for file in video.get("video_files", [])
                if file.get("file_type") == "video/mp4"
            ]

            if not files:
                continue

            files.sort(key=lambda file: abs((file.get("width", 1080) or 1080) - 1080))

            for file in files:
                raw_path = target_path + ".raw.mp4"

                try:
                    if os.path.exists(raw_path):
                        os.remove(raw_path)

                    download_file(file["link"], raw_path, asset_type="video")
                    normalize_video(raw_path, target_path)

                    if os.path.exists(raw_path):
                        os.remove(raw_path)

                    if min_brightness:
                        bright = video_brightness(target_path)
                        if bright is not None and bright < min_brightness:
                            os.remove(target_path)
                            raise ValueError(f"too dark ({bright:.0f} < {min_brightness})")

                    _USED_IDS.add(video.get("id"))
                    print(f"Valid Pexels clip ready: {target_path}")
                    return target_path

                except Exception as error:
                    print(f"Pexels clip failed, trying another clip: {error}")
                    if os.path.exists(raw_path):
                        os.remove(raw_path)
                    if os.path.exists(target_path):
                        os.remove(target_path)

    raise RuntimeError(f"No valid Pexels video found for '{keyword}'.")


def fetch_pixabay_clip(keyword, target_path, alt_keyword=""):
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    if not PIXABAY_API_KEY:
        raise RuntimeError("PIXABAY_API_KEY set nahi hai.")

    keyword_words = keyword.split()
    query_candidates = [keyword]
    if alt_keyword:
        query_candidates.append(alt_keyword)

    if len(keyword_words) > 2:
        query_candidates.append(" ".join(keyword_words[:2]))
        query_candidates.append(" ".join(keyword_words[-2:]))

    query_candidates += random.sample(PEXELS_SEARCH_TERMS, k=min(2, len(PEXELS_SEARCH_TERMS)))

    hits = []

    for query in query_candidates:
        url = (
            "https://pixabay.com/api/videos/"
            f"?key={PIXABAY_API_KEY}"
            f"&q={requests.utils.quote(query)}"
            "&per_page=20"
        )

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        hits = response.json().get("hits", [])

        if hits:
            break

    if not hits:
        raise RuntimeError(f"No Pixabay video found for '{keyword}'.")

    hits = [h for h in hits if h.get("id") not in _USED_IDS] or hits
    hits = hits[:4]
    last_error = None

    for hit in hits:
        try:
            videos = hit.get("videos", {})
            video_url = (
                videos.get("medium", {}).get("url")
                or videos.get("small", {}).get("url")
                or videos.get("large", {}).get("url")
            )

            if not video_url:
                continue

            raw_path = target_path + ".raw.mp4"
            download_file(video_url, raw_path, asset_type="video")
            normalize_video(raw_path, target_path)

            if os.path.exists(raw_path):
                os.remove(raw_path)

            _USED_IDS.add(hit.get("id"))
            return target_path

        except Exception as error:
            last_error = error
            raw_path = target_path + ".raw.mp4"
            if os.path.exists(raw_path):
                os.remove(raw_path)

    raise RuntimeError(f"All Pixabay clips failed for '{keyword}': {last_error}")


# ============================================================
# MAIN SCENE VIDEO FETCHER - AI FIRST, STOCK FALLBACK
# ============================================================
def fetch_scene_video(keyword, target_path, min_duration=3, min_brightness=0,
                       alt_keyword="", narration="", scene_index=0):
    """
    Priority:
      1. Pollinations AI image + motion (PRIMARY - free, match karta hai)
      2. Pexels stock video (fallback)
      3. Pixabay stock video (fallback)
      4. Pollinations simple fallback (last resort)
    """
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    errors = []

    # ---- 1. AI IMAGE + MOTION (PRIMARY) ----
    try:
        print(f"  [AI] Generating scene-specific visual...")
        return fetch_ai_scene_clip(
            narration=narration,
            keyword=keyword,
            target_path=target_path,
            duration=max(min_duration, 5),
            scene_index=scene_index,
        )
    except Exception as error:
        errors.append(f"AI image: {error}")
        print(f"  AI failed, trying stock footage...")
        if os.path.exists(target_path):
            os.remove(target_path)

    # ---- 2. PEXELS ----
    try:
        return fetch_pexels_clip(keyword, target_path, min_duration=min_duration,
                                 min_brightness=min_brightness, alt_keyword=alt_keyword)
    except Exception as error:
        errors.append(f"Pexels: {error}")
        if os.path.exists(target_path):
            os.remove(target_path)

    # ---- 3. PIXABAY ----
    try:
        return fetch_pixabay_clip(keyword, target_path, alt_keyword=alt_keyword)
    except Exception as error:
        errors.append(f"Pixabay: {error}")
        if os.path.exists(target_path):
            os.remove(target_path)

    # ---- 4. LAST RESORT: simple AI image ----
    try:
        return fetch_ai_scene_clip(
            narration=keyword,
            keyword=keyword,
            target_path=target_path,
            duration=max(min_duration, 5),
            scene_index=99,
        )
    except Exception as error:
        errors.append(f"AI fallback: {error}")

    raise RuntimeError(
        f"'{keyword}' ke liye koi valid visual nahi mil saka:\n" + "\n".join(errors)
    )


def fetch_scene_clips(scenes, scene_durations, output_dir="assets/scene_clips"):
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    for index, (scene, duration) in enumerate(zip(scenes, scene_durations)):
        target_path = os.path.join(output_dir, f"scene_{index}.mp4")

        keyword = (
            (scene.get("search_keyword") or scene.get("visual_keyword") or "").strip()
            or random.choice(PEXELS_SEARCH_TERMS)
        )

        narration = (scene.get("narration") or "").strip()
        alt_keyword = (scene.get("search_alt") or "").strip()

        print(f"\nFetching scene {index + 1}: {keyword}")
        if narration:
            print(f"  Narration: {narration[:80]}...")

        fetch_scene_video(
            keyword=keyword,
            target_path=target_path,
            min_duration=max(2, int(duration)),
            alt_keyword=alt_keyword,
            narration=narration,
            scene_index=index,
        )

        if not validate_video(target_path):
            raise RuntimeError(
                f"Scene {index + 1} video is invalid after all fallbacks: {target_path}"
            )

        paths.append(target_path)

    return paths

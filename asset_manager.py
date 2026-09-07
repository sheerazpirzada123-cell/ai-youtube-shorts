import requests
import os
import random
import subprocess

# Free Royalty-Free Assets Direct Links
BGM_URL = "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=suspense-scary-10332.mp3"
WHOOSH_SFX_URL = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c35f9923ed.mp3?filename=whoosh-6316.mp3"
POP_SFX_URL = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=pop-39222.mp3"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
PEXELS_SEARCH_TERMS = ["space", "abstract background", "nature", "ocean", "galaxy", "clouds timelapse"]

def download_file(url, target_path, extra_headers=None):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return

    print(f"Downloading asset: {target_path}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "*/*",
    }
    if extra_headers:
        headers.update(extra_headers)

    try:
        r = requests.get(url, stream=True, headers=headers, timeout=30)
        r.raise_for_status()  # non-200 (404/403 etc) par turant exception raise karega

        content_type = r.headers.get("Content-Type", "")
        if "audio" not in content_type and "video" not in content_type and "octet-stream" not in content_type:
            raise ValueError(
                f"Unexpected content-type '{content_type}' for {target_path}. "
                f"URL shayad expired/invalid hai: {url}"
            )

        with open(target_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # Download ke baad file size check - agar bohot chhoti hai to ye asli asset nahi
        if os.path.getsize(target_path) < 1024:
            os.remove(target_path)
            raise ValueError(f"Downloaded file for {target_path} bohot chhota/invalid hai. URL check karein: {url}")

    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)  # corrupt/partial file na chhode
        raise RuntimeError(f"Asset download fail hua ({target_path}): {e}") from e


def fetch_pexels_clip(keyword, target_path, min_duration=3):
    """
    Pexels API se diye gaye keyword ke hisaab se ek vertical (portrait) video dhoondh kar
    download karta hai. Agar keyword ka koi result na mile to generic fallback keywords try karta hai
    taake pipeline kabhi crash na ho.
    """
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return

    if not PEXELS_API_KEY:
        raise RuntimeError(
            "PEXELS_API_KEY set nahi hai. GitHub repo secret 'PEXELS_API_KEY' workflow ke env mein pass karein."
        )

    headers = {"Authorization": PEXELS_API_KEY}
    search_url = "https://api.pexels.com/videos/search"

    # Pehle asal keyword try karo, phir generic fallback keywords (agar koi result na mile)
    queries_to_try = [keyword] + random.sample(PEXELS_SEARCH_TERMS, k=min(2, len(PEXELS_SEARCH_TERMS)))

    for query in queries_to_try:
        print(f"Searching Pexels for '{query}'...")
        params = {"query": query, "orientation": "portrait", "per_page": 15}
        resp = requests.get(search_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Sirf itni lambi clips rakho jo scene ki duration cover kar sakein
        videos = [v for v in data.get("videos", []) if v.get("duration", 0) >= min_duration]
        if not videos:
            continue

        video = random.choice(videos)
        files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"]
        if not files:
            continue

        files.sort(key=lambda f: (f.get("width") or 0), reverse=True)
        suitable = [f for f in files if (f.get("width") or 0) <= 1080] or files
        chosen = suitable[0]

        download_file(chosen["link"], target_path)
        return

    raise RuntimeError(f"'{keyword}' (aur fallback keywords) ke liye koi suitable Pexels video nahi mila.")


def fetch_pixabay_clip(keyword, target_path):
    """Pexels fail ho jaye toh Pixabay se try karta hai (dusra free stock source)."""
    if not PIXABAY_API_KEY:
        raise RuntimeError("PIXABAY_API_KEY set nahi hai.")

    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(keyword)}&per_page=3"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    if not hits:
        raise RuntimeError(f"'{keyword}' ke liye Pixabay par koi video nahi mila.")

    vid_url = hits[0]["videos"]["medium"]["url"]
    download_file(vid_url, target_path)


def fetch_fallback_ai_clip(keyword, target_path, duration=6):
    """
    Pexels aur Pixabay dono fail ho jayein toh Pollinations se ek background image
    generate karke usse zoompan (slow zoom) wala video banata hai, taake pipeline
    kabhi bhi crash na ho aur hamesha koi na koi visual mil jaye.
    """
    img_prompt = requests.utils.quote(f"{keyword}, cinematic background, vertical 9:16")
    img_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1080&height=1920&nologo=true"
    img_file = target_path + ".jpg"

    res = requests.get(img_url, timeout=30)
    res.raise_for_status()
    with open(img_file, "wb") as f:
        f.write(res.content)

    zoom_cmd = [
        "ffmpeg", "-loop", "1", "-i", img_file,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
               "zoompan=z='min(zoom+0.0015,1.3)':d=150:s=1080x1920:fps=25",
        "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", target_path,
    ]
    subprocess.run(zoom_cmd, check=True, capture_output=True, text=True)
    os.remove(img_file)


def fetch_scene_video(keyword, target_path, min_duration=3):
    """
    Ek scene ke liye video clip laata hai, is priority order mein:
    Pexels -> Pixabay -> AI-generated background (zoompan image).
    Koi ek step fail ho toh agla try hota hai, sab fail ho tabhi exception uthta hai.
    """
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return

    errors = []
    try:
        fetch_pexels_clip(keyword, target_path, min_duration=min_duration)
        return
    except Exception as e:
        errors.append(f"Pexels: {e}")

    try:
        fetch_pixabay_clip(keyword, target_path)
        return
    except Exception as e:
        errors.append(f"Pixabay: {e}")

    try:
        fetch_fallback_ai_clip(keyword, target_path, duration=max(min_duration, 4))
        return
    except Exception as e:
        errors.append(f"AI fallback: {e}")

    raise RuntimeError(f"'{keyword}' ke liye koi bhi visual source kaam nahi kar saka: " + " | ".join(errors))


def fetch_scene_clips(scenes, scene_durations, output_dir="assets/scene_clips"):
    """
    Har scene ke visual_keyword ke hisaab se alag clip download karta hai.
    scene_durations = us scene ki voiceover duration (seconds), taake bohot chhoti clips skip ho jayein.
    Returns list of video file paths, same order as scenes.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for i, (scene, duration) in enumerate(zip(scenes, scene_durations)):
        target_path = os.path.join(output_dir, f"scene_{i}.mp4")
        keyword = scene.get("visual_keyword", "").strip() or random.choice(PEXELS_SEARCH_TERMS)
        fetch_scene_video(keyword, target_path, min_duration=max(2, int(duration)))
        paths.append(target_path)
    return paths


def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    # BGM aur Whoosh/Pop SFX filhaal disable hain (Pixabay links expire ho chuke - 403) - baad mein fix karenge
    # download_file(BGM_URL, "assets/bgm.mp3")
    # download_file(WHOOSH_SFX_URL, "assets/whoosh.mp3")
    # download_file(POP_SFX_URL, "assets/pop.mp3")
    # Background video ab scene-wise fetch_scene_clips() se aati hai (main.py dekhein)

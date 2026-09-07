import requests
import os
import random

# Free Royalty-Free Assets Direct Links
BGM_URL = "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=suspense-scary-10332.mp3"
WHOOSH_SFX_URL = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c35f9923ed.mp3?filename=whoosh-6316.mp3"
POP_SFX_URL = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=pop-39222.mp3"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
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


def fetch_scene_clips(scenes, scene_durations, output_dir="assets/scene_clips"):
    """
    Har scene ke visual_keyword ke hisaab se alag Pexels clip download karta hai.
    scene_durations = us scene ki voiceover duration (seconds), taake bohot chhoti clips skip ho jayein.
    Returns list of video file paths, same order as scenes.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for i, (scene, duration) in enumerate(zip(scenes, scene_durations)):
        target_path = os.path.join(output_dir, f"scene_{i}.mp4")
        keyword = scene.get("visual_keyword", "").strip() or random.choice(PEXELS_SEARCH_TERMS)
        fetch_pexels_clip(keyword, target_path, min_duration=max(2, int(duration)))
        paths.append(target_path)
    return paths


def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    # BGM aur Whoosh/Pop SFX filhaal disable hain (Pixabay links expire ho chuke - 403) - baad mein fix karenge
    # download_file(BGM_URL, "assets/bgm.mp3")
    # download_file(WHOOSH_SFX_URL, "assets/whoosh.mp3")
    # download_file(POP_SFX_URL, "assets/pop.mp3")
    # Background video ab scene-wise fetch_scene_clips() se aati hai (main.py dekhein)

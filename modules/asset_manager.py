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


def fetch_pexels_video(target_path="assets/bg_video.mp4"):
    """Pexels API se ek random vertical (portrait) background video dhoondh kar download karta hai."""
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return

    if not PEXELS_API_KEY:
        raise RuntimeError(
            "PEXELS_API_KEY set nahi hai. GitHub repo secret 'PEXELS_API_KEY' workflow ke env mein pass karein."
        )

    query = random.choice(PEXELS_SEARCH_TERMS)
    print(f"Searching Pexels for '{query}' background video...")

    search_url = "https://api.pexels.com/videos/search"
    params = {"query": query, "orientation": "portrait", "per_page": 10}
    headers = {"Authorization": PEXELS_API_KEY}

    resp = requests.get(search_url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    videos = data.get("videos", [])
    if not videos:
        raise RuntimeError(f"Pexels par '{query}' ke liye koi video nahi mila.")

    video = random.choice(videos)
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"]
    if not files:
        raise RuntimeError("Chuni gayi Pexels video mein koi mp4 file nahi mili.")

    # Sabse acha portrait/HD quality wala file chunein (bohot bada file avoid karne ke liye ~1080 width cap)
    files.sort(key=lambda f: (f.get("width") or 0), reverse=True)
    suitable = [f for f in files if (f.get("width") or 0) <= 1080] or files
    chosen = suitable[0]

    # Pexels ke video CDN links seedhe download hote hain, koi extra header ki zaroorat nahi
    download_file(chosen["link"], target_path)


def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    
    # BGM aur Whoosh/Pop SFX filhaal disable hain (Pixabay links expire ho chuke - 403) - baad mein fix karenge
    # download_file(BGM_URL, "assets/bgm.mp3")
    # download_file(WHOOSH_SFX_URL, "assets/whoosh.mp3")
    # download_file(POP_SFX_URL, "assets/pop.mp3")
    fetch_pexels_video("assets/bg_video.mp4")

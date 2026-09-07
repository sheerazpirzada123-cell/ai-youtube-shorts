import requests
import os

# Free Royalty-Free Assets Direct Links
BGM_URL = "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=suspense-scary-10332.mp3"
WHOOSH_SFX_URL = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c35f9923ed.mp3?filename=whoosh-6316.mp3"
POP_SFX_URL = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=pop-39222.mp3"
DEFAULT_BG_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-in-the-space-4065-large.mp4"

def download_file(url, target_path):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return

    print(f"Downloading asset: {target_path}...")
    headers = {"User-Agent": "Mozilla/5.0"}  # kuch CDNs bina User-Agent ke block/403 kar dete hain

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

def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    
    download_file(BGM_URL, "assets/bgm.mp3")
    download_file(WHOOSH_SFX_URL, "assets/whoosh.mp3")
    download_file(POP_SFX_URL, "assets/pop.mp3")
    download_file(DEFAULT_BG_VIDEO, "assets/bg_video.mp4")

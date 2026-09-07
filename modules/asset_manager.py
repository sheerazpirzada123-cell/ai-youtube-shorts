import requests
import os

# Free Royalty-Free Assets Direct Links
BGM_URL = "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=suspense-scary-10332.mp3"
WHOOSH_SFX_URL = "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c35f9923ed.mp3?filename=whoosh-6316.mp3"
POP_SFX_URL = "https://cdn.pixabay.com/download/audio/2021/08/04/audio_bb630cc098.mp3?filename=pop-39222.mp3"
DEFAULT_BG_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-in-the-space-4065-large.mp4"

def download_file(url, target_path):
    if not os.path.exists(target_path):
        print(f"Downloading asset: {target_path}...")
        r = requests.get(url, stream=True)
        with open(target_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    
    download_file(BGM_URL, "assets/bgm.mp3")
    download_file(WHOOSH_SFX_URL, "assets/whoosh.mp3")
    download_file(POP_SFX_URL, "assets/pop.mp3")
    download_file(DEFAULT_BG_VIDEO, "assets/bg_video.mp4")

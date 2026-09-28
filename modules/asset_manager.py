import requests
import os
import random
import subprocess
import shutil


# ============================================================
# RELIABLE SFX URLs (Mixkit - no API key needed)
# ============================================================
SFX_SOURCES = {
    "whoosh.mp3": "https://assets.mixkit.co/active_storage/sfx/2571/2571-preview.mp3",
    "whoosh2.mp3": "https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3",
    "pop.mp3": "https://assets.mixkit.co/active_storage/sfx/2358/2358-preview.mp3",
    "pop2.mp3": "https://assets.mixkit.co/active_storage/sfx/2354/2354-preview.mp3",
    "impact.mp3": "https://assets.mixkit.co/active_storage/sfx/2185/2185-preview.mp3",
    "swoosh.mp3": "https://assets.mixkit.co/active_storage/sfx/2569/2569-preview.mp3",
    "ding.mp3": "https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3",
}

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")


PEXELS_SEARCH_TERMS = [
    "space galaxy stars",
    "abstract background dark",
    "nature forest fog",
    "ocean waves storm",
    "underwater deep sea",
    "clouds timelapse dramatic",
    "mountains landscape aerial",
    "city street night",
    "night city lights",
    "crowd people walking",
    "technology computer code",
    "human brain animation",
    "human eye closeup",
    "hands closeup",
    "wildlife animals closeup",
    "fire flames dark",
    "rain window moody",
    "desert sand dunes",
    "sunset sky dramatic",
    "ancient ruins temple",
    "gold coins money",
    "clock time lapse",
    "books library dark",
    "science laboratory",
    "rocket space launch",
    "storm lightning thunder",
    "ice glacier arctic",
    "volcano eruption lava",
    "microscope science lab",
    "astronaut space suit",
]


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
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
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
        with requests.get(url, stream=True, headers=headers, timeout=(20, 180)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()

            if asset_type == "video":
                if "video" not in content_type and "octet-stream" not in content_type:
                    raise ValueError(f"Unexpected video content type: {content_type}")
            elif asset_type == "audio":
                if "audio" not in content_type and "octet-stream" not in content_type and "mpeg" not in content_type:
                    print(f"Warning: Unexpected audio content type: {content_type}")

            with open(temp_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)

        if not os.path.exists(temp_path):
            raise RuntimeError("Downloaded file was not created.")

        if os.path.getsize(temp_path) < 50000:
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


def fetch_pexels_clip(keyword, target_path, min_duration=3):
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY set nahi hai.")

    headers = {"Authorization": PEXELS_API_KEY}
    search_url = "https://api.pexels.com/videos/search"

    fallback_count = min(5, len(PEXELS_SEARCH_TERMS))

    keyword_words = keyword.split()
    simplified_queries = []

    if len(keyword_words) > 2:
        simplified_queries.append(" ".join(keyword_words[-2:]))
        simplified_queries.append(" ".join(keyword_words[:2]))

    queries_to_try = (
        [keyword]
        + simplified_queries
        + random.sample(PEXELS_SEARCH_TERMS, k=fallback_count)
    )

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
        ]

        if not videos:
            continue

        random.shuffle(videos)

        for video in videos:
            files = [
                file
                for file in video.get("video_files", [])
                if file.get("file_type") == "video/mp4"
            ]

            if not files:
                continue

            files.sort(key=lambda file: abs((file.get("width", 720) or 720) - 720))

            for file in files:
                raw_path = target_path + ".raw.mp4"

                try:
                    if os.path.exists(raw_path):
                        os.remove(raw_path)

                    download_file(file["link"], raw_path, asset_type="video")
                    normalize_video(raw_path, target_path)

                    if os.path.exists(raw_path):
                        os.remove(raw_path)

                    print(f"Valid Pexels clip ready: {target_path}")
                    return target_path

                except Exception as error:
                    print(f"Pexels clip failed, trying another clip: {error}")
                    if os.path.exists(raw_path):
                        os.remove(raw_path)
                    if os.path.exists(target_path):
                        os.remove(target_path)

    raise RuntimeError(f"No valid Pexels video found for '{keyword}'.")


def fetch_pixabay_clip(keyword, target_path):
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    if not PIXABAY_API_KEY:
        raise RuntimeError("PIXABAY_API_KEY set nahi hai.")

    keyword_words = keyword.split()
    query_candidates = [keyword]

    if len(keyword_words) > 2:
        query_candidates.append(" ".join(keyword_words[-2:]))
        query_candidates.append(" ".join(keyword_words[:2]))

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

    random.shuffle(hits)
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

            return target_path

        except Exception as error:
            last_error = error
            raw_path = target_path + ".raw.mp4"
            if os.path.exists(raw_path):
                os.remove(raw_path)

    raise RuntimeError(f"All Pixabay clips failed for '{keyword}': {last_error}")


def fetch_fallback_ai_clip(keyword, target_path, duration=6):
    if os.path.exists(target_path):
        os.remove(target_path)

    img_prompt = requests.utils.quote(f"{keyword}, cinematic background, vertical 9:16")
    img_url = (
        "https://image.pollinations.ai/prompt/"
        f"{img_prompt}"
        "?width=1080"
        "&height=1920"
        "&nologo=true"
    )

    img_file = target_path + ".jpg"
    response = requests.get(img_url, timeout=90)
    response.raise_for_status()

    with open(img_file, "wb") as file:
        file.write(response.content)

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", img_file,
        "-vf",
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "zoompan="
        "z='min(zoom+0.0008,1.15)':"
        "d=150:"
        "s=1080x1920:"
        "fps=30",
        "-t", str(max(duration, 5)),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        target_path
    ]

    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=180)

    if os.path.exists(img_file):
        os.remove(img_file)

    if result.returncode != 0:
        raise RuntimeError("AI fallback FFmpeg failed:\n" + result.stderr[-1500:])

    if not validate_video(target_path):
        raise RuntimeError("AI fallback generated an invalid video.")

    return target_path


def fetch_scene_video(keyword, target_path, min_duration=3):
    if validate_video(target_path):
        return target_path

    if os.path.exists(target_path):
        os.remove(target_path)

    errors = []

    try:
        return fetch_pexels_clip(keyword, target_path, min_duration=min_duration)
    except Exception as error:
        errors.append(f"Pexels: {error}")
        if os.path.exists(target_path):
            os.remove(target_path)

    try:
        return fetch_pixabay_clip(keyword, target_path)
    except Exception as error:
        errors.append(f"Pixabay: {error}")
        if os.path.exists(target_path):
            os.remove(target_path)

    try:
        return fetch_fallback_ai_clip(keyword, target_path, duration=max(min_duration, 4))
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
            scene.get("visual_keyword", "").strip()
            or random.choice(PEXELS_SEARCH_TERMS)
        )

        print(f"\nFetching scene {index + 1}: {keyword}")

        fetch_scene_video(keyword, target_path, min_duration=max(2, int(duration)))

        if not validate_video(target_path):
            raise RuntimeError(
                f"Scene {index + 1} video is invalid after all fallbacks: {target_path}"
            )

        paths.append(target_path)

    return paths


def prepare_background_audio(sfx_folder="assets/sfx"):
    os.makedirs(sfx_folder, exist_ok=True)

    # Purane failed (0-byte) files delete karo
    for f in os.listdir(sfx_folder):
        full_path = os.path.join(sfx_folder, f)
        try:
            if os.path.isfile(full_path) and os.path.getsize(full_path) < 1000:
                os.remove(full_path)
                print(f"Deleted failed SFX: {f}")
        except Exception:
            pass

    downloaded = 0
    for filename, url in SFX_SOURCES.items():
        target = os.path.join(sfx_folder, filename)
        if os.path.exists(target) and os.path.getsize(target) > 1000:
            print(f"SFX already exists: {filename}")
            downloaded += 1
            continue
        try:
            print(f"Downloading SFX: {filename}")
            download_file(url, target, asset_type="audio")
            downloaded += 1
            print(f"  {filename} downloaded")
        except Exception as e:
            print(f"  SFX '{filename}' skipped: {e}")

    print(f"Total SFX ready: {downloaded}/{len(SFX_SOURCES)}")


def prepare_all_assets():
    os.makedirs("assets", exist_ok=True)
    prepare_background_audio()

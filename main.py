import os
import sys

from modules import brain, audio, asset_manager, composer, youtube_uploader

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- YouTube auto-upload (free, YouTube Data API v3) --------------------
# NOTE: these names must match the secrets injected in .github/workflows/run.yml
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YT_PRIVACY_STATUS = os.getenv("YT_PRIVACY_STATUS", "public")
# Extra safety switch: even if all 3 credentials above are present, upload only
# runs when this is explicitly set to "true" (repo Variable). Defaults to false
# so you can test the pipeline without accidentally publishing to your channel.
YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").strip().lower() == "true"

FINAL_OUTPUT = "final_short.mp4"

DEFAULT_STORY = {
    "title": "Mind Blowing Facts 🤯 #Shorts",
    "description": "Kuch aisay hairat-angez facts jo aapko chaunka denge!\n\n"
                    "#Shorts #Facts #HindiFacts #Viral #Trending #AmazingFacts",
    "tags": ["shorts", "facts", "hindi facts", "amazing facts", "viral shorts", "did you know"],
    "scenes": [
        {"visual_keyword": "galaxy space stars",
         "narration": "Kya aapko pata hai, hamari galaxy mein taron ki sankhya samandar ki reti ke kano se bhi zyada hai!"},
        {"visual_keyword": "deep ocean waves",
         "narration": "Duniya ka sabse gehra hissa itna andhera hai ke wahan rooh kaanp jaye!"},
    ],
}


def get_story():
    """Gemini se ('Facts Mine' style) fact script generate karta hai. Agar API key
    missing ho ya Gemini call fail ho jaye, to ek chhota default script use karta hai
    taake pipeline kabhi crash na ho."""
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY set nahi hai, default script use kar rahe hain.")
        return DEFAULT_STORY

    try:
        print("Generating Facts Mine style script via Gemini...")
        return brain.generate_fact_script(GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini script generation failed ({e}), default script use kar rahe hain.")
        return DEFAULT_STORY


def build_video(story):
    scenes_raw = story["scenes"]
    scenes = []
    audio_paths = []
    durations = []
    word_timings = []

    for i, scene in enumerate(scenes_raw):
        narration = (scene.get("narration") or "").strip()
        if not narration:
            print(f"\n--- Scene {i + 1}/{len(scenes_raw)}: skipped (Gemini ne is scene ke liye 'narration' nahi diya) ---")
            continue

        print(f"\n--- Scene {i + 1}/{len(scenes_raw)}: generating voiceover ---")
        try:
            audio_path = f"assets/audio_{i}.mp3"
            audio.generate_voiceover(narration, output_path=audio_path)

            from moviepy.editor import AudioFileClip
            clip = AudioFileClip(audio_path)
            duration = clip.duration
            clip.close()

            scenes.append(scene)
            audio_paths.append(audio_path)
            durations.append(duration)
            word_timings.append(audio.estimate_word_timings(narration, duration))
        except Exception as e:
            print(f"Scene {i + 1} failed, skipping: {e}")

    if not scenes:
        raise RuntimeError("Koi bhi scene successfully process nahi ho saka.")

    print("\n--- Fetching scene video clips (Pexels -> Pixabay -> AI fallback) ---")
    video_paths = asset_manager.fetch_scene_clips(scenes, durations)

    print("\n--- Composing final video with captions ---")
    composer.render_short_video(
        scenes, video_paths, audio_paths,
        scene_word_timings=word_timings,
        output_file=FINAL_OUTPUT,
    )
    return FINAL_OUTPUT


def upload(video_path, story):
    if not YOUTUBE_UPLOAD_ENABLED:
        print("YOUTUBE_UPLOAD_ENABLED is not 'true', skipping upload.")
        return None

    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        print("YouTube credentials missing, skipping upload.")
        return None

    try:
        return youtube_uploader.upload_video(
            video_path,
            title=story.get("title", "Amazing Facts 🤯 #Shorts")[:100],
            description=story.get("description", "")[:5000],
            tags=story.get("tags") or ["shorts", "facts"],
            privacy_status=YT_PRIVACY_STATUS,
        )
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None


if __name__ == "__main__":
    print("=== Facts Mine Style Short Bot Started ===")
    story = get_story()

    try:
        final_video = build_video(story)
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)

    print(f"\nSUCCESS: Short Ready: {final_video}")
    upload(final_video, story)

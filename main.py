import os
from moviepy.editor import AudioFileClip
from modules.brain import generate_fact_script
from modules.audio import generate_scene_audios
from modules.asset_manager import fetch_scene_clips
from modules.composer import render_short_video
from modules.youtube_uploader import YouTubeUploader

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")  # Environment variable / GitHub secret se read hoga

def main():
    print("1. Generating Scene-by-Scene Hindi Fact Script...")
    script_data = generate_fact_script(GEMINI_API_KEY)
    scenes = script_data["scenes"]
    print(f"Title: {script_data['title']}")
    print(f"Scenes: {len(scenes)}")

    print("2. Generating Voiceover for each Scene...")
    scene_audio_paths = generate_scene_audios(scenes)
    scene_durations = [AudioFileClip(p).duration for p in scene_audio_paths]

    print("3. Fetching matching Pexels clip for each Scene...")
    scene_video_paths = fetch_scene_clips(scenes, scene_durations)

    print("4. Rendering Final Short Video (synced clips + captions)...")
    render_short_video(scenes, scene_video_paths, scene_audio_paths, "output_short.mp4")
    print("Success! Your Short video is ready: output_short.mp4")

    print("5. Uploading to YouTube...")
    uploader = YouTubeUploader()
    uploader.upload_video(
        file_path="output_short.mp4",
        title=script_data["title"],
        description=script_data["description"],
        tags=script_data.get("tags", []),
        privacy_status="public",
    )
    print("All done!")

if __name__ == "__main__":
    main()

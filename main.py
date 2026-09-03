import asyncio
import os
import shutil
from dotenv import load_dotenv

# NOTE: These imports assume brain.py, asset_manager.py, audio.py, and
# composer.py all live inside a `modules/` folder (with an __init__.py in
# it) next to this file. If your repo currently has brain.py at the project
# root, move it into modules/brain.py — otherwise this import will fail
# with "ModuleNotFoundError: No module named 'modules'".
from modules.brain import ContentBrain
from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.composer import Composer

# Load environment variables from .env file (for local testing)
load_dotenv()

PROJECT_ROOT = os.getcwd()
ASSETS_ROOT = os.path.join(PROJECT_ROOT, "assets")


def clean_cache():
    """
    Safely deletes temporary files.
    Includes a Safety Lock to prevent deleting anything outside the project.
    """
    print("🧹 Cleaning up temporary files...")

    folders_to_clean = [
        os.path.join(ASSETS_ROOT, "audio_clips"),
        os.path.join(ASSETS_ROOT, "video_clips"),
        os.path.join(ASSETS_ROOT, "temp"),
    ]

    for folder in folders_to_clean:
        folder = os.path.abspath(folder)

        # SAFETY CHECK 1: Ensure folder actually exists
        if not os.path.exists(folder):
            continue

        # SAFETY CHECK 2: Folder must be a real subdirectory of our
        # project's assets/ directory (not just contain the word "assets"
        # somewhere in the path, which the old string check allowed).
        if os.path.commonpath([folder, ASSETS_ROOT]) != ASSETS_ROOT:
            print(f"    🚨 SECURITY ALERT: Skipping {folder} because it looks unsafe!")
            continue

        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    print(f"      Deleted: {filename}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"    ❌ Failed to delete {file_path}. Reason: {e}")

    print("✨ Workspace clean!")


async def main():
    print("🚀 STARTING AUTOMATION...")

    # 1. BRAIN: Get Script
    brain = ContentBrain()
    try:
        topic = brain.get_trending_topic()
        script = brain.generate_script(topic)
    except Exception as e:
        print(f"❌ Brain Error: {e}")
        return

    if not script:
        print("❌ Script generation failed.")
        return

    # 2. AUDIO: Generate Voice
    audio_engine = AudioEngine()
    try:
        script = await audio_engine.process_script(script)
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return

    # 3. ASSETS: Get Stock Video
    asset_manager = AssetManager()
    try:
        assets_map = asset_manager.get_videos(script)
    except Exception as e:
        print(f"❌ Asset Error: {e}")
        return

    # 4. COMPOSER: Merge Video + Audio
    composer = Composer()

    try:
        final_scene_paths = composer.render_all_scenes(script, assets_map)
    except Exception as e:
        print(f"❌ Composer Error: {e}")
        return

    # 5. STITCH WITH TRANSITIONS
    if final_scene_paths:
        composer.concatenate_with_transitions(final_scene_paths)
        clean_cache()
    else:
        print("❌ Failed to generate any scenes.")


if __name__ == "__main__":
    asyncio.run(main())

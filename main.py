import os
from modules.brain import generate_fact_script
from modules.audio import generate_hindi_audio
from modules.asset_manager import prepare_all_assets
from modules.composer import render_short_video

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")  # Environment variable / GitHub secret se read hoga

def main():
    print("1. Downloading/Checking BGM, SFX & Background Video...")
    prepare_all_assets()
    
    print("2. Generating Random Hindi Fact Script...")
    script_data = generate_fact_script(GEMINI_API_KEY)
    print(f"Title: {script_data['title']}")
    
    print("3. Generating Voiceover...")
    generate_hindi_audio(script_data['script'])
    
    print("4. Rendering Final Short Video (Audio + Music + Sound Effects)...")
    render_short_video("output_short.mp4")
    
    print("Success! Your Short video is ready: output_short.mp4")

if __name__ == "__main__":
    main()

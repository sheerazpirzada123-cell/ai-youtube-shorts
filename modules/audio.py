import os
import asyncio
import edge_tts
from mutagen.mp3 import MP3

class AudioEngine:
    def __init__(self, voice="hi-IN-MadhurNeural"):
        # "hi-IN-MadhurNeural" is an energetic Hindi male voice.
        # Alternative Hindi male options: "hi-IN-NiranjanNeural"
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, text, output_filename, retries=3):
        """
        Generates realistic male Hindi voiceover with slight pace and depth adjustment.
        """
        output_path = os.path.join(self.output_dir, output_filename)
        
        for attempt in range(retries):
            try:
                # rate="+8%" for snappy short pacing, pitch="-2Hz" for a deeper, authoritative narrator tone
                communicate = edge_tts.Communicate(
                    text, 
                    self.voice, 
                    rate="+8%", 
                    pitch="-2Hz"
                )
                await communicate.save(output_path)
                return output_path
            
            except Exception as e:
                print(f"      ⚠️ Audio Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    print("      ❌ Failed to generate audio after max retries.")
                    raise e

    def get_audio_duration(self, file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            print(f"❌ Error reading audio length: {e}")
            return 0.0

    async def process_script(self, script_data):
        print(f"🎙️ Generating Hindi Male Voiceovers for {len(script_data)} MCU scenes...")
        
        for scene in script_data:
            scene_id = scene['id']
            text = scene['text']
            filename = f"voice_{scene_id}.mp3"
            
            try:
                file_path = await self.generate_audio(text, filename)
                duration = self.get_audio_duration(file_path)
                
                scene['audio_path'] = file_path
                scene['duration'] = duration
                
                print(f"   ✅ Scene {scene_id} [Audio Ready]: {duration:.2f}s")
                await asyncio.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Skipping Scene {scene_id} due to audio error.")
                continue
            
        return script_data

import asyncio
import os
import edge_tts

async def create_voiceover(text, output_file="voice.mp3"):
    # Energetic Male Hindi Voice
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_file)

def generate_hindi_audio(script_text, output_file="voice.mp3"):
    asyncio.run(create_voiceover(script_text, output_file))

def generate_scene_audios(scenes, output_dir="scene_audio"):
    """
    Har scene ke liye alag voiceover MP3 banata hai (scene_0.mp3, scene_1.mp3, ...).
    Isse har scene ki exact duration pata chal jati hai, jo video clips ko
    sync karne ke liye zaroori hai. Returns list of file paths in scene order.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for i, scene in enumerate(scenes):
        path = os.path.join(output_dir, f"scene_{i}.mp3")
        asyncio.run(create_voiceover(scene["narration"], path))
        paths.append(path)
    return paths

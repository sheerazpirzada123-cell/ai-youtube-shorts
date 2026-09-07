import asyncio
import edge_tts

async def create_voiceover(text, output_file="voice.mp3"):
    # Energetic Male Hindi Voice
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_file)

def generate_hindi_audio(script_text):
    asyncio.run(create_voiceover(script_text))

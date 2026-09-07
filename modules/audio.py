import os
import asyncio
import edge_tts
from gtts import gTTS
from moviepy.editor import AudioFileClip, CompositeAudioClip

async def generate_tts_async(text, output_path):
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)

def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    """
    Generates voiceover using edge-tts with a robust fallback to gTTS 
    if Microsoft's servers block or fail to return audio in GitHub Actions.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    clean_text = " ".join(text.split())
    
    # Try edge-tts first
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(generate_tts_async(clean_text, output_path), loop)
        else:
            asyncio.run(generate_tts_async(clean_text, output_path))
        
        # Verify if file was successfully created and is valid
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            print("✅ Voiceover generated successfully using edge-tts.")
            return output_path
    except Exception as e:
        print(f"⚠️ edge-tts warning: {e}. Switching to gTTS fallback...")

    # Fallback to gTTS if edge-tts fails
    try:
        tts = gTTS(text=clean_text, lang="en", slow=False)
        tts.save(output_path)
        print("✅ Voiceover generated successfully using gTTS fallback.")
        return output_path
    except Exception as e:
        raise Exception(f"❌ Both edge-tts and gTTS failed to generate audio: {e}")

def estimate_word_timings(text, duration):
    """
    Total voiceover duration ko har word ke character-count ke hisaab se 
    approximate hisse mein baant deta hai taake captions sync rahein.
    """
    words = [w for w in text.split() if w.strip()]
    if not words or duration <= 0:
        return []

    weights = [max(len(w), 1) for w in words]
    total_weight = sum(weights)

    timings = []
    t = 0.0
    for word, weight in zip(words, weights):
        seg_duration = duration * (weight / total_weight)
        timings.append({"text": word, "start": t})
        t += seg_duration
    return timings

def add_background_music_and_sfx(voiceover_path, output_path="assets/final_audio.mp3", bg_music_path="assets/audio/bg_music.mp3", bg_volume=0.15):
    """
    Voiceover ke sath background music mix karne ka function (with proper ducking).
    """
    try:
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover file not found at {voiceover_path}")
            
        voiceover = AudioFileClip(voiceover_path)
        audio_clips = [voiceover]
        
        if os.path.exists(bg_music_path) and os.path.getsize(bg_music_path) > 0:
            bg_music = AudioFileClip(bg_music_path).volumex(bg_volume)
            
            if bg_music.duration < voiceover.duration:
                bg_music = bg_music.loop(duration=voiceover.duration)
            else:
                bg_music = bg_music.subclip(0, voiceover.duration)
                
            audio_clips.append(bg_music)
        else:
            print(f"⚠️ Background music file is missing or empty. Proceeding with voiceover only.")
        
        final_audio = CompositeAudioClip(audio_clips)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_audio.write_audiofile(output_path, fps=44100, logger=None)
        print(f"Successfully created mixed audio at {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"Error in adding background music: {e}")
        return voiceover_path

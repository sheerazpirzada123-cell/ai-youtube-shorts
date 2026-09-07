import os
import asyncio
import edge_tts
from moviepy.editor import AudioFileClip, CompositeAudioClip

async def generate_tts_async(text, output_path="assets/voiceover.mp3"):
    # Energetic and human-like male voice (Christopher)
    voice = "en-US-ChristopherNeural" 
    
    # rate="+10%" se voice thori fast aur energetic ho jaye gi
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)

def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    """
    Generates human-like energetic male voiceover using edge-tts.
    Clean text ensures minimum gaps between sentences.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    clean_text = " ".join(text.split())
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(generate_tts_async(clean_text, output_path), loop)
        else:
            asyncio.run(generate_tts_async(clean_text, output_path))
    except RuntimeError:
        asyncio.run(generate_tts_async(clean_text, output_path))
    
    return output_path

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
        
        if os.path.exists(bg_music_path):
            bg_music = AudioFileClip(bg_music_path).volumex(bg_volume)
            
            if bg_music.duration < voiceover.duration:
                bg_music = bg_music.loop(duration=voiceover.duration)
            else:
                bg_music = bg_music.subclip(0, voiceover.duration)
                
            audio_clips.append(bg_music)
        else:
            print(f"Warning: Background music not found at {bg_music_path}. Proceeding with voiceover only.")
        
        final_audio = CompositeAudioClip(audio_clips)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_audio.write_audiofile(output_path, fps=44100)
        print(f"Successfully created mixed audio at {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"Error in adding background music: {e}")
        return voiceover_path

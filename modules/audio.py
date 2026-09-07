import os
from moviepy.editor import AudioFileClip, CompositeAudioClip
import requests
from gtts import gTTS

# ElevenLabs keys fallback list (optional - script works fine on gTTS alone)
ELEVEN_KEYS = [
    os.getenv("ELEVEN_KEY_1", ""),
    os.getenv("ELEVEN_KEY_2", ""),
    os.getenv("ELEVEN_KEY_3", ""),
]
ELEVEN_KEYS = [k for k in ELEVEN_KEYS if k.strip()]


def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    """
    Scene ke Hindi narration text ko voiceover audio file mein convert karta hai.
    Pehle ElevenLabs try karta hai (agar ELEVEN_KEY_1/2/3 secrets set hon - behtar,
    natural awaz), warna gTTS par fallback karta hai (free, hamesha available).
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    for key in ELEVEN_KEYS:
        try:
            url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            headers = {"xi-api-key": key, "Content-Type": "application/json"}
            payload = {
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.35, "similarity_boost": 0.85},
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200 and res.content:
                with open(output_path, "wb") as f:
                    f.write(res.content)
                return output_path
        except Exception as e:
            print(f"ElevenLabs voiceover failed, trying next option: {e}")

    tts = gTTS(text=text, lang="hi", slow=False)
    tts.save(output_path)
    return output_path


def estimate_word_timings(text, duration):
    """
    Hamare paas asli forced-alignment (word-level timestamps) nahi hai, isliye ye
    function total voiceover duration ko har word ke (character-count ke hisaab se
    weighted) approximate hisse mein baant deta hai - taake composer.py TikTok-style
    word-by-word captions dikha sake. Bilkul frame-perfect nahi hoga lekin dikhne mein
    kaafi close lagta hai.
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
    Voiceover ke sath background music mix karne ka function.
    bg_volume = 0.15 rakha hai taake music halka chale aur bolne ki awaz saaf sunai de.
    """
    try:
        # 1. Voiceover load karein
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover file not found at {voiceover_path}")
            
        voiceover = AudioFileClip(voiceover_path)
        audio_clips = [voiceover]
        
        # 2. Background music load karein agar exist karti hai
        if os.path.exists(bg_music_path):
            bg_music = AudioFileClip(bg_music_path).volumex(bg_volume)
            
            # Agar music chota hai toh loop karein, warna video ki length tak trim karein
            if bg_music.duration < voiceover.duration:
                bg_music = bg_music.loop(duration=voiceover.duration)
            else:
                bg_music = bg_music.subclip(0, voiceover.duration)
                
            audio_clips.append(bg_music)
        else:
            print(f"Warning: Background music not found at {bg_music_path}. Proceeding with voiceover only.")
        
        # 3. Audio clips ko combine karein
        final_audio = CompositeAudioClip(audio_clips)
        
        # 4. Export karein
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_audio.write_audiofile(output_path, fps=44100)
        print(f"Successfully created mixed audio at {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"Error in adding background music: {e}")
        return voiceover_path

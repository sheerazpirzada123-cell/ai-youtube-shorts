import os
import asyncio
import subprocess
import edge_tts
from gtts import gTTS
from moviepy.editor import (
    AudioFileClip,
    AudioClip,
    CompositeAudioClip,
    concatenate_audioclips,
)

INTER_SCENE_PAUSE = 0.08  # Thoda sa gap — natural lagti hai

VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = "+8%"        # +14% se +8% — words saaf sunai denge
VOICE_PITCH = "-1Hz"

# -30dB se -40dB — sirf bilkul khamosh portions trim honge, words nahi katenge
SILENCE_TRIM_DB = "-40dB"
SILENCE_MIN_START = 0.2   # 0.1 se 0.2 — words ko safe rakhega


async def generate_tts_async(text, output_path):
    communicate = edge_tts.Communicate(
        text=text, voice=VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH
    )
    await communicate.save(output_path)


def _trim_silence(path):
    trimmed_path = path + ".trimmed.mp3"
    command = [
        "ffmpeg", "-y", "-i", path,
        "-af",
        f"silenceremove=start_periods=1:start_threshold={SILENCE_TRIM_DB}:"
        f"start_silence={SILENCE_MIN_START},"
        f"areverse,"
        f"silenceremove=start_periods=1:start_threshold={SILENCE_TRIM_DB}:"
        f"start_silence={SILENCE_MIN_START},"
        f"areverse",
        "-ar", "44100",
        trimmed_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(trimmed_path) and os.path.getsize(trimmed_path) > 500:
            os.replace(trimmed_path, path)
        else:
            if os.path.exists(trimmed_path):
                os.remove(trimmed_path)
    except Exception as e:
        print(f"Silence trim skipped for {path}: {e}")
        if os.path.exists(trimmed_path):
            os.remove(trimmed_path)


# Baaki functions same as before...
def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    clean_text = " ".join(text.split())
    if not clean_text:
        raise ValueError("Voiceover ke liye text empty hai.")

    try:
        asyncio.run(generate_tts_async(clean_text, output_path))
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            _trim_silence(output_path)
            print(f"Voiceover generated using {VOICE}")
            return output_path
        raise Exception("Edge TTS ne valid audio file generate nahi ki.")
    except Exception as e:
        print(f"Edge TTS failed: {e}. Switching to gTTS...")

    try:
        tts = gTTS(text=clean_text, lang="hi", slow=False)
        tts.save(output_path)
        _trim_silence(output_path)
        print("Voiceover generated using gTTS fallback.")
        return output_path
    except Exception as e:
        raise Exception(f"Both Edge TTS and gTTS failed: {e}")


def concatenate_voiceovers(audio_paths, output_path="assets/voiceover_full.mp3"):
    if not audio_paths:
        raise ValueError("concatenate_voiceovers: audio_paths empty hai.")
    if len(audio_paths) == 1:
        return audio_paths[0]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    clips = [AudioFileClip(p) for p in audio_paths]
    silence = AudioClip(lambda t: 0, duration=INTER_SCENE_PAUSE, fps=44100)
    padded = []
    for i, clip in enumerate(clips):
        padded.append(clip)
        if i < len(clips) - 1:
            padded.append(silence)
    try:
        final = concatenate_audioclips(padded)
        final.write_audiofile(output_path, fps=44100, logger=None)
    finally:
        for clip in clips:
            clip.close()
    return output_path


def add_background_music_and_sfx(voiceover_path, output_path="assets/final_audio.mp3",
                                  bg_music_path="assets/audio/bg_music.mp3", bg_volume=0.20):
    """bg_volume 0.10 se 0.20 kiya — ab sunai dega."""
    try:
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover not found: {voiceover_path}")
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
            print("Background music missing. Using voice only.")
        final_audio = CompositeAudioClip(audio_clips)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        final_audio.write_audiofile(output_path, fps=44100, logger=None)
        print(f"Final audio created: {output_path}")
        return output_path
    except Exception as e:
        print(f"Audio mixing error: {e}")
        return voiceover_path

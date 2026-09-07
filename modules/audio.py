import asyncio
import os
import edge_tts
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

# Edge-TTS ke WordBoundary events mein "offset"/"duration" 100-nanosecond ticks mein
# aate hain (Azure/.NET convention) - seconds mein convert karne ke liye divide karo.
_TICKS_PER_SECOND = 10_000_000
_SILENCE_THRESH_DB = -45  # isse quiet audio ko "silence" maana jata hai trimming ke liye

VOICE = "hi-IN-MadhurNeural"
RATE = "+25%"
PITCH = "+15Hz"


async def _synthesize_with_boundaries(text, output_file, voice=VOICE, rate=RATE, pitch=PITCH):
    """
    Edge-TTS ko STREAM mode mein call karta hai (sirf .save() ki jagah) taake audio ke
    saath saath har WORD ka exact start/end time (WordBoundary events) bhi mil jaye -
    ye word-by-word captions banane ke liye zaroori hai.

    Returns: list of {"text": str, "start": float, "end": float} seconds mein,
    is untrimmed audio file ke shuru se relative.
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words = []
    with open(output_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / _TICKS_PER_SECOND
                duration = chunk["duration"] / _TICKS_PER_SECOND
                words.append({
                    "text": chunk["text"],
                    "start": start,
                    "end": start + duration,
                })
    return words


def _trim_silence_and_shift_words(mp3_path, words):
    """
    Har scene ki mp3 ke shuru/aakhir mein Edge-TTS thoda silence chhod deta hai - isi
    silence ki wajah se scenes jodne par sentences ke beech 1-1.5s ka "ruk-ruk kar"
    gap sunayi deta tha. Ye function:
    1. Leading + trailing silence ko trim karta hai (audio ab turant shuru/khatam hoga).
    2. Word timings ko usi hisaab se shift karta hai taake captions sync mein rahein.
    """
    audio = AudioSegment.from_file(mp3_path, format="mp3")

    leading_ms = detect_leading_silence(audio, silence_threshold=_SILENCE_THRESH_DB)
    trailing_ms = detect_leading_silence(audio.reverse(), silence_threshold=_SILENCE_THRESH_DB)
    trailing_ms = min(trailing_ms, max(0, len(audio) - leading_ms - 50))  # safety: kam se kam 50ms bachao

    trimmed = audio[leading_ms: len(audio) - trailing_ms]
    trimmed.export(mp3_path, format="mp3")

    shift = leading_ms / 1000.0
    new_duration = len(trimmed) / 1000.0
    shifted_words = [
        {
            "text": w["text"],
            "start": min(max(0.0, w["start"] - shift), new_duration),
            "end": min(max(0.0, w["end"] - shift), new_duration),
        }
        for w in words
    ]
    return new_duration, shifted_words


async def create_voiceover(text, output_file="voice.mp3"):
    await _synthesize_with_boundaries(text, output_file)


def generate_hindi_audio(script_text, output_file="voice.mp3"):
    asyncio.run(create_voiceover(script_text, output_file))


def generate_scene_audios(scenes, output_dir="scene_audio"):
    """
    Har scene ke liye alag voiceover MP3 banata hai (scene_0.mp3, scene_1.mp3, ...),
    silence-trim karta hai (taake scenes jodne par gap na aaye), aur har word ka
    exact start/end time bhi return karta hai (word-by-word captions ke liye).

    Returns: (list of audio file paths, list of per-scene word-timing lists)
             scene_word_timings[i] scenes[i] se corresponds karta hai.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    scene_word_timings = []

    for i, scene in enumerate(scenes):
        path = os.path.join(output_dir, f"scene_{i}.mp3")
        raw_words = asyncio.run(_synthesize_with_boundaries(scene["narration"], path))
        _, shifted_words = _trim_silence_and_shift_words(path, raw_words)
        paths.append(path)
        scene_word_timings.append(shifted_words)

    return paths, scene_word_timings

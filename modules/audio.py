import os
import asyncio
import subprocess
import edge_tts
from gtts import gTTS
from moviepy.editor import (
    AudioFileClip,
    AudioClip,
    CompositeAudioClip,
    concatenate_audioclips
)

# Chhota sa natural breathing gap jab do scenes ke voiceover jode jate hain.
# Bilkul zero gap ek doosre mein "mashed" laga sakta hai, lekin bade gaps
# "reading" wala feel dete hain - ye beech ka balance hai.
INTER_SCENE_PAUSE = 0.12


# Natural Hindi male neural voice. hi-IN-MadhurNeural is currently the only
# male neural voice Edge TTS ships for Hindi - it defaults to a fairly deep,
# "announcer" style read. Nudging the pitch up a touch and keeping the rate
# close to normal speaking speed makes it land closer to a natural adult
# guy's voice instead of a deep robotic AI read.
VOICE = "hi-IN-MadhurNeural"

# Normal conversational pace - not sped up, not slow ("+4%" pushed it into
# a rushed, robotic-sounding read).
VOICE_RATE = "+0%"

# Slightly higher pitch than default = sounds like a younger/natural adult
# male instead of the very deep default AI read. Tweak between "+0Hz" and
# "+6Hz" to taste if it still sounds too deep or gets too "chipmunky".
VOICE_PITCH = "+4Hz"

# How much silence to trim off the start/end of every per-scene voiceover
# clip. Edge TTS leaves a small pause on each clip; when 6-8 of these get
# stitched together back-to-back it adds up into noticeable dead air between
# sentences, which is exactly what makes it sound like someone "reading"
# instead of speaking naturally.
SILENCE_TRIM_DB = "-35dB"


async def generate_tts_async(text, output_path):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH
    )

    await communicate.save(output_path)


def _trim_silence(path):
    """
    Har scene ke voiceover clip ke start/end se silence hata deta hai,
    taake jab clips ek dusre ke saath jode jayein to beech mein
    unnatural gap na aaye. Agar ffmpeg fail ho jaye to original file
    ko as-is chhod deta hai (pipeline kabhi crash nahi hoga).
    """
    trimmed_path = path + ".trimmed.mp3"

    command = [
        "ffmpeg", "-y", "-i", path,
        "-af",
        f"silenceremove=start_periods=1:start_threshold={SILENCE_TRIM_DB}:"
        f"start_silence=0.05,"
        f"areverse,"
        f"silenceremove=start_periods=1:start_threshold={SILENCE_TRIM_DB}:"
        f"start_silence=0.05,"
        f"areverse",
        "-ar", "44100",
        trimmed_path,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=60
        )
        if (
            result.returncode == 0
            and os.path.exists(trimmed_path)
            and os.path.getsize(trimmed_path) > 500
        ):
            os.replace(trimmed_path, path)
        else:
            if os.path.exists(trimmed_path):
                os.remove(trimmed_path)
    except Exception as e:
        print(f"Silence trim skipped for {path}: {e}")
        if os.path.exists(trimmed_path):
            os.remove(trimmed_path)


def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    """
    Hindi natural neural voice generate karta hai.

    Primary:
        Microsoft Edge Neural TTS

    Fallback:
        Hindi gTTS
    """

    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )

    clean_text = " ".join(text.split())

    if not clean_text:
        raise ValueError("Voiceover ke liye text empty hai.")

    # ------------------------------------------
    # EDGE TTS - PRIMARY NATURAL NEURAL VOICE
    # ------------------------------------------

    try:

        asyncio.run(
            generate_tts_async(
                clean_text,
                output_path
            )
        )

        if (
            os.path.exists(output_path)
            and os.path.getsize(output_path) > 1000
        ):

            _trim_silence(output_path)

            print(
                f"Voiceover generated successfully "
                f"using {VOICE}"
            )

            return output_path

        raise Exception(
            "Edge TTS ne valid audio file generate nahi ki."
        )

    except Exception as e:

        print(
            f"Edge TTS failed: {e}"
        )

        print(
            "Switching to Hindi gTTS fallback..."
        )


    # ------------------------------------------
    # GTTS - HINDI FALLBACK
    # ------------------------------------------

    try:

        tts = gTTS(
            text=clean_text,
            lang="hi",
            slow=False
        )

        tts.save(output_path)

        _trim_silence(output_path)

        print(
            "Hindi voiceover generated successfully "
            "using gTTS fallback."
        )

        return output_path

    except Exception as e:

        raise Exception(
            "Both Edge TTS and gTTS failed "
            f"to generate audio: {e}"
        )


def estimate_word_timings(text, duration):

    """
    Total voiceover duration ko words mein divide karta hai
    taake captions approximate sync mein rahein.
    """

    words = [
        word
        for word in text.split()
        if word.strip()
    ]

    if not words or duration <= 0:
        return []

    weights = [
        max(len(word), 1)
        for word in words
    ]

    total_weight = sum(weights)

    timings = []

    current_time = 0.0

    for word, weight in zip(
        words,
        weights
    ):

        word_duration = (
            duration *
            (
                weight /
                total_weight
            )
        )

        timings.append(
            {
                "text": word,
                "start": current_time
            }
        )

        current_time += word_duration

    return timings


def concatenate_voiceovers(
    audio_paths,
    output_path="assets/voiceover_full.mp3"
):

    """
    Har scene ke voiceovers ko ek final
    voiceover file mein merge karta hai.
    """

    if not audio_paths:

        raise ValueError(
            "concatenate_voiceovers: "
            "audio_paths list empty hai."
        )


    if len(audio_paths) == 1:

        return audio_paths[0]


    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )


    clips = [
        AudioFileClip(path)
        for path in audio_paths
    ]

    silence = AudioClip(
        lambda t: 0,
        duration=INTER_SCENE_PAUSE,
        fps=44100
    )

    padded_clips = []
    for i, clip in enumerate(clips):
        padded_clips.append(clip)
        if i < len(clips) - 1:
            padded_clips.append(silence)

    try:

        final = concatenate_audioclips(
            padded_clips
        )

        final.write_audiofile(
            output_path,
            fps=44100,
            logger=None
        )

    finally:

        for clip in clips:

            clip.close()


    return output_path


def add_background_music_and_sfx(
    voiceover_path,
    output_path="assets/final_audio.mp3",
    bg_music_path="assets/audio/bg_music.mp3",
    bg_volume=0.10
):

    """
    Voice ko main priority deta hai aur
    background music ko low rakhta hai.
    """

    try:

        if not os.path.exists(
            voiceover_path
        ):

            raise FileNotFoundError(
                f"Voiceover not found: "
                f"{voiceover_path}"
            )


        voiceover = AudioFileClip(
            voiceover_path
        )


        audio_clips = [
            voiceover
        ]


        if (
            os.path.exists(bg_music_path)
            and os.path.getsize(bg_music_path) > 0
        ):

            bg_music = AudioFileClip(
                bg_music_path
            ).volumex(
                bg_volume
            )


            if (
                bg_music.duration
                < voiceover.duration
            ):

                bg_music = bg_music.loop(
                    duration=voiceover.duration
                )

            else:

                bg_music = bg_music.subclip(
                    0,
                    voiceover.duration
                )


            audio_clips.append(
                bg_music
            )


        else:

            print(
                "Background music missing. "
                "Using voice only."
            )


        final_audio = CompositeAudioClip(
            audio_clips
        )


        output_dir = (
            os.path.dirname(output_path)
            or "."
        )


        os.makedirs(
            output_dir,
            exist_ok=True
        )


        final_audio.write_audiofile(
            output_path,
            fps=44100,
            logger=None
        )


        print(
            f"Final audio created: "
            f"{output_path}"
        )


        return output_path


    except Exception as e:

        print(
            f"Audio mixing error: {e}"
        )

        return voiceover_path

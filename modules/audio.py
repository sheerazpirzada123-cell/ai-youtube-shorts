import os
import asyncio
import edge_tts
from gtts import gTTS
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips
)


# Natural Hindi male neural voice
VOICE = "hi-IN-MadhurNeural"

# Thori energetic, lekin robotic ya zyada fast nahi
VOICE_RATE = "+4%"


async def generate_tts_async(text, output_path):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=VOICE_RATE,
        pitch="+0Hz"
    )

    await communicate.save(output_path)


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


    try:

        final = concatenate_audioclips(
            clips
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

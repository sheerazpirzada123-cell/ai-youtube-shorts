import os
import random

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    ColorClip
)


def load_valid_video_clip(path):
    """
    Agar kisi wajah se koi clip corrupt ho
    to usko skip karega.

    Ek corrupt video ki wajah se
    pura workflow fail nahi hoga.
    """

    if not isinstance(path, str):
        print(f"⚠️ Invalid path type: {type(path)}")
        return None

    if not os.path.exists(path):
        print(f"⚠️ Video file missing: {path}")
        return None

    if os.path.getsize(path) < 50000:
        print(f"⚠️ Video file too small: {path}")
        return None

    try:
        clip = VideoFileClip(path)

        # Duration check karo pehle
        if clip.duration <= 0:
            print(f"⚠️ Invalid duration: {path}")
            clip.close()
            return None

        # Resize to standard shorts dimensions (1080x1920)
        if clip.w != 1080 or clip.h != 1920:
            print(f"🔄 Resizing {path} to 1080x1920")
            clip = clip.resize((1080, 1920))

        # First frame ko force karke read karte hain.
        # Isse corrupt MP4 immediately detect ho jati hai.
        frame_time = min(0.1, max(0, clip.duration / 2))
        
        try:
            clip.get_frame(frame_time)
        except Exception as e:
            print(f"⚠️ Cannot read frame from {path}: {e}")
            clip.close()
            return None

        print(f"✓ Valid video loaded: {path}")
        return clip

    except Exception as error:
        print(f"⚠️ Skipping invalid video clip {path}: {error}")
        try:
            if "clip" in locals() and clip is not None:
                clip.close()
        except Exception:
            pass
        return None


def create_placeholder_clip(duration=5, width=1080, height=1920):
    """
    Agar koi video fail ho jaaye to ek placeholder black clip
    banate hain taake pipeline crash na ho.
    """
    print(f"🎨 Creating placeholder clip ({duration}s)")
    placeholder = ColorClip(
        size=(width, height),
        color=(0, 0, 0)
    ).set_duration(duration)
    return placeholder


def render_short_video(
    video_clips_paths,
    voiceover_path,
    bg_music_path="assets/audio/bg_music.mp3",
    sfx_folder="assets/sfx",
    output_path="assets/final_short.mp4",
    scene_word_timings=None,
    **kwargs
):
    """
    Video clips ko safely combine karta hai.
    Corrupt clip detect hone par usko skip karta hai.
    """

    voiceover = None
    bg_music = None
    final_video = None
    final_audio = None
    clips = []

    try:
        print("🎬 Assembling professional YouTube Short...")

        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover not found at {voiceover_path}")

        voiceover = AudioFileClip(voiceover_path)
        total_duration = voiceover.duration

        if total_duration <= 0:
            raise RuntimeError("Voiceover duration is invalid.")

        # ===============================
        # FLATTEN VIDEO PATHS
        # ===============================
        flat_paths = []

        if isinstance(video_clips_paths, list):
            for item in video_clips_paths:
                if isinstance(item, list):
                    for path in item:
                        if isinstance(path, str):
                            flat_paths.append(path)
                elif isinstance(item, str):
                    flat_paths.append(item)
        elif isinstance(video_clips_paths, str):
            flat_paths.append(video_clips_paths)

        if not flat_paths:
            print("⚠️ No video paths provided!")
            flat_paths = []

        # ===============================
        # SAFE VIDEO LOADING
        # ===============================
        loaded_count = 0
        for path in flat_paths:
            clip = load_valid_video_clip(path)
            if clip is not None:
                clips.append(clip)
                loaded_count += 1

        print(f"✓ Successfully loaded {loaded_count}/{len(flat_paths)} video clips")

        # Agar koi bhi clip load nahi hua to placeholder banate hain
        if not clips:
            print("⚠️ No valid video clips found, creating placeholder...")
            placeholder = create_placeholder_clip(
                duration=total_duration,
                width=1080,
                height=1920
            )
            clips = [placeholder]

        # ===============================
        # CONCATENATE VIDEOS
        # ===============================
        print(f"Combining {len(clips)} clips...")

        if len(clips) == 1:
            # Agar sirf ek clip hai to concatenation skip karte hain
            final_video = clips[0]
        else:
            try:
                final_video = concatenate_videoclips(clips, method="compose")
            except Exception as e:
                print(f"⚠️ Concatenation failed: {e}, using first clip only")
                final_video = clips[0]

        # ✅ FIX: Check if final_video is None
        if final_video is None:
            print("❌ Final video is None! Using placeholder.")
            final_video = create_placeholder_clip(
                duration=total_duration,
                width=1080,
                height=1920
            )

        if final_video.duration <= 0:
            raise RuntimeError("Final video duration is invalid.")

        print(f"Video duration: {final_video.duration:.2f}s, Voiceover: {total_duration:.2f}s")

        # ===============================
        # MATCH VOICEOVER DURATION
        # ===============================
        if final_video.duration > total_duration:
            print(f"🔄 Trimming video from {final_video.duration:.2f}s to {total_duration:.2f}s")
            trimmed = final_video.subclip(0, total_duration)
            final_video.close()
            final_video = trimmed

        elif final_video.duration < total_duration:
            print(f"🔄 Looping video from {final_video.duration:.2f}s to {total_duration:.2f}s")
            loops = int(total_duration // final_video.duration) + 1
            looped = (
                final_video
                .loop(n=loops)
                .subclip(0, total_duration)
            )
            final_video.close()
            final_video = looped

        # ===============================
        # AUDIO
        # ===============================
        audio_tracks = [voiceover]

        if (os.path.exists(bg_music_path) and os.path.getsize(bg_music_path) > 1000):
            try:
                bg_music = AudioFileClip(bg_music_path).volumex(0.08)

                if bg_music.duration < total_duration:
                    bg_music = bg_music.loop(duration=total_duration)
                else:
                    bg_music = bg_music.subclip(0, total_duration)

                audio_tracks.append(bg_music)
            except Exception as e:
                print(f"⚠️ Background music failed: {e}")

        # ===============================
        # SOUND EFFECTS
        # ===============================
        if os.path.exists(sfx_folder):
            sfx_files = [
                os.path.join(sfx_folder, filename)
                for filename in os.listdir(sfx_folder)
                if filename.lower().endswith((".mp3", ".wav"))
            ]

            if sfx_files:
                cut_interval = total_duration / max(len(clips), 1)
                current_time = cut_interval

                while current_time < total_duration - 1:
                    sfx_path = random.choice(sfx_files)

                    try:
                        sfx = (
                            AudioFileClip(sfx_path)
                            .volumex(0.20)
                            .set_start(current_time)
                        )
                        audio_tracks.append(sfx)
                    except Exception as error:
                        print(f"SFX skipped: {error}")

                    current_time += cut_interval

        # ===============================
        # FINAL AUDIO
        # ===============================
        if len(audio_tracks) > 0:
            final_audio = CompositeAudioClip(audio_tracks)
            final_video = final_video.set_audio(final_audio)

        output_directory = os.path.dirname(output_path) or "."
        os.makedirs(output_directory, exist_ok=True)

        # ===============================
        # EXPORT
        # ===============================
        print("Rendering final MP4...")

        final_video.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            bitrate="5000k",
            threads=2,
            ffmpeg_params=[
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart"
            ],
            logger=None
        )

        print(f"✅ Professional video successfully created at {output_path}")
        return output_path

    except Exception as error:
        print(f"❌ Error in creating video: {error}")
        raise

    finally:
        try:
            if final_audio is not None:
                final_audio.close()
        except Exception:
            pass

        try:
            if final_video is not None:
                final_video.close()
        except Exception:
            pass

        try:
            if bg_music is not None:
                bg_music.close()
        except Exception:
            pass

        try:
            if voiceover is not None:
                voiceover.close()
        except Exception:
            pass

        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass

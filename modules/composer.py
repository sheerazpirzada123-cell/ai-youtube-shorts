import os
import random
import subprocess

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


def safe_trim_video(video_clip, target_duration):
    """
    Safely trim/extend video to target duration.
    
    Issue: Direct .subclip() can cause 'NoneType' errors
    Solution: Save and reload if duration mismatch
    """
    try:
        if video_clip is None:
            print(f"⚠️ Video is None, cannot trim")
            return None
            
        if video_clip.duration <= 0:
            print(f"⚠️ Invalid video duration: {video_clip.duration}")
            return None
        
        # Agar duration almost same hai to skip karenge
        duration_diff = abs(video_clip.duration - target_duration)
        if duration_diff < 0.5:  # Less than 0.5 second difference
            print(f"✓ Duration already close ({video_clip.duration:.2f}s)")
            return video_clip
        
        # Trim using set_end to avoid moviepy subclip issues
        if video_clip.duration > target_duration:
            print(f"🔄 Trimming video from {video_clip.duration:.2f}s to {target_duration:.2f}s")
            trimmed = video_clip.set_end(target_duration)
            return trimmed
        else:
            return video_clip
            
    except Exception as e:
        print(f"⚠️ Trimming failed: {e}, returning original")
        return video_clip


def safe_loop_video(video_clip, target_duration):
    """
    Safely loop/extend video to target duration.
    
    Issue: .loop().subclip() can cause issues
    Solution: Use padding instead
    """
    try:
        if video_clip is None or video_clip.duration <= 0:
            return None
        
        if video_clip.duration >= target_duration:
            return video_clip
        
        print(f"🔄 Extending video from {video_clip.duration:.2f}s to {target_duration:.2f}s")
        
        # Calculate how many loops we need
        loops_needed = int(target_duration // video_clip.duration) + 1
        
        # Loop the video
        looped = video_clip.loop(n=loops_needed)
        
        # Trim to exact duration
        looped = looped.set_end(target_duration)
        
        return looped
        
    except Exception as e:
        print(f"⚠️ Looping failed: {e}, returning original")
        return video_clip


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

        # ✅ FIX #1: Check if final_video is None
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
        # MATCH VOICEOVER DURATION - SAFE WAY
        # ===============================
        
        if final_video.duration > total_duration:
            # ✅ FIX #2: Use safe_trim_video instead of direct subclip
            final_video = safe_trim_video(final_video, total_duration)
            
        elif final_video.duration < total_duration:
            # ✅ FIX #3: Use safe_loop_video instead of direct loop
            final_video = safe_loop_video(final_video, total_duration)

        # ✅ FIX #4: Validate final_video again after trimming
        if final_video is None:
            print("❌ Video became None after trimming! Using placeholder.")
            final_video = create_placeholder_clip(
                duration=total_duration,
                width=1080,
                height=1920
            )

        if final_video.duration <= 0:
            print("❌ Final video has invalid duration! Using placeholder.")
            final_video = create_placeholder_clip(
                duration=total_duration,
                width=1080,
                height=1920
            )

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
                    bg_music = bg_music.set_end(total_duration)

                audio_tracks.append(bg_music)
            except Exception as e:
                print(f"⚠️ Background music failed: {e}")

        # ===============================
        # SOUND EFFECTS
        # ===============================
        if os.path.exists(sfx_folder):
            try:
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
            except Exception as e:
                print(f"⚠️ Sound effects folder error: {e}")

        # ===============================
        # FINAL AUDIO
        # ===============================
        if len(audio_tracks) > 0:
            final_audio = CompositeAudioClip(audio_tracks)
            final_video = final_video.set_audio(final_audio)

        output_directory = os.path.dirname(output_path) or "."
        os.makedirs(output_directory, exist_ok=True)

        # ===============================
        # EXPORT WITH RETRY
        # ===============================
        print("Rendering final MP4...")

        try:
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                bitrate="5000k",
                threads=2,
                verbose=False,
                logger=None,
                ffmpeg_params=[
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart"
                ]
            )
        except Exception as write_error:
            print(f"⚠️ Initial write failed: {write_error}")
            print("Trying with different codec...")
            
            # Fallback: Try with different parameters
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="fast",
                verbose=False,
                logger=None,
                ffmpeg_params=[
                    "-pix_fmt",
                    "yuv420p"
                ]
            )

        print(f"✅ Professional video successfully created at {output_path}")
        return output_path

    except Exception as error:
        print(f"❌ Error in creating video: {error}")
        import traceback
        traceback.print_exc()
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

import os
import random
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_audioclips, concatenate_videoclips, vfx, TextClip, CompositeVideoClip
)
import moviepy.audio.fx.all as afx

TARGET_W = 1080
TARGET_H = 1920

BG_MUSIC_VOLUME = 0.20
SCENE_GAP = 0.05

# CTA text overlay settings — subtle rakho
CTA_TEXT = "Like ❤️"
CTA_FONT_SIZE = 60
CTA_POSITION = ("center", 0.88)  # screen ke neeche 88% par
CTA_START_RATIO = 0.55           # video ke 55% ke baad dikhega
CTA_FADE_DURATION = 0.5


class ShortsComposer:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _fit_vertical(clip):
        if clip.w / clip.h > TARGET_W / TARGET_H:
            clip = clip.resize(height=TARGET_H)
            clip = clip.crop(x_center=clip.w / 2, width=TARGET_W)
        else:
            clip = clip.resize(width=TARGET_W)
            clip = clip.crop(y_center=clip.h / 2, height=TARGET_H)
        if (clip.w, clip.h) != (TARGET_W, TARGET_H):
            clip = clip.resize((TARGET_W, TARGET_H))
        return clip

    @staticmethod
    def _prepare_scene_video(path, duration):
        try:
            clip = VideoFileClip(path, audio=False)
        except Exception as e:
            raise RuntimeError(
                f"VideoFileClip fail hua '{path}' ke liye: {e}"
            )

        if clip.duration is None or clip.duration <= 0:
            clip.close()
            raise RuntimeError(
                f"Clip '{path}' ki duration invalid hai: {clip.duration}"
            )

        if clip.duration < duration + 0.2:
            try:
                clip = clip.fx(vfx.loop, duration=duration + 0.5)
            except Exception as e:
                clip.close()
                raise RuntimeError(
                    f"Loop fail hua '{path}' ke liye: {e}"
                )
        else:
            spare = max(0.0, clip.duration - duration - 0.2)
            if spare > 0.1:
                start = random.uniform(0, spare)
            else:
                start = 0.0
            end = start + duration
            if end > clip.duration:
                end = clip.duration
                start = max(0.0, end - duration)
            try:
                clip = clip.subclip(start, end)
            except Exception as e:
                clip.close()
                raise RuntimeError(
                    f"Subclip fail hua '{path}' ke liye "
                    f"(start={start}, end={end}, dur={clip.duration}): {e}"
                )

        return ShortsComposer._fit_vertical(clip)

    @staticmethod
    def _make_cta_overlay(total_duration):
        """
        Subtle 'Like' text overlay banata hai jo video ke 55% ke baad
        fade-in hoti hai aur end tak dikhti hai.
        Agar font na mile to None return karega (crash nahi karega).
        """
        try:
            font_candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
            font_file = next(
                (f for f in font_candidates if os.path.exists(f)), None
            )
            if not font_file:
                print("⚠️ CTA overlay: font nahi mila, skip kar rahe hain.")
                return None

            cta_clip = TextClip(
                CTA_TEXT,
                fontsize=CTA_FONT_SIZE,
                color="white",
                font=font_file,
                stroke_color="black",
                stroke_width=2,
                method="caption",
            )
            cta_clip = cta_clip.set_position(CTA_POSITION).set_duration(
                total_duration
            )

            # Fade-in start time
            start_time = total_duration * CTA_START_RATIO
            cta_clip = cta_clip.set_start(start_time)

            # Fade-in / fade-out
            cta_clip = cta_clip.crossfadein(CTA_FADE_DURATION)

            # Opacity thoda kam karo taake subtle lage
            cta_clip = cta_clip.set_opacity(0.85)

            return cta_clip
        except Exception as e:
            print(f"⚠️ CTA overlay banane mein error: {e}")
            return None

    def _add_background_music(self, voice_audio, total_duration, bg_music_path):
        audio_tracks = [voice_audio]
        bg_music = None
        try:
            if bg_music_path and os.path.exists(bg_music_path):
                print(f"🎵 BG music: {bg_music_path} (vol {BG_MUSIC_VOLUME})")
                bg_music_raw = AudioFileClip(bg_music_path)

                if bg_music_raw.duration is None or bg_music_raw.duration <= 0:
                    print("⚠️ BG music ki duration invalid hai, skip.")
                    bg_music_raw.close()
                    bg_music = None
                else:
                    bg_music = bg_music_raw
                    if bg_music.duration < total_duration:
                        loop_count = int(total_duration // bg_music.duration) + 2
                        bg_music = concatenate_audioclips(
                            [bg_music] * loop_count
                        )
                    if bg_music.duration > total_duration:
                        bg_music = bg_music.subclip(0, total_duration)
                    bg_music = bg_music.volumex(BG_MUSIC_VOLUME)
                    bg_music = (
                        bg_music
                        .fx(afx.audio_fadein, 0.5)
                        .fx(afx.audio_fadeout, 1.0)
                    )
                    audio_tracks.append(bg_music)
            else:
                print("⚠️ bg_music nahi mila. Bina BG ke banegi.")
        except Exception as e:
            print(f"⚠️ BG music process karne mein error: {e}")
            bg_music = None

        return CompositeAudioClip(audio_tracks), bg_music

    def _export(self, video_clip, output_filename):
        output_path = os.path.join(self.output_dir, output_filename)
        video_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "22"],
            temp_audiofile=os.path.join(self.output_dir, "temp_audio.m4a"),
            remove_temp=True,
        )
        return output_path

    def create_multi_scene_short(self, clip_paths, voiceover_paths,
                                  output_filename="final_short.mp4",
                                  bg_music_path="bg_music.mp3",
                                  add_cta=True):
        print("🎬 Multi-scene composition...")

        if not clip_paths or not voiceover_paths:
            raise ValueError("clip_paths ya voiceover_paths empty hain.")

        count = min(len(clip_paths), len(voiceover_paths))
        if len(clip_paths) != len(voiceover_paths):
            print(
                f"⚠️ clip_paths={len(clip_paths)}, "
                f"voiceover_paths={len(voiceover_paths)} — "
                f"sirf pehle {count} use karenge."
            )

        for i in range(count):
            if not os.path.exists(clip_paths[i]):
                raise FileNotFoundError(
                    f"Scene {i+1} ka video clip nahi mila: {clip_paths[i]}"
                )
            if not os.path.exists(voiceover_paths[i]):
                raise FileNotFoundError(
                    f"Scene {i+1} ki voiceover nahi mili: {voiceover_paths[i]}"
                )

        voice_clips = []
        video_scenes = []
        opened_audio = []
        opened_video = []
        timeline = 0.0

        try:
            for index in range(count):
                clip_path = clip_paths[index]
                voice_path = voiceover_paths[index]

                try:
                    voice = AudioFileClip(voice_path)
                except Exception as e:
                    raise RuntimeError(
                        f"Scene {index+1} ki voice load nahi hui: {e}"
                    )

                opened_audio.append(voice)

                if voice.duration is None or voice.duration <= 0.1:
                    raise RuntimeError(
                        f"Scene {index+1} ki voice duration invalid: "
                        f"{voice.duration}"
                    )

                scene_duration = voice.duration + SCENE_GAP

                try:
                    scene_video = self._prepare_scene_video(
                        clip_path, scene_duration
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"Scene {index+1} ka video prepare nahi hua: {e}"
                    )

                opened_video.append(scene_video)
                video_scenes.append(scene_video)
                voice_clips.append(voice.set_start(timeline))
                timeline += scene_duration
                print(
                    f"   scene {index+1}: video={scene_video.duration:.2f}s, "
                    f"voice={voice.duration:.2f}s"
                )

            total_duration = timeline
            print(f"⏱️ Total: {total_duration:.1f}s")

            if not voice_clips:
                raise RuntimeError(
                    "Koi bhi voice clip ready nahi hui — composition rok diya."
                )

            voice_track = CompositeAudioClip(voice_clips).set_duration(
                total_duration
            )
            final_audio, bg_music = self._add_background_music(
                voice_track, total_duration, bg_music_path
            )
            if bg_music is not None:
                opened_audio.append(bg_music)

            if not video_scenes:
                raise RuntimeError("Koi bhi video scene ready nahi hui.")

            video = concatenate_videoclips(video_scenes, method="chain")
            video = video.set_audio(final_audio).set_duration(total_duration)

            # CTA overlay add karo (optional, fail ho to skip)
            if add_cta:
                cta_overlay = self._make_cta_overlay(total_duration)
                if cta_overlay is not None:
                    try:
                        video = CompositeVideoClip(
                            [video, cta_overlay],
                            size=(TARGET_W, TARGET_H)
                        ).set_duration(total_duration)
                        print("✅ CTA overlay added (subtle 'Like' text)")
                    except Exception as e:
                        print(f"⚠️ CTA overlay compose fail: {e}")

            output_path = self._export(video, output_filename)

            try:
                video.close()
            except Exception:
                pass

        finally:
            for clip in opened_audio:
                try:
                    clip.close()
                except Exception:
                    pass
            for clip in opened_video:
                try:
                    clip.close()
                except Exception:
                    pass

        print(f"✅ Video ready: {output_path}")
        return output_path

    # OLD method — backward compat
    def create_short(self, video_path, voiceover_path,
                     output_filename="final_short.mp4",
                     bg_music_path="bg_music.mp3"):
        print("🎬 Single-clip composition...")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video nahi mili: {video_path}")
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover nahi mili: {voiceover_path}")

        voiceover_clip = AudioFileClip(voiceover_path)
        final_duration = voiceover_clip.duration

        video_clip = VideoFileClip(video_path)
        if video_clip.duration < final_duration:
            video_clip = video_clip.fx(vfx.loop, duration=final_duration)
        else:
            video_clip = video_clip.subclip(0, final_duration)

        final_audio, bg_music = self._add_background_music(
            voiceover_clip, final_duration, bg_music_path
        )
        video_clip = video_clip.set_audio(final_audio)

        # CTA overlay
        cta_overlay = self._make_cta_overlay(final_duration)
        if cta_overlay is not None:
            try:
                video_clip = CompositeVideoClip(
                    [video_clip, cta_overlay],
                    size=(TARGET_W, TARGET_H)
                ).set_duration(final_duration)
            except Exception as e:
                print(f"⚠️ CTA overlay fail: {e}")

        output_path = self._export(video_clip, output_filename)

        video_clip.close()
        voiceover_clip.close()
        if bg_music is not None:
            try:
                bg_music.close()
            except Exception:
                pass

        print(f"✅ Video ready: {output_path}")
        return output_path

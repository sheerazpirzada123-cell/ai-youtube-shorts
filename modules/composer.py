import os
import random
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_audioclips, concatenate_videoclips, vfx,
    TextClip, CompositeVideoClip
)
import moviepy.audio.fx.all as afx

TARGET_W = 1080
TARGET_H = 1920

BG_MUSIC_VOLUME = 0.15
SCENE_GAP = 0.05
SFX_VOLUME = 0.55

# ============================================================
# CAPTION SETTINGS — Premium TikTok/Reels style
# ============================================================
CAPTION_FONT_SIZE = 72
CAPTION_POSITION = ("center", 0.55)
CAPTION_FADE = 0.10
CAPTION_COLOR = "#FFFFFF"
CAPTION_STROKE_COLOR = "#000000"
CAPTION_STROKE_WIDTH = 6

# CTA settings
CTA_TEXT = "Follow for more"
CTA_FONT_SIZE = 58
CTA_POSITION = ("center", 0.85)
CTA_START_RATIO = 0.55
CTA_FADE_DURATION = 0.5

SFX_FOLDER = "assets/sfx"


class ShortsComposer:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _get_font_file():
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "assets/fonts/DejaVuSans-Bold.ttf",
            "assets/fonts/NotoSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for f in font_candidates:
            if os.path.exists(f):
                print("Font found: " + f)
                return f

        try:
            import subprocess
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "sans:bold"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                if os.path.exists(path):
                    print("Font via fc-match: " + path)
                    return path
        except Exception as e:
            print("fc-match failed: " + str(e))

        print("Koi bhi font nahi mila!")
        return None

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
            raise RuntimeError("VideoFileClip fail: " + path + ": " + str(e))

        if clip.duration is None or clip.duration <= 0:
            clip.close()
            raise RuntimeError("Clip duration invalid: " + path)

        if clip.duration < duration + 0.2:
            try:
                clip = clip.fx(vfx.loop, duration=duration + 0.5)
            except Exception as e:
                clip.close()
                raise RuntimeError("Loop fail: " + path + ": " + str(e))
        else:
            spare = max(0.0, clip.duration - duration - 0.2)
            start = random.uniform(0, spare) if spare > 0.1 else 0.0
            end = start + duration
            if end > clip.duration:
                end = clip.duration
                start = max(0.0, end - duration)
            try:
                clip = clip.subclip(start, end)
            except Exception as e:
                clip.close()
                raise RuntimeError("Subclip fail: " + path + ": " + str(e))

        return ShortsComposer._fit_vertical(clip)

    @staticmethod
    def _make_caption_overlay(text, start_time, duration, font_file):
        try:
            if not text or not text.strip() or not font_file:
                return None

            display_text = text.strip().upper()
            if len(display_text) > 55:
                display_text = display_text[:52] + "..."

            # Word wrap — 2 lines
            words = display_text.split()
            if len(words) > 5:
                mid = len(words) // 2
                line1 = " ".join(words[:mid])
                line2 = " ".join(words[mid:])
                display_text = line1 + "\n" + line2

            # ImageMagick ke bina TextClip nahi banta — try karo
            try:
                caption_clip = TextClip(
                    display_text,
                    fontsize=CAPTION_FONT_SIZE,
                    color=CAPTION_COLOR,
                    font=font_file,
                    stroke_color=CAPTION_STROKE_COLOR,
                    stroke_width=CAPTION_STROKE_WIDTH,
                    method="caption",
                    size=(TARGET_W - 80, None),
                    align="center",
                )
            except Exception as e:
                print("TextClip fail (ImageMagick issue): " + str(e))
                return None

            caption_clip = caption_clip.set_position(CAPTION_POSITION)
            caption_clip = caption_clip.set_duration(duration)
            caption_clip = caption_clip.set_start(start_time)
            caption_clip = caption_clip.crossfadein(CAPTION_FADE).crossfadeout(CAPTION_FADE)
            caption_clip = caption_clip.set_opacity(1.0)

            print("Caption added at " + str(round(start_time, 1)) + "s")
            return caption_clip
        except Exception as e:
            print("Caption error: " + str(e))
            return None

    @staticmethod
    def _make_cta_overlay(total_duration, font_file):
        try:
            if not font_file:
                return None

            cta_clip = TextClip(
                CTA_TEXT,
                fontsize=CTA_FONT_SIZE,
                color="#FFD700",
                font=font_file,
                stroke_color="#000000",
                stroke_width=4,
                method="caption",
            )
            cta_clip = cta_clip.set_position(CTA_POSITION).set_duration(total_duration)
            start_time = total_duration * CTA_START_RATIO
            cta_clip = cta_clip.set_start(start_time)
            cta_clip = cta_clip.crossfadein(CTA_FADE_DURATION)
            cta_clip = cta_clip.set_opacity(1.0)
            return cta_clip
        except Exception as e:
            print("CTA error: " + str(e))
            return None

    def _build_sfx_track(self, scene_timings, total_duration):
        sfx_clips = []
        sfx_dir = SFX_FOLDER

        if not os.path.isdir(sfx_dir):
            print("SFX folder nahi mila: " + sfx_dir)
            return None

        available = {}
        for f in os.listdir(sfx_dir):
            if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg")):
                full = os.path.join(sfx_dir, f)
                if os.path.getsize(full) > 1000:
                    available[f.lower()] = full

        if not available:
            print("SFX folder khaali hai")
            return None

        print("SFX available: " + str(list(available.keys())))

        def pick(preferred):
            for key in available:
                if preferred.lower().replace(".mp3", "") in key:
                    return available[key]
            return None

        # Scene 1 (hook) — impact sound
        impact = pick("impact") or pick("whoosh") or pick("pop")
        if impact:
            try:
                intro = AudioFileClip(impact).volumex(SFX_VOLUME)
                intro = intro.subclip(0, min(1.5, intro.duration))
                intro = intro.set_start(0.0)
                sfx_clips.append(intro)
                print("SFX intro impact at 0.0s")
            except Exception as e:
                print("Intro SFX fail: " + str(e))

        # Har scene transition — whoosh
        whoosh = pick("whoosh") or pick("swoosh")
        if whoosh:
            for i, (start_t, dur_t) in enumerate(scene_timings):
                if i == 0:
                    continue
                try:
                    sfx = AudioFileClip(whoosh).volumex(SFX_VOLUME * 0.8)
                    sfx = sfx.subclip(0, min(0.7, sfx.duration))
                    sfx = sfx.set_start(start_t - 0.05)
                    sfx_clips.append(sfx)
                    print("SFX transition at " + str(round(start_t, 1)) + "s")
                except Exception as e:
                    print("Transition SFX fail: " + str(e))

        # CTA — pop/ding
        pop = pick("pop") or pick("ding")
        if pop and scene_timings:
            cta_time = scene_timings[-1][0]
            try:
                sfx = AudioFileClip(pop).volumex(SFX_VOLUME)
                sfx = sfx.subclip(0, min(0.6, sfx.duration))
                sfx = sfx.set_start(cta_time)
                sfx_clips.append(sfx)
                print("SFX CTA pop at " + str(round(cta_time, 1)) + "s")
            except Exception as e:
                print("CTA SFX fail: " + str(e))

        if not sfx_clips:
            return None

        return sfx_clips

    def _add_background_music(self, voice_audio, total_duration, bg_music_path):
        audio_tracks = [voice_audio]
        bg_music = None
        try:
            if bg_music_path and os.path.exists(bg_music_path):
                print("BG music: " + bg_music_path)
                bg_music_raw = AudioFileClip(bg_music_path)

                if bg_music_raw.duration is None or bg_music_raw.duration <= 0:
                    bg_music_raw.close()
                    bg_music = None
                else:
                    bg_music = bg_music_raw
                    if bg_music.duration < total_duration:
                        loop_count = int(total_duration // bg_music.duration) + 2
                        bg_music = concatenate_audioclips([bg_music] * loop_count)
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
                print("bg_music nahi mila")
        except Exception as e:
            print("BG music error: " + str(e))
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
                                  add_cta=True,
                                  scene_narrations=None):
        print("Multi-scene composition START")

        if not clip_paths or not voiceover_paths:
            raise ValueError("clip_paths ya voiceover_paths empty hain")

        count = min(len(clip_paths), len(voiceover_paths))
        print("Scenes: " + str(count))

        font_file = self._get_font_file()
        if not font_file:
            print("FONT NAHI MILA - Captions skip ho jayengi")
        else:
            print("Font ready: " + font_file)

        voice_clips = []
        video_scenes = []
        opened_audio = []
        opened_video = []
        timeline = 0.0
        scene_timings = []

        try:
            for index in range(count):
                clip_path = clip_paths[index]
                voice_path = voiceover_paths[index]

                try:
                    voice = AudioFileClip(voice_path)
                except Exception as e:
                    raise RuntimeError("Scene voice load fail: " + str(e))

                opened_audio.append(voice)

                if voice.duration is None or voice.duration <= 0.1:
                    raise RuntimeError("Scene voice invalid")

                scene_duration = voice.duration + SCENE_GAP
                scene_timings.append((timeline, voice.duration))

                try:
                    scene_video = self._prepare_scene_video(clip_path, scene_duration)
                except Exception as e:
                    raise RuntimeError("Scene video fail: " + str(e))

                opened_video.append(scene_video)
                video_scenes.append(scene_video)
                voice_clips.append(voice.set_start(timeline))
                timeline += scene_duration
                print("Scene " + str(index + 1) + " ready")

            total_duration = timeline
            print("Total: " + str(round(total_duration, 1)) + "s")

            if not voice_clips:
                raise RuntimeError("No voice clips ready")

            voice_track = CompositeAudioClip(voice_clips).set_duration(total_duration)

            final_audio, bg_music = self._add_background_music(
                voice_track, total_duration, bg_music_path
            )
            if bg_music is not None:
                opened_audio.append(bg_music)

            sfx_clips = self._build_sfx_track(scene_timings, total_duration)
            if sfx_clips:
                print(str(len(sfx_clips)) + " SFX clips added")
                sfx_track = CompositeAudioClip(sfx_clips).set_duration(total_duration)
                final_audio = CompositeAudioClip([final_audio, sfx_track])
                for s in sfx_clips:
                    opened_audio.append(s)

            video = concatenate_videoclips(video_scenes, method="chain")
            video = video.set_audio(final_audio).set_duration(total_duration)

            overlays = []

            if scene_narrations and font_file:
                for i, (start_t, dur_t) in enumerate(scene_timings):
                    if i >= len(scene_narrations):
                        break
                    narration_text = scene_narrations[i]
                    caption = self._make_caption_overlay(
                        narration_text, start_t, dur_t, font_file
                    )
                    if caption is not None:
                        overlays.append(caption)
                print(str(len(overlays)) + " captions added")

            if add_cta and font_file:
                cta_overlay = self._make_cta_overlay(total_duration, font_file)
                if cta_overlay is not None:
                    overlays.append(cta_overlay)
                    print("CTA overlay added")

            if overlays:
                try:
                    video = CompositeVideoClip(
                        [video] + overlays,
                        size=(TARGET_W, TARGET_H)
                    ).set_duration(total_duration)
                except Exception as e:
                    print("Overlay compose fail: " + str(e))

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

        print("Video ready: " + output_path)
        return output_path

    def create_short(self, video_path, voiceover_path,
                     output_filename="final_short.mp4",
                     bg_music_path="bg_music.mp3"):
        print("Single-clip composition")

        if not os.path.exists(video_path):
            raise FileNotFoundError("Video nahi mili: " + video_path)
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError("Voiceover nahi mili: " + voiceover_path)

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

        font_file = self._get_font_file()
        if font_file:
            cta_overlay = self._make_cta_overlay(final_duration, font_file)
            if cta_overlay is not None:
                try:
                    video_clip = CompositeVideoClip(
                        [video_clip, cta_overlay],
                        size=(TARGET_W, TARGET_H)
                    ).set_duration(final_duration)
                except Exception as e:
                    print("CTA overlay fail: " + str(e))

        output_path = self._export(video_clip, output_filename)

        video_clip.close()
        voiceover_clip.close()
        if bg_music is not None:
            try:
                bg_music.close()
            except Exception:
                pass

        print("Video ready: " + output_path)
        return output_path

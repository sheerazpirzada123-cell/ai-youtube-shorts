import os
import random
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_audioclips, concatenate_videoclips, vfx
)
import moviepy.audio.fx.all as afx

TARGET_W = 1080
TARGET_H = 1920

# 0.05 -> 0.12 -> 0.20 — ab clearly sunai dega
BG_MUSIC_VOLUME = 0.20

SCENE_GAP = 0.05


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
        clip = VideoFileClip(path, audio=False)
        if clip.duration < duration:
            clip = clip.fx(vfx.loop, duration=duration)
        else:
            spare = clip.duration - duration - 0.1
            start = random.uniform(0, spare) if spare > 0.1 else 0
            clip = clip.subclip(start, start + duration)
        return ShortsComposer._fit_vertical(clip)

    def _add_background_music(self, voice_audio, total_duration, bg_music_path):
        audio_tracks = [voice_audio]
        bg_music = None
        if bg_music_path and os.path.exists(bg_music_path):
            print(f"🎵 BG music: {bg_music_path} (vol {BG_MUSIC_VOLUME})")
            bg_music = AudioFileClip(bg_music_path)
            if bg_music.duration < total_duration:
                loop_count = int(total_duration // bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loop_count)
            bg_music = bg_music.subclip(0, total_duration)
            bg_music = bg_music.volumex(BG_MUSIC_VOLUME)
            bg_music = bg_music.fx(afx.audio_fadein, 0.5).fx(afx.audio_fadeout, 1.0)
            audio_tracks.append(bg_music)
        else:
            print("⚠️ bg_music nahi mila. Bina BG ke banegi.")
        return CompositeAudioClip(audio_tracks), bg_music

    def _export(self, video_clip, output_filename):
        output_path = os.path.join(self.output_dir, output_filename)
        video_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",           # veryfast se medium — better quality
            ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "22"],  # 23 se 22
            temp_audiofile=os.path.join(self.output_dir, "temp_audio.m4a"),
            remove_temp=True,
        )
        return output_path

    def create_multi_scene_short(self, clip_paths, voiceover_paths,
                                  output_filename="final_short.mp4",
                                  bg_music_path="bg_music.mp3"):
        print("🎬 Multi-scene composition...")
        if not clip_paths or len(clip_paths) != len(voiceover_paths):
            raise ValueError("clip_paths aur voiceover_paths barabar honi chahiye.")

        voice_clips = []
        video_scenes = []
        opened = []
        timeline = 0.0
        try:
            for index, (clip_path, voice_path) in enumerate(zip(clip_paths, voiceover_paths), start=1):
                voice = AudioFileClip(voice_path)
                opened.append(voice)
                scene_duration = voice.duration + SCENE_GAP
                scene_video = self._prepare_scene_video(clip_path, scene_duration)
                video_scenes.append(scene_video)
                voice_clips.append(voice.set_start(timeline))
                timeline += scene_duration
                print(f"   scene {index}: {scene_duration:.2f}s")

            total_duration = timeline
            print(f"⏱️ Total: {total_duration:.1f}s")

            voice_track = CompositeAudioClip(voice_clips).set_duration(total_duration)
            final_audio, bg_music = self._add_background_music(voice_track, total_duration, bg_music_path)
            if bg_music is not None:
                opened.append(bg_music)

            video = concatenate_videoclips(video_scenes, method="chain")
            video = video.set_audio(final_audio).set_duration(total_duration)

            output_path = self._export(video, output_filename)
            video.close()
        finally:
            for clip in opened:
                try:
                    clip.close()
                except Exception:
                    pass
            for clip in video_scenes:
                try:
                    clip.close()
                except Exception:
                    pass

        print(f"✅ Video ready: {output_path}")
        return output_path

    # OLD method — backward compat
    def create_short(self, video_path, voiceover_path, output_filename="final_short.mp4",
                     bg_music_path="bg_music.mp3"):
        print("🎬 Single-clip composition...")
        voiceover_clip = AudioFileClip(voiceover_path)
        final_duration = voiceover_clip.duration
        video_clip = VideoFileClip(video_path)
        if video_clip.duration < final_duration:
            video_clip = video_clip.fx(vfx.loop, duration=final_duration)
        else:
            video_clip = video_clip.subclip(0, final_duration)
        final_audio, bg_music = self._add_background_music(voiceover_clip, final_duration, bg_music_path)
        video_clip = video_clip.set_audio(final_audio)
        output_path = self._export(video_clip, output_filename)
        video_clip.close()
        voiceover_clip.close()
        if bg_music is not None:
            bg_music.close()
        print(f"✅ Video ready: {output_path}")
        return output_path

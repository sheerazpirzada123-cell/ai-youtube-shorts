import os
import random
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
    afx
)

class ShortsComposer:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def create_short(self, video_path, voiceover_path, output_filename="final_short.mp4", bg_music_path="bg_music.mp3"):
        """
        Combines background video, voiceover audio, and background music together.
        """
        print("🎬 Video composition start ho rahi hai...")
        
        # 1. Load Video Clip
        video_clip = VideoFileClip(video_path)
        video_duration = video_clip.duration

        # 2. Load Voiceover Audio
        voiceover_clip = AudioFileClip(voiceover_path)
        
        # Video length ko voiceover ke barabar trim karna
        final_duration = min(video_duration, voiceover_clip.duration)
        video_clip = video_clip.subclip(0, final_duration)
        voiceover_clip = voiceover_clip.subclip(0, final_duration)

        audio_tracks = [voiceover_clip]

        # 3. Add Background Music (If File Exists)
        if os.path.exists(bg_music_path):
            print(f"🎵 Background music mil gaya: {bg_music_path}")
            bg_music = AudioFileClip(bg_music_path)
            
            # Agar BG Music video se chota hai, toh loop karein
            if bg_music.duration < final_duration:
                loop_count = int(final_duration // bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loop_count)
            
            # BG Music ko video ki length jitna katein aur volume low karein (12%)
            bg_music = bg_music.subclip(0, final_duration)
            bg_music = bg_music.volumex(0.12)  # Voiceover saaf sunane ke liye 0.12 volume
            
            audio_tracks.append(bg_music)
        else:
            print("⚠️ Warning: bg_music.mp3 nahi mila. Video bina BG music ke banegi.")

        # 4. Mix Voiceover & BG Music
        final_audio = CompositeAudioClip(audio_tracks)
        video_clip = video_clip.set_audio(final_audio)

        # 5. Export Final Video
        output_path = os.path.join(self.output_dir, output_filename)
        video_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="ultrafast"
        )
        
        # Closes memory channels
        video_clip.close()
        voiceover_clip.close()
        if 'bg_music' in locals():
            bg_music.close()

        print(f"✅ Video ready ho gayi hai: {output_path}")
        return output_path

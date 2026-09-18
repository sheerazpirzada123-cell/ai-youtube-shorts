import os
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
    vfx
)

class ShortsComposer:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def create_short(self, video_path, voiceover_path, output_filename="final_short.mp4", bg_music_path="bg_music.mp3"):
        print("🎬 Video composition start ho rahi hai...")
        
        # 1. Load Voiceover Audio (Full length target)
        voiceover_clip = AudioFileClip(voiceover_path)
        final_duration = voiceover_clip.duration

        # 2. Load Video & Loop if needed
        video_clip = VideoFileClip(video_path)
        
        if video_clip.duration < final_duration:
            video_clip = video_clip.fx(vfx.loop, duration=final_duration)
        else:
            video_clip = video_clip.subclip(0, final_duration)

        audio_tracks = [voiceover_clip]

        # 3. Add Background Music (Low Volume - 5%)
        if os.path.exists(bg_music_path):
            print(f"🎵 Background music mil gaya: {bg_music_path}")
            bg_music = AudioFileClip(bg_music_path)
            
            if bg_music.duration < final_duration:
                loop_count = int(final_duration // bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loop_count)
            
            bg_music = bg_music.subclip(0, final_duration)
            bg_music = bg_music.volumex(0.05)  # 5% volume for clear narration
            
            audio_tracks.append(bg_music)
        else:
            print("⚠️ Warning: bg_music.mp3 nahi mila. Video bina BG music ke banegi.")

        # 4. Mix Audio & Set to Video
        final_audio = CompositeAudioClip(audio_tracks)
        video_clip = video_clip.set_audio(final_audio)

        # 5. Export Video
        output_path = os.path.join(self.output_dir, output_filename)
        video_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="ultrafast"
        )
        
        video_clip.close()
        voiceover_clip.close()
        if 'bg_music' in locals():
            bg_music.close()

        print(f"✅ Video ready ho gayi hai: {output_path}")
        return output_path

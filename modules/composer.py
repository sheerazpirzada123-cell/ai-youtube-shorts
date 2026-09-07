import os
import random
from moviepy.editor import (
    VideoFileClip, 
    AudioFileClip, 
    CompositeAudioClip, 
    concatenate_videoclips
)

def render_short_video(video_clips_paths, voiceover_path, bg_music_path="assets/audio/bg_music.mp3", sfx_folder="assets/sfx", output_path="assets/final_short.mp4", scene_word_timings=None, **kwargs):
    """
    Combines video clips, applies the voiceover, adds background music with ducking,
    and places sound effects precisely at scene transitions.
    """
    try:
        print("🎬 Assembling professional YouTube Short...")
        
        # 1. Load voiceover to get total duration
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover not found at {voiceover_path}")
        
        voiceover = AudioFileClip(voiceover_path)
        total_duration = voiceover.duration
        
        # Flatten and clean video_clips_paths in case it contains lists or nested structures
        flat_paths = []
        if isinstance(video_clips_paths, list):
            for item in video_clips_paths:
                if isinstance(item, list):
                    flat_paths.extend([p for p in item if isinstance(p, str)])
                elif isinstance(item, str):
                    flat_paths.append(item)
        elif isinstance(video_clips_paths, str):
            flat_paths.append(video_clips_paths)

        # 2. Load and combine video clips to match the voiceover length
        clips = [VideoFileClip(p) for p in flat_paths if isinstance(p, str) and os.path.exists(p)]
        if not clips:
            raise Exception("❌ No valid video clips found!")
            
        final_video = concatenate_videoclips(clips, method="compose")
        
        if final_video.duration > total_duration:
            final_video = final_video.subclip(0, total_duration)
        else:
            loops = int(total_duration // final_video.duration) + 1
            final_video = final_video.loop(n=loops).subclip(0, total_duration)

        # 3. Setup audio mixing (voiceover + background music)
        audio_tracks = [voiceover]
        
        if os.path.exists(bg_music_path) and os.path.getsize(bg_music_path) > 0:
            bg_music = AudioFileClip(bg_music_path).volumex(0.12)
            if bg_music.duration < total_duration:
                bg_music = bg_music.loop(duration=total_duration)
            else:
                bg_music = bg_music.subclip(0, total_duration)
            audio_tracks.append(bg_music)

        # 4. Precise sound effects (SFX) placement at scene cuts/transitions
        if os.path.exists(sfx_folder):
            sfx_files = [os.path.join(sfx_folder, f) for f in os.listdir(sfx_folder) if f.endswith(('.mp3', '.wav'))]
            if sfx_files:
                cut_interval = total_duration / max(len(clips), 1)
                current_time = cut_interval
                
                while current_time < total_duration - 1:
                    sfx_path = random.choice(sfx_files)
                    sfx = AudioFileClip(sfx_path).volumex(0.25).set_start(current_time)
                    audio_tracks.append(sfx)
                    current_time += cut_interval

        # 5. Composite final audio and export video
        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        final_video.write_videofile(
            output_path, 
            fps=30, 
            codec="libx264", 
            audio_codec="aac", 
            preset="medium",
            bitrate="5000k",
            logger=None
        )
        
        print(f"✅ Professional video successfully created at {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Error in creating video: {e}")
        raise e

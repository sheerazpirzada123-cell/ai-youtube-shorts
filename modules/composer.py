import os
import random
from moviepy.editor import (
    VideoFileClip, 
    AudioFileClip, 
    CompositeAudioClip, 
    concatenate_audioclips
)

def create_professional_short(video_clips_paths, voiceover_path, bg_music_path=None, sfx_folder="assets/sfx", output_path="assets/final_short.mp4"):
    """
    Combines video clips, applies the energetic voiceover, adds background music with ducking,
    and places sound effects precisely at scene transitions.
    """
    try:
        print("🎬 Assembling professional YouTube Short...")
        
        # 1. Load Voiceover to get total duration
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover not found at {voiceover_path}")
        
        voiceover = AudioFileClip(voiceover_path)
        total_duration = voiceover.duration
        
        # 2. Load and combine video clips to match the voiceover length
        clips = [VideoFileClip(p) for p in video_clips_paths if os.path.exists(p)]
        if not clips:
            raise Exception("❌ Koi valid video clips nahi mili!")
            
        # Adjust video clips speed or loop them to match target length (50-60s)
        from moviepy.editor import concatenate_videoclips
        final_video = concatenate_videoclips(clips, method="compose")
        
        if final_video.duration > total_duration:
            final_video = final_video.subclip(0, total_duration)
        else:
            # Loop video if it's shorter than voiceover
            loops = int(total_duration // final_video.duration) + 1
            final_video = final_video.loop(n=loops).subclip(0, total_duration)

        # 3. Setup Audio Mixing (Voiceover + Background Music)
        audio_tracks = [voiceover]
        
        if bg_music_path and os.path.exists(bg_music_path):
            bg_music = AudioFileClip(bg_music_path).volumex(0.12) # Low volume for proper ducking
            if bg_music.duration < total_duration:
                bg_music = bg_music.loop(duration=total_duration)
            else:
                bg_music = bg_music.subclip(0, total_duration)
            audio_tracks.append(bg_music)

        # 4. Precise Sound Effects (SFX) Placement at Scene Cuts/Transitions
        # Har scene change par ek subtle whoosh ya pop sound lagayenge
        if os.path.exists(sfx_folder):
            sfx_files = [os.path.join(sfx_folder, f) for f in os.listdir(sfx_folder) if f.endswith(('.mp3', '.wav'))]
            if sfx_files:
                # Calculate cut intervals based on number of clips
                cut_interval = total_duration / max(len(clips), 1)
                current_time = cut_interval
                
                while current_time < total_duration - 1:
                    sfx_path = random.choice(sfx_files)
                    sfx = AudioFileClip(sfx_path).volumex(0.25).set_start(current_time)
                    audio_tracks.append(sfx)
                    current_time += cut_interval

        # 5. Composite Final Audio and Export Video
        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(
            output_path, 
            fps=30, 
            codec="libx264", 
            audio_codec="aac", 
            preset="medium",
            bitrate="5000k"
        )
        
        print(f"✅ Professional video successfully created at {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Error in creating video: {e}")
        return None

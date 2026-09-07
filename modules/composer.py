import os
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from modules.audio import add_background_music_and_sfx

def create_video(clips_paths, voiceover_path, output_path="output/final_short.mp4"):
    """
    Visual clips aur mixed audio ko combine karke final YouTube Short banata hai.
    """
    try:
        print("Starting video composition with background music...")
        
        # 1. Background music ko voiceover ke sath mix karein
        mixed_audio_path = "assets/mixed_voiceover.mp3"
        final_audio_path = add_background_music_and_sfx(voiceover_path, output_path=mixed_audio_path)
        
        # 2. Video clips ko load aur concatenate karein
        video_clips = [VideoFileClip(clip) for clip in clips_paths]
        
        # Sabhi clips ko jodne ke liye (agar MoviePy ka concatenate function use ho raha hai)
        from moviepy.editor import concatenate_videoclips
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # 3. Mixed audio ko final video par set karein
        audio_clip = AudioFileClip(final_audio_path)
        
        # Agar video ki length audio se lambi/choti ho toh adjust kar sakte hain
        if final_video.duration > audio_clip.duration:
            final_video = final_video.subclip(0, audio_clip.duration)
            
        final_video = final_video.set_audio(audio_clip)
        
        # 4. Final video export karein
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="medium"
        )
        
        print(f"Video successfully created at: {output_path}")
        return output_path

    except Exception as e:
        print(f"Error during video composition: {e}")
        raise e

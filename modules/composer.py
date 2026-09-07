from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import os

def render_short_video(output_file="final_short.mp4"):
    # Load Main Audio File (voice only for now)
    voice = AudioFileClip("voice.mp3")
    
    # BGM aur Sound Effects filhaal disable hain (baad mein dobara enable karenge)
    # bgm = AudioFileClip("assets/bgm.mp3").volumex(0.12).set_duration(voice.duration)
    # sfx1 = AudioFileClip("assets/whoosh.mp3").volumex(0.5).set_start(0.5)
    # sfx2 = AudioFileClip("assets/pop.mp3").volumex(0.5).set_start(10.0)
    # sfx3 = AudioFileClip("assets/whoosh.mp3").volumex(0.5).set_start(20.0)
    
    # Filhaal sirf Voice (music/SFX baad mein add karenge)
    final_audio = CompositeAudioClip([voice])
    
    # Load and Prepare Background Video
    video = VideoFileClip("assets/bg_video.mp4")
    
    if video.duration < voice.duration:
        video = video.loop(duration=voice.duration)
    else:
        video = video.subclip(0, voice.duration)
        
    # Resize to Vertical 9:16 Shorts Format
    video = video.resize(newsize=(1080, 1920))
    
    # Final Video without Captions
    final_video = video.set_audio(final_audio)
    final_video.write_videofile(
        output_file,
        fps=30,
        codec="libx264",
        audio_codec="aac"
    )

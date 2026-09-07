import os
from moviepy.editor import AudioFileClip, CompositeAudioClip

def generate_voiceover(text, output_path="assets/voiceover.mp3"):
    """
    Purana voiceover generation function (agar aapke project mein gTTS ya koi aur library use ho rahi hai, 
    usko yahan adjust kiya ja sakta hai. Yeh ek basic placeholder/wrapper hai).
    """
    # Agar aapka pehle se jo code hai, aap use rakh sakte hain.
    pass

def add_background_music_and_sfx(voiceover_path, output_path="assets/final_audio.mp3", bg_music_path="assets/audio/bg_music.mp3", bg_volume=0.15):
    """
    Voiceover ke sath background music mix karne ka function.
    bg_volume = 0.15 rakha hai taake music halka chale aur bolne ki awaz saaf sunai de.
    """
    try:
        # 1. Voiceover load karein
        if not os.path.exists(voiceover_path):
            raise FileNotFoundError(f"Voiceover file not found at {voiceover_path}")
            
        voiceover = AudioFileClip(voiceover_path)
        audio_clips = [voiceover]
        
        # 2. Background music load karein agar exist karti hai
        if os.path.exists(bg_music_path):
            bg_music = AudioFileClip(bg_music_path).volumex(bg_volume)
            
            # Agar music chota hai toh loop karein, warna video ki length tak trim karein
            if bg_music.duration < voiceover.duration:
                bg_music = bg_music.loop(duration=voiceover.duration)
            else:
                bg_music = bg_music.subclip(0, voiceover.duration)
                
            audio_clips.append(bg_music)
        else:
            print(f"Warning: Background music not found at {bg_music_path}. Proceeding with voiceover only.")
        
        # 3. Audio clips ko combine karein
        final_audio = CompositeAudioClip(audio_clips)
        
        # 4. Export karein
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_audio.write_audiofile(output_path, fps=44100)
        print(f"Successfully created mixed audio at {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"Error in adding background music: {e}")
        return voiceover_path

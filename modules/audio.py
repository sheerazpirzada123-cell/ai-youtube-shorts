import os


class AudioEngine:
    """
    There is NO narration/voiceover/TTS anymore — the video is a silent
    cat b-roll montage scored with background music + real cat sound
    effects only (mixed in modules/composer.py from assets/bgm/ and
    assets/sfx/).

    This class is kept only as a tiny, explicit pipeline step so main.py
    stays readable: it just makes sure the bgm/sfx folders exist and warns
    early if they're empty, instead of silently producing a video with no
    audio at all.
    """

    def __init__(self):
        self.bgm_dir = os.path.join(os.getcwd(), "assets", "bgm")
        self.sfx_dir = os.path.join(os.getcwd(), "assets", "sfx")
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.sfx_dir, exist_ok=True)

    def _has_audio_files(self, folder):
        if not os.path.isdir(folder):
            return False
        valid_ext = (".mp3", ".wav", ".m4a", ".aac")
        return any(f.lower().endswith(valid_ext) for f in os.listdir(folder))

    def check_audio_assets(self, script_data):
        """
        No-op on the script itself (nothing to generate per scene anymore —
        durations are fixed in brain.py). Just logs whether bgm/sfx are
        actually available, since a video with neither would end up
        completely silent.
        """
        has_bgm = self._has_audio_files(self.bgm_dir)
        has_sfx = self._has_audio_files(self.sfx_dir)

        if not has_bgm and not has_sfx:
            print("   ⚠️ No files in assets/bgm/ or assets/sfx/ — the final "
                  "video will have NO audio at all. Drop a royalty-free "
                  "music track into assets/bgm/ and/or cat sound clips "
                  "(meow.mp3, purr.mp3, etc) into assets/sfx/.")
        else:
            print(f"   🎵 Background music available: {has_bgm}")
            print(f"   🐱 Cat sound effects available: {has_sfx}")

        return script_data

import os
import random
import ffmpeg


class Composer:
    def __init__(self):
        self.temp_dir = os.path.join(os.getcwd(), "assets", "temp")
        self.final_dir = os.path.join(os.getcwd(), "assets", "final")
        self.bgm_dir = os.path.join(os.getcwd(), "assets", "bgm")
        # Drop short cat sound-effect clips here (meow.mp3, purr.mp3, etc —
        # royalty-free) and they get looped quietly under the music, so the
        # video has real cat audio and not just music. Safe to leave empty
        # (sfx is skipped, same as bgm being optional).
        self.sfx_dir = os.path.join(os.getcwd(), "assets", "sfx")

        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        os.makedirs(self.bgm_dir, exist_ok=True)
        os.makedirs(self.sfx_dir, exist_ok=True)
        self.transitions = ['fade', 'diagbr', 'diagtl']

    def _pick_bgm(self):
        """Returns a random BGM track from assets/bgm/, or None if empty."""
        if not os.path.isdir(self.bgm_dir):
            return None
        valid_ext = (".mp3", ".wav", ".m4a", ".aac")
        tracks = [
            os.path.join(self.bgm_dir, f) for f in os.listdir(self.bgm_dir)
            if f.lower().endswith(valid_ext)
        ]
        return random.choice(tracks) if tracks else None

    def _pick_sfx(self):
        """Returns a random cat sound-effect clip from assets/sfx/, or None if empty."""
        if not os.path.isdir(self.sfx_dir):
            return None
        valid_ext = (".mp3", ".wav", ".m4a", ".aac")
        clips = [
            os.path.join(self.sfx_dir, f) for f in os.listdir(self.sfx_dir)
            if f.lower().endswith(valid_ext)
        ]
        return random.choice(clips) if clips else None

    def get_duration(self, filepath):
        try:
            probe = ffmpeg.probe(filepath)
            return float(probe['format']['duration'])
        except:
            return 0.0

    def process_scene(self, scene, video_pair):
        """
        Renders ONE silent (video-only) scene: 50/50 A/B split between the
        two clips fetched for this scene (Pixabay animation -> Pexels
        fallback, see asset_manager.py), scaled/cropped to portrait.

        There is no voiceover anymore, so no audio is attached here at
        all — music + cat sfx are mixed once, over the WHOLE final video,
        in concatenate_with_transitions() below. That's simpler and avoids
        the music restarting/clicking at every scene cut.
        """
        scene_id = scene['id']
        total_duration = scene['duration']
        output_path = os.path.join(self.temp_dir, f"scene_{scene_id}.mp4")

        try:
            path_a, path_b = video_pair

            duration_a = total_duration / 2
            duration_b = (total_duration / 2) + 0.5

            stream_a = (
                ffmpeg.input(path_a, stream_loop=-1)
                .trim(duration=duration_a)
                .setpts('PTS-STARTPTS')
                .filter('scale', 1080, 1920).filter('crop', 1080, 1920)
                .filter('fps', fps=30, round='up')
            )

            stream_b = (
                ffmpeg.input(path_b, stream_loop=-1)
                .trim(duration=duration_b)
                .setpts('PTS-STARTPTS')
                .filter('scale', 1080, 1920).filter('crop', 1080, 1920)
                .filter('fps', fps=30, round='up')
            )

            video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            runner = ffmpeg.output(
                video_stream,
                output_path,
                vcodec='libx264',
                pix_fmt='yuv420p',
            )

            runner.run(overwrite_output=True, quiet=True)
            return output_path

        except ffmpeg.Error as e:
            print(f"❌ Render Fail Scene {scene_id}: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None

    def render_all_scenes(self, script_data, video_pairs):
        """Renders each scene's silent video clip."""
        rendered_paths = []

        for i, scene in enumerate(script_data):
            current_pair = video_pairs[i]
            if current_pair is None:
                continue

            output_path = self.process_scene(scene, current_pair)
            if output_path:
                rendered_paths.append(output_path)

        return rendered_paths

    def concatenate_with_transitions(self, video_paths, output_filename="final_short.mp4"):
        """
        Stitches the silent rendered scenes together with video transitions,
        then lays a SINGLE continuous audio track over the whole thing:
        looped background music (assets/bgm/) mixed with a looped cat
        sound-effect clip (assets/sfx/), both optional. Doing this once at
        the end (rather than per scene) avoids the music restarting/
        clicking at every cut.
        INCLUDES FIXES FOR: Windows 0x80004005 Error & Playback Issues.
        """
        print("🎬 Stitching final video...")
        output_path = os.path.join(self.final_dir, output_filename)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                print("⚠️ Warning: Could not delete old file. It might be open in a player.")

        if not video_paths:
            return None

        input1 = ffmpeg.input(video_paths[0])
        v_stream = input1.video

        current_dur = self.get_duration(video_paths[0])

        for i in range(1, len(video_paths)):
            next_clip = ffmpeg.input(video_paths[i])
            next_dur = self.get_duration(video_paths[i])

            trans_dur = 0.5
            offset = current_dur - trans_dur

            effect = random.choice(self.transitions)
            print(f"   ✨ Transition {i}: '{effect}' at {offset:.2f}s")

            v_stream = ffmpeg.filter(
                [v_stream, next_clip.video],
                'xfade',
                transition=effect,
                duration=trans_dur,
                offset=offset
            )

            current_dur = (current_dur + next_dur) - trans_dur

        total_duration = current_dur

        # Build the final audio track: music + cat sound effects only (no
        # narration). Both are optional and looped/trimmed to the final
        # video's total length.
        bgm_path = self._pick_bgm()
        sfx_path = self._pick_sfx()
        audio_tracks = []

        if bgm_path:
            print(f"   🎵 Adding background music: {os.path.basename(bgm_path)}")
            audio_tracks.append(
                ffmpeg.input(bgm_path, stream_loop=-1)
                .filter('atrim', duration=total_duration)
                .filter('asetpts', 'PTS-STARTPTS')
                .filter('volume', 0.5)
            )
        else:
            print("   ℹ️ No background music found in assets/bgm/ — skipping BGM "
                  "(add a royalty-free instrumental .mp3 there to enable it).")

        if sfx_path:
            print(f"   🐱 Adding cat sound effects: {os.path.basename(sfx_path)}")
            audio_tracks.append(
                ffmpeg.input(sfx_path, stream_loop=-1)
                .filter('atrim', duration=total_duration)
                .filter('asetpts', 'PTS-STARTPTS')
                .filter('volume', 0.7)
            )
        else:
            print("   ℹ️ No cat sound effects found in assets/sfx/ — skipping "
                  "(add meow/purr .mp3 clips there to enable real cat audio).")

        if len(audio_tracks) == 2:
            a_stream = ffmpeg.filter(audio_tracks, 'amix', inputs=2, duration='first', dropout_transition=2)
        elif len(audio_tracks) == 1:
            a_stream = audio_tracks[0]
        else:
            # Neither bgm nor sfx available — output a silent track so the
            # video still has a valid (silent) audio stream instead of none.
            a_stream = ffmpeg.input(
                'anullsrc=channel_layout=stereo:sample_rate=44100', f='lavfi', t=total_duration
            )

        try:
            output_kwargs = dict(
                vcodec='libx264',   # Standard H.264 video
                acodec='aac',       # Standard AAC audio
                pix_fmt='yuv420p',  # 🔥 FIX 1: Windows compatibility
                movflags='faststart', # 🔥 FIX 2: Corruption fix
                preset='medium',
            )
            runner = ffmpeg.output(v_stream, a_stream, output_path, **output_kwargs)

            runner.run(overwrite_output=True, quiet=False)

            print(f"✅ FINAL VIDEO SAVED: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            error_log = e.stderr.decode('utf8') if e.stderr else str(e)
            print(f"❌ Stitching Error: {error_log}")
            return None

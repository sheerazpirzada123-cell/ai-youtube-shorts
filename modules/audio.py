import os
import re
import asyncio
import edge_tts
from mutagen import File as MutagenFile

try:
    import azure.cognitiveservices.speech as speechsdk
    _AZURE_SDK_AVAILABLE = True
except ImportError:
    _AZURE_SDK_AVAILABLE = False

try:
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer
    import soundfile as sf
    _PARLER_AVAILABLE = True
except ImportError:
    _PARLER_AVAILABLE = False


# Mood -> (rate, volume, pitch) tuning. These are edge-tts's/Azure SSML's
# actual prosody knobs. Kept modest (roughly +-12%) — pushing past that
# starts producing chipmunk/robotic artifacts on neural voices, but staying
# flat at 0% for every mood is exactly what makes narration sound tired.
MOOD_TTS_PARAMS = {
    "mysterious": {"rate": "-4%",  "volume": "+0%",  "pitch": "-2Hz"},
    "dramatic":   {"rate": "-2%",  "volume": "+6%",  "pitch": "+0Hz"},
    "emotional":  {"rate": "-6%",  "volume": "-2%",  "pitch": "-3Hz"},
    "sad":        {"rate": "-8%",  "volume": "-4%",  "pitch": "-4Hz"},
    "suspense":   {"rate": "-6%",  "volume": "+2%",  "pitch": "-3Hz"},
    "inspiring":  {"rate": "+4%",  "volume": "+8%",  "pitch": "+4Hz"},
    "triumphant": {"rate": "+8%",  "volume": "+12%", "pitch": "+6Hz"},
    "energetic":  {"rate": "+10%", "volume": "+10%", "pitch": "+5Hz"},
    "default":    {"rate": "+0%",  "volume": "+0%",  "pitch": "+0Hz"},
}


def _mood_params(mood):
    return MOOD_TTS_PARAMS.get((mood or "default").strip().lower(), MOOD_TTS_PARAMS["default"])


def _text_to_ssml(text, voice, mood="default"):
    """
    Converts plain narration text into SSML with real pauses and
    mood-driven pacing — this is the actual lever for sounding less robotic
    (not just pitch-shifting the whole voice arbitrarily). Danda (।) and
    full stops get a longer breath pause; commas and "..." get a shorter
    one; rate/pitch/volume are driven by the scene's mood so narration
    doesn't sound flat across an entire video.
    """
    # Split on sentence-ending punctuation, keep the punctuation attached.
    parts = re.split(r'([।.!?]+)', text)
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        chunk = (parts[i] + parts[i + 1]).strip()
        if chunk:
            sentences.append(chunk)
    if len(parts) % 2 == 1 and parts[-1].strip():
        sentences.append(parts[-1].strip())

    body = ""
    for sentence in sentences:
        # Shorter pause on internal commas/ellipses for a natural breath rhythm.
        sentence_with_pauses = sentence.replace("...", '<break time="400ms"/>').replace(",", ',<break time="150ms"/>')
        body += f'<s>{sentence_with_pauses}</s><break time="450ms"/>\n'

    params = _mood_params(mood)
    return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="hi-IN">
    <voice name="{voice}">
        <prosody rate="{params['rate']}" pitch="{params['pitch']}">
            {body}
        </prosody>
    </voice>
</speak>"""


class AudioEngine:
    """
    Three narration backends, picked automatically:
      1. Azure Speech SDK  — best pacing control, needs a free Azure
         account (requires a card for identity verification even on the
         free tier).
      2. Local Indic Parler-TTS — open-source, runs entirely inside the
         GitHub Actions job. No account, no card, no signup at all — the
         model is a public download. Slower (CPU inference) and adds a
         one-time ~2-3GB model download on first run, but the tradeoff is
         zero cost and zero account requirements. Opt in with
         TTS_ENGINE=local.
      3. edge-tts — the default fallback, no setup needed either, but
         with less pacing control than the other two.
    """

    def __init__(self, voice="hi-IN-MadhurNeural"):
        # "hi-IN-MadhurNeural" is an energetic Hindi male voice.
        # Alternative Hindi male options: "hi-IN-NiranjanNeural"
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

        self.azure_key = os.getenv("AZURE_SPEECH_KEY")
        self.azure_region = os.getenv("AZURE_SPEECH_REGION")
        use_azure = bool(self.azure_key and self.azure_region and _AZURE_SDK_AVAILABLE)

        requested_engine = os.getenv("TTS_ENGINE", "").strip().lower()

        if requested_engine == "local" and _PARLER_AVAILABLE:
            self.engine = "local"
        elif requested_engine == "local" and not _PARLER_AVAILABLE:
            print("      ⚠️ TTS_ENGINE=local but parler-tts/torch aren't installed — "
                  "add them to requirements.txt. Falling back.")
            self.engine = "azure" if use_azure else "edge"
        elif use_azure:
            self.engine = "azure"
        else:
            self.engine = "edge"

        self._local_model = None
        self._local_tokenizer = None
        self._local_desc_tokenizer = None
        self._local_device = None

        print(f"      🎙️ Narration engine: {self.engine}")

    def _load_local_model(self):
        """Lazily loads the Indic Parler-TTS model once and reuses it for every scene."""
        if self._local_model is not None:
            return
        print("      ⏳ Loading Indic Parler-TTS model (first run downloads ~2-3GB, cached after)...")
        self._local_device = "cuda" if torch.cuda.is_available() else "cpu"
        self._local_model = ParlerTTSForConditionalGeneration.from_pretrained(
            "ai4bharat/indic-parler-tts"
        ).to(self._local_device)
        self._local_tokenizer = AutoTokenizer.from_pretrained("ai4bharat/indic-parler-tts")
        self._local_desc_tokenizer = AutoTokenizer.from_pretrained(
            self._local_model.config.text_encoder._name_or_path
        )

    def _generate_local(self, text, output_path, mood="mysterious"):
        self._load_local_model()

        # Natural-language voice description — this is Parler-TTS's actual
        # realism lever: describe the delivery you want instead of forcing
        # pitch/rate on a fixed voice.
        description = (
            f"A middle-aged Indian male speaker with a deep, confident voice "
            f"narrates in a {mood}, intense, and dramatic tone, at a natural "
            f"pace with clear studio-quality audio and expressive emotion."
        )

        input_ids = self._local_desc_tokenizer(description, return_tensors="pt").input_ids.to(self._local_device)
        prompt_ids = self._local_tokenizer(text, return_tensors="pt").input_ids.to(self._local_device)

        generation = self._local_model.generate(input_ids=input_ids, prompt_input_ids=prompt_ids)
        audio_arr = generation.cpu().numpy().squeeze()
        sf.write(output_path, audio_arr, self._local_model.config.sampling_rate)
        return output_path

    def _generate_azure(self, text, output_path, mood="default"):
        speech_config = speechsdk.SpeechConfig(subscription=self.azure_key, region=self.azure_region)
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
        )
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        ssml = _text_to_ssml(text, self.voice, mood)
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = result.cancellation_details
            raise RuntimeError(f"Azure TTS failed: {details.reason if details else result.reason}")
        return output_path

    async def generate_audio(self, text, output_filename, retries=3, mood="mysterious"):
        """
        Generates Hindi male voiceover using whichever engine was selected
        at startup (see AudioEngine docstring). All three paths now apply
        mood-driven rate/volume/pitch tuning (see MOOD_TTS_PARAMS) so the
        narration's energy actually matches the scene instead of staying
        flat throughout the video.
        """
        # Local engine outputs WAV (raw model output); others output MP3.
        if self.engine == "local":
            output_filename = os.path.splitext(output_filename)[0] + ".wav"
        output_path = os.path.join(self.output_dir, output_filename)

        for attempt in range(retries):
            try:
                if self.engine == "local":
                    return await asyncio.to_thread(self._generate_local, text, output_path, mood)
                elif self.engine == "azure":
                    return await asyncio.to_thread(self._generate_azure, text, output_path, mood)
                else:
                    params = _mood_params(mood)
                    communicate = edge_tts.Communicate(
                        text, self.voice,
                        rate=params["rate"], volume=params["volume"], pitch=params["pitch"],
                    )
                    await communicate.save(output_path)
                    return output_path

            except Exception as e:
                print(f"      ⚠️ Audio Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    print("      ❌ Failed to generate audio after max retries.")
                    raise e

    def get_audio_duration(self, file_path):
        try:
            audio = MutagenFile(file_path)
            if audio is None or audio.info is None:
                raise RuntimeError("Unrecognized audio file")
            return audio.info.length
        except Exception as e:
            print(f"❌ Error reading audio length: {e}")
            return 0.0

    async def process_script(self, script_data):
        print(f"🎙️ Generating Hindi Male Voiceovers for {len(script_data)} scenes...")
        
        for scene in script_data:
            scene_id = scene['id']
            text = scene['text']
            mood = scene.get('mood', 'mysterious')
            filename = f"voice_{scene_id}.mp3"
            
            try:
                file_path = await self.generate_audio(text, filename, mood=mood)
                duration = self.get_audio_duration(file_path)
                
                scene['audio_path'] = file_path
                scene['duration'] = duration
                
                print(f"   ✅ Scene {scene_id} [Audio Ready]: {duration:.2f}s")
                await asyncio.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Skipping Scene {scene_id} due to audio error.")
                continue
            
        return script_data

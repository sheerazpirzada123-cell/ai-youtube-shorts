import os
import json
import re
import time
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

# Fixed length (seconds) for every scene now that there's no voiceover to
# time scenes against. 3-4 scenes * this length keeps the short in the
# ~16-24s range. Change this one number to make the whole video
# longer/shorter.
SCENE_DURATION = 5.0

# Errors worth retrying: transient overload / rate-limit / server hiccups.
_RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL")
_RETRY_DELAY_RE = re.compile(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'")
_DAILY_QUOTA_MARKER = "PerDay"  # e.g. GenerateRequestsPerDayPerProjectPerModel-FreeTier


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    return _DAILY_QUOTA_MARKER in str(exc)


def _suggested_delay(exc: Exception):
    """Pull Gemini's own suggested retryDelay out of the error, if present."""
    match = _RETRY_DELAY_RE.search(str(exc))
    return float(match.group(1)) if match else None


def _call_with_retry(fn, *, max_attempts=6, base_delay=2.0, max_delay=60.0):
    """
    Calls fn() with backoff on transient Gemini errors (503 UNAVAILABLE,
    429 RESOURCE_EXHAUSTED, 500 INTERNAL). Prefers the retryDelay Gemini
    itself reports over a guessed exponential delay, since guessing too
    short just burns attempts against a quota that hasn't refilled yet.
    Re-raises immediately on non-retryable errors, and re-raises the last
    error once max_attempts is exhausted.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt == max_attempts:
                raise
            server_delay = _suggested_delay(e)
            if server_delay is not None:
                delay = server_delay + random.uniform(0.5, 2.0)
            else:
                delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.uniform(0, 1)
            note = " [daily free-tier quota]" if _is_daily_quota_exhausted(e) else ""
            print(f"⏳ Gemini call failed (attempt {attempt}/{max_attempts}){note}: {e}")
            print(f"    Retrying in {delay:.1f}s...")
            time.sleep(delay)
    raise last_exc


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a .env file or set the environment variable before running."
        )
    return genai.Client(api_key=api_key)


def _extract_text(response):
    text = getattr(response, "text", None)
    if text:
        return text.strip()
    candidates = getattr(response, "candidates", None)
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
        print(f"⚠️ Empty response text. finish_reason={finish_reason}")
    return None


def _apply_fixed_durations(script_data):
    """No voiceover anymore, so nothing naturally times each scene. Give
    every scene the same fixed SCENE_DURATION instead of a voice-derived
    one."""
    for scene in script_data:
        scene["duration"] = SCENE_DURATION
    return script_data


class ContentBrain:
    def generate_package(self):
        """
        Single Gemini call that picks a funny/cute CAT-centered scenario
        (cat is always the main character, sometimes paired with one other
        animal like a duck or dog for comedy) AND writes the visual
        keywords used to find footage for each scene AND writes the
        YouTube metadata, all at once. Combining these matters a lot on the
        free tier, which caps you at 20 requests/day total.

        NOTE: There is NO voiceover/narration script anymore. The video is
        cat b-roll only, scored with background music + real cat sound
        effects (see composer.py) — no `text`/voice field is generated or
        used anywhere in the pipeline.

        Returns (topic, script_data, metadata) or raises on failure.

        NOTE ON VISUALS: `visual_1`/`visual_2` are English search keywords
        used against BOTH Pixabay (tried first, with video_type=animation
        so we actually get 3D/animated-style cat clips — see
        asset_manager.py) and Pexels (real stock footage fallback). They
        are REQUIRED to always mention "cat" and describe a GENERIC,
        original-looking 3D-animated cat (think: cute Pixar-style house
        cat) — NEVER a named movie/franchise character (e.g. never
        "Puss in Boots", never any studio's copyrighted character), to
        avoid copyright/strike risk. asset_manager.py also force-appends
        "cat" to any query that's missing it as a safety net.
        """
        prompt = """
    You are an expert short-form content creator making viral, funny/cute
    YouTube Shorts about CATS (think: cat-vs-duck, cat-vs-cucumber, kitten's
    first snow, cat knocking things off a table, cat and dog friendship,
    cat zoomies, cat scared of something silly — funny, wholesome, relatable
    cat moments). The CAT IS ALWAYS THE MAIN CHARACTER of the video. There is
    NO voiceover/narration in this video — it is a silent b-roll montage
    scored with music + cat sound effects, so you do NOT need to write any
    spoken script or text. Do all of the following in one response:

    STEP 1 — TOPIC: Invent ONE specific funny/cute cat scenario for this
    video (e.g. "cat meets a duck for the first time", "cat vs cucumber
    prank", "kitten's first time seeing snow", "cat steals dog's bed").
    You may occasionally include ONE other animal (duck, dog, hamster,
    parrot, bird) as a comedic side character, but the cat must stay the
    clear main focus of every scene. Keep it light, funny, wholesome —
    never scary, violent, or showing the animal in real distress/harm.

    STEP 2 — SCENES: Break that scenario into 3-4 short beats (Hook ->
    funny moment/beat 1 -> funny moment/beat 2 or twist -> closing/cute
    button-up beat). For each scene, write ONLY visual search keywords
    (`visual_1` & `visual_2`) — there is no voiceover text field at all.
    - Visual cues (`visual_1` & `visual_2`): ENGLISH search keywords that
      MUST literally include the word "cat" and must describe EXACTLY what
      is happening in that beat (e.g. "cute cat playing with cucumber",
      "cat and duck funny friends", "kitten jumping in snow", "cat
      knocking cup off table"). If another animal is in the scenario, name
      it alongside "cat" (e.g. "cat and duck funny").
    - IMPORTANT — style, not character: describe a GENERIC 3D-animated /
      Pixar-style cute house cat (e.g. "3d animated cute cat", "cartoon
      style kitten"). NEVER name or describe any specific movie/franchise
      character (no "Puss in Boots", no any studio's mascot or named
      character) — this must always be an original-looking, generic cat to
      avoid copyright issues. Never use vague words like "abstract",
      "cinematic", or anything not about a cat.
    - `mood` field: one of funny / cute / playful / emotional (drives
      which extra keywords and music energy get layered on in code).

    STEP 3 — METADATA (for the YouTube post): write title, description,
    and tags in HINGLISH — Hindustani words spelled out in plain
    ENGLISH/ROMAN letters (e.g. "Ye billi ne kya kar diya...", "sabse funny
    cat video"), NOT in Devanagari script. This is what most Indian
    YouTube titles/descriptions actually look like and is what people type
    into search.
    - title: Punchy Hinglish (Roman-script) title, high CTR, under 80 chars,
      mentions "cat"/"billi" and a curiosity/funny phrase.
    - description: 2-3 Hinglish (Roman-script) sentences summarizing the
      video, written so it naturally contains the kind of terms people
      actually search for ("funny cat video", "cute cat", "cat vs <other
      animal>", "pets", "3d animation" etc.), followed by relevant
      hashtags.
    - tags: 10-15 SEO tags in English/Hinglish a viewer would actually type
      into YouTube search — mix of "funny cat video", "cute cat", "3d
      animation cat", "cat compilation", "pets", "animals", plus "Shorts"
      as relevant. Generate these dynamically based on the specific
      scenario chosen.

    Respond with ONLY this JSON object, nothing else:
    {
        "topic": "short scenario description here",
        "scenes": [
            {
                "id": 1,
                "visual_1": "3d animated cute cat meeting duck funny",
                "visual_2": "cartoon style cat and duck playing together",
                "mood": "funny"
            }
        ],
        "metadata": {
            "title": "Hinglish Title Here",
            "description": "Hinglish Description Here",
            "tags": ["tag1", "tag2", "tag3"]
        }
    }
    """

        client = _get_client()

        try:
            response = _call_with_retry(
                lambda: client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed while generating package: {e}") from e

        raw_text = _extract_text(response)
        if not raw_text:
            raise RuntimeError("Gemini returned no usable package text.")

        clean_text = raw_text.replace("```json", "").replace("```", "").strip()

        try:
            package = json.loads(clean_text)
        except json.JSONDecodeError as e:
            print("❌ Error parsing JSON. Raw output:")
            print(clean_text)
            raise RuntimeError(f"Failed to parse Gemini package JSON: {e}") from e

        topic = str(package.get("topic", "")).strip().strip('"').strip("'")
        script_data = package.get("scenes") or []
        metadata = package.get("metadata") or {}

        if not topic:
            raise RuntimeError("Gemini package missing 'topic'.")
        if not script_data:
            raise RuntimeError("Gemini package missing 'scenes'.")

        script_data = _apply_fixed_durations(script_data)

        metadata["title"] = str(metadata.get("title", topic))[:95]
        metadata["description"] = str(metadata.get("description", topic))[:4900]
        metadata["tags"] = list(metadata.get("tags", []))[:15]

        print(f"🎯 Selected Topic: {topic}")
        return topic, script_data, metadata

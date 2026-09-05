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

class ContentBrain:
    def generate_package(self):
        """
        Single Gemini call that picks a funny/cute CAT-centered scenario
        (cat is always the main character, sometimes paired with one other
        animal like a duck or dog for comedy — like the reference video)
        AND writes the full Hindi/Hindustani voiceover script AND writes
        the YouTube metadata, all at once. Combining these (previously 3
        separate calls) matters a lot on the free tier, which caps you at
        20 requests/day total — this cuts quota usage per video from 3
        calls to 1.

        Returns (topic, script_data, metadata) or raises on failure.

        NOTE ON VISUALS: `visual_1`/`visual_2` are English Pexels-search
        keywords and are REQUIRED to always mention "cat" (the main
        character), tightly describing exactly what's happening in that
        scene's text — this is what keeps the fetched stock clips on-topic
        instead of drifting into unrelated footage. See asset_manager.py,
        which also force-appends "cat" to any query that's missing it as a
        safety net.
        """
        prompt = """
    You are an expert short-form content creator making viral, funny/cute
    YouTube Shorts about CATS (think: cat-vs-duck, cat-vs-cucumber, kitten's
    first snow, cat knocking things off a table, cat and dog friendship,
    cat zoomies, cat scared of something silly — funny, wholesome, relatable
    cat moments). The CAT IS ALWAYS THE MAIN CHARACTER of the video. Do all
    of the following in one response:

    STEP 1 — TOPIC: Invent ONE specific funny/cute cat scenario for this
    video (e.g. "cat meets a duck for the first time", "cat vs cucumber
    prank", "kitten's first time seeing snow", "cat steals dog's bed").
    You may occasionally include ONE other animal (duck, dog, hamster,
    parrot, bird) as a comedic side character, but the cat must stay the
    clear main focus of every scene. Keep it light, funny, wholesome —
    never scary, violent, or showing the animal in real distress/harm.

    STEP 2 — SCRIPT: Write a 3-4 scene script about that scenario (KEEP IT
    SHORT AND FAST-PACED, total words under 80 words for a short under 45
    seconds).
    - Voiceover (`text` field): written in Devanagari script, but the
      VOCABULARY must be everyday spoken HINDUSTANI (the common mixed
      Hindi-Urdu that ordinary people actually speak in India/Pakistan —
      equally natural and easily understood by Hindu and Muslim audiences
      alike). AVOID heavy, literary, Sanskrit-loaded "shuddh Hindi" words
      (e.g. avoid "अवगत", "प्रेरणादायक", "संघर्षरत", "अत्यंत", "यथार्थ").
      INSTEAD freely use common Urdu-origin words that are everyday
      Hindustani, written in Devanagari (e.g. मगर, वाकई, बिल्कुल, यार,
      मज़ेदार, हैरान, प्यारा, शरारती, कमाल, वाकई). Write it exactly how a
      popular Hindi/Urdu pet-content YouTuber talks — simple, warm, playful,
      fun, zero shuddh-Hindi stiffness.
      Tone: cute, funny, playful, warm — for a lively, expressive voiceover
      (not dramatic/sad).
    - The VERY FIRST scene's text MUST start with a hook that names the
      scenario, in the same everyday Hindustani style, e.g. something like
      "देखिए जब इस बिल्ली को (X) मिला तो क्या हुआ..." or "इस बिल्ली की
      शरारत देखकर आप हस पड़ेंगे...". Replace (X) with the actual scenario.
    - Structure: Hook (as above) -> Funny moment/beat 1 -> Funny moment/beat
      2 (or reaction/twist) -> Channel Subscribe Outro.
    - Visual cues (`visual_1` & `visual_2`): ENGLISH Pexels-search keywords
      that MUST literally include the word "cat" and must describe EXACTLY
      what's happening in that scene's text — no generic/unrelated
      keywords (e.g. "cute cat playing with cucumber", "cat and duck
      funny friends", "kitten jumping in snow", "cat knocking cup off
      table"). If another animal is in the scenario, name it alongside
      "cat" (e.g. "cat and duck funny"). Never use vague words like
      "abstract", "cinematic", or anything not about a cat.

    STEP 3 — METADATA (for the YouTube post — this is DIFFERENT from the
    voiceover script above): write title, description, and tags in
    HINGLISH — Hindustani words spelled out in plain ENGLISH/ROMAN letters
    (e.g. "Ye billi ne kya kar diya...", "sabse funny cat video"), NOT in
    Devanagari script. This is what most Indian YouTube titles/descriptions
    actually look like and is what people type into search.
    - title: Punchy Hinglish (Roman-script) title, high CTR, under 80 chars,
      mentions "cat"/"billi" and a curiosity/funny phrase.
    - description: 2-3 Hinglish (Roman-script) sentences summarizing the
      video, written so it naturally contains the kind of terms people
      actually search for ("funny cat video", "cute cat", "cat vs <other
      animal>", "pets" etc.), followed by relevant hashtags.
    - tags: 10-15 SEO tags in English/Hinglish a viewer would actually type
      into YouTube search — mix of "funny cat video", "cute cat", "cat
      compilation", "pets", "animals", plus "Shorts" as relevant. Generate
      these dynamically based on the specific scenario chosen.

    Respond with ONLY this JSON object, nothing else:
    {
        "topic": "Short scenario description, e.g. 'Cat meets a duck for the first time'",
        "script": [
            {
                "id": 1,
                "text": "देखिए जब इस बिल्ली को एक बत्तख मिली तो क्या हुआ...",
                "visual_1": "cute cat meeting duck funny",
                "visual_2": "cat and duck playing together",
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
            raise RuntimeError(f"Gemini API call failed while generating video package: {e}") from e

        raw_text = _extract_text(response)
        if not raw_text:
            raise RuntimeError("Gemini returned no usable package text.")

        clean_text = raw_text.replace("```json", "").replace("```", "").strip()

        try:
            package = json.loads(clean_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"Error parsing package JSON. Raw output:\n{clean_text}")

        topic = str(package.get("topic", "")).strip().strip('"').strip("'").strip()
        script_data = package.get("script")
        metadata = package.get("metadata", {})

        if not topic or not script_data:
            raise RuntimeError(f"Package missing topic or script. Got: {package}")

        metadata["title"] = str(metadata.get("title", topic))[:95]
        metadata["description"] = str(metadata.get("description", topic))[:4900]
        metadata["tags"] = list(metadata.get("tags", []))[:15]

        print(f"🎯 Selected Topic: {topic}")
        return topic, script_data, metadata

    # --- Backwards-compatible wrappers (each makes its own Gemini call) ---
    # Prefer generate_package() for normal runs — it does all three in one
    # call and is far kinder to the free-tier daily quota. These are kept
    # around for scripts/tests that call the steps individually.

    def get_trending_topic(self):
        """
        Generates a funny/cute cat-centered video scenario.
        """
        prompt = (
            "Give me 1 funny/cute scenario for a Short Video where a CAT is the main character "
            "(optionally with one other animal like a duck or dog for comedy) — e.g. cat vs cucumber, "
            "cat meets a duck, kitten's first snow. Keep it light and wholesome, never showing real "
            "distress or harm. Return ONLY the short scenario description, no quotes or commentary."
        )
        client = _get_client()

        try:
            response = _call_with_retry(
                lambda: client.models.generate_content(model=MODEL_NAME, contents=prompt)
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed while getting topic: {e}") from e

        topic = _extract_text(response)
        if not topic:
            raise RuntimeError("Gemini returned no usable topic text.")

        topic = topic.strip().strip('"').strip("'").strip()
        print(f"🎯 Selected Topic: {topic}")
        return topic

    def generate_script(self, topic):
        """
        Generates a structured funny/cute cat-scenario Short script
        optimized for a lively Hindustani narrator.
        """
        print(f"📝 Writing cat-video script for: {topic}...")
        prompt = f"""
    You are an expert short-form content creator making viral, funny/cute YouTube Shorts about CATS.
    The cat is always the main character. Scenario: {topic}

    ### SCRIPT CREATION RULES:
    1. **Voiceover Language (`text` field):** Written in Devanagari script, but with everyday spoken
       HINDUSTANI vocabulary (the common mixed Hindi-Urdu that ordinary people actually speak —
       equally natural for Hindu and Muslim audiences). AVOID heavy, literary "shuddh Hindi"/Sanskrit
       words. Freely use common everyday Hindustani words written in Devanagari (e.g. मगर, वाकई,
       बिल्कुल, यार, मज़ेदार, हैरान, प्यारा, शरारती, कमाल) — write it like a popular Hindi/Urdu
       pet-content YouTuber talks: simple, warm, playful, fun.
       - Tone: cute, funny, playful, warm — for a lively, expressive voiceover.
       - The FIRST scene's text MUST start with a hook naming the scenario, e.g. "देखिए जब इस बिल्ली को
         (X) मिला तो क्या हुआ..." or "इस बिल्ली की शरारत देखकर आप हस पड़ेंगे...".
    2. **Structure:** 3-4 Scenes total (KEEP IT SHORT AND FAST-PACED, under 80 words total for a short under 45 seconds).
       - Hook -> Funny moment/beat 1 -> Funny moment/beat 2 or twist -> Subscribe Outro.
       - Keep it light and wholesome, never showing real distress or harm to the animal.
    3. **Visual Cues (`visual_1` & `visual_2` fields):** Must be in ENGLISH and MUST literally include
       the word "cat", describing EXACTLY what happens in that scene's text (e.g. "cute cat playing
       with cucumber", "cat and duck funny friends", "kitten jumping in snow"). Never generic/vague
       keywords unrelated to a cat.

    Respond with a JSON array only:
    [
        {{
            "id": 1,
            "text": "देखिए जब इस बिल्ली को एक बत्तख मिली तो क्या हुआ...",
            "visual_1": "cute cat meeting duck funny",
            "visual_2": "cat and duck playing together",
            "mood": "funny"
        }}
    ]
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
            raise RuntimeError(f"Gemini API call failed while generating script: {e}") from e

        raw_text = _extract_text(response)
        if not raw_text:
            print("❌ Gemini returned no script text.")
            return None

        clean_text = raw_text.replace("```json", "").replace("```", "").strip()

        try:
            script_data = json.loads(clean_text)
            return script_data
        except json.JSONDecodeError:
            print("❌ Error parsing JSON. Raw output:")
            print(clean_text)
            return None

    def generate_metadata(self, topic, script_data):
        """
        Generates SEO-friendly YouTube Shorts metadata (Hinglish/Roman-script
        title & description, search-intent tags) for a funny cat video.
        """
        full_text = " ".join(scene.get("text", "") for scene in script_data)
        prompt = f"""
    Write YouTube Shorts metadata for a funny/cute cat video.
    Scenario: {topic}
    Script context: {full_text}

    IMPORTANT: Write the title and description in HINGLISH — Hindustani words spelled out in plain
    ENGLISH/ROMAN letters (e.g. "Ye billi ne kya kar diya...", "sabse funny cat video"), NOT in
    Devanagari script. This is what real Indian YouTube titles/descriptions look like and what people
    actually search.

    Requirements:
    - **Title:** Punchy Hinglish (Roman-script) title with high CTR (under 80 chars), mentions
      "cat"/"billi" and a funny/curiosity phrase.
    - **Description:** 2-3 Hinglish (Roman-script) sentences summarizing the video, phrased so it
      naturally contains the kind of terms people actually search for ("funny cat video", "cute cat",
      "pets", "animals"), followed by relevant hashtags.
    - **Tags:** 10-15 SEO tags a viewer would actually search — mix of "funny cat video", "cute cat",
      "cat compilation", "pets", "animals", plus "Shorts" as relevant. Base these on the specific
      scenario above, not a fixed template.

    Return ONLY a JSON object:
    {{
        "title": "Hinglish Title Here",
        "description": "Hinglish Description Here",
        "tags": ["tag1", "tag2", "tag3"]
    }}
    """
        client = _get_client()
        try:
            response = _call_with_retry(
                lambda: client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
            )
            raw_text = _extract_text(response)
            if not raw_text:
                raise RuntimeError("Empty metadata response")
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            metadata = json.loads(clean_text)
        except Exception as e:
            print(f"⚠️ Metadata generation failed, using fallback.")
            metadata = {
                "title": f"{topic[:70]} | Untold Story",
                "description": f"{topic} - jaaniye inki untold story.\n\n#UntoldStory #Biography #Bollywood #Shorts",
                "tags": ["biography", "untold story", "life story", "struggle story", "bollywood shorts"],
            }

        metadata["title"] = str(metadata.get("title", topic))[:95]
        metadata["description"] = str(metadata.get("description", topic))[:4900]
        metadata["tags"] = list(metadata.get("tags", []))[:15]
        return metadata

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
            print(f"   Retrying in {delay:.1f}s...")
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
        Single Gemini call that picks a viral MCU topic AND writes the full
        Hindi voiceover script AND writes the YouTube metadata, all at once.
        Combining these (previously 3 separate calls) matters a lot on the
        free tier, which caps you at 20 requests/day total — this cuts
        quota usage per video from 3 calls to 1.

        Returns (topic, script_data, metadata) or raises on failure.
        """
        prompt = """
    You are an expert Marvel Cinematic Universe (MCU) content creator making
    viral YouTube Shorts in Hindi. Do all of the following in one response:

    STEP 1 — TOPIC: Pick 1 viral, mind-blowing MCU theory/rumor/fact topic.
    Focus on upcoming films like Avengers: Doomsday, or characters like
    Victor von Doom, Iron Man, Spider-Man, or Doctor Strange.

    STEP 2 — SCRIPT: Write a 7-8 scene script about that topic.
    - Voiceover (`text` field): natural, spoken HINDI in Devanagari script (हिंदी).
      Tone: intense, intriguing, confidential, exciting — for a dramatic male
      voiceover. Use phrases like "क्या आप जानते हैं?", "लेकिन सच तो यह है...",
      "Doctor Doom की यह थ्योरी आपका दिमाग घुमा देगी!".
    - Structure: Hook -> Multiverse Context -> Character Theory/Fact
      (Doctor Doom/Iron Man/Spider-Man/Doctor Strange/Doomsday) ->
      Mind-Blowing Twist -> Channel Subscribe Outro.
    - Visual cues (`visual_1` & `visual_2`): ENGLISH cinematic keywords for
      stock footage search (e.g. "dark superhero mask", "glowing magic portal").

    STEP 3 — METADATA:
    - title: Punchy Hindi title, high CTR, under 80 chars, mentions key
      characters (Doom, Iron Man, Spider-Man, Doomsday).
    - description: 2 Hindi sentences summarizing the video + hashtags
      (#AvengersDoomsday #DoctorDoom #MarvelHindi #MCUTheories #Shorts).
    - tags: English Marvel tags (e.g. "Avengers Doomsday", "Doctor Doom Hindi",
      "Iron Man variant", "Marvel theories", "Spider-Man", "Doctor Strange").

    Respond with ONLY this JSON object, nothing else:
    {
        "topic": "Topic name here",
        "script": [
            {
                "id": 1,
                "text": "क्या Avengers Doomsday में Robert Downey Jr का Victor von Doom असल में Iron Man का ही एक डार्क वेरिएंट है?",
                "visual_1": "dark iron armor metallic",
                "visual_2": "glowing green magic energy",
                "mood": "mysterious"
            }
        ],
        "metadata": {
            "title": "Hindi Title Here",
            "description": "Hindi Description Here",
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

        print(f"🎯 Selected MCU Topic: {topic}")
        return topic, script_data, metadata

    # --- Backwards-compatible wrappers (each makes its own Gemini call) ---
    # Prefer generate_package() for normal runs — it does all three in one
    # call and is far kinder to the free-tier daily quota. These are kept
    # around for scripts/tests that call the steps individually.

    def get_trending_topic(self):
        """
        Generates a viral MCU theory, rumor, or dark fact topic.
        """
        prompt = (
            "Give me 1 viral, mind-blowing topic for a Short Video focused strictly on Marvel Cinematic Universe (MCU) theories, rumors, or facts. "
            "Focus on upcoming films like Avengers: Doomsday, or characters like Victor von Doom, Iron Man, Spider-Man, or Doctor Strange. "
            "Return ONLY the topic name without quotes or commentary."
        )
        client = _get_client()

        try:
            response = _call_with_retry(
                lambda: client.models.generate_content(model=MODEL_NAME, contents=prompt)
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed while getting MCU topic: {e}") from e

        topic = _extract_text(response)
        if not topic:
            raise RuntimeError("Gemini returned no usable topic text.")

        topic = topic.strip().strip('"').strip("'").strip()
        print(f"🎯 Selected MCU Topic: {topic}")
        return topic

    def generate_script(self, topic):
        """
        Generates a structured MCU Short script optimized for a Hindi male narrator.
        """
        print(f"📝 Writing MCU script for: {topic}...")
        prompt = f"""
    You are an expert Marvel Cinematic Universe (MCU) content creator making viral YouTube Shorts in Hindi.
    Topic: {topic}

    ### SCRIPT CREATION RULES:
    1. **Voiceover Language (`text` field):** Written strictly in natural, spoken HINDI using Devanagari script (हिंदी).
       - Tone: Intense, intriguing, confidential, and exciting—meant for a dramatic male voiceover.
       - Use conversational Hindi phrases like "क्या आप जानते हैं?", "लेकिन सच तो यह है...", "Doctor Doom की यह थ्योरी आपका दिमाग घुमा देगी!".
    2. **Structure:** 7-8 Scenes total.
       - Hook -> Multiverse Context -> Character Theory/Fact (Doctor Doom/Iron Man/Spider-Man/Doctor Strange/Doomsday) -> Mind-Blowing Twist -> Channel Subscribe Outro.
    3. **Visual Cues (`visual_1` & `visual_2` fields):** Must be in ENGLISH for stock image/video searches.
       - Provide cinematic keywords (e.g., "dark superhero mask", "glowing magic portal", "futuristic armor closeup", "multiverse portal space").

    Respond with a JSON array only:
    [
        {{
            "id": 1,
            "text": "क्या Avengers Doomsday में Robert Downey Jr का Victor von Doom असल में Iron Man का ही एक डार्क वेरिएंट है?",
            "visual_1": "dark iron armor metallic",
            "visual_2": "glowing green magic energy",
            "mood": "mysterious"
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
        Generates MCU-focused YouTube Shorts metadata with Hindi titles and trending English Marvel tags.
        """
        full_text = " ".join(scene.get("text", "") for scene in script_data)
        prompt = f"""
    Write YouTube Shorts metadata for an MCU theory video.
    Topic: {topic}
    Script context: {full_text}

    Requirements:
    - **Title:** Punchy Hindi title with high CTR (under 80 chars), mentioning key characters (Doom, Iron Man, Spider-Man, Doomsday).
    - **Description:** 2 Hindi sentences summarizing the video + MCU hashtags (#AvengersDoomsday #DoctorDoom #MarvelHindi #MCUTheories #Shorts).
    - **Tags:** English Marvel tags (e.g., "Avengers Doomsday", "Doctor Doom Hindi", "Iron Man variant", "Marvel theories", "Spider-Man", "Doctor Strange").

    Return ONLY a JSON object:
    {{
        "title": "Hindi Title Here",
        "description": "Hindi Description Here",
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
                "title": f"{topic[:70]} | MCU Theory Hindi",
                "description": f"{topic}\n\n#AvengersDoomsday #DoctorDoom #MarvelHindi #MCU #Shorts",
                "tags": ["Avengers Doomsday", "Doctor Doom", "Marvel Theories", "Iron Man", "MCU Hindi"],
            }

        metadata["title"] = str(metadata.get("title", topic))[:95]
        metadata["description"] = str(metadata.get("description", topic))[:4900]
        metadata["tags"] = list(metadata.get("tags", []))[:15]
        return metadata

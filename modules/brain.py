import os
import json
import time
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

# Errors worth retrying: transient overload / rate-limit / server hiccups.
_RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL")


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


def _call_with_retry(fn, *, max_attempts=5, base_delay=2.0, max_delay=30.0):
    """
    Calls fn() with exponential backoff + jitter on transient Gemini errors
    (503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, 500 INTERNAL). Re-raises
    immediately on non-retryable errors, and re-raises the last error once
    max_attempts is exhausted.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt == max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.uniform(0, 1)
            print(f"⏳ Gemini call failed (attempt {attempt}/{max_attempts}): {e}")
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

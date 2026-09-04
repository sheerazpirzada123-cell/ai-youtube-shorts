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
        Single Gemini call that picks a famous Indian actor + an
        untold/life-story angle AND writes the full Hindi voiceover script
        AND writes the YouTube metadata, all at once. Combining these
        (previously 3 separate calls) matters a lot on the free tier, which
        caps you at 20 requests/day total — this cuts quota usage per video
        from 3 calls to 1.

        Returns (topic, script_data, metadata) or raises on failure.

        NOTE ON VISUALS: `visual_1`/`visual_2` are generic English mood
        keywords (e.g. "old indian village house", "film award stage
        spotlight") for stock B-roll — Pexels has no real footage/photos of
        any actual actor, so it can never fetch the real person. If you want
        genuine photos of the actor (childhood pics etc.), drop your own
        rights-cleared images into assets/actor_photos/<actor-slug>/ — the
        asset manager will use those first and only fall back to generic
        stock for scenes that have no matching local photo.
        """
        prompt = """
    You are an expert Indian celebrity content creator making viral YouTube
    Shorts in Hindi about famous Indian film actors' untold stories / life
    journeys (struggle, childhood, rise to fame, lesser-known facts). Do all
    of the following in one response:

    STEP 1 — TOPIC: Pick 1 well-known, popular Indian actor (Bollywood or
    major regional cinema) whose untold story / life journey would get high
    curiosity and views. Avoid anything about their current legal cases,
    health conditions, or unverified scandal/gossip — stick to their career
    journey, struggle, background, and publicly known biographical facts.

    STEP 2 — SCRIPT: Write a 3-4 scene script about that actor's untold/life
    story (KEEP IT SHORT AND FAST-PACED, total words under 80 words for a short under 45 seconds).
    - Voiceover (`text` field): written in Devanagari script, but the
      VOCABULARY must be everyday spoken HINDUSTANI (the common mixed
      Hindi-Urdu that ordinary people actually speak in India/Pakistan —
      equally natural and easily understood by Hindu and Muslim audiences
      alike). AVOID heavy, literary, Sanskrit-loaded "shuddh Hindi" words
      (e.g. avoid "अवगत", "प्रेरणादायक", "संघर्षरत", "अत्यंत", "यथार्थ").
      INSTEAD freely use common Urdu-origin words that are everyday
      Hindustani, written in Devanagari (e.g. मगर, वाकई, ज़िंदगी, तकलीफ,
      हकीकत, फैसला, मोहब्बत, बेहतरीन, यकीन, मुश्किल, कामयाबी, इज़्ज़त,
      जज़्बात, हिम्मत, नसीब). Write it exactly how a popular Hindi/Urdu
      YouTuber talks — simple, warm, conversational, zero shuddh-Hindi
      stiffness.
      Tone: intriguing, warm, confidential, emotional — for a dramatic male
      voiceover.
    - The VERY FIRST scene's text MUST start with this exact hook pattern
      (replace ACTOR_NAME with the actor's real name):
      "(ACTOR_NAME) के बारे में आपको ये बातें शायद ही पता होंगी..."
      then continue the hook in the same everyday Hindustani style.
    - Structure: Hook (as above) -> Early life / background -> Struggle
      phase -> Big break/turning point -> Channel Subscribe Outro.
    - Only use publicly known, non-defamatory biographical information.
      Do not invent private/personal claims that aren't publicly established.
    - Visual cues (`visual_1` & `visual_2`): ENGLISH generic mood keywords
      for stock B-roll that do NOT depend on it being that specific person
      (e.g. "small indian village house", "old film camera vintage",
      "award show red carpet lights", "newspaper clipping vintage",
      "crowd cheering concert night"). Never reference copyrighted movie
      scenes/posters.

    STEP 3 — METADATA (for the YouTube post — this is DIFFERENT from the
    voiceover script above): write title, description, and tags in
    HINGLISH — Hindustani words spelled out in plain ENGLISH/ROMAN letters
    (e.g. "Kya aapko pata hai...", "iski untold story", "life journey"),
    NOT in Devanagari script. This is what most Indian YouTube
    titles/descriptions actually look like and is what people type into
    search.
    - title: Punchy Hinglish (Roman-script) title, high CTR, under 80 chars,
      includes the actor's name and a curiosity phrase like "Untold Story".
    - description: 2-3 Hinglish (Roman-script) sentences summarizing the
      video, written so it naturally contains the kind of terms people
      actually search for (actor name + "biography", "life story",
      "untold story", "struggle story", "unknown facts" etc.), followed by
      relevant hashtags including the actor's name.
    - tags: 10-15 SEO tags in English/Hinglish a viewer would actually type
      into YouTube search — mix of actor name variants + "biography", "life
      story", "untold story", "struggle story", "unknown facts", "success
      story", plus "Shorts"/"Bollywood" as relevant. Generate these
      dynamically based on the specific actor and story angle chosen.

    Respond with ONLY this JSON object, nothing else:
    {
        "topic": "Actor Name - short angle description",
        "script": [
            {
                "id": 1,
                "text": "(Actor Name) के बारे में आपको ये बातें शायद ही पता होंगी...",
                "visual_1": "small indian village house",
                "visual_2": "old family photo album",
                "mood": "emotional"
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
        Generates a popular Indian actor + untold-story angle topic.
        """
        prompt = (
            "Give me 1 popular, high-curiosity topic for a Short Video about a famous Indian film "
            "actor's untold story / life journey (childhood, struggle, big break, or a lesser-known "
            "fact). Use only publicly known, non-defamatory biographical information — no unverified "
            "gossip, health, or legal claims. Return ONLY the actor name + short angle, no quotes or "
            "commentary."
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
        Generates a structured Indian-actor untold-story Short script
        optimized for a Hindi male narrator.
        """
        print(f"📝 Writing untold-story script for: {topic}...")
        prompt = f"""
    You are an expert Indian celebrity content creator making viral YouTube Shorts in Hindi about a
    famous Indian actor's untold story / life journey.
    Topic: {topic}

    ### SCRIPT CREATION RULES:
    1. **Voiceover Language (`text` field):** Written in Devanagari script, but with everyday spoken
       HINDUSTANI vocabulary (the common mixed Hindi-Urdu that ordinary people actually speak —
       equally natural for Hindu and Muslim audiences). AVOID heavy, literary "shuddh Hindi"/Sanskrit
       words (e.g. avoid "अवगत", "प्रेरणादायक", "संघर्षरत", "यथार्थ"). Freely use common Urdu-origin
       everyday words written in Devanagari (e.g. मगर, वाकई, ज़िंदगी, तकलीफ, हकीकत, फैसला, मोहब्बत,
       बेहतरीन, यकीन, मुश्किल, कामयाबी, इज़्ज़त, जज़्बात, हिम्मत, नसीब) — write it like a popular
       Hindi/Urdu YouTuber talks, simple and conversational, not stiff/literary.
       - Tone: intriguing, warm, confidential, emotional — meant for a dramatic male voiceover.
       - The FIRST scene's text MUST start with the exact hook pattern (actor's real name in place of
         ACTOR_NAME): "(ACTOR_NAME) के बारे में आपको ये बातें शायद ही पता होंगी..." then continue the hook
         in the same everyday Hindustani style.
    2. **Structure:** 3-4 Scenes total (KEEP IT SHORT AND FAST-PACED, under 80 words total for a short under 45 seconds).
       - Hook -> Struggle phase -> Big break -> Outro.
       - Only use publicly known, non-defamatory biographical information.
    3. **Visual Cues (`visual_1` & `visual_2` fields):** Must be in ENGLISH, generic mood keywords for
       stock footage that do NOT depend on it being that specific real person (e.g. "small indian
       village house", "old film camera vintage", "award show red carpet lights", "newspaper clipping
       vintage"). Never reference copyrighted movie scenes/posters.

    Respond with a JSON array only:
    [
        {{
            "id": 1,
            "text": "(Actor Name) के बारे में आपको ये बातें शायद ही पता होंगी...",
            "visual_1": "small indian village house",
            "visual_2": "old family photo album",
            "mood": "emotional"
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
        title & description, search-intent tags) for an Indian actor
        untold-story video.
        """
        full_text = " ".join(scene.get("text", "") for scene in script_data)
        prompt = f"""
    Write YouTube Shorts metadata for a video about a famous Indian actor's untold story / life journey.
    Topic: {topic}
    Script context: {full_text}

    IMPORTANT: Write the title and description in HINGLISH — Hindustani words spelled out in plain
    ENGLISH/ROMAN letters (e.g. "Kya aapko pata hai...", "iski untold story"), NOT in Devanagari script.
    This is what real Indian YouTube titles/descriptions look like and what people actually search.

    Requirements:
    - **Title:** Punchy Hinglish (Roman-script) title with high CTR (under 80 chars), includes the
      actor's name and a curiosity phrase like "Untold Story".
    - **Description:** 2-3 Hinglish (Roman-script) sentences summarizing the video, phrased so it
      naturally contains the kind of terms people actually search for (actor name + "biography", "life
      story", "untold story", "struggle story", "unknown facts"), followed by relevant hashtags
      including the actor's name.
    - **Tags:** 10-15 SEO tags a viewer would actually search — mix of the actor's name (and common
      spelling variants) with "biography", "life story", "untold story", "struggle story", "unknown
      facts", "success story", plus "Shorts"/"Bollywood" as relevant. Base these on the specific actor
      and story angle in the topic above, not a fixed template.

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

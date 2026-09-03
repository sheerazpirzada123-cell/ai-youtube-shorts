import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# NOTE: gemini-1.5-flash has been retired by Google (all Gemini 1.5 models
# now return 404). Use a currently supported model instead. Swap this if
# Google deprecates it later — check https://ai.google.dev/gemini-api/docs/models
MODEL_NAME = "gemini-2.5-flash"


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a .env file or set the environment variable before running."
        )
    return genai.Client(api_key=api_key)


def _extract_text(response):
    """
    Safely pull text out of a Gemini response. Returns None if the model
    returned nothing usable (e.g. blocked by safety filters, empty candidates).
    """
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    # Fallback: check candidates directly (covers cases where .text is empty
    # because of safety blocks / finish_reason issues)
    candidates = getattr(response, "candidates", None)
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
        print(f"⚠️ Empty response text. finish_reason={finish_reason}")
    return None


class ContentBrain:
    def get_trending_topic(self):
        """
        In a full build, this would scrape Google Trends or Twitter.
        For now, we ask Gemini to pick a viral niche topic.
        """
        prompt = (
            "Give me 1 specific, viral, and engaging topic for a Short Documentary. "
            "It should be a 'Engaging Did you know' fact or a 'Fun/intriguing Engaging News'. "
            "Return ONLY the topic name, with no quotes, labels, or extra commentary."
        )
        client = _get_client()

        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed while getting topic: {e}") from e

        topic = _extract_text(response)
        if not topic:
            raise RuntimeError("Gemini returned no usable topic text (possibly blocked).")

        # Strip stray quotes/markdown the model sometimes adds anyway
        topic = topic.strip().strip('"').strip("'").strip()
        print(f"🎯 Selected Topic: {topic}")
        return topic

    def generate_script(self, topic):
        """
        Generates a structured JSON script with visual cues.
        """
        print(f"📝 Writing script for: {topic}...")
        prompt = f"""
    You are the lead scriptwriter for a high-retention "Edutainment" YouTube Shorts channel.
    Topic: {topic}

    ### GOAL:
    Create a script where every sentence has a "Visual Switch".
    To keep retention high, we need TWO different stock videos for every single scene.

    ### 1. SCRIPT REQUIREMENTS (The Voiceover):
    - **Perspective:** Strictly **3rd Person** ("Scientists found...", "The ocean hides...").
    - **Tone:** Engaging, fast-paced, logical. No fluff.
    - **Structure:** 8-9 Scenes total.
    - **Flow:** Hook -> Context -> Mechanism (How it works) -> Twist -> Outro.

    ### 2. VISUAL REQUIREMENTS (Dual Visuals):
    - For EVERY scene, provide TWO distinct search terms:
      - **visual_1:** Matches the *start* of the sentence.
      - **visual_2:** Matches the *end* of the sentence or provides a reaction/context.
    - **Strictly Literal:** If the text is "The economy crashed," do NOT search "sad man". Search "Stock market red chart".

    Respond with a JSON array only, matching this shape:
    [
        {{
            "id": 1,
            "text": "In 1995, fourteen wolves were released into Yellowstone Park, and they changed the rivers.",
            "visual_1": "wolves running snow aerial",
            "visual_2": "river flowing forest drone",
            "mood": "intriguing"
        }}
    ]
    """

        client = _get_client()

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                # Ask the API to guarantee valid JSON instead of relying on
                # manual markdown-fence stripping, which is fragile.
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed while generating script: {e}") from e

        raw_text = _extract_text(response)
        if not raw_text:
            print("❌ Gemini returned no script text (possibly blocked).")
            return None

        # Still strip markdown fences defensively, in case the model
        # ignores response_mime_type on some SDK/model versions.
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
        Generates a YouTube Shorts title, description, and tags for the
        finished video. Kept as a separate lightweight call so a failure
        here doesn't waste the (expensive) script generation call.
        """
        full_text = " ".join(scene.get("text", "") for scene in script_data)
        prompt = f"""
    You are writing YouTube Shorts metadata for a short documentary video.
    Topic: {topic}
    Script (for context only): {full_text}

    Return ONLY a JSON object with this exact shape, no markdown fences:
    {{
        "title": "Under 90 characters, punchy, curiosity-driven, no clickbait lies",
        "description": "2-4 sentences summarizing the video, then 5-8 relevant hashtags on a new line",
        "tags": ["short", "list", "of", "8-12", "single-or-two-word", "keywords"]
    }}
    """
        client = _get_client()
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            raw_text = _extract_text(response)
            if not raw_text:
                raise RuntimeError("empty metadata response")
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            metadata = json.loads(clean_text)
        except Exception as e:
            print(f"⚠️ Metadata generation failed ({e}), falling back to topic as title.")
            metadata = {
                "title": topic[:90],
                "description": f"{topic}\n\n#shorts #trending",
                "tags": ["shorts", "trending"],
            }

        # Guardrails: YouTube hard-caps title at 100 chars.
        metadata["title"] = str(metadata.get("title", topic))[:95]
        metadata["description"] = str(metadata.get("description", topic))[:4900]
        metadata["tags"] = list(metadata.get("tags", []))[:15]
        return metadata


# --- TESTING THE MODULE ---
if __name__ == "__main__":
    brain = ContentBrain()
    topic = brain.get_trending_topic()
    script = brain.generate_script(topic)

    if script:
        with open("script.json", "w") as f:
            json.dump(script, f, indent=4)
        print("✅ Script saved to script.json")
    else:
        print("❌ No script to save.")

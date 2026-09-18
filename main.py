import os
import json
import time
import re
import requests
import asyncio
import edge_tts
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from modules.composer import ShortsComposer
from modules.youtube_uploader import upload_video

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)

ASSETS_DIR = "assets"
TEMP_VIDEO_DIR = os.path.join(ASSETS_DIR, "video_clips")
TEMP_AUDIO_DIR = os.path.join(ASSETS_DIR, "audio_clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "final")

for directory in [TEMP_VIDEO_DIR, TEMP_AUDIO_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

KEYWORD_MAP = {
    "blood falls": "Antarctica red waterfall blood falls glacier",
    "dancing forest": "Kaliningrad curved twisted pine trees forest",
    "eternal flame": "New York eternal flame waterfall cavern cave fire",
    "antarctica": "antarctica glacier ice freeze landscape",
    "bermuda triangle": "bermuda triangle ocean storm dark water",
    "surtsey island": "volcano island emergence sea ocean lava"
}

def get_optimized_search_query(text):
    text_lower = text.lower()
    for key, search_term in KEYWORD_MAP.items():
        if key in text_lower:
            return search_term
    return text

def generate_script(max_retries=3, base_wait=25):
    prompt = """
    Write a smooth, fast-paced engaging YouTube Short script in simple spoken Hindi/Urdu mixed with common English words.

    STRICT LANGUAGE & STYLE RULES:
    1. NO hard or formal Hindi words (Strictly avoid: prakriti, chattaan, rahasya, adbhut, drishya, etc.).
    2. Use simple daily conversational Hindi/Urdu with simple English words (waterfall, fire, mystery, natural gas, place, dangerous, scientists).
    3. VERY IMPORTANT FOR CONTINUOUS FLOW: DO NOT use full stops (.), question marks (?), or commas (,) inside the narration text so there are NO LONG PAUSES OR GAPS between sentences. Keep sentences connected seamlessly.

    DURATION & STRUCTURAL RULES:
    1. Total length MUST be 30 to 40 seconds long (70-80 words total).
    2. Return ONLY a valid JSON list of objects containing "narration" and "search_keyword".

    Example JSON Output Format:
    [
      {
        "narration": "Kya aapne kabhi waterfall ke bilkul neeche aag jalti dekhi hai New York mein ek aisi jagah hai jahan pani ke andar bhi natural fire hamesha jalti rehti hai",
        "search_keyword": "New York eternal flame waterfall cavern cave fire"
      },
      {
        "narration": "Log isey Eternal Flame Falls kehte hain Scientists ke mutabiq zameen ke neeche se nikalne wali gas is aag ko kabhie bujhne nahi deti",
        "search_keyword": "Eternal flame falls cave fire natural gas"
      }
    ]
    """

    # Quota issues avoid karne ke liye gemini-1.5-flash model
    model = genai.GenerativeModel("gemini-1.5-flash")

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(prompt)
            clean_json = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*

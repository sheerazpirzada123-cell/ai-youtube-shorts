import google.generativeai as genai
import json
import random

FACT_TOPICS = [
    "Wahiyat aur Ajeeb Facts",
    "Insaan ke Jism ke Mind-Blowing Sach",
    "Janwaro ki Shocking Duniya",
    "Antariksh ke Khaufnak Facts",
    "Psychology ke Magical Facts"
]

def generate_fact_script(api_key):
    genai.configure(api_key=api_key)
    selected_topic = random.choice(FACT_TOPICS)
    
    prompt = f"""
    You are a YouTube Shorts scriptwriter like Facts Mine. 
    Write an engaging 30-second Hindi facts script on: "{selected_topic}".
    
    RULES:
    1. Language MUST BE natural spoken Hindi (Devanagari script).
    2. Directly start with a energetic hook.
    3. Output strictly in JSON format without markdown codeblocks:
    {{"title": "Title Here", "script": "Hindi spoken content..."}}
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

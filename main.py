import os
import json
import requests
import google.generativeai as genai

# Setup Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# 1. Custom Keywords Mapping for Exact B-Roll Matching
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

# 2. Strict Script Generation Prompt
def generate_script():
    prompt = """
    Create an engaging, mysterious YouTube Short script in Hindi/Urdu.
    
    STRICT RULES:
    1. Duration: MUST be between 30 to 45 seconds (around 70 to 85 words max).
    2. Focus: Pick ONLY 1 or 2 specific mysteries or places per video (e.g., Blood Falls or Eternal Flame Falls) so the context is detailed and focused.
    3. Formatting: Return a valid JSON list where each object has "narration" and "search_keyword".
    
    Example Output Format:
    [
      {
        "narration": "Kya aapne kabhi zameen ke neeche pani mein jalti hui aag dekhi hai?",
        "search_keyword": "New York eternal flame waterfall cavern cave fire"
      },
      {
        "narration": "Antarctica mein ek aisi jagah hai jahan barf ke beech se laal rang ka paani behta hai, jise Blood Falls kehte hain.",
        "search_keyword": "Antarctica red waterfall blood falls glacier"
      }
    ]
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    
    try:
        # Clean response text in case markdown formatting is included
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        script_data = json.loads(clean_json)
        return script_data
    except Exception as e:
        print(f"Error parsing script JSON: {e}")
        return []

# 3. Fetch Stock Video from Pexels API
def fetch_broll_video(query):
    optimized_query = get_optimized_search_query(query)
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={optimized_query}&per_page=1&orientation=portrait"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("videos"):
            video_files = data["videos"][0]["video_files"]
            # Pick high-quality link
            return video_files[0]["link"]
    
    print(f"No exact match found for: {optimized_query}. Using fallback.")
    return None

def main():
    print("Generating 30-45s Short script...")
    script_data = generate_script()
    
    if not script_data:
        print("Script generation failed.")
        return

    print(f"Script generated with {len(script_data)} scenes.\n")
    
    for idx, scene in enumerate(script_data, start=1):
        narration = scene.get("narration")
        keyword = scene.get("search_keyword")
        
        print(f"Scene {idx}: {narration}")
        print(f"Search Query: {keyword}")
        
        video_url = fetch_broll_video(keyword)
        print(f"Video B-Roll URL: {video_url}\n" + "-"*40)

if __name__ == "__main__":
    main()

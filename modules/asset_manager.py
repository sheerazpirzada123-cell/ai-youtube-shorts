import os
import requests
import random
import re
from dotenv import load_dotenv

# Character -> extra stock-safe visual keywords. Pexels has no licensed
# Marvel footage (nor should it), so we can't fetch the actual character —
# but we CAN bias the search toward generic footage that visually reads as
# "that kind of character" so the clip stops being random when a specific
# name is mentioned in the scene.
CHARACTER_KEYWORDS = {
    "doom": ["metal mask armor", "gothic villain cape", "dark medieval armor"],
    "victor von doom": ["metal mask armor", "gothic villain cape"],
    "iron man": ["futuristic metal suit", "red gold armor closeup", "robotic hand glow"],
    "tony stark": ["futuristic metal suit", "high tech lab"],
    "spider-man": ["web silhouette city", "red mask closeup", "climbing building night"],
    "spiderman": ["web silhouette city", "red mask closeup"],
    "peter parker": ["young man city rooftop", "web silhouette city"],
    "doctor strange": ["red cloak mystic", "glowing magic circle", "sorcerer hands energy"],
    "strange": ["red cloak mystic", "glowing magic circle"],
    "multiverse": ["portal energy swirl", "fractured glass dimension", "parallel universe abstract"],
    "avengers": ["team silhouette city", "epic battle skyline"],
}


def _detect_character_terms(*texts):
    """Scan scene text/topic for known character names and return extra keywords."""
    combined = " ".join(t.lower() for t in texts if t)
    extra = []
    for name, keywords in CHARACTER_KEYWORDS.items():
        if name in combined:
            extra.extend(keywords)
    return extra


class AssetManager:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            raise RuntimeError("PEXELS_API_KEY is not set. Create a .env file or set the environment variable before running.")
        self.base_url = "https://api.pexels.com/videos/search"
        self.headers = {
            "Authorization": self.api_key
        }
        
        # Ensure download directory exists
        self.assets_dir = os.path.join(os.getcwd(), "assets", "video_clips")
        os.makedirs(self.assets_dir, exist_ok=True)

    def search_video(self, query, duration_min=4, prefer_relevance=True):
        """
        Searches Pexels for a portrait video matching the query.
        Returns the download URL or None.

        prefer_relevance=True picks Pexels' top-ranked result among the
        duration-valid candidates instead of a random one, so the clip
        actually matches the query instead of being a coin flip.
        """
        print(f"   🔍 Searching Pexels for: '{query}'...")
        
        params = {
            "query": query,
            "per_page": 5,        # Fetch top 5 results to pick from
            "orientation": "portrait",
            "size": "medium"      # 'medium' is usually HD ready, saves bandwidth
        }
        
        try:
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)
            if response.status_code != 200:
                print(f"      ⚠️ API Error: {response.status_code}")
                return None
                
            data = response.json()
            
            if not data.get('videos'):
                # Retry strategy: Simplify query if complex query fails
                if " " in query:
                    simple_query = query.split()[-1] # Try last word (usually the noun)
                    print(f"      ⚠️ No results. Retrying with '{simple_query}'...")
                    return self.search_video(simple_query, duration_min, prefer_relevance)
                return None
            
            # Filter logic: Prefer videos that aren't too short (at least 4 seconds).
            # Keep Pexels' original relevance order (don't re-sort by anything else).
            valid_videos = [v for v in data['videos'] if v['duration'] >= duration_min]
            
            if not valid_videos:
                valid_videos = data['videos'] # Fallback to whatever exists

            if prefer_relevance:
                # Pexels returns results ordered by relevance to the query —
                # take the best match instead of a random one.
                selected_video = valid_videos[0]
            else:
                selected_video = random.choice(valid_videos)
            
            # Get best quality video file link
            video_files = selected_video['video_files']
            video_files.sort(key=lambda x: x['width'] * x['height'], reverse=True)
            
            download_link = video_files[0]['link']
            return download_link

        except Exception as e:
            print(f"      ❌ Error searching Pexels: {e}")
            return None

    def download_video(self, url, filename):
        """
        Downloads the video content to a local file.
        """
        save_path = os.path.join(self.assets_dir, filename)
        
        # Caching strategy
        if os.path.exists(save_path):
            return save_path

        try:
            with requests.get(url, stream=True, timeout=15) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return save_path
        except Exception as e:
            print(f"      ❌ Error downloading {filename}: {e}")
            return None

    def get_videos(self, script_data, topic=""):
        """
        Downloads TWO videos per scene (A and B), biasing the search query
        toward whichever MCU character is actually being discussed in that
        scene (falls back to the overall topic if a scene doesn't name one).
        Returns a list of tuples: [(path_a, path_b), (path_a, path_b), ...]
        """
        print("🎥 Starting Double-Feature Video Download...")
        video_pairs = []

        for scene in script_data:
            scene_id = scene['id']
            scene_text = scene.get('text', '')

            # 1. Get base search terms from the script
            query_a = scene.get('visual_1', scene.get('keywords', 'abstract'))
            query_b = scene.get('visual_2', query_a)

            # 1b. Bias toward whichever character this scene actually names,
            # so "Doom" scenes don't end up with random Spider-Man footage
            # and vice versa.
            character_terms = _detect_character_terms(scene_text, topic)
            if character_terms:
                query_a = f"{query_a} {character_terms[0]}"
                query_b = f"{query_b} {character_terms[min(1, len(character_terms)-1)]}"
            
            # 2. Search & Download Clip A
            url_a = self.search_video(query_a)
            path_a = None
            if url_a:
                path_a = self.download_video(url_a, f"scene_{scene_id}_a.mp4")
            
            # 3. Search & Download Clip B
            url_b = self.search_video(query_b)
            path_b = None
            if url_b:
                path_b = self.download_video(url_b, f"scene_{scene_id}_b.mp4")
            
            # 4. Fallback Logic (Self-Healing)
            # If B fails, use A twice. If A fails, use B twice.
            if not path_a and path_b: 
                path_a = path_b
                print(f"      ⚠️ Scene {scene_id} Clip A missing. Using Clip B for both.")
            if not path_b and path_a: 
                path_b = path_a
                print(f"      ⚠️ Scene {scene_id} Clip B missing. Using Clip A for both.")

            # 5. Final Check
            if path_a and path_b:
                video_pairs.append((path_a, path_b))
                print(f"   ✅ Scene {scene_id} Ready (A + B).")
            else:
                print(f"   ❌ Scene {scene_id} Completely Failed (No videos found).")
                video_pairs.append(None)

        return video_pairs

# --- TESTING ---
if __name__ == "__main__":
    manager = AssetManager()
    
    # Test with new dual-visual format
    test_script = [
        {
            "id": 1, 
            "visual_1": "cyberpunk city neon", 
            "visual_2": "hacker typing computer"
        }
    ]
    
    results = manager.get_videos(test_script)
    print("🎥 Assets Downloaded:", results)

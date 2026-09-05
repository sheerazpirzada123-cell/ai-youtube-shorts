import os
import requests
import random
import re
import unicodedata
from dotenv import load_dotenv

try:
    import ffmpeg
    _FFMPEG_AVAILABLE = True
except ImportError:
    _FFMPEG_AVAILABLE = False

# Cat-video mood -> extra cat-centric keywords. This dict biases the B-roll
# search toward the right *mood/beat* for that part of the scenario (funny
# reaction, cute/wholesome, playful chase, calm ending) while ALWAYS keeping
# "cat" in every keyword, since the cat is the main character and must stay
# the visual focus in every scene.
STAGE_KEYWORDS = {
    "funny": ["funny cat reaction", "cat surprised jump", "cat doing silly thing"],
    "मज़ेदार": ["funny cat reaction", "cat surprised jump"],
    "cute": ["cute cat close up", "kitten playing cute", "cat cuddling adorable"],
    "प्यारा": ["cute cat close up", "kitten playing cute"],
    "playful": ["cat playing chasing", "cat pouncing toy", "kitten zoomies playful"],
    "शरारती": ["cat playing chasing", "kitten zoomies playful"],
    "emotional": ["cat calm relaxing", "cat cuddling owner", "cat purring closeup"],
    "sad": ["cat calm sitting alone", "cat looking window"],
    "default": ["cute cat playing", "cat funny moment"],
}

# Curated, safe fallback queries for when Pexels has NO results at all for a
# scene's query. Previously this fell back to retrying with just the query's
# *last word* — which is how totally unrelated clips (a Turkish snack shop,
# an anime cosplay video, a "click here" ad) ended up in the video: a stray
# single word like "album" or "shop" or "click" matches whatever Pexels has
# tagged with that word, with zero relevance to the video. This list is
# deliberately always cat-related, so a fallback never produces something
# wildly off-topic (e.g. a random dog/duck video with no cat at all, or an
# unrelated abstract clip).
SAFE_FALLBACK_QUERIES = [
    "cute cat playing",
    "funny cat video",
    "kitten playing cute",
    "cat close up face",
    "cat jumping playful",
    "cat and owner cuddle",
    "cat sitting window",
    "cat pouncing toy",
]


def _detect_stage_terms(*texts):
    """Scan scene text/topic/mood for cat-video beat cues and return extra cat-centric keywords."""
    combined = " ".join(t.lower() for t in texts if t)
    extra = []
    for name, keywords in STAGE_KEYWORDS.items():
        if name in combined:
            extra.extend(keywords)
    return extra


def _ensure_cat_in_query(query):
    """
    Safety net: the cat is always the main character, so every Pexels query
    must literally contain "cat" — otherwise a scene could drift into
    off-topic footage (e.g. just "duck swimming" with no cat in frame at
    all). If the script's visual keywords already say "cat" (they're
    prompted to), this is a no-op; if not, it appends "cat" so the search
    still stays on the main character.
    """
    query = (query or "").strip()
    if not query:
        return "cute cat playing"
    if "cat" not in query.lower():
        query = f"{query} cat"
    return query


def slugify(name):
    """Turns an actor name / topic string into a filesystem-safe folder slug."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "actor"


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
                # No results for this specific query — retry with a curated,
                # on-theme SAFE_FALLBACK_QUERIES pick instead of shrinking to
                # a single ambiguous word (that's what used to cause totally
                # unrelated results like anime cosplay or a random shop, since
                # a lone word like "album" or "shop" matches Pexels' loose
                # tagging with zero relevance to the video).
                fallback_query = random.choice(SAFE_FALLBACK_QUERIES)
                print(f"      ⚠️ No results for '{query}'. Retrying with safe fallback '{fallback_query}'...")
                params["query"] = fallback_query
                response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    return None
                data = response.json()
                if not data.get('videos'):
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
        Downloads/prepares TWO Pexels clips per scene (A and B). The cat is
        always the main character, so every query is forced to include
        "cat" (see _ensure_cat_in_query) and is built directly from that
        scene's own visual_1/visual_2 keywords — this keeps clips tied to
        what the script is actually describing in that scene, instead of
        drifting to generic/unrelated footage.

        Returns a list of tuples: [(path_a, path_b), (path_a, path_b), ...]
        """
        print("🎥 Starting Double-Feature Video Download...")
        video_pairs = []

        for i, scene in enumerate(script_data):
            scene_id = scene['id']
            scene_text = scene.get('text', '')
            mood = scene.get('mood', '')

            # 1. Base search terms come straight from THIS scene's own
            # script fields — never a generic/unrelated fallback — so the
            # clip matches what's actually being said right now.
            default_query = "cute cat playing"
            query_a = scene.get('visual_1') or scene.get('keywords') or default_query
            query_b = scene.get('visual_2') or default_query

            # 1b. Bias toward the scene's mood/beat (funny/cute/playful/etc)
            # for extra on-theme flavor, still cat-centric.
            stage_terms = _detect_stage_terms(scene_text, topic, mood)
            if stage_terms:
                query_a = f"{query_a} {stage_terms[0]}"
                query_b = f"{query_b} {stage_terms[min(1, len(stage_terms)-1)]}"

            # 1c. Safety net: force "cat" into both queries no matter what,
            # since the cat must remain the visual main character.
            query_a = _ensure_cat_in_query(query_a)
            query_b = _ensure_cat_in_query(query_b)

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
            "visual_1": "cute cat meeting duck funny",
            "visual_2": "cat and duck playing together",
            "mood": "funny",
        }
    ]

    results = manager.get_videos(test_script, topic="Cat meets a duck for the first time")
    print("🎥 Assets Downloaded:", results)

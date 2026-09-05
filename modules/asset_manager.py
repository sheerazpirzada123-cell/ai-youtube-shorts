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
    "funny": ["funny 3d cat reaction", "animated cat surprised jump", "cartoon cat doing silly thing"],
    "मज़ेदार": ["funny cat reaction", "cat surprised jump"],
    "cute": ["cute 3d animated cat close up", "animated kitten playing cute", "cartoon cat cuddling adorable"],
    "प्यारा": ["cute cat close up", "kitten playing cute"],
    "playful": ["3d animated cat playing chasing", "cartoon cat pouncing toy", "animated kitten zoomies playful"],
    "शरारती": ["cat playing chasing", "kitten zoomies playful"],
    "emotional": ["3d animated cat calm relaxing", "cartoon cat cuddling owner", "animated cat purring closeup"],
    "sad": ["cat calm sitting alone", "cat looking window"],
    "default": ["cute 3d animated cat playing", "cartoon cat funny moment"],
}

# Curated, safe fallback queries for when a source has NO results at all for
# a scene's query. Previously this fell back to retrying with just the
# query's *last word* — which is how totally unrelated clips (a Turkish
# snack shop, an anime cosplay video, a "click here" ad) ended up in the
# video: a stray single word like "album" or "shop" or "click" matches
# whatever the source has tagged with that word, with zero relevance. This
# list is deliberately always cat-related, so a fallback never produces
# something wildly off-topic.
SAFE_FALLBACK_QUERIES = [
    "cute 3d animated cat playing",
    "funny cartoon cat video",
    "animated kitten playing cute",
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
    Safety net: the cat is always the main character, so every search query
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
    """
    Fetches cat b-roll from TWO sources, in this order per query:

      1. Pixabay, with `video_type=animation` — Pixabay is the only one of
         the two that actually lets you filter for animated/3D-style clips
         (`video_type=film` is the other option; Pexels' API has no such
         filter at all, it's real-camera stock footage only). This is what
         gets us actual 3D-animated cat clips instead of real cats.
      2. Pexels — real stock-video fallback, used whenever Pixabay has no
         animated match for that query (or PIXABAY_API_KEY isn't set), so a
         scene never comes back empty.

    Set PIXABAY_API_KEY (free, from https://pixabay.com/api/docs/) alongside
    the existing PEXELS_API_KEY to enable the animated-clip search.
    """

    def __init__(self):
        load_dotenv()

        self.pexels_api_key = os.getenv("PEXELS_API_KEY")
        if not self.pexels_api_key:
            raise RuntimeError("PEXELS_API_KEY is not set. Create a .env file or set the environment variable before running.")
        self.pexels_url = "https://api.pexels.com/videos/search"
        self.pexels_headers = {"Authorization": self.pexels_api_key}

        # Optional — if missing we just skip straight to Pexels for every
        # query (still works, just without the animated-style clips).
        self.pixabay_api_key = os.getenv("PIXABAY_API_KEY")
        self.pixabay_url = "https://pixabay.com/api/videos/"
        if not self.pixabay_api_key:
            print("      ℹ️ PIXABAY_API_KEY not set — skipping animated-clip search, using Pexels only.")

        # Ensure download directory exists
        self.assets_dir = os.path.join(os.getcwd(), "assets", "video_clips")
        os.makedirs(self.assets_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Pixabay (animated clips)
    # ------------------------------------------------------------------
    def search_pixabay_animation(self, query, duration_min=4):
        """
        Searches Pixabay for a VERTICAL-friendly animated/3D-style video
        matching the query, using video_type=animation — the actual filter
        that gets us cartoon/3D clips instead of real-camera footage.
        Returns a download URL or None (never raises — a miss here just
        means AssetManager falls back to Pexels).
        """
        if not self.pixabay_api_key:
            return None

        print(f"   🔍 Searching Pixabay (animation) for: '{query}'...")
        params = {
            "key": self.pixabay_api_key,
            "q": query,
            "video_type": "animation",  # <-- the filter Pexels doesn't have
            "orientation": "vertical",  # prefer portrait-shot source clips
            "safesearch": "true",
            "per_page": 20,  # Pixabay's minimum allowed value
        }

        try:
            response = requests.get(self.pixabay_url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"      ⚠️ Pixabay API Error: {response.status_code}")
                return None

            data = response.json()
            hits = data.get("hits") or []
            if not hits:
                print(f"      ℹ️ No Pixabay animation results for '{query}'.")
                return None

            # Pixabay doesn't sort by "duration-valid first", so do that
            # ourselves; keep Pixabay's own relevance order otherwise.
            def clip_duration(hit):
                return hit.get("duration", 0)

            valid_hits = [h for h in hits if clip_duration(h) >= duration_min]
            if not valid_hits:
                valid_hits = hits

            selected = valid_hits[0]
            video_files = selected.get("videos", {})

            # Pick the largest available rendition Pixabay offers
            # (large > medium > small > tiny), since Pixabay doesn't give
            # per-file width/height the way Pexels does.
            for size in ("large", "medium", "small", "tiny"):
                if size in video_files and video_files[size].get("url"):
                    return video_files[size]["url"]

            return None

        except Exception as e:
            print(f"      ❌ Error searching Pixabay: {e}")
            return None

    # ------------------------------------------------------------------
    # Pexels (real stock-footage fallback)
    # ------------------------------------------------------------------
    def search_pexels(self, query, duration_min=4, prefer_relevance=True):
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
            response = requests.get(self.pexels_url, headers=self.pexels_headers, params=params, timeout=10)
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
                response = requests.get(self.pexels_url, headers=self.pexels_headers, params=params, timeout=10)
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

    def search_video(self, query, duration_min=4, prefer_relevance=True):
        """
        Tries Pixabay's animated-clip search first (real 3D/cartoon-style
        cat footage), and only falls back to Pexels real stock footage if
        Pixabay has nothing for this query (or isn't configured). Returns a
        download URL or None.
        """
        url = self.search_pixabay_animation(query, duration_min=duration_min)
        if url:
            return url

        return self.search_pexels(query, duration_min=duration_min, prefer_relevance=prefer_relevance)

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
        Downloads/prepares TWO clips per scene (A and B), searching Pixabay
        (animation) first, then Pexels (stock) as fallback (see
        search_video). The cat is always the main character, so every
        query is forced to include "cat" (see _ensure_cat_in_query) and is
        built directly from that scene's own visual_1/visual_2 keywords —
        this keeps clips tied to what the scene is actually about, instead
        of drifting to generic/unrelated footage.

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
            # clip matches what's actually being shown right now.
            default_query = "cute 3d animated cat playing"
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

            # 2. Search & Download Clip A (Pixabay animation -> Pexels)
            url_a = self.search_video(query_a)
            path_a = None
            if url_a:
                path_a = self.download_video(url_a, f"scene_{scene_id}_a.mp4")

            # 3. Search & Download Clip B (Pixabay animation -> Pexels)
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
            "visual_1": "3d animated cute cat meeting duck funny",
            "visual_2": "cartoon style cat and duck playing together",
            "mood": "funny",
        }
    ]

    results = manager.get_videos(test_script, topic="Cat meets a duck for the first time")
    print("🎥 Assets Downloaded:", results)

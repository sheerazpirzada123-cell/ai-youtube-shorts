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

# Life-story-stage -> extra stock-safe mood keywords. Pexels has NO real
# photos/footage of any actual person (it's generic royalty-free stock),
# so it can never fetch a real, identifiable actor. This dict only biases
# the generic B-roll search toward the right *mood* for that part of the
# story (childhood, struggle, fame, etc). For genuine photos of the actor
# themself (childhood pics and so on), drop your own rights-cleared images
# into assets/actor_photos/<actor-slug>/ — see get_local_actor_photos().
STAGE_KEYWORDS = {
    "childhood": ["small indian village house", "old family photo album", "children playing street india"],
    "बचपन": ["small indian village house", "old family photo album"],
    "struggle": ["empty audition room", "rain on window night", "person walking alone city"],
    "संघर्ष": ["empty audition room", "rain on window night"],
    "break": ["spotlight stage reveal", "film clapperboard vintage", "camera flash paparazzi"],
    "फिल्म": ["film clapperboard vintage", "old film camera vintage"],
    "award": ["award show red carpet lights", "trophy golden closeup", "applause crowd theatre"],
    "पुरस्कार": ["award show red carpet lights", "trophy golden closeup"],
    "success": ["crowd cheering concert night", "flashing camera lights", "city skyline night lights"],
    "सफलता": ["crowd cheering concert night", "flashing camera lights"],
}

# Curated, safe fallback moods for when Pexels has NO results at all for a
# scene's query. Previously this fell back to retrying with just the query's
# *last word* — which is how totally unrelated clips (a Turkish snack shop,
# an anime cosplay video, a "click here" ad) ended up in biography videos:
# a stray single word like "album" or "shop" or "click" matches whatever
# Pexels has tagged with that word, with zero relevance to the story. This
# list is deliberately generic-but-on-theme for a life-story/biography video,
# so a fallback never produces something wildly off-topic.
SAFE_FALLBACK_QUERIES = [
    "vintage film reel cinema",
    "old typewriter paper desk",
    "empty theatre stage spotlight",
    "black and white photograph vintage",
    "city lights night motivational",
    "clapperboard film set",
    "rain window silhouette",
    "sunrise over city skyline",
]


def _detect_stage_terms(*texts):
    """Scan scene text/topic for story-stage cues and return extra mood keywords."""
    combined = " ".join(t.lower() for t in texts if t)
    extra = []
    for name, keywords in STAGE_KEYWORDS.items():
        if name in combined:
            extra.extend(keywords)
    return extra


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

        # Where YOU manually place real, rights-cleared photos of an actor
        # (childhood pics, old press photos you have permission to use, etc).
        # One subfolder per actor, e.g. assets/actor_photos/shah-rukh-khan/.
        # Pexels itself can never supply these — it only has generic stock.
        self.actor_photos_dir = os.path.join(os.getcwd(), "assets", "actor_photos")
        os.makedirs(self.actor_photos_dir, exist_ok=True)

        # Cache for photos auto-fetched from Wikimedia Commons (free-licensed
        # only). Kept separate from actor_photos_dir so your manual curation
        # is never mixed with/overwritten by the automated fetch.
        self.wikimedia_cache_dir = os.path.join(os.getcwd(), "assets", "actor_photos_wikimedia")
        os.makedirs(self.wikimedia_cache_dir, exist_ok=True)
        # Wikimedia asks every API client to send an identifying User-Agent.
        self.wikimedia_headers = {
            "User-Agent": "ActorShortsBot/1.0 (personal YouTube Shorts project; contact: set-your-email@example.com)"
        }

    def fetch_wikimedia_photos(self, actor_name, limit=6, force_refresh=False):
        """
        Automatically finds and downloads FREE-LICENSED photos of the actor
        from Wikimedia Commons (public domain / CC-BY / CC-BY-SA / CC0 only —
        never anything marked non-free/fair-use). This is legal because
        Commons only hosts content its uploaders have explicitly released
        under a free license.

        Coverage note: Commons mostly has press/event/red-carpet photos from
        the actor's public career — it almost never has private childhood
        photos (those are essentially never free-licensed anywhere). So this
        fills in the "adult/career era" gap automatically; childhood-era
        photos still need your own manually-sourced, rights-cleared images
        in assets/actor_photos/<slug>/.

        Writes a credits.txt next to the downloaded files listing each
        photo's author and license — many CC licenses (CC-BY, CC-BY-SA)
        legally require you to credit the author, e.g. in the video
        description. Check credits.txt and add that credit before publishing.

        Returns a list of local image paths (possibly empty on failure/no
        results). Cached per actor — pass force_refresh=True to re-query.
        """
        slug = slugify(actor_name)
        folder = os.path.join(self.wikimedia_cache_dir, slug)
        os.makedirs(folder, exist_ok=True)

        cached = [
            os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        if cached and not force_refresh:
            return cached

        print(f"   🌐 Searching Wikimedia Commons for free-licensed photos of '{actor_name}'...")
        search_url = "https://commons.wikimedia.org/w/api.php"

        try:
            # Step 1: find candidate file titles in the File: namespace.
            search_resp = requests.get(
                search_url,
                headers=self.wikimedia_headers,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": actor_name,
                    "srnamespace": 6,  # File: namespace
                    "srlimit": limit * 3,  # over-fetch, we'll filter by license
                },
                timeout=10,
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("query", {}).get("search", [])
            if not hits:
                print("      ⚠️ No Wikimedia Commons results found.")
                return []

            titles = [h["title"] for h in hits]

            # Step 2: fetch image URL + license metadata for those titles.
            info_resp = requests.get(
                search_url,
                headers=self.wikimedia_headers,
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata|size",
                    "titles": "|".join(titles),
                },
                timeout=10,
            )
            info_resp.raise_for_status()
            pages = info_resp.json().get("query", {}).get("pages", {})

        except Exception as e:
            print(f"      ❌ Wikimedia API error: {e}")
            return []

        free_license_markers = ("cc0", "cc-by", "public domain", "pd-", "cc by")
        credits_lines = []
        downloaded = []

        for page in pages.values():
            if len(downloaded) >= limit:
                break

            imageinfo = (page.get("imageinfo") or [None])[0]
            if not imageinfo:
                continue

            url = imageinfo.get("url", "")
            if not url.lower().endswith((".jpg", ".jpeg", ".png")):
                continue  # skip svg/pdf/audio/etc results

            extmeta = imageinfo.get("extmetadata", {})
            license_short = extmeta.get("LicenseShortName", {}).get("value", "").lower()
            usage_terms = extmeta.get("UsageTerms", {}).get("value", "").lower()

            is_free = any(marker in license_short or marker in usage_terms for marker in free_license_markers)
            if not is_free:
                continue  # skip anything not clearly free/public-domain

            artist = re.sub("<[^<]+?>", "", extmeta.get("Artist", {}).get("value", "Unknown"))
            license_name = extmeta.get("LicenseShortName", {}).get("value", "Unknown license")
            page_title = page.get("title", "file")

            filename = f"{slug}_{len(downloaded)+1}.jpg"
            save_path = os.path.join(folder, filename)

            try:
                with requests.get(url, headers=self.wikimedia_headers, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    with open(save_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                downloaded.append(save_path)
                credits_lines.append(f"{filename} — {page_title} — by {artist} — {license_name} — source: {url}")
                print(f"      ✅ Downloaded ({license_name}): {page_title}")
            except Exception as e:
                print(f"      ❌ Failed to download {page_title}: {e}")

        if credits_lines:
            with open(os.path.join(folder, "credits.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "Auto-fetched from Wikimedia Commons — free-licensed only.\n"
                    "Some licenses (CC-BY, CC-BY-SA) legally require crediting the author.\n"
                    "Check each line below and add attribution to your video description before publishing:\n\n"
                )
                f.write("\n".join(credits_lines))

        if not downloaded:
            print("      ⚠️ No free-licensed photos survived filtering.")

        return downloaded

    def get_local_actor_photos(self, actor_name):
        """
        Returns a list of local image paths for this actor, if you've placed
        any in assets/actor_photos/<actor-slug>/. Empty list if none exist —
        callers should fall back to generic Pexels stock in that case.
        """
        folder = os.path.join(self.actor_photos_dir, slugify(actor_name))
        if not os.path.isdir(folder):
            return []
        valid_ext = (".jpg", ".jpeg", ".png", ".webp")
        photos = [
            os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.lower().endswith(valid_ext)
        ]
        return photos

    def image_to_video(self, image_path, filename, duration=4):
        """
        Converts a still photo into a short looping video clip so the
        composer (which expects video files) can use it exactly like a
        Pexels clip. Cached like download_video().
        """
        if not _FFMPEG_AVAILABLE:
            print("      ⚠️ ffmpeg-python not available, can't convert photo to video.")
            return None

        save_path = os.path.join(self.assets_dir, filename)
        if os.path.exists(save_path):
            return save_path

        try:
            (
                ffmpeg
                .input(image_path, loop=1, t=duration)
                .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                .filter('crop', 1080, 1920)
                .filter('fps', fps=30)
                .output(save_path, vcodec='libx264', pix_fmt='yuv420p')
                .run(overwrite_output=True, quiet=True)
            )
            return save_path
        except Exception as e:
            print(f"      ❌ Error converting photo {image_path} to video: {e}")
            return None

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

    def get_videos(self, script_data, topic="", actor_name=None):
        """
        Downloads/prepares TWO clips per scene (A and B).

        Priority per scene:
          1. Your own local photos of the actor, if you've placed any in
             assets/actor_photos/<actor-slug>/ — these get converted to
             short video clips and cycled across scenes. Best source since
             only you can legally clear e.g. private childhood photos.
          2. Free-licensed photos auto-fetched from Wikimedia Commons (topped
             up automatically when you have fewer than 4 manual photos) —
             mostly career/press/event photos, never private ones.
          3. Generic Pexels stock B-roll, biased toward the story stage
             (childhood/struggle/award/etc) mentioned in that scene, used
             only when no real photo is available at all.

        Returns a list of tuples: [(path_a, path_b), (path_a, path_b), ...]
        """
        print("🎥 Starting Double-Feature Video Download...")
        video_pairs = []

        actor_name = actor_name or topic

        # 1. Your own manually-curated, rights-cleared photos (best source —
        # can include childhood pics etc, since only you can clear those).
        local_photos = self.get_local_actor_photos(actor_name)

        # 2. Auto-fetched free-licensed career/press photos from Wikimedia
        # Commons. Always attempted (it's cached after the first run, so
        # this costs nothing on reruns) and merged with any manual photos —
        # for a well-known actor like this, real photos are the single
        # biggest fix for irrelevant-visuals issues, so we lean on this hard.
        wiki_photos = self.fetch_wikimedia_photos(actor_name, limit=8)
        local_photos = local_photos + wiki_photos

        if local_photos:
            print(f"   🖼️ Using {len(local_photos)} real photo(s) for '{actor_name}' (manual + Wikimedia).")
        else:
            print(f"   ℹ️ No real photos found for '{actor_name}' (checked assets/actor_photos/{slugify(actor_name)}/ "
                  f"and Wikimedia Commons) — falling back to generic stock B-roll for every scene.")

        for i, scene in enumerate(script_data):
            scene_id = scene['id']
            scene_text = scene.get('text', '')

            # 0. If we have real local photos of the actor, use two of them
            # for this scene (cycling through the pool) instead of stock.
            if local_photos:
                photo_a = local_photos[(2 * i) % len(local_photos)]
                photo_b = local_photos[(2 * i + 1) % len(local_photos)]
                path_a = self.image_to_video(photo_a, f"scene_{scene_id}_a.mp4")
                path_b = self.image_to_video(photo_b, f"scene_{scene_id}_b.mp4")
                if path_a and path_b:
                    video_pairs.append((path_a, path_b))
                    print(f"   ✅ Scene {scene_id} Ready (local photos).")
                    continue
                # If photo conversion failed for some reason, fall through
                # to generic stock below instead of losing the scene.

            # 1. Get base search terms from the script
            # Falling back to the literal word "abstract" used to send that
            # exact query to Pexels, which returns generic unrelated shape/
            # motion clips — this was the biggest source of visual mismatch.
            # Fall back to the video's own topic instead, so an unlabeled
            # scene still gets an on-theme B-roll.
            default_query = topic.strip() if topic and topic.strip() else "cinematic biography storytelling"
            query_a = scene.get('visual_1') or scene.get('keywords') or default_query
            query_b = scene.get('visual_2') or default_query

            # 1b. Bias toward the story stage this scene is actually about
            # (childhood/struggle/award/etc), so clips match the moment.
            stage_terms = _detect_stage_terms(scene_text, topic)
            if stage_terms:
                query_a = f"{query_a} {stage_terms[0]}"
                query_b = f"{query_b} {stage_terms[min(1, len(stage_terms)-1)]}"
            
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
            "visual_1": "small indian village house", 
            "visual_2": "old family photo album"
        }
    ]
    
    results = manager.get_videos(test_script, topic="Test Actor - untold story")
    print("🎥 Assets Downloaded:", results)

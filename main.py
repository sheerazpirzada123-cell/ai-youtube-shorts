# 3. Fetch & Download Stock Video from Pexels API
def download_broll_video(query, save_path):
    optimized_query = get_optimized_search_query(query)
    headers = {"Authorization": PEXELS_API_KEY}
    # Video duration filter pass karein (at least portrait orientation with multiple results)
    url = f"https://api.pexels.com/videos/search?query={optimized_query}&per_page=5&orientation=portrait"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("videos"):
            # Select the video with longest duration if available
            videos = data["videos"]
            selected_video = max(videos, key=lambda v: v.get("duration", 0))
            video_files = selected_video["video_files"]
            video_url = video_files[0]["link"]
            
            v_res = requests.get(video_url, stream=True)
            if v_res.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in v_res.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                return True

    print(f"No video found for: {optimized_query}")
    return False

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# YouTube API scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service():
    """
    Authenticates and returns the YouTube API service object.
    Checks environment variables first (for GitHub Actions), then local files.
    """
    creds = None

    # GitHub Actions environment variables check
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    print(f"✓ YOUTUBE_CLIENT_ID exists: {bool(client_id)}")
    print(f"✓ YOUTUBE_CLIENT_SECRET exists: {bool(client_secret)}")
    print(f"✓ YOUTUBE_REFRESH_TOKEN exists: {bool(refresh_token)}")

    if client_id and client_secret and refresh_token:
        from google.oauth2.credentials import Credentials
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES
        )
        try:
            # Force refresh to get a valid access token from refresh token
            creds.refresh(Request())
        except Exception as e:
            print(f"⚠️ Token refresh warning: {e}")
    else:
        # Fallback for local token file if running locally
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)

    # Refresh or prompt login if credentials are still invalid/expired
    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Refresh failed: {e}")

        if not creds or not creds.valid:
            if os.path.exists("client_secret.json"):
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secret.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open("token.pickle", "wb") as token:
                    pickle.dump(creds, token)
            else:
                raise Exception("❌ YouTube Credentials ghayab hain! GitHub Secrets check karein.")

    return build("youtube", "v3", credentials=creds)

def upload_video(video_path, title, description, tags=None, category_id="22", privacy_status="public"):
    """
    Uploads a video to YouTube.
    """
    if tags is None:
        tags = ["shorts", "youtubeshorts"]

    youtube = get_youtube_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    print(f"Uploading '{title}'...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"✅ Video successfully uploaded! Video ID: {response.get('id')}")
    return response.get('id')

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service(client_id=None, client_secret=None, refresh_token=None):
    creds = None

    # Priority 1: Main.py se aaye huye credentials ya Environment variables
    c_id = client_id or os.getenv("YOUTUBE_CLIENT_ID")
    c_secret = client_secret or os.getenv("YOUTUBE_CLIENT_SECRET")
    r_token = refresh_token or os.getenv("YOUTUBE_REFRESH_TOKEN")

    print(f"✓ YOUTUBE_CLIENT_ID exists: {bool(c_id)}")
    print(f"✓ YOUTUBE_CLIENT_SECRET exists: {bool(c_secret)}")
    print(f"✓ YOUTUBE_REFRESH_TOKEN exists: {bool(r_token)}")

    if c_id and c_secret and r_token:
        creds = Credentials(
            token=None,
            refresh_token=r_token,
            client_id=c_id,
            client_secret=c_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES
        )
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"⚠️ Token refresh warning: {e}")
    else:
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)

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

def upload_video(video_path, title, description, tags=None, category_id="22", privacy_status="public", client_id=None, client_secret=None, refresh_token=None):
    if tags is None:
        tags = ["shorts", "youtubeshorts"]

    # Youtube service call with credentials
    youtube = get_youtube_service(client_id, client_secret, refresh_token)

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

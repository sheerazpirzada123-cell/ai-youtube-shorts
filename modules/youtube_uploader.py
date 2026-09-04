import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader:
    """
    Uploads a finished video to YouTube.

    Auth uses a long-lived refresh token instead of the interactive
    client_secret.json flow, because GitHub Actions runners have no
    browser to complete an OAuth consent screen. Generate the refresh
    token ONCE locally with get_refresh_token.py, then store it as a
    GitHub Actions secret (YOUTUBE_REFRESH_TOKEN) alongside your
    YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET (both also come from the
    same client_secret.json you already have).
    """

    def __init__(self):
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        missing = [
            name
            for name, val in [
                ("YOUTUBE_CLIENT_ID", client_id),
                ("YOUTUBE_CLIENT_SECRET", client_secret),
                ("YOUTUBE_REFRESH_TOKEN", refresh_token),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"Missing required env vars for YouTube upload: {', '.join(missing)}. "
                "Run get_refresh_token.py locally once and add these as GitHub Actions secrets."
            )

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        creds.refresh(Request())  # exchange refresh_token for a fresh access token
        self.youtube = build("youtube", "v3", credentials=creds)

    def upload_video(
        self,
        file_path,
        title,
        description,
        tags=None,
        category_id="22",  # "People & Blogs" — change if you want a different default
        privacy_status="public",  # "public", "private", or "unlisted"
        made_for_kids=False,
    ):
        """
        Uploads file_path to YouTube and returns the resulting video ID.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No video file at {file_path}")

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")

        print(f"⬆️  Uploading '{title}' to YouTube...")
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        try:
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"   ...{int(status.progress() * 100)}% uploaded")
        except HttpError as e:
            raise RuntimeError(f"YouTube upload failed: {e}") from e

        video_id = response.get("id")
        print(f"✅ Uploaded: https://youtube.com/shorts/{video_id}")
        return video_id

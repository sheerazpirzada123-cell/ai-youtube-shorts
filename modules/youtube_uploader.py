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
    else:
        # Fallback for local token file if running locally
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)

    # Refresh or prompt login if credentials are invalid/expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.path.exists("client_secret.json"):
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secret.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
                with open("token.pickle", "wb") as token:
                    pickle.dump(creds, token)
            else:
                raise Exception("❌ YouTube Credentials ghayab hain! GitHub Secrets (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN) check karein.")

    return build("youtube", "v3", credentials=creds)

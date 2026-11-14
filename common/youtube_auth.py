"""Credenciales de YouTube a partir de variables de entorno (GitHub Secrets)."""
import os

from google.oauth2.credentials import Credentials
import google_auth_httplib2
import httplib2
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

_creds = None


def credentials():
    global _creds
    if _creds is None:
        missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Faltan variables: {', '.join(missing)}")
        _creds = Credentials(
            token=None,
            refresh_token=os.environ["YT_REFRESH_TOKEN"],
            client_id=os.environ["YT_CLIENT_ID"],
            client_secret=os.environ["YT_CLIENT_SECRET"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
    return _creds


def _http():
    # timeout de 5 minutos por request (las subidas van en partes de 8 MB)
    return google_auth_httplib2.AuthorizedHttp(credentials(), http=httplib2.Http(timeout=300))


def youtube():
    return build("youtube", "v3", http=_http(), cache_discovery=False)


def analytics():
    return build("youtubeAnalytics", "v2", http=_http(), cache_discovery=False)

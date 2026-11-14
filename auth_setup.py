"""Paso único: autorizar tu canal de YouTube.

Se corre UNA sola vez en tu computadora:
    pip install google-auth-oauthlib
    python auth_setup.py ruta/al/client_secret.json

Se abre el navegador, elegís la cuenta del canal y aceptás. Al final te muestra los
3 valores para pegar en GitHub -> Settings -> Secrets and variables -> Actions.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main():
    if len(sys.argv) < 2:
        print("Uso: python auth_setup.py ruta/al/client_secret.json")
        sys.exit(1)
    path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    info = data.get("installed") or data.get("web")
    print("\n✅ Autorizado. Creá estos 3 secrets en GitHub (no los compartas con nadie):\n")
    print(f"YT_CLIENT_ID      = {info['client_id']}")
    print(f"YT_CLIENT_SECRET  = {info['client_secret']}")
    print(f"YT_REFRESH_TOKEN  = {creds.refresh_token}")


if __name__ == "__main__":
    main()

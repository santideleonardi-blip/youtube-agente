"""StickRider — Publicador y estadísticas (credenciales SR_YT_* mapeadas a YT_* por el workflow)."""
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ET = dt.timezone(dt.timedelta(hours=-5))
# Público hispanohablante: el grueso está en México (UTC-6) y Colombia/Perú (UTC-5); el pico de Shorts es a la noche.
# 19 ET = 00 UTC = 18 México · 19 Colombia/Perú · 20 Venezuela/Chile · 21 Argentina (España queda de madrugada).
PUBLISH_HOUR_ET = int(os.getenv("SR_PUBLISH_HOUR_ET") or "19")


def next_slot(state, now=None):
    """Próximo horario libre a la hora de publicación (un video por día), con al menos 2 h de margen."""
    now = now or dt.datetime.now(dt.timezone.utc)
    taken = {v.get("publish_at", "")[:10] for v in state.get("videos", []) if v.get("publish_at")}
    day = now.astimezone(ET).date()
    for k in range(0, 14):
        d = day + dt.timedelta(days=k)
        t = dt.datetime(d.year, d.month, d.day, PUBLISH_HOUR_ET, 0, tzinfo=ET).astimezone(dt.timezone.utc)
        if t - now >= dt.timedelta(hours=2) and t.strftime("%Y-%m-%d") not in taken:
            return t
    return now + dt.timedelta(hours=3)


def upload(video, script, state, thumb=None):
    from googleapiclient.http import MediaFileUpload
    from common.youtube_auth import youtube
    title = script["title"][:95]
    if "#shorts" not in title.lower() and len(title) < 88:
        title = f"{title} #shorts"
    desc = script.get("description", "").strip() + "\n\n#shorts #historia #historiasreales #curiosidades #stickrider"
    t = next_slot(state)
    body = {
        "snippet": {"title": title, "description": desc[:4900], "tags": script.get("tags", [])[:15], "categoryId": "27",
                    "defaultLanguage": "es", "defaultAudioLanguage": "es"},
        "status": {"privacyStatus": "private", "publishAt": t.strftime("%Y-%m-%dT%H:%M:%S.0Z"),
                   "selfDeclaredMadeForKids": False, "embeddable": True},
    }
    req = youtube().videos().insert(part="snippet,status", body=body,
                                    media_body=MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    print(f"[publicador] subido https://youtu.be/{resp['id']} — se publica {t.astimezone(ET):%a %d %H:%M} ET")
    if thumb and os.path.exists(thumb):
        try:  # portada propia: requiere el canal verificado (youtube.com/verify)
            youtube().thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(thumb, mimetype="image/jpeg")).execute()
            print("[publicador] portada propia puesta")
        except Exception as e:  # noqa: BLE001
            print(f"[publicador] YouTube no aceptó la portada ({str(e)[:200]}): queda la que elige YouTube")
    return resp["id"], t.strftime("%Y-%m-%dT%H:%M:%SZ")


def refresh_stats(state):
    """Vistas / likes / comentarios de cada video (para que el guionista aprenda qué engancha)."""
    ids = [v["youtube_id"] for v in state.get("videos", []) if v.get("youtube_id")]
    if not ids or not os.getenv("YT_REFRESH_TOKEN"):
        return
    from common.youtube_auth import youtube
    yt = youtube()
    for i in range(0, len(ids), 50):
        res = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        st = {x["id"]: x["statistics"] for x in res.get("items", [])}
        for v in state["videos"]:
            s = st.get(v.get("youtube_id"))
            if s:
                v["views"] = int(s.get("viewCount", 0)); v["likes"] = int(s.get("likeCount", 0)); v["comments"] = int(s.get("commentCount", 0))
    # retención (YouTube Analytics) de los que tienen +48 h
    try:
        from common.youtube_auth import analytics
        an = analytics()
        today = dt.date.today().isoformat()
        for v in state["videos"]:
            if not v.get("youtube_id") or not v.get("publish_at"):
                continue
            pub = dt.datetime.fromisoformat(v["publish_at"].replace("Z", "+00:00"))
            if dt.datetime.now(dt.timezone.utc) - pub < dt.timedelta(hours=48):
                continue
            r = an.reports().query(ids="channel==MINE", startDate=pub.date().isoformat(), endDate=today,
                                   metrics="averageViewPercentage,averageViewDuration", filters=f"video=={v['youtube_id']}").execute()
            rows = r.get("rows") or []
            if rows:
                v["avg_view_pct"] = round(float(rows[0][0]), 1); v["avg_view_s"] = round(float(rows[0][1]), 1)
    except Exception as e:  # noqa: BLE001
        print(f"[estadísticas] sin retención: {str(e)[:160]}")


def insights(state):
    """Lo que el guionista tiene que saber de lo que ya se publicó (cuando haya datos suficientes)."""
    done = [v for v in state.get("videos", []) if v.get("views") is not None and v.get("publish_at")]
    old = [v for v in done if dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(v["publish_at"].replace("Z", "+00:00")) > dt.timedelta(hours=48)]
    if len(old) < 3:
        return ""
    old.sort(key=lambda v: (v.get("avg_view_pct") or 0) * 10 + v.get("views", 0), reverse=True)
    fmt = lambda v: f'- "{v["title"]}" — hook: "{v.get("hook", "")}" — {v.get("views", 0)} views, {v.get("avg_view_pct", "?")}% watched'  # noqa: E731
    best, worst = old[:3], old[-3:]
    return ("WHAT OUR AUDIENCE LIKED (more of this kind of story and hook):\n" + "\n".join(fmt(v) for v in best) +
            "\nWHAT DID NOT WORK (avoid this kind):\n" + "\n".join(fmt(v) for v in worst))

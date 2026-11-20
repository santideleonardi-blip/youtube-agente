"""Agente 4 — Publicador.

Crea título llamativo, descripción, tags y miniatura, y sube el video a YouTube.
"""
import datetime as dt
import os
import re
import textwrap

from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

import config
from common import llm, schedule
from common.youtube_auth import youtube


def _metadata(topic, script, fmt, state):
    serie = config.SERIES.get(topic.get("series") or "classic", config.SERIES["classic"])
    best = sorted([v for v in state["videos"] if v.get("views")], key=lambda v: v["views"], reverse=True)[:5]
    return llm.ask_json(
        f"""You are a YouTube packaging expert (titles, thumbnails, SEO) for a viral animated channel.
Niche: {config.NICHE}
Video format: {fmt}
Topic: {topic['topic']}
Summary: {script.get('summary', '')}
Hook line: {script['scenes'][0]['narration']}
Our best titles so far (learn from them): {[(v['title'], v['views']) for v in best] or "none yet"}

Write packaging that maximises click-through WITHOUT lying about the content:
- title: max 70 characters, curiosity-driven, and it MUST start with "What Would Happen If"
  (the channel's signature format), e.g. "What Would Happen If You Never Slept?".
  {"Add #shorts at the end." if fmt == "short" else ""}
- thumbnail_text: 2-4 punchy words in CAPS (complements the title, does not repeat it).
- description: 2-3 engaging sentences, then "Subscribe to {config.CHANNEL_NAME} for a new mind-bending
  hypothetical every day!" (no hashtags in the description, they are added separately).
- hashtags: 5-7 hashtags that people actually search, ordered from most to least important: first the
  1-2 most specific to THIS topic (e.g. #TRex #Dinosaurs, #GTA6, #Sleep), then broad discovery ones for the
  niche (#Science #WhatIf #Facts #Space #Biology...). CamelCase, no spaces, only relevant ones (YouTube
  penalises misleading hashtags). Do NOT include #shorts or {serie['hashtag']} (added automatically).
- tags: 10-15 SEO tags.
- first_comment: the channel's first comment under the video, written as Max: ONE short, fun question that
  makes viewers want to answer (pick a side, choose an option, guess), max 120 characters, 0-1 emoji.
  E.g. "Would you trade your arms for mantis shrimp punches? Yes or no? 👇". No links, no "subscribe".

Return JSON: {{"title": "...", "thumbnail_text": "...", "description": "...", "hashtags": ["#..."], "tags": ["..."],
"first_comment": "..."}}""",
        temperature=0.8,
    )


MAX_HASHTAGS = 8          # YouTube ignora TODOS si hay más de 15; con 5-8 es lo recomendado


def _clean_tag(t):
    t = re.sub(r"[^0-9A-Za-z_]", "", str(t).lstrip("#"))
    return f"#{t}" if t and not t.isdigit() else None


def apply_hashtags(title, description, fmt, topic_tags, series_tag, requested=()):
    """Pone los hashtags donde más rinden:
    - título: el hashtag más específico del tema (y #shorts en los Shorts), es clickeable en la app;
    - descripción: una línea con todos; los 3 primeros los muestra YouTube arriba del título.
    Los pedidos (p. ej. #GTA6) van primero."""
    seen, tags = set(), []
    for t in list(requested) + list(topic_tags or []) + [series_tag]:
        c = _clean_tag(t)
        if c and c.lower() not in seen and c.lower() != "#shorts":
            seen.add(c.lower())
            tags.append(c)
    tags = tags[:MAX_HASHTAGS]
    base = re.sub(r"\s*#\w+", "", title).strip()          # el título queda sin hashtags y se rearma
    suffix = [tags[0]] if tags else []
    if fmt == "short":
        suffix.append("#shorts")
    new_title = base
    for t in suffix:
        if len(f"{new_title} {t}") <= 100:
            new_title = f"{new_title} {t}"
    body = re.sub(r"(\n\s*)?(#\w+\s*)+$", "", (description or "").rstrip()).rstrip()
    line = " ".join(tags + (["#shorts"] if fmt == "short" else []))
    return new_title, f"{body}\n\n{line}" if line else body


def _ensure_hashtag(description, tag):
    return description if tag.lower() in description.lower() else f"{description.rstrip()}\n{tag}"


def _playlist_id(yt, state, series):
    """Lista de reproducción de la serie (se crea la primera vez). Ayuda a que miren varios videos seguidos."""
    ids = state.setdefault("playlists", {})
    if ids.get(series):
        return ids[series]
    serie = config.SERIES[series]
    res = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": serie["playlist"],
                    "description": f"{serie['label']}: Max lives a new 'What would happen if...?' in every episode.",
                    "defaultLanguage": "en"},
        "status": {"privacyStatus": "public"},
    }).execute()
    ids[series] = res["id"]
    print(f"[publicador] lista creada: {serie['playlist']}")
    return res["id"]


def _add_to_playlist(yt, state, series, video_id):
    if series not in config.SERIES:
        return
    try:
        pid = _playlist_id(yt, state, series)
        yt.playlistItems().insert(part="snippet", body={
            "snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}},
        }).execute()
    except Exception as e:  # noqa: BLE001
        print(f"[publicador] no pude agregarlo a la lista de la serie: {e}")


def _thumbnail(cover, text, out):
    img = Image.open(cover).convert("RGB")
    W, H = 1280, 720
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    d = ImageDraw.Draw(img)
    size = 120
    lines = textwrap.wrap(text.upper(), width=12)[:3]
    while size > 50:
        font = ImageFont.truetype(config.FONT_BOLD, size)
        if all(d.textlength(l, font=font) < W * 0.9 for l in lines):
            break
        size -= 8
    y = H - (len(lines) * (size + 10)) - 40
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        x = (W - tw) / 2
        d.text((x, y), line, font=font, fill=(255, 230, 0) if i == 0 else (255, 255, 255),
               stroke_width=max(size // 12, 4), stroke_fill=(0, 0, 0))
        y += size + 10
    img.save(out, "JPEG", quality=92)
    return out


def run(topic, script, render, fmt, state, job_id):
    meta = _metadata(topic, script, fmt, state)
    title = meta.get("title", topic["topic"])[:100]
    series = topic.get("series") or "classic"
    serie_tag = config.SERIES.get(series, config.SERIES["classic"])["hashtag"]
    title, meta["description"] = apply_hashtags(title, meta.get("description", ""), fmt, meta.get("hashtags", []),
                                                 serie_tag, topic.get("hashtags", []))
    status = {"selfDeclaredMadeForKids": False, "embeddable": True}
    if config.PUBLISH_MODE == "public":
        status["privacyStatus"] = "public"
    publish_at = None
    if config.PUBLISH_MODE == "scheduled":
        status["privacyStatus"] = "private"
        publish_at = schedule.next_publish_time(state)
        status["publishAt"] = publish_at.strftime("%Y-%m-%dT%H:%M:%S.0Z")
        print(f"[publicador] se publica: {publish_at.astimezone(schedule.ET):%a %d %H:%M} ET "
              f"({publish_at.astimezone(dt.timezone(dt.timedelta(hours=-3))):%H:%M} Argentina)")
    else:
        status["privacyStatus"] = "private"

    body = {
        "snippet": {
            "title": title,
            "description": meta.get("description", ""),
            "tags": meta.get("tags", [])[:15],
            "categoryId": config.CATEGORY_ID,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
    if os.getenv("DRY_RUN") == "1":
        print(f"[publicador] DRY_RUN — no subo. Título: {title}")
        return {"youtube_id": None, "title": title, "meta": meta, "publish_at": None}

    yt = youtube()
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(render["video"], chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    print(f"[publicador] subido: https://youtu.be/{vid} ({status['privacyStatus']})")
    _add_to_playlist(yt, state, series, vid)

    if fmt == "long":
        try:
            thumb = _thumbnail(render["cover"], meta.get("thumbnail_text", ""),
                               os.path.join(config.OUTPUT_DIR, f"{job_id}_thumb.jpg"))
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb)).execute()
        except Exception as e:  # noqa: BLE001
            print(f"[publicador] no pude poner la miniatura (¿canal sin verificar por teléfono?): {e}")
    return {"youtube_id": vid, "title": title, "meta": meta, "publish_at": publish_at}


def post_pending_comments(state, now=None):
    """Cuando un video ya salió público, el canal deja el primer comentario con una pregunta (invita a
    responder: los comentarios cuentan como interacción). Mientras está programado (privado) no se puede."""
    now = now or dt.datetime.now(dt.timezone.utc)
    yt = None
    for v in state.get("videos", []):
        text = (v.get("first_comment") or "").strip()
        if not text or v.get("comment_id") or not v.get("youtube_id") or v.get("comment_tries", 0) >= 3:
            continue
        live = v.get("publish_at") or v.get("uploaded_at")
        if not live or dt.datetime.fromisoformat(live) > now:
            continue
        try:
            yt = yt or youtube()
            res = yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": v["youtube_id"], "topLevelComment": {"snippet": {"textOriginal": text[:500]}}}}).execute()
            v["comment_id"] = res.get("id")
            print(f"[publicador] comentario publicado en {v['youtube_id']}: {text}")
        except Exception as e:  # noqa: BLE001
            v["comment_tries"] = v.get("comment_tries", 0) + 1
            print(f"[publicador] no pude comentar en {v['youtube_id']}: {str(e)[:200]}")

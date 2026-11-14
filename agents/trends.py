"""Agente 1 — Investigador de tendencias.

Busca los videos del nicho que más vistas están sacando en los últimos días
y elige el próximo tema (sin repetir los que ya hicimos).
"""
import datetime as dt

import config
from common import llm
from common.youtube_auth import youtube


def _trending_videos(days=10, per_query=15):
    yt = youtube()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in config.TREND_QUERIES:
        try:
            res = yt.search().list(
                part="id", q=q, type="video", order="viewCount", publishedAfter=since,
                relevanceLanguage="en", maxResults=per_query,
            ).execute()
            ids += [i["id"]["videoId"] for i in res.get("items", [])]
        except Exception as e:  # noqa: BLE001
            print(f"[tendencias] búsqueda '{q}' falló: {e}")
    ids = list(dict.fromkeys(ids))[:50]
    if not ids:
        return []
    res = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute()
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for it in res.get("items", []):
        pub = dt.datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))
        hours = max((now - pub).total_seconds() / 3600, 1)
        views = int(it["statistics"].get("viewCount", 0))
        out.append({
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "views": views,
            "views_per_hour": round(views / hours),
            "duration": it["contentDetails"]["duration"],
        })
    out.sort(key=lambda x: x["views_per_hour"], reverse=True)
    return out[:20]


def run(state, fmt, notes, topic_insights=None):
    trending = []
    try:
        trending = _trending_videos()
    except Exception as e:  # noqa: BLE001
        print(f"[tendencias] no pude consultar YouTube: {e}")
    done = [v["topic"] for v in state["videos"]][-150:]
    top = [v for v in state["videos"] if v.get("views")]
    top = sorted(top, key=lambda v: v["views"], reverse=True)[:5]

    pick = llm.ask_json(
        f"""You are the trend researcher of a faceless YouTube channel.
Niche: {config.NICHE_DESCRIPTION}
Next video format: {fmt} ({'YouTube Short, under 60 seconds' if fmt == 'short' else 'long video, 8-10 minutes'}).

What is getting the most views per hour in the niche right now:
{trending or "No live data available — rely on your knowledge of evergreen viral 'what if' topics."}

Our best performing videos so far: {[(v['title'], v['views']) for v in top] or "none yet"}
Topics we ALREADY covered (never repeat or closely rephrase these): {done or "none"}
Analyst notes: {notes}
What the analyst learned about which TOPICS work on OUR channel (highest priority, follow it): {topic_insights or "no data yet"}

Pick ONE topic with the highest viral potential. Never copy another creator's exact title or
premise word for word: if you take inspiration from a trending video, give it a clearly different twist for this format. Prefer topics that ride a current
trend or are proven evergreen curiosities, and that can be explained visually. Avoid medical, financial
or legal advice, real tragedies, gore or politics.

Return JSON: {{"topic": "What if ...?", "angle": "the specific hook/angle that makes it irresistible",
"why": "short reason based on the data"}}""",
        temperature=1.0,
    )
    print(f"[tendencias] tema elegido: {pick.get('topic')} — {pick.get('why')}")
    return pick

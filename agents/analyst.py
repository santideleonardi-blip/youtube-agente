"""Agente 5 — Analista.

- Lee la curva de retención de los videos ya publicados (YouTube Analytics).
- Detecta en qué segundo se va la gente y qué escena/frase había ahí.
- Le deja notas al guionista.
- Decide el formato del próximo video (short o largo).
"""
import datetime as dt

from common import llm, schedule
from common import series as series_mod
from common.youtube_auth import analytics, youtube

MIN_AGE_HOURS = 48  # YouTube tarda ~2 días en tener datos de retención


def _retention_curve(video_id, published):
    start = published[:10]
    end = dt.date.today().isoformat()
    res = analytics().reports().query(
        ids="channel==MINE",
        startDate=start,
        endDate=end,
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
    ).execute()
    return [(r[0], r[1], r[2]) for r in res.get("rows", [])]


def _scene_at(video, ratio):
    t = ratio * video.get("duration", 0)
    current = None
    for sc in video.get("scenes", []):
        if sc["start"] <= t:
            current = sc
    return current, t


def _drop_points(video, curve, top=3):
    drops = []
    for (r0, w0, _), (r1, w1, _) in zip(curve, curve[1:]):
        drops.append((w0 - w1, r1))
    drops.sort(reverse=True)
    out = []
    for size, ratio in drops[:top]:
        if size <= 0.02:
            continue
        scene, t = _scene_at(video, ratio)
        out.append({
            "second": round(t, 1),
            "drop_pct": round(size * 100, 1),
            "narration": (scene or {}).get("narration", "")[:300],
        })
    return out


def _stats(ids):
    if not ids:
        return {}
    res = youtube().videos().list(part="statistics", id=",".join(ids[:50])).execute()
    return {i["id"]: i["statistics"] for i in res.get("items", [])}


def _enforce_mix(state, fmt, long_share, now):
    """Mantiene la proporción de largos que pidió el estratega y como mucho 1 largo por día
    (tardan mucho en renderizar y gastan el cupo diario de imágenes)."""
    arg = dt.timezone(dt.timedelta(hours=-3))
    today = now.astimezone(arg).date()
    vids = [v for v in state["videos"] if v.get("youtube_id")]
    long_today = any(v["format"] == "long" and dt.datetime.fromisoformat(v["uploaded_at"]).astimezone(arg).date() == today
                     for v in vids)
    if long_today:
        return "short"
    last = vids[-9:]
    if len(last) >= 3:
        actual = sum(v["format"] == "long" for v in last) / len(last)
        if actual < long_share - 0.15:
            print(f"[analista] pocos largos últimamente ({actual:.0%} vs objetivo {long_share:.0%}) -> largo")
            return "long"
        if actual > long_share + 0.15:
            return "short"
    return fmt


def run(state):
    now = dt.datetime.now(dt.timezone.utc)
    uploaded = [v for v in state["videos"] if v.get("youtube_id")]
    report = []

    stats = {}
    try:
        stats = _stats([v["youtube_id"] for v in uploaded[-50:]])
    except Exception as e:  # noqa: BLE001
        print(f"[analista] no pude leer estadísticas: {e}")

    for v in uploaded[-50:]:
        s = stats.get(v["youtube_id"], {})
        v["views"] = int(s.get("viewCount", v.get("views", 0)))
        v["likes"] = int(s.get("likeCount", v.get("likes", 0)))
        live_since = v.get("publish_at") or v["uploaded_at"]
        age_h = (now - dt.datetime.fromisoformat(live_since)).total_seconds() / 3600
        if age_h < MIN_AGE_HOURS or v.get("analyzed"):
            continue
        try:
            curve = _retention_curve(v["youtube_id"], v["uploaded_at"])
        except Exception as e:  # noqa: BLE001
            print(f"[analista] sin retención para {v['youtube_id']}: {e}")
            continue
        if not curve:
            continue
        v["retention_end"] = round(curve[-1][1], 3)
        v["drops"] = _drop_points(v, curve)
        v["analyzed"] = True
        report.append({"title": v["title"], "format": v["format"], "views": v["views"],
                       "retention_end": v["retention_end"], "drops": v["drops"],
                       "hook": v.get("scenes", [{}])[0].get("narration", "")})

    # Estadísticas por formato
    fs = {}
    for fmt in ("short", "long"):
        vids = [v for v in uploaded if v["format"] == fmt]
        fs[fmt] = {"count": len(vids),
                   "avg_views": round(sum(v.get("views", 0) for v in vids) / len(vids)) if vids else 0}
    state["format_stats"] = fs

    slots, slot_avg = schedule.best_slots(state)
    if slots != state.get("publish_slots_et"):
        print(f"[analista] horarios de publicación (ET): {slots} — vistas promedio por horario: {slot_avg}")
    state["publish_slots_et"] = slots

    state["series_stats"] = series_mod.stats(state)
    recent = [{"title": v["title"], "format": v["format"], "series": v.get("series", "classic"), "views": v.get("views", 0),
               "avg_view_pct": v.get("avg_view_pct"), "subs_gained": v.get("subs_gained")} for v in uploaded[-12:]]
    strat = state.get("strategy") or {}
    long_share = float(strat.get("long_share", 0.33))
    decision = llm.ask_json(
        f"""You are the data analyst of a faceless YouTube channel.
Channel niche: What If...? science & history hypotheticals (English, animated).

New retention analyses (where viewers left and what was being said):
{report or "No new retention data yet."}

Recent videos and views: {recent or "No videos yet (new channel)."}
Average views per format: {fs}
Average views per series (Max's Adventures / Challenges / Curiosities / classic; videos older than 48 h): {state["series_stats"]}

Tasks:
1. Write 3-6 short, concrete, actionable notes for the scriptwriter (what to avoid / repeat, based on
   drop points and what performed). If there is no data yet, give best-practice notes for strong
   retention (hook in first 2 seconds, open loops, no slow intros, pattern interrupts).
2. Content strategy: compare which TOPICS / themes / hooks got the most views and retention.
   Write 2-5 "topic_insights": concrete conclusions about WHAT the videos should be about
   (e.g. "body-swap with animals beats space topics 3x", "avoid slow historical topics",
   "challenge episodes keep viewers longer than adventures").
   Keep the useful previous insights unless the data contradicts them.
   Previous insights: {state.get("topic_insights", [])}
3. Decide the format of the NEXT video: "short" or "long".
   The growth strategist set the target mix: about {long_share:.0%} long videos ({strat.get("long_share_reason", "default mix")}).
   Follow that mix; deviate only if the data clearly says so.

Return JSON: {{"notes": ["..."], "topic_insights": ["..."], "next_format": "short"|"long", "reason": "..."}}""",
        temperature=0.4,
    )
    if decision.get("topic_insights"):
        state["topic_insights"] = decision["topic_insights"][:6]
    fmt = decision.get("next_format", "short")
    if fmt not in ("short", "long"):
        fmt = "short"
    fmt = _enforce_mix(state, fmt, long_share, now)
    state["feedback"] = (state.get("feedback", []) + [{
        "date": now.isoformat(), "notes": decision.get("notes", []), "reason": decision.get("reason", "")
    }])[-20:]
    print(f"[analista] próximo formato: {fmt} — {decision.get('reason', '')}")
    return {"format": fmt, "notes": decision.get("notes", []), "topic_insights": state.get("topic_insights", [])}

"""Agente 6 — Estratega de crecimiento.

Corre una vez por día (antes que el resto) y se encarga de ESCALAR el canal:
- Mide el canal: suscriptores, vistas por día, horas de visualización (videos largos) y vistas de Shorts.
- Calcula el avance hacia la monetización (YouTube Partner Program) y a qué ritmo se va.
- Decide cuántos videos por día producir (sube de a 1 cuando el canal aguanta más volumen sin perder
  calidad, baja si el volumen empieza a hundir las vistas por video).
- Decide qué proporción de videos largos vs Shorts conviene según qué camino a la monetización avanza más rápido.
- Deja "notas de foco" para el investigador y el guionista (experimentos, variedad para no parecer contenido en serie).
- Escribe un reporte legible en data/growth_report.md.
"""
import datetime as dt
import os
import statistics

import config
from common import llm
from common.youtube_auth import analytics, youtube

ARG = dt.timezone(dt.timedelta(hours=-3))

# Requisitos del Programa de Partners de YouTube para canales que aplican desde el 1/2/2027.
# (Antes de esa fecha eran 4.000 h / 10M de vistas de Shorts; apuntamos directo a los nuevos.)
YPP_ADS = {"subs": 1000, "watch_hours_365d": 8000, "shorts_views_90d": 20_000_000}
YPP_FAN = {"subs": 500, "watch_hours_365d": 3000, "shorts_views_90d": 3_000_000}

MIN_DAILY = 1
MAX_DAILY = 4          # tope por cupo de la API de YouTube (~2.100 de 10.000 unidades por video subido)
START_DAILY = 2
CADENCE_REVIEW_DAYS = 7
MIN_VIDEOS_TO_SCALE = 7
LONG_SHARE_RANGE = (0.2, 0.6)   # siempre se sigue probando el otro formato
RUN_EVERY_HOURS = 20
REPORT_FILE = os.path.join(config.DATA_DIR, "growth_report.md")


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _parse(ts):
    return dt.datetime.fromisoformat(ts) if ts else None


def _channel_stats():
    res = youtube().channels().list(part="statistics", mine=True).execute()
    items = res.get("items", [])
    if not items:
        return {}
    s = items[0]["statistics"]
    return {"subs": int(s.get("subscriberCount", 0)), "total_views": int(s.get("viewCount", 0)),
            "video_count": int(s.get("videoCount", 0))}


def _per_video(days):
    """Métricas por video en la ventana de los últimos `days` días."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    res = analytics().reports().query(
        ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
        metrics="views,estimatedMinutesWatched,averageViewPercentage,subscribersGained",
        dimensions="video", sort="-views", maxResults=200,
    ).execute()
    return {r[0]: {"views": int(r[1]), "minutes": float(r[2]), "avg_pct": float(r[3]), "subs": int(r[4])}
            for r in res.get("rows", [])}


def _daily(days=28):
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    res = analytics().reports().query(
        ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
        metrics="views,subscribersGained,estimatedMinutesWatched", dimensions="day", sort="day",
    ).execute()
    return [{"day": r[0], "views": int(r[1]), "subs": int(r[2]), "minutes": float(r[3])}
            for r in res.get("rows", [])]


def collect(state):
    """Junta todas las métricas que pueda. Si una consulta falla, sigue con lo que haya."""
    m = {"subs": None, "watch_hours_365d": 0.0, "shorts_views_90d": 0, "daily": []}
    fmt_by_id = {v["youtube_id"]: v["format"] for v in state["videos"] if v.get("youtube_id")}
    try:
        m.update(_channel_stats())
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] no pude leer el canal: {e}")
    try:
        year = _per_video(365)
        m["watch_hours_365d"] = round(sum(r["minutes"] for vid, r in year.items()
                                          if fmt_by_id.get(vid) == "long") / 60, 1)
        for v in state["videos"]:
            r = year.get(v.get("youtube_id"))
            if r:
                v["avg_view_pct"] = round(r["avg_pct"], 1)
                v["subs_gained"] = r["subs"]
                v["minutes_watched"] = round(r["minutes"])
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] sin métricas anuales por video: {e}")
    try:
        q = _per_video(90)
        m["shorts_views_90d"] = sum(r["views"] for vid, r in q.items() if fmt_by_id.get(vid) == "short")
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] sin métricas de 90 días: {e}")
    try:
        month = _per_video(28)
        m["long_minutes_28d"] = sum(r["minutes"] for vid, r in month.items() if fmt_by_id.get(vid) == "long")
        m["shorts_views_28d"] = sum(r["views"] for vid, r in month.items() if fmt_by_id.get(vid) == "short")
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] sin métricas de 28 días: {e}")
    try:
        m["daily"] = _daily(28)
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] sin métricas diarias: {e}")
    return m


def _pace(m):
    """Ritmo de los últimos 28 días, y qué fracción del objetivo se alcanzaría sosteniéndolo
    durante la ventana completa que mide YouTube (365 días para horas, 90 para Shorts)."""
    days = m["daily"][-28:]
    n = max(len(days), 1)
    long_hours_day = m.get("long_minutes_28d", 0) / 60 / 28
    shorts_views_day = m.get("shorts_views_28d", 0) / 28
    return {
        "views_day": round(sum(d["views"] for d in days) / n, 1),
        "subs_day": round(sum(d["subs"] for d in days) / n, 2),
        "long_hours_day": round(long_hours_day, 2),
        "shorts_views_day": round(shorts_views_day),
        "long_path_fraction": round(long_hours_day * 365 / YPP_ADS["watch_hours_365d"], 3),
        "shorts_path_fraction": round(shorts_views_day * 90 / YPP_ADS["shorts_views_90d"], 3),
    }


def _eta_days(current, target, per_day):
    if current is None:
        return None
    if current >= target:
        return 0
    if per_day <= 0:
        return None
    return int((target - current) / per_day) + 1


def _median_views(videos):
    vals = [v.get("views", 0) for v in videos]
    return statistics.median(vals) if vals else 0


def decide_cadence(state, now):
    """Sube o baja la cantidad de videos por día, como mucho 1 paso por semana."""
    strat = state.get("strategy", {})
    cadence = strat.get("daily_target", START_DAILY)
    last_change = _parse(strat.get("cadence_changed_at"))
    if last_change and (now - last_change).days < CADENCE_REVIEW_DAYS:
        return cadence, f"se mantiene en {cadence}/día (la próxima revisión es a los {CADENCE_REVIEW_DAYS} días del último cambio)"

    def live(v):
        t = _parse(v.get("publish_at") or v.get("uploaded_at"))
        return t, v
    vids = [(t, v) for t, v in map(live, state["videos"]) if v.get("youtube_id") and t and (now - t).total_seconds() > 48 * 3600]
    recent = [v for t, v in vids if (now - t).days < 7]
    prev = [v for t, v in vids if 7 <= (now - t).days < 14]
    if len(vids) < MIN_VIDEOS_TO_SCALE or len(recent) < 3:
        return cadence, f"se mantiene en {cadence}/día: todavía hay pocos videos con datos ({len(vids)})"

    med_recent, med_prev = _median_views(recent), _median_views(prev)
    # aguantó bien la semana: las vistas por video no se cayeron (o todavía no hay semana previa para comparar)
    ratio = (med_recent / med_prev) if med_prev else 1.0
    failures = len([f for f in state.get("failures", []) if (now - _parse(f)).days < 7])
    if ratio >= 0.8 and failures <= 1 and cadence < MAX_DAILY:
        return cadence + 1, (f"sube a {cadence + 1}/día: la mediana de vistas por video se sostuvo "
                             f"({med_recent:.0f} vs {med_prev:.0f} la semana anterior), así que más volumen = más alcance")
    if ratio < 0.5 and cadence > MIN_DAILY:
        return cadence - 1, (f"baja a {cadence - 1}/día: las vistas por video cayeron fuerte "
                             f"({med_recent:.0f} vs {med_prev:.0f}); conviene menos volumen y más calidad")
    return cadence, f"se mantiene en {cadence}/día (mediana de vistas {med_recent:.0f} vs {med_prev:.0f})"


def decide_long_share(state, pace):
    """Qué proporción de largos producir según cuál camino a la monetización avanza más rápido."""
    analyzed = [v for v in state["videos"] if v.get("analyzed")]
    longs = [v for v in analyzed if v["format"] == "long"]
    shorts = [v for v in analyzed if v["format"] == "short"]
    if len(longs) < 2 or len(shorts) < 4:
        return 0.33, "fase de prueba: 1 de cada 3 videos es largo hasta tener datos de los dos formatos"
    lf, sf = pace["long_path_fraction"], pace["shorts_path_fraction"]
    if lf >= sf * 1.3:
        share, why = 0.5, f"los videos largos acercan más a la monetización (ritmo {lf:.1%} vs {sf:.1%} de Shorts)"
    elif sf >= lf * 1.3:
        share, why = 0.25, f"los Shorts acercan más a la monetización (ritmo {sf:.1%} vs {lf:.1%} de largos)"
    else:
        share, why = 0.33, f"los dos caminos van parejos ({lf:.1%} largos vs {sf:.1%} Shorts)"
    lo, hi = LONG_SHARE_RANGE
    return max(lo, min(hi, share)), why


def _focus_notes(state, metrics, pace, cadence, long_share):
    top = sorted([v for v in state["videos"] if v.get("views")], key=lambda v: v["views"], reverse=True)[:8]
    low = sorted([v for v in state["videos"] if v.get("analyzed")], key=lambda v: v.get("views", 0))[:5]
    recent_titles = [v["title"] for v in state["videos"][-15:]]
    return llm.ask_json(
        f"""You are the growth strategist of an automated faceless YouTube channel.
Channel: {config.NICHE_DESCRIPTION}
Goal: grow views and subscribers steadily and reach YouTube monetization
(1,000 subs + 8,000 watch hours from long videos in 12 months, or 20M Shorts views in 90 days).

Current metrics: subscribers={metrics.get('subs')}, long-video watch hours (365d)={metrics['watch_hours_365d']},
Shorts views (90d)={metrics['shorts_views_90d']}. Pace per day: {pace}.
Production plan: {cadence} videos/day, {long_share:.0%} long videos.
Best videos (title, views, avg % viewed, subs gained):
{[(v['title'], v.get('views'), v.get('avg_view_pct'), v.get('subs_gained')) for v in top] or 'none yet'}
Worst analysed videos: {[(v['title'], v.get('views')) for v in low] or 'none yet'}
Last titles published: {recent_titles}
Previous focus notes: {state.get('strategy', {}).get('focus_notes', [])}

IMPORTANT: YouTube can deny monetization to channels that look mass-produced or repetitive
("inauthentic content"). The channel must show real variety and added value: varied angles,
recurring series, different hook styles, real science, Max the character with personality.

Write:
1. "focus_notes": 3-5 concrete directions for the next days for the topic researcher and scriptwriter
   (e.g. a series to start or double down on, one experiment to run this week, what to stop doing,
   how to vary structure/titles so videos don't feel templated). Base them on the data when there is data.
2. "experiment": ONE specific A/B-style experiment for this week and how we'll know if it worked.
3. "summary_es": 2-3 sentences IN SPANISH (Argentina), simple words, explaining to the channel owner
   how the channel is doing and what the system will do next.

Return JSON: {{"focus_notes": ["..."], "experiment": "...", "summary_es": "..."}}""",
        temperature=0.6,
    )


def _n(x, dec=0):
    """Número con formato argentino (1.234,5)."""
    txt = f"{x:,.{dec}f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _bar(frac, width=20):
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled) + f" {frac:.1%}"


def write_report(state, metrics, pace, strat, now):
    subs = metrics.get("subs") or 0
    wh = metrics["watch_hours_365d"]
    sv = metrics["shorts_views_90d"]
    eta_subs = _eta_days(subs, YPP_ADS["subs"], pace["subs_day"])
    eta = lambda d: "ya está" if d == 0 else (f"~{d} días al ritmo actual" if d else "sin ritmo todavía")  # noqa: E731
    top = sorted([v for v in state["videos"] if v.get("views")], key=lambda v: v["views"], reverse=True)[:5]
    lines = [
        "# Reporte de crecimiento — WhatWouldHappenIf?",
        "",
        f"_Actualizado: {now.astimezone(ARG):%d/%m/%Y %H:%M} (Argentina). Lo escribe solo el agente Estratega una vez por día._",
        "",
        "## Resumen",
        strat.get("summary_es") or "Todavía no hay datos suficientes para un resumen.",
        "",
        "## Camino a la monetización (reglas desde el 1/2/2027)",
        "Hacen falta **1.000 suscriptores** y además **una** de estas dos: 8.000 horas de videos largos en 12 meses "
        "**o** 20 millones de vistas de Shorts en 90 días.",
        "",
        "| Requisito | Ahora | Objetivo | Avance | Cuándo |",
        "|---|---|---|---|---|",
        f"| Suscriptores | {_n(subs)} | 1.000 | `{_bar(subs / YPP_ADS['subs'])}` | {eta(eta_subs)} |",
        f"| Horas de videos largos (12 meses) | {_n(wh)} | 8.000 | `{_bar(wh / YPP_ADS['watch_hours_365d'])}` | "
        f"{eta(_eta_days(wh, YPP_ADS['watch_hours_365d'], pace['long_hours_day']))} |",
        f"| Vistas de Shorts (90 días) | {_n(sv)} | 20.000.000 | `{_bar(sv / YPP_ADS['shorts_views_90d'])}` | "
        f"ritmo: {pace['shorts_path_fraction']:.1%} del objetivo cada 90 días |",
        "",
        f"Primer escalón (membresías y Super Thanks, sin anuncios): 500 suscriptores + 3.000 h o 3M de vistas de Shorts — "
        f"suscriptores {subs}/500.",
        "",
        "## Ritmo (promedio últimos 28 días)",
        f"- Vistas por día: **{_n(pace['views_day'])}**",
        f"- Suscriptores nuevos por día: **{_n(pace['subs_day'], 1)}**",
        f"- Horas de videos largos por día: **{_n(pace['long_hours_day'], 1)}**",
        "",
        "## Plan de producción",
        f"- Videos por día: **{strat['daily_target']}** — {strat['cadence_reason']}",
        f"- Videos largos: **{strat['long_share']:.0%}** — {strat['long_share_reason']}",
        f"- Experimento de la semana: {strat.get('experiment') or '—'}",
        "",
        "### Notas de foco para el investigador y el guionista",
        *([f"- {n}" for n in strat.get("focus_notes", [])] or ["- (todavía ninguna)"]),
        "",
        "## Mejores videos",
        *([f"- {v['title']} — {_n(v.get('views', 0))} vistas"
           + (f", {v['avg_view_pct']}% visto" if v.get("avg_view_pct") is not None else "")
           + (f", +{v['subs_gained']} subs" if v.get("subs_gained") else "")
           for v in top] or ["- (todavía sin datos)"]),
        "",
    ]
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run(state, force=False):
    now = _now()
    strat = state.setdefault("strategy", {"daily_target": START_DAILY, "long_share": 0.33, "focus_notes": []})
    strat.setdefault("daily_target", START_DAILY)
    last = _parse(strat.get("last_run"))
    if not force and last and (now - last).total_seconds() < RUN_EVERY_HOURS * 3600:
        return strat

    metrics = collect(state)
    pace = _pace(metrics)
    old_cadence = strat.get("daily_target", START_DAILY)
    cadence, cadence_reason = decide_cadence(state, now)
    long_share, long_reason = decide_long_share(state, pace)
    if cadence != old_cadence:
        strat["cadence_changed_at"] = now.isoformat()
        print(f"[estratega] cadencia {old_cadence} -> {cadence} videos/día")
    if not strat.get("cadence_changed_at"):
        strat["cadence_changed_at"] = now.isoformat()

    strat.update({
        "daily_target": cadence, "cadence_reason": cadence_reason,
        "long_share": long_share, "long_share_reason": long_reason,
        "metrics": {k: v for k, v in metrics.items() if k != "daily"}, "pace": pace,
        "last_run": now.isoformat(),
    })
    try:
        notes = _focus_notes(state, metrics, pace, cadence, long_share)
        strat["focus_notes"] = [n for n in notes.get("focus_notes", []) if isinstance(n, str)][:5]
        strat["experiment"] = notes.get("experiment", "")
        strat["summary_es"] = notes.get("summary_es", "")
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] sin notas de foco esta vez: {e}")

    hist = state.setdefault("growth_history", [])
    hist.append({"date": now.date().isoformat(), "subs": metrics.get("subs"),
                 "watch_hours_365d": metrics["watch_hours_365d"], "shorts_views_90d": metrics["shorts_views_90d"],
                 "views_day": pace["views_day"], "daily_target": cadence, "long_share": long_share})
    state["growth_history"] = hist[-120:]
    try:
        write_report(state, metrics, pace, strat, now)
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] no pude escribir el reporte: {e}")
    print(f"[estratega] plan: {cadence} videos/día, {long_share:.0%} largos — {cadence_reason}")
    return strat

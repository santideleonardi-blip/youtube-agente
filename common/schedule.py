"""Horarios de publicación pensados para el público de Estados Unidos (hora del Este, ET).

- Hay horarios candidatos. El sistema arranca con 2 recomendados y el analista,
  con datos reales, se queda con los que mejor rinden (probando otros de vez en cuando).
"""
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CANDIDATE_HOURS_ET = [11, 13, 15, 17, 19, 21]
DEFAULT_SLOTS_ET = [15, 19]      # 3 PM y 7 PM ET: tarde y prime time en EE.UU.
SLOT_PRIORITY_ET = [15, 19, 17, 13, 21, 11]  # orden en que se suman horarios cuando sube la cadencia
MIN_REVIEW_HOURS = 3             # tiempo mínimo para que puedas revisar antes de que salga


def next_publish_time(state, now=None):
    """Próximo horario libre (de los elegidos por el analista) con al menos MIN_REVIEW_HOURS de margen."""
    now = now or dt.datetime.now(dt.timezone.utc)
    slots = state.get("publish_slots_et") or DEFAULT_SLOTS_ET
    used = {v.get("publish_at") for v in state.get("videos", []) if v.get("publish_at")}
    earliest = now + dt.timedelta(hours=MIN_REVIEW_HOURS)
    day = earliest.astimezone(ET).date()
    for add in range(0, 4):
        d = day + dt.timedelta(days=add)
        for hour in sorted(slots):
            t = dt.datetime(d.year, d.month, d.day, hour, 0, tzinfo=ET).astimezone(dt.timezone.utc)
            if t >= earliest and t.isoformat() not in used:
                return t
    return earliest


def best_slots(state):
    """Elige tantos horarios como videos por día decidió el estratega, según las vistas promedio
    de los videos ya publicados en cada horario (probando uno nuevo de vez en cuando)."""
    n = max(1, min(len(CANDIDATE_HOURS_ET), int((state.get("strategy") or {}).get("daily_target", 2))))
    perf = {}
    for v in state.get("videos", []):
        h = v.get("publish_hour_et")
        if h is None or not v.get("analyzed"):
            continue
        perf.setdefault(h, []).append(v.get("views", 0))
    avg = {h: sum(x) / len(x) for h, x in perf.items() if len(x) >= 2}
    current = state.get("publish_slots_et") or DEFAULT_SLOTS_ET
    if len(avg) < 2:
        ranked = list(current)
    else:
        ranked = sorted(avg, key=avg.get, reverse=True)
    # completar (o recortar) hasta n horarios
    for h in list(current) + SLOT_PRIORITY_ET:
        if len(ranked) >= n:
            break
        if h not in ranked:
            ranked.append(h)
    ranked = ranked[:n]
    # exploración: cada 6 videos prueba un horario que todavía no tiene datos suficientes
    total = len([v for v in state.get("videos", []) if v.get("youtube_id")])
    untested = [h for h in CANDIDATE_HOURS_ET if h not in avg and h not in ranked]
    if untested and total and total % 6 == 0 and len(ranked) >= 2:
        ranked = ranked[:-1] + [untested[0]]
    return sorted(ranked), avg

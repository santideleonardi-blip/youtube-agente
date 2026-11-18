"""Pedidos de temas puntuales (por ejemplo de Santi: "mañana sale GTA 6, hagamos un video de eso").

Están en data/topic_requests.json, se pueden agregar a mano. Cada pedido:
  {"id": "gta6", "topic": "What would happen if ...?", "series": "challenge", "format": "short",
   "not_before": "2026-11-18", "angle": "...", "notes": ["..."], "done": false}
El próximo video usa el primer pedido pendiente cuya fecha (Argentina) ya llegó, en vez de que el
investigador elija tema. Se marca hecho cuando el video se sube.
"""
import datetime as dt
import json
import os

import config
from common import schedule

PATH = os.path.join(config.ROOT, "data", "topic_requests.json")
ART = dt.timezone(dt.timedelta(hours=-3))


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(items):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def next_request(now=None):
    today = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ART).date().isoformat()
    for r in _load():
        if not r.get("done") and r.get("topic") and r.get("not_before", "") <= today:
            return r
    return None


def mark_done(req_id, video_id=None):
    items = _load()
    for r in items:
        if r.get("id") == req_id:
            r["done"] = True
            r["youtube_id"] = video_id
    _save(items)

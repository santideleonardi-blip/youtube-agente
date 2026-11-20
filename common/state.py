"""Memoria del sistema: historial de videos y notas del analista (data/state.json)."""
import json
import os

import config

DEFAULT = {"videos": [], "feedback": [], "format_stats": {}}


def load():
    if os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in DEFAULT.items():
            data.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)())
        return data
    return json.loads(json.dumps(DEFAULT))


MATURE_HOURS = 48   # antes de esto las vistas de un video todavía no dicen nada


def matured(v, now=None, hours=MATURE_HOURS):
    """Video subido que ya lleva 48 h publicado: sus vistas sirven para comparar.
    (No depende de "analyzed": YouTube no da curva de retención a muchos videos chicos y quedaban afuera.)"""
    import datetime as dt

    if not v.get("youtube_id"):
        return False
    since = v.get("publish_at") or v.get("uploaded_at")
    if not since:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        return (now - dt.datetime.fromisoformat(since)).total_seconds() / 3600 >= hours
    except ValueError:
        return False


def save(state):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

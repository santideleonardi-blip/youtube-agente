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


def save(state):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

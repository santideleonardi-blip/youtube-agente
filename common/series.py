"""Series del canal: todos los videos siguen siendo "What would happen if...?", pero Max lo vive de
formas distintas (aventura, reto, curiosidad o clásico). Da variedad real (contra la política de
"contenido no auténtico") y el sistema aprende qué serie funciona mejor.
"""
import os
import random

import config
from common.state import matured

MIN_AGE_HOURS = 48     # antes de esto las vistas de un video todavía no dicen nada
MIN_VIDEOS = 3         # con menos videos por serie no se saca ninguna conclusión
WEIGHT_RANGE = (0.5, 2.0)


def _views_by_series(state):
    out = {k: [] for k in config.SERIES}
    for v in state.get("videos", []):
        s = v.get("series")
        if s in out and matured(v):
            out[s].append(v.get("views", 0))
    return out


def stats(state):
    """{serie: {"count", "avg_views"}} contando solo videos ya analizados (>48 h publicados)."""
    vbs = _views_by_series(state)
    return {k: {"count": len(vs), "avg_views": round(sum(vs) / len(vs)) if vs else 0} for k, vs in vbs.items()}


def weights(state):
    """Arrancan todas iguales; cuando una serie tiene datos, pesa según sus vistas vs. el promedio."""
    st = stats(state)
    with_data = [s["avg_views"] for s in st.values() if s["count"] >= MIN_VIDEOS]
    overall = (sum(with_data) / len(with_data)) if with_data else 0
    lo, hi = WEIGHT_RANGE
    w = {}
    for k, s in st.items():
        if s["count"] >= MIN_VIDEOS and overall > 0:
            w[k] = max(lo, min(hi, s["avg_views"] / overall))
        else:
            w[k] = 1.0  # sin datos: se le da la misma chance (hay que probarla)
    return w


def pick(state, rng=random):
    """Elige la serie del próximo video: ponderada por rendimiento y sin repetir la del video anterior."""
    forced = os.getenv("FORCE_SERIES")
    if forced in config.SERIES:
        return forced
    w = weights(state)
    last = next((v.get("series") for v in reversed(state.get("videos", [])) if v.get("series")), None)
    options = [k for k in config.SERIES if k != last] or list(config.SERIES)
    choice = rng.choices(options, weights=[w[k] for k in options])[0]
    print(f"[series] pesos {({k: round(x, 2) for k, x in w.items()})}, anterior: {last} -> {choice}")
    return choice

"""Orquestador: corre los 5 agentes en cadena para producir y subir UN video.

Orden: Analista (formato + notas) -> Investigador (tema) -> Guionista -> Animador -> Publicador
"""
import datetime as dt
import os
import sys
import time
import traceback

from agents import analyst, animator, publisher, scriptwriter, trends
from common import state as st


def main():
    state = st.load()
    job_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"=== Nuevo video {job_id} ===")

    forced = os.getenv("FORCE_FORMAT")
    try:
        decision = analyst.run(state)
    except Exception as e:  # noqa: BLE001
        print(f"[analista] falló, sigo con valores por defecto: {e}")
        decision = {"format": "short", "notes": []}
    fmt = forced if forced in ("short", "long") else decision["format"]
    st.save(state)

    topic = trends.run(state, fmt, decision["notes"])
    script = scriptwriter.run(topic, fmt, decision["notes"], state.get("feedback", []))
    render = animator.run(script, fmt, job_id)
    pub = publisher.run(topic, script, render, fmt, state, job_id)

    state["videos"].append({
        "job_id": job_id,
        "youtube_id": pub["youtube_id"],
        "title": pub["title"],
        "topic": topic["topic"],
        "format": fmt,
        "duration": round(render["duration"], 2),
        "scenes": render["scenes"],
        "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    st.save(state)
    print("=== Listo ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)

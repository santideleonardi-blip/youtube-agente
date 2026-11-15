"""Orquestador: corre los agentes en cadena para producir y subir UN video.

Orden: Estratega (1 vez por día: cuántos videos por día y qué mezcla) -> Analista (formato + notas)
       -> Investigador (tema) -> Guionista -> Animador -> Publicador

El workflow se dispara en 4 turnos por día; el estratega decide cuántos se usan (1 a 4).
"""
import datetime as dt
import os
import sys
import time
import traceback

import config
from agents import analyst, animator, publisher, scriptwriter, strategist, trends
from common import llm, schedule
from common import state as st


ARG = dt.timezone(dt.timedelta(hours=-3))
# Turnos de producción (hora Argentina) en el orden en que se van habilitando al subir la cadencia.
# Tienen que coincidir con los cron de .github/workflows/run.yml (08:07, 11:07, 15:07, 19:07 ARG).
TURNS_ARG = [8, 15, 11, 19]


def should_produce(state, now=None):
    """¿Le toca producir a este turno? Usa los primeros N turnos del día (N = videos/día del estratega)
    y, si un turno anterior falló, el siguiente lo recupera."""
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(ARG)
    target = int((state.get("strategy") or {}).get("daily_target", 2))
    allowed = sorted(TURNS_ARG[:target])
    passed = [h for h in allowed if h <= local.hour]
    done_today = len([v for v in state["videos"] if v.get("youtube_id")
                      and dt.datetime.fromisoformat(v["uploaded_at"]).astimezone(ARG).date() == local.date()])
    ok = done_today < len(passed)
    print(f"[turno] {local:%H:%M} ARG — objetivo {target}/día, hechos hoy {done_today}, "
          f"turnos habilitados {allowed} -> {'produzco' if ok else 'no toca, salgo'}")
    return ok


def _note_quota(state, manual):
    """Si se agotó el cupo diario gratis de Gemini o de imágenes (Cloudflare), lo anota: el estratega no sube la cadencia."""
    if os.getenv("DRY_RUN") != "1":  # las corridas manuales reales también gastan cupo de imágenes
        _add_cf_usage(state, animator.cf_images, exhausted=animator.cf_quota_hit)
        st.save(state)
    if manual:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if llm.quota_hit:
        print(f"[llm] cupo diario agotado en: {sorted(llm.quota_hit)}")
        state["quota_hits"] = (state.get("quota_hits", []) + [now])[-20:]
    if animator.cf_quota_hit:
        state["image_quota_hits"] = (state.get("image_quota_hits", []) + [now])[-20:]
    st.save(state)


def _cf_usage(state):
    """Imágenes FLUX.2 usadas hoy (día UTC, que es cuando se renueva el cupo de Cloudflare)."""
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    u = state.get("cf_usage") or {}
    return u if u.get("date") == today else {"date": today, "images": 0, "exhausted": False}


def _add_cf_usage(state, n, exhausted=False):
    u = _cf_usage(state)
    u["images"] += n
    u["exhausted"] = u.get("exhausted") or exhausted
    state["cf_usage"] = u


def images_left(state):
    u = _cf_usage(state)
    if u.get("exhausted"):
        return 0
    return (animator.CF_DAILY_NEURONS - 300) // animator.CF_NEURONS_PER_IMAGE - u["images"]


def main():
    state = st.load()
    job_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" or os.getenv("DRY_RUN") == "1"

    try:
        strat = strategist.run(state)
    except Exception as e:  # noqa: BLE001
        print(f"[estratega] falló, sigo con el plan anterior: {e}")
        strat = state.get("strategy") or {}
    st.save(state)
    if not manual and not should_produce(state):
        return

    print(f"=== Nuevo video {job_id} ===")
    forced = os.getenv("FORCE_FORMAT")
    try:
        decision = analyst.run(state)
    except Exception as e:  # noqa: BLE001
        print(f"[analista] falló, sigo con valores por defecto: {e}")
        decision = {"format": "short", "notes": [], "topic_insights": state.get("topic_insights", [])}
    fmt = forced if forced in ("short", "long") else decision["format"]
    last_up = max((dt.datetime.fromisoformat(v["uploaded_at"]) for v in state["videos"] if v.get("youtube_id")), default=None)
    if last_up and (dt.datetime.now(dt.timezone.utc) - last_up).total_seconds() > 36 * 3600:
        animator.ALLOW_FALLBACK = True  # el canal lleva mucho sin videos: mejor otro estilo que nada
        print("[animador] más de 36 h sin videos: si falta cupo de FLUX.2 se permite el respaldo")
    left = images_left(state)
    need = {f: animator.images_needed(f, config.FORMATS[f]["scenes"][1]) for f in ("short", "long")}
    if not animator.ALLOW_FALLBACK and need[fmt] > left:
        if fmt == "long" and need["short"] <= left:
            print(f"[animador] quedan ~{left} imágenes FLUX.2 hoy: no alcanzan para un largo ({need['long']}) -> Short")
            fmt = "short"
        else:
            print(f"[animador] quedan ~{left} imágenes FLUX.2 hoy (hacen falta {need[fmt]}): se pospone al próximo turno")
            st.save(state)
            return
    st.save(state)
    focus = [f"[growth strategy] {n}" for n in strat.get("focus_notes", [])]
    if strat.get("experiment"):
        focus.append(f"[experiment this week] {strat['experiment']}")
    notes = list(decision["notes"]) + focus

    try:
        topic = trends.run(state, fmt, notes, decision.get("topic_insights"))
        try:
            script = scriptwriter.run(topic, fmt, notes, state.get("feedback", []))
        except scriptwriter.ScriptTooShort as e:
            # un "largo" de 3 minutos no suma horas y se ve flojo: mejor un buen Short del mismo tema
            print(f"[guionista] {e} -> lo hago como Short")
            fmt = "short"
            script = scriptwriter.run(topic, fmt, notes, state.get("feedback", []))
        try:
            render = animator.run(script, fmt, job_id)
        except animator.ImageQuotaExhausted as e:
            print(f"[animador] {e}")
            _note_quota(state, manual)
            print("=== Pospuesto: el próximo turno lo vuelve a intentar ===")
            return
        pub = publisher.run(topic, script, render, fmt, state, job_id)
    except Exception:
        _note_quota(state, manual)
        if not manual:
            state["failures"] = (state.get("failures", []) + [dt.datetime.now(dt.timezone.utc).isoformat()])[-20:]
            st.save(state)
        raise
    _note_quota(state, manual)
    if not pub.get("youtube_id"):
        print("=== Listo (prueba, no se subió) ===")
        return

    state["videos"].append({
        "job_id": job_id,
        "youtube_id": pub["youtube_id"],
        "title": pub["title"],
        "topic": topic["topic"],
        "format": fmt,
        "duration": round(render["duration"], 2),
        "scenes": render["scenes"],
        "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "publish_at": pub["publish_at"].isoformat() if pub.get("publish_at") else None,
        "publish_hour_et": pub["publish_at"].astimezone(schedule.ET).hour if pub.get("publish_at") else None,
    })
    st.save(state)
    print("=== Listo ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)

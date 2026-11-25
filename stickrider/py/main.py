"""StickRider — un Short por corrida: investigar → guion → voz → director → sonido → render → subir.

Uso:  python stickrider/py/main.py                (corrida normal)
      DRY_RUN=1 python stickrider/py/main.py      (genera el video pero no lo sube)
      SR_SCRIPT=archivo.json ...                  (usa un guion ya escrito, sin Gemini)
"""
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import director  # noqa: E402
import publish  # noqa: E402
import render  # noqa: E402
import sound  # noqa: E402
import voice  # noqa: E402

STATE = os.path.join(SR, "data", "state.json")
OUT = os.getenv("SR_OUT", os.path.join(os.path.dirname(SR), "output", "stickrider"))


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"videos": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)


def main():
    t0 = time.time()
    dry = os.getenv("DRY_RUN") == "1"
    state = load_state()
    if os.getenv("GITHUB_EVENT_NAME") == "schedule" and not dry:
        now = dt.datetime.now(dt.timezone.utc)
        pend = [v for v in state.get("videos", []) if v.get("publish_at")
                and dt.datetime.fromisoformat(v["publish_at"].replace("Z", "+00:00")) > now]
        if pend:  # hay varias corridas programadas por día (por si GitHub atrasa una): si ya hay un video esperando, no hago otro
            print(f"[stickrider] ya hay un video programado ({pend[-1]['publish_at']}): no hago otro")
            return
    try:
        publish.refresh_stats(state)
    except Exception as e:  # noqa: BLE001
        print(f"[estadísticas] no pude actualizar: {str(e)[:200]}")
    job = os.getenv("SR_JOB") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M")
    wd = os.path.join(OUT, job)
    os.makedirs(wd, exist_ok=True)
    # ---- guion ----
    sp = os.path.join(wd, "script.json")
    if os.getenv("SR_SCRIPT"):
        with open(os.environ["SR_SCRIPT"]) as f:
            import writer
            script = writer.validate(json.load(f))
    elif os.path.exists(sp):
        with open(sp) as f:
            script = json.load(f)
    else:
        import writer
        ins = publish.insights(state)
        try:
            notes, sources = writer.research(state, ins)
            script = writer.write(notes, sources, ins)
        except Exception as e:  # noqa: BLE001
            # la clave de StickRider sin cupo: probar con la clave de respaldo (la del canal de Max)
            fb = os.getenv("GEMINI_API_KEY_FALLBACK")
            if not fb or fb == os.getenv("GEMINI_API_KEY") or not any(x in str(e) for x in ("429", "RESOURCE_EXHAUSTED", "quota", "Gemini no respondió")):
                raise
            print(f"[guionista] la clave de StickRider no tiene cupo ({str(e)[:120]}): uso la clave de respaldo")
            from common import llm
            os.environ["GEMINI_API_KEY"] = fb
            llm._client, llm._models = None, None
            llm._exhausted.clear()
            notes, sources = writer.research(state, ins)
            script = writer.write(notes, sources, ins)
        with open(os.path.join(wd, "research.txt"), "w") as f:
            f.write(notes + "\n\n" + json.dumps(sources, indent=1))
    with open(sp, "w") as f:
        json.dump(script, f, indent=1, ensure_ascii=False)
    # ---- voz, director, sonido ----
    wav = os.path.join(wd, "voice.wav")
    timings, total_s = voice.speak([l["text"] for l in script["lines"]], wav)
    spec = director.build(script, timings, total_s)
    with open(os.path.join(wd, "spec.json"), "w") as f:
        json.dump(spec, f, indent=1)
    mix = os.path.join(wd, "mix.wav")
    sound.mix(wav, spec, script["mood"], abs(hash(script["story_key"])) % 10_000, mix)
    # ---- render ----
    segs = render.render(spec, os.path.join(wd, "render"), float(os.getenv("SR_SCALE", "1")))
    video = os.path.join(OUT, f"stickrider_{job}.mp4")
    render.assemble(segs, mix, video)
    bad = render.blank_frames(video)
    if bad:
        print(f"[render] ⚠️ {len(bad)} cuadros vacíos: {bad[:20]}")
        if len(bad) > 3:
            raise RuntimeError("el video tiene cuadros vacíos: no se sube")
    print(f"[stickrider] video listo en {(time.time() - t0) / 60:.1f} min")
    # ---- subir ----
    rec = {"date": dt.date.today().isoformat(), "story_key": script["story_key"], "title": script["title"],
           "hook": script["lines"][0]["text"], "mood": script["mood"], "seconds": round(total_s, 1)}
    if dry or not os.getenv("YT_REFRESH_TOKEN"):
        print("[publicador] DRY_RUN o sin credenciales de StickRider: no subo")
        return
    vid, at = publish.upload(video, script, state)
    rec.update(youtube_id=vid, publish_at=at)
    state["videos"].append(rec)
    save_state(state)


if __name__ == "__main__":
    main()

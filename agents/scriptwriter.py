"""Agente 2 — Guionista. Escribe el guion escena por escena."""
import config
from common import llm


class ScriptTooShort(RuntimeError):
    """Un guion de video largo quedó muy por debajo del mínimo aun después de ampliarlo."""


def _ensure_max(scenes):
    """Max es el protagonista: si alguna imagen quedó sin él, se lo agrega reaccionando a la escena."""
    for sc in scenes:
        p = (sc.get("image_prompt") or "").strip()
        if "Max" not in p:
            sc["image_prompt"] = f"Max in the foreground reacting to the scene: {p}" if p else \
                f"Max reacting to: {sc.get('narration', '')[:200]}"
    return scenes


def _as_script(res):
    """El modelo a veces devuelve directamente la lista de escenas en vez de {"scenes": [...]}."""
    if isinstance(res, list):
        return {"scenes": [sc for sc in res if isinstance(sc, dict)]}
    return res if isinstance(res, dict) else {}


def run(topic, fmt, notes, past_feedback):
    spec = config.FORMATS[fmt]
    serie = config.SERIES.get(topic.get("series") or "classic", config.SERIES["classic"])
    wmin, wmax = spec["target_words"]
    smin, smax = spec["scenes"]
    history = [n for fb in past_feedback[-5:] for n in fb.get("notes", [])]

    script = llm.ask_json(
        f"""You are the head scriptwriter of a viral animated YouTube channel.
Niche: {config.NICHE_DESCRIPTION}
Topic: {topic['topic']}
Angle: {topic.get('angle', '')}
Format: {"YouTube Short (vertical, under 58 seconds)" if fmt == "short" else "long-form video, 8-10 minutes"}

Feedback from the analyst (where viewers dropped off and what to do better) — FOLLOW IT:
{notes}
Older lessons: {history[-10:]}

Rules:
- Total narration: {wmin}-{wmax} words, split into {smin}-{smax} scenes
  (about {round((wmin + wmax) / 2 / ((smin + smax) / 2))} words per scene). Length matters: count your words.
- The video answers the question "{topic['topic']}". The first sentence states the premise in a gripping way.
- Scene 1 is the hook: a shocking or curious statement in the first sentence. No "Hey guys", no intro.
- Keep open loops ("but that's not even the worst part..."), escalate stakes, pay off at the end.
- Simple spoken English, short sentences, accurate science/history, light humour.
- {"End with a line that loops back to the start so viewers rewatch." if fmt == "short" else "Every ~60 seconds add a pattern interrupt or new mini-question. End with a teaser for another What If."}
- MAX IS THE PROTAGONIST of the channel and of this video. Tell the story through Max: he lives the
  "what if" scenario, reacts to it, explores it, explains it and tries things out
  (e.g. "Max wakes up and the gravity has doubled..."). The narrator talks about what Max sees, feels
  and does; the science is shown through what happens to him. He is the only recurring person.
- Each scene needs an image prompt describing ONE clear visual (Max, objects, setting) that matches the
  narration. Max appears in EVERY image, doing or reacting to what the narration says. Do not include any
  text in the images. Write him exactly as "Max" (just the name: his look is added automatically,
  so do NOT describe his face, hair or clothes, and never give him a different outfit, hat or helmet).
  Never depict children. Make the first image the most striking and dramatic one (it is the hook).
- SERIES: this is a "{serie['label']}" episode. {serie['script_rules']}

Return JSON:
{{"scenes": [{{"narration": "...", "image_prompt": "..."}}],
  "summary": "one-sentence summary of the video"}}""",
        temperature=0.9,
    )
    script = _as_script(script)
    scenes = [s for s in script.get("scenes", []) if isinstance(s, dict) and s.get("narration")]
    if len(scenes) < 3:
        raise RuntimeError("El guion vino vacío o incompleto")
    script["scenes"] = scenes
    _ensure_max(scenes)

    # Los modelos tienden a quedarse cortos en guiones largos: si falta texto, se lo pide ampliar
    # (hasta 2 veces) y se queda con la mejor versión. Un largo de 4 min no suma horas de visualización.
    for attempt in range(2):
        words = _words(script)
        if words >= wmin * 0.9:
            break
        print(f"[guionista] guion corto ({words} palabras, objetivo {wmin}-{wmax}) — pido ampliarlo")
        try:
            longer = _expand(script, topic, fmt, wmin, wmax, smax)
        except Exception as e:  # noqa: BLE001
            print(f"[guionista] no pude ampliarlo: {e}")
            break
        if _words(longer) > words:
            script = longer
    print(f"[guionista] {len(script['scenes'])} escenas, {_words(script)} palabras")
    if fmt == "long" and _words(script) < wmin * 0.7:
        raise ScriptTooShort(f"guion largo de solo {_words(script)} palabras (mínimo {wmin})")
    return script


def _words(script):
    return sum(len(sc["narration"].split()) for sc in script["scenes"])


def _expand(script, topic, fmt, wmin, wmax, smax):
    """Amplía el guion por partes (de hasta 20 escenas): pedidos más chicos = el modelo respeta mejor el largo."""
    scenes = script["scenes"]
    target = (wmin + wmax) // 2
    serie = config.SERIES.get(topic.get("series") or "classic", config.SERIES["classic"])
    chunk = 20
    parts = [scenes[i:i + chunk] for i in range(0, len(scenes), chunk)]
    out_scenes = []
    for n, part in enumerate(parts):
        share = len(part) / len(scenes)
        part_target = round(target * share)
        part_words = sum(len(sc["narration"].split()) for sc in part)
        per_scene = max(1, round(part_target / len(part)))
        where = ("the BEGINNING" if n == 0 else "the END" if n == len(parts) - 1 else "the MIDDLE") if len(parts) > 1 else "the whole video"
        res = llm.ask_json(
            f"""You are expanding part {n + 1} of {len(parts)} ({where}) of a script for a
{"YouTube Short" if fmt == "short" else "long-form YouTube video"} about "{topic['topic']}".
This part has {part_words} words; it must have about {part_target} words (~{per_scene} words per scene).

Rewrite EACH scene longer, keeping its order, meaning and role in the story (keep the hook if this is
the beginning, keep the ending if this is the end). Go deeper: surprising facts, concrete numbers and
comparisons, step-by-step consequences, mini open loops, light humour. No filler, no repetition,
no greetings, no "in this video". Keep the same number of scenes ({len(part)}).
Each scene keeps its "image_prompt" (ONE clear visual, no text; Max appears in every
image as the protagonist, written just "Max", without describing his looks or clothes; never children).
Keep Max as the protagonist of the narration too: the story is what happens to him.
Series: "{serie['label']}" — {serie['script_rules']}

Full video summary: {script.get('summary', '')}
Scenes to expand:
{part}

Return JSON: {{"scenes": [{{"narration": "...", "image_prompt": "..."}}]}}""",
            temperature=0.7,
        )
        res = _as_script(res)
        new = [sc for sc in res.get("scenes", []) if isinstance(sc, dict) and sc.get("narration")]
        new_words = sum(len(sc["narration"].split()) for sc in new)
        if len(new) >= max(1, len(part) // 2) and new_words > part_words:
            for sc, old in zip(new, part + [{}] * len(new)):
                sc.setdefault("image_prompt", old.get("image_prompt") or sc["narration"])
            out_scenes += new
        else:
            out_scenes += part  # si esta parte salió mal, se queda la original
    return {"scenes": _ensure_max(out_scenes[:smax]), "summary": script.get("summary", "")}

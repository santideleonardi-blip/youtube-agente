"""Agente 2 — Guionista. Escribe el guion escena por escena."""
import config
from common import llm


def run(topic, fmt, notes, past_feedback):
    spec = config.FORMATS[fmt]
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
- Each scene needs an image prompt describing ONE clear visual (characters, objects, setting) that
  matches the narration. Do not include any text in the images. When a person is needed, use the
  channel's recurring character: "Max, an adult explorer with messy brown hair and an orange jumpsuit".
  Never depict children. Make the first image the most striking and dramatic one (it is the hook).

Return JSON:
{{"scenes": [{{"narration": "...", "image_prompt": "..."}}],
  "summary": "one-sentence summary of the video"}}""",
        temperature=0.9,
    )
    scenes = [s for s in script.get("scenes", []) if s.get("narration")]
    if len(scenes) < 3:
        raise RuntimeError("El guion vino vacío o incompleto")
    script["scenes"] = scenes

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
    return script


def _words(script):
    return sum(len(sc["narration"].split()) for sc in script["scenes"])


def _expand(script, topic, fmt, wmin, wmax, smax):
    """Amplía el guion por partes (de hasta 20 escenas): pedidos más chicos = el modelo respeta mejor el largo."""
    scenes = script["scenes"]
    target = (wmin + wmax) // 2
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
Each scene keeps its "image_prompt" (ONE clear visual, no text; people = "Max, an adult explorer with
messy brown hair and an orange jumpsuit"; never children).

Full video summary: {script.get('summary', '')}
Scenes to expand:
{part}

Return JSON: {{"scenes": [{{"narration": "...", "image_prompt": "..."}}]}}""",
            temperature=0.7,
        )
        new = [sc for sc in res.get("scenes", []) if sc.get("narration")]
        new_words = sum(len(sc["narration"].split()) for sc in new)
        if len(new) >= max(1, len(part) // 2) and new_words > part_words:
            for sc, old in zip(new, part + [{}] * len(new)):
                sc.setdefault("image_prompt", old.get("image_prompt") or sc["narration"])
            out_scenes += new
        else:
            out_scenes += part  # si esta parte salió mal, se queda la original
    return {"scenes": out_scenes[:smax], "summary": script.get("summary", "")}

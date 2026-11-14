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
    words = _words(script)
    target = (wmin + wmax) // 2
    out = llm.ask_json(
        f"""This script for a {"YouTube Short" if fmt == "short" else "long-form YouTube video"} about
"{topic['topic']}" is TOO SHORT: it has {words} words and needs {wmin}-{wmax} words (aim for {target}).

Rewrite it at full length. Keep the same hook, story arc, tone and ending, but go deeper: add more
surprising facts, concrete numbers and comparisons, step-by-step consequences, mini open loops and
light humour. Do NOT pad with filler or repeat yourself. Each existing scene should grow to roughly
{max(1, round(target / max(len(script['scenes']), 1)))} words; you may add new scenes (max {smax} in total).
Every scene keeps an "image_prompt" (ONE clear visual, no text; people = "Max, an adult explorer with
messy brown hair and an orange jumpsuit"; never children).

Current script:
{script['scenes']}

Return JSON: {{"scenes": [{{"narration": "...", "image_prompt": "..."}}], "summary": "{script.get('summary', '')}"}}""",
        temperature=0.7,
    )
    scenes = [sc for sc in out.get("scenes", []) if sc.get("narration")][:smax]
    for sc in scenes:
        sc.setdefault("image_prompt", sc["narration"])
    if len(scenes) < 3:
        raise RuntimeError("ampliación vacía")
    return {"scenes": scenes, "summary": out.get("summary") or script.get("summary", "")}

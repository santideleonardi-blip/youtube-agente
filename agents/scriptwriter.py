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
- Total narration: {wmin}-{wmax} words, split into {smin}-{smax} scenes.
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
    print(f"[guionista] {len(scenes)} escenas, {sum(len(s['narration'].split()) for s in scenes)} palabras")
    return script

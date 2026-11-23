"""StickRider — Guionista.

1) Investiga: Gemini con búsqueda de Google elige una historia REAL poco conocida y junta los datos con fuentes.
2) Escribe: guion con la fórmula medida en 20 shorts de referencia + un "beat" visual por línea (set, luz, toma,
   personajes, acciones) usando SOLO el vocabulario que el motor sabe dibujar.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from common import llm  # noqa: E402

SETS = {
    "street": "narrow cobbled old-town lane between gabled houses (Europe, 1400s-1900s)",
    "square": "old-town market square, a town hall at the back (good for crowds, officials, stages, public events)",
    "road": "dirt road through green fields and hills, mountains ahead (journeys, travel, wagons)",
    "shrine": "small stone chapel with a bell tower on a hilltop (church, religion, pilgrims)",
    "field": "open countryside, trees and hills (farms, battles, nature, outdoor experiments)",
    "sea": "wooden ship deck at sea, open water all around (voyages, sailors, pirates, explorers)",
    "desert": "sand dunes with pyramids in the distance (Egypt, deserts, ancient times, expeditions)",
    "snow": "snowy plain with a pine forest and mountains (winter, polar, cold, Russia, expeditions)",
    "room": "interior room with a window and a door (offices, labs, homes, courtrooms, meetings)",
    "city": "modern city street with tall buildings and cars (1900s-today)",
}
LOOKS = ["townsman", "townswoman", "noble", "musician", "priest", "soldier", "kid", "king", "queen", "worker",
         "suit", "woman", "scientist", "doctor", "sailor", "pilot", "farmer"]
ACTS = ["stand", "walk", "dance", "wave", "cheer", "sit", "fall", "play"]
EXPRS = ["neutral", "stern", "grin", "laugh", "whistle", "nervous", "shock", "relief", "relief_open", "dazed", "pained",
         "smile", "smile_closed", "yawn"]
SHOTS = ["wide", "medium", "close", "low", "crowd", "aerial"]
PROPS = ["stage", "wagon", "table", "statue", "barrel", "crate", "chest", "car", "tent", "rock"]
FX = ["none", "burst", "stars", "puff", "splash"]
MOODS = ["jig", "playful", "mystery", "tense", "epic"]

STYLE = """You write 40-55 second YouTube Shorts for the channel StickRider: TRUE stories, told by one fast, steady male
narrator over flat stick-figure cartoons. The formula below was measured on 20 viral shorts of the genre; follow it.

SCRIPT FORMULA
1. HOOK (line 1, 8-16 words): the paradox stated as a fact, no setup, no "did you know", no question.
   e.g. "In 1518, a city tried to cure a dancing epidemic... with more dancing."
2. SETTING (1-2 lines): present tense, concrete: year, place, a named person (or "a man named X"), a number.
3. ESCALATION (3-5 lines): each beat bigger than the last. Include 1-2 SHORT in-character dialogue lines in quotes
   (e.g. 'His boss says: "That's impossible."') and 1 exaggeration joke.
4. MYSTERY BEAT (1 line): a question the viewer is now asking ("So why didn't anyone stop him?").
5. PIVOT: a line that starts with "You see," and gives the real mechanism, with an EVERYDAY analogy
   ("It's like ...", "Think about the last time you ...").
6. IRONIC PAYOFF (last 1-2 lines): short, lands the twist. The video ends on the last word. No call to action, no
   "subscribe", no moral lecture.
- 120-170 words total, 10-15 lines, sentences ~8-16 words, plain spoken English, contractions, no jargon.
- Every line must be something we can SHOW. Facts must be true and match the sources; if historians disagree on a
  number, say "some say" or use the modern estimate. Never invent quotes and present them as real: dialogue lines are
  clearly dramatized and must match what is documented.
- Numbers as words when spoken naturally ("four hundred", "fifteen eighteen" for a year)."""


def _grounded_text(prompt):
    """Una consulta con búsqueda de Google (para datos reales). Devuelve texto."""
    from google.genai import types
    client = llm._get_client()
    last = None
    for model in llm._available_models():
        try:
            cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.7)
            resp = llm._with_timeout(lambda: client.models.generate_content(model=model, contents=prompt, config=cfg), 180)
            txt = resp.text or ""
            urls = []
            try:
                for c in resp.candidates or []:
                    gm = getattr(c, "grounding_metadata", None)
                    for ch in (getattr(gm, "grounding_chunks", None) or []):
                        w = getattr(ch, "web", None)
                        if w and getattr(w, "uri", None):
                            urls.append({"title": getattr(w, "title", ""), "uri": w.uri})
            except Exception:  # noqa: BLE001
                pass
            if txt.strip():
                print(f"[guionista] investigación con {model} ({len(urls)} fuentes)")
                return txt, urls
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[guionista] {model} sin búsqueda: {str(e)[:160]}")
    raise RuntimeError(f"no pude investigar: {last}")


def research(state, insights):
    used = [v.get("story_key", "") for v in state.get("videos", [])][-80:]
    prompt = f"""Find ONE true, little-known, surprising story for a 45-second YouTube Short. "All kinds of real stories":
history, science, crime that's funny not gory, business blunders, weird laws, sports, inventions, animals, disasters
with a twist, kings and fools. It must have a paradox or ironic twist, cause and effect you can SHOW with simple
cartoon characters, and facts verifiable on reputable sites (Britannica, Smithsonian, History.com, BBC, NatGeo,
university or museum pages, major newspapers).
Avoid these stories already used: {json.dumps(used)}
{insights}
Search the web, verify the key facts and numbers, then answer in plain text with:
STORY KEY: a short unique slug
TITLE IDEA:
WHEN / WHERE:
WHAT HAPPENED (8-12 bullet facts with numbers, names, dates):
THE TWIST:
WHY IT HAPPENED (the real mechanism, simply):
DISPUTED POINTS (what historians/sources disagree on):"""
    return _grounded_text(prompt)


def write(notes, sources, insights=""):
    sets = "\n".join(f"- {k}: {v}" for k, v in SETS.items())
    prompt = f"""{STYLE}

RESEARCH NOTES (the only facts you may use):
{notes}

{insights}

Now write the short as JSON. Every line gets a visual "beat" built ONLY from this vocabulary:
SETS:
{sets}
LIGHT: day | golden (sunset, warm) | night (use for the "You see," explanation or dark moments; change light only
  with the story, at most 3 changes)
SHOT: wide (establish, show the place) | medium (one or two characters, waist up) | close (a face, for reactions,
  dialogue and jokes) | low (hero/dramatic, from below) | crowd (many people) | aerial (from above, scale, numbers)
LOOKS (character costumes): {", ".join(LOOKS)}
ACTS: {", ".join(ACTS)}   (play = playing a drum/instrument; fall = lying on the ground)
EXPRESSIONS: {", ".join(EXPRS)}
PROPS (optional, max 2 per line): {", ".join(PROPS)}
FX (optional cartoon effect on the focus character): {", ".join(FX)}
MUSIC MOOD (whole video): {", ".join(MOODS)}

Rules for beats:
- Keep the SAME set for consecutive lines that happen in the same place (the camera then moves continuously
  between lines instead of cutting). Change set only when the story changes place (max 4 sets per video).
- Vary the SHOT from line to line (never the same shot 3 times in a row). Hook: crowd/wide/low with action.
  Dialogue and jokes: close. Numbers: aerial or crowd with a caption.
- "on_screen": the cast members visible in that line (1-4), each with act and expr that ILLUSTRATE the line
  literally (shock when surprised, laugh when mocking, dazed, pained, cheer when celebrating...).
- "crowd": none | few (8) | many (40) | huge (150), with an act, when the story has many people.
- "caption": optional 1-4 characters/words shown big on screen for a key number or year (e.g. "1518", "400",
  "$2M"); at most 3 captions per video.
- Cast: 1-4 recurring characters with ids, a look that fits the era and role, and v (0-9) to vary colours/face.

JSON format:
{{
 "story_key": "slug", "title": "max 70 chars, curiosity-driven, no clickbait lies, no hashtags",
 "description": "2-3 sentences + 'Sources:' with 1-3 URLs from the research",
 "tags": ["8-12 tags"], "mood": "jig",
 "cast": [{{"id": "anna", "look": "townswoman", "v": 1}}],
 "lines": [
  {{"text": "spoken line", "set": "street", "light": "day", "shot": "wide", "focus": "anna or crowd",
    "on_screen": [{{"id": "anna", "act": "dance", "expr": "dazed"}}],
    "crowd": {{"size": "none", "act": "stand", "expr": "neutral"}},
    "props": [], "fx": "none", "caption": ""}}
 ]
}}
Sources you may cite: {json.dumps(sources[:6])}"""
    out = llm.ask_json(prompt, system="You are a top YouTube Shorts writer and storyboard artist. Output only JSON.", temperature=0.85)
    return validate(out)


def _pick(v, allowed, default):
    v = str(v or "").strip().lower()
    return v if v in allowed else default


def validate(s):
    """Limpia el JSON del modelo para que el motor nunca reciba algo que no sabe dibujar."""
    cast = []
    for c in s.get("cast", [])[:5]:
        cid = re.sub(r"[^a-z0-9_]", "", str(c.get("id", "")).lower()) or f"c{len(cast)}"
        cast.append({"id": cid, "look": _pick(c.get("look"), LOOKS, "townsman"), "v": int(c.get("v", len(cast))) % 10})
    ids = {c["id"] for c in cast}
    lines, prev_set = [], None
    for ln in s.get("lines", []):
        text = str(ln.get("text", "")).strip()
        if not text:
            continue
        st = _pick(ln.get("set"), SETS, prev_set or "street")
        prev_set = st
        on = []
        for o in ln.get("on_screen", [])[:4]:
            oid = re.sub(r"[^a-z0-9_]", "", str(o.get("id", "")).lower())
            if oid in ids:
                on.append({"id": oid, "act": _pick(o.get("act"), ACTS, "stand"), "expr": _pick(o.get("expr"), EXPRS, "neutral")})
        cr = ln.get("crowd") or {}
        size = _pick(cr.get("size"), ["none", "few", "many", "huge"], "none")
        props = [p for p in (_pick(x, PROPS, "") for x in ln.get("props", [])[:2]) if p]
        focus = re.sub(r"[^a-z0-9_]", "", str(ln.get("focus", "")).lower())
        lines.append({
            "text": text, "set": st, "light": _pick(ln.get("light"), ["day", "golden", "night"], "day"),
            "shot": _pick(ln.get("shot"), SHOTS, "medium"),
            "focus": focus if focus in ids or focus == "crowd" else (on[0]["id"] if on else "crowd"),
            "on_screen": on, "crowd": {"size": size, "act": _pick(cr.get("act"), ACTS, "stand"), "expr": _pick(cr.get("expr"), EXPRS, "neutral")},
            "props": props, "fx": _pick(ln.get("fx"), FX, "none"), "caption": str(ln.get("caption", "") or "")[:8],
        })
    if len(lines) < 6:
        raise ValueError(f"guion demasiado corto ({len(lines)} líneas)")
    words = sum(len(l["text"].split()) for l in lines)
    print(f"[guionista] {len(lines)} líneas, {words} palabras: {s.get('title')}")
    return {
        "story_key": re.sub(r"[^a-z0-9-]", "", str(s.get("story_key", "")).lower().replace(" ", "-"))[:60] or "story",
        "title": str(s.get("title", "A True Story"))[:90], "description": str(s.get("description", "")),
        "tags": [str(t)[:40] for t in s.get("tags", [])][:12], "mood": _pick(s.get("mood"), MOODS, "playful"),
        "cast": cast, "lines": lines,
    }

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

STYLE = """Escribes Shorts de YouTube de 40-55 segundos para el canal StickRider: HISTORIAS REALES contadas por un
narrador masculino, rápido y parejo, sobre dibujos de personajes de palito. Todo en ESPAÑOL NEUTRO latinoamericano
(tuteo, nada de voseo ni de modismos de un solo país; "ustedes", nunca "vosotros"). La fórmula de abajo se midió en
20 shorts virales del género: síguela.

FÓRMULA DEL GUION
1. GANCHO (línea 1, 8-16 palabras): la paradoja dicha como un hecho, sin introducción, sin "¿sabías que...?",
   sin pregunta. Ej.: "En mil quinientos dieciocho, una ciudad intentó curar una epidemia de baile... con más baile."
2. ESCENA (1-2 líneas): en presente, concreta: año, lugar, una persona con nombre (o "un hombre llamado X"), un número.
3. ESCALADA (3-5 líneas): cada momento más grande que el anterior. Incluye 1-2 diálogos CORTOS entre comillas
   (ej.: 'Su jefe le dice: "Eso es imposible."') y 1 chiste de exageración.
4. MISTERIO (1 línea): la pregunta que el espectador ya se está haciendo ("¿Y por qué nadie lo detuvo?").
5. GIRO: una línea que empieza con "Resulta que" y explica el mecanismo real con una analogía de la vida
   COTIDIANA ("Es como cuando...", "Piensa en la última vez que...").
6. REMATE IRÓNICO (última 1-2 líneas): corto, cierra el giro. El video termina en la última palabra. Nada de
   "suscríbete", nada de moraleja.
- 110-160 palabras en total, 10-15 líneas, oraciones de ~8-16 palabras, español hablado y natural, sin tecnicismos.
- Cada línea tiene que poder MOSTRARSE. Los datos tienen que ser verdaderos y coincidir con las fuentes; si los
  historiadores no se ponen de acuerdo en un número, di "algunos dicen" o usa la estimación moderna. Los diálogos
  son dramatizaciones: no inventes citas presentadas como reales.
- Los números y años van con LETRAS, como se dicen ("cuatrocientos", "mil quinientos dieciocho"), para que la voz
  los lea bien. Los nombres extranjeros, en su forma española si existe."""


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
    raise RuntimeError(f"no pude investigar con búsqueda: {last}")


def _research_offline(prompt):
    """Sin búsqueda web (el plan gratis de Gemini no la incluye): el modelo investiga con lo que sabe y solo elige
    historias muy documentadas. Las fuentes se citan por nombre de obra/artículo, no con links inventados."""
    out = llm.ask_json(prompt + """

You have NO web access for this answer: choose only a story that is very well documented (it has its own
Wikipedia/Britannica article and appears in museums, encyclopedias or major newspapers), use only facts you are
sure of, and mark anything uncertain as disputed. Answer as JSON:
{"notes": "the full plain-text answer with the sections above",
 "sources": [{"title": "Wikipedia (English or Spanish) / Britannica article title or book", "uri": ""}]}""",
                       system="You are a careful history researcher. Output only JSON.", temperature=0.7)
    notes = str(out.get("notes", "")).strip()
    if len(notes) < 200:
        raise RuntimeError("investigación sin búsqueda demasiado corta")
    srcs = [s for s in out.get("sources", []) if isinstance(s, dict) and s.get("title")][:4]
    print(f"[guionista] investigación SIN búsqueda web ({len(srcs)} fuentes por nombre)")
    return notes, srcs


def research(state, insights):
    used = [v.get("story_key", "") for v in state.get("videos", [])][-80:]
    prompt = f"""Find ONE true, little-known, surprising story for a 45-second YouTube Short IN SPANISH for a Spanish-speaking
audience (Latin America and Spain). "All kinds of real stories": history, science, crime that's funny not gory, business
blunders, weird laws, sports, inventions, disasters with a twist, kings and fools. Mix world stories with stories from
Latin America and Spain. It must have a paradox or ironic twist, cause and effect you can SHOW with simple
cartoon characters, and facts verifiable on reputable sites (Britannica, Smithsonian, History.com, BBC, NatGeo,
university or museum pages, major newspapers, also reputable Spanish-language sources).
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
    if os.getenv("SR_NO_SEARCH") != "1":
        try:
            return _grounded_text(prompt)
        except Exception as e:  # noqa: BLE001
            print(f"[guionista] la búsqueda web no está disponible ({str(e)[:120]}): sigo sin búsqueda")
    return _research_offline(prompt)


def write(notes, sources, insights=""):
    sets = "\n".join(f"- {k}: {v}" for k, v in SETS.items())
    prompt = f"""{STYLE}

RESEARCH NOTES (the only facts you may use):
{notes}

{insights}

Now write the short as JSON. The spoken "text", the "title", the "description" and the "tags" are in SPANISH (neutral
Latin American). The vocabulary values below stay exactly as written (they are codes for the animation engine).
Every line gets a visual "beat" built ONLY from this vocabulary:
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
- The MYSTERY line and the "Resulta que" line usually switch to night light (explanation mood).
  Dialogue and jokes: close. Numbers: aerial or crowd with a caption.
- "on_screen": the cast members visible in that line (1-4), each with act and expr that ILLUSTRATE the line
  literally (shock when surprised, laugh when mocking, dazed, pained, cheer when celebrating...).
- "crowd": none | few (8) | many (40) | huge (150), with an act, when the story has many people.
- "caption": optional 1-4 characters/words shown big on screen for a key number or year, written with digits
  (e.g. "1518", "400", "$2M"); at most 3 captions per video.
- Cast: 1-4 recurring characters with ids, a look that fits the era and role, and v (0-9) to vary colours/face.

JSON format:
{{
 "story_key": "slug-en-ingles", "title": "en español, máx. 70 caracteres, genera curiosidad, sin mentir, sin hashtags",
 "description": "2-3 oraciones en español + 'Fuentes:' con 1-3 fuentes de la investigación (la URL si la hay; si no, el nombre del artículo, p. ej. 'Wikipedia: Tulipomanía'). Nunca inventes URLs.",
 "tags": ["8-12 tags en español"], "mood": "jig",
 "cast": [{{"id": "anna", "look": "townswoman", "v": 1}}],
 "lines": [
  {{"text": "línea hablada en español", "set": "street", "light": "day", "shot": "wide", "focus": "anna or crowd",
    "on_screen": [{{"id": "anna", "act": "dance", "expr": "dazed"}}],
    "crowd": {{"size": "none", "act": "stand", "expr": "neutral"}},
    "props": [], "fx": "none", "caption": ""}}
 ]
}}
Sources you may cite: {json.dumps(sources[:6])}"""
    out = llm.ask_json(prompt, system="You are a top Spanish-language YouTube Shorts writer and storyboard artist. Output only JSON.", temperature=0.85)
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
        "title": str(s.get("title", "Una historia real"))[:90], "description": str(s.get("description", "")),
        "tags": [str(t)[:40] for t in s.get("tags", [])][:12], "mood": _pick(s.get("mood"), MOODS, "playful"),
        "cast": cast, "lines": lines,
    }

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
narrador masculino sobre dibujos de personajes de palito. Todo en ESPAÑOL NEUTRO latinoamericano (tuteo, nada de
voseo ni de modismos de un solo país; "ustedes", nunca "vosotros").

LO MÁS IMPORTANTE: QUE SE ENTIENDA A LA PRIMERA Y QUE FLUYA.
El espectador escucha una sola vez, sin poder volver atrás, y no sabe NADA del tema. Cuéntalo como se lo contarías
a un amigo en voz alta: una historia con principio, medio y final, no una lista de datos.
- ORDEN: de principio a fin, en orden cronológico, causa → consecuencia. Nunca saltes adelante y atrás.
- HILO: cada línea sigue a la anterior. Usa conectores naturales al comienzo de muchas líneas: "Entonces", "Pero",
  "Así que", "El problema es que", "Para colmo", "Al final". Nada de frases sueltas o telegráficas
  ("Julio. París. Un hombre." está PROHIBIDO): siempre oraciones completas, con sujeto y verbo.
- UN PROTAGONISTA: presenta claro quién es (un cocinero francés, un soldado, un rey...) y síguelo. Máximo 2 nombres
  propios en todo el video; a los demás llámalos por su rol ("el rey", "su esposa", "los soldados").
- PALABRAS SIMPLES: las que entiende un chico de 12 años. Si aparece algo raro (un cargo, una moneda, un lugar),
  explícalo en 3-5 palabras ("florines, la moneda holandesa"). Nada de tecnicismos ni de palabras rebuscadas.
- POCOS NÚMEROS: máximo 3 números en todo el guion, y solo los que asombran. Redondea ("casi mil", "unos cuatrocientos").
- SIN AMBIGÜEDADES: que nunca haya dudas de quién hace qué. Evita "él/ella/esto" si puede confundir: repite el rol.
- DIÁLOGOS: di siempre quién habla antes de la frase: 'El general le grita al cocinero: "¡Esto es imposible!"'.
- Oraciones de 6-15 palabras. Una idea por oración.

FÓRMULA DEL GUION (medida en 20 shorts virales del género)
1. GANCHO (línea 1, 8-15 palabras): la paradoja dicha como un hecho, que se entienda sola, sin introducción, sin
   "¿sabías que...?", sin pregunta. Ej.: "En mil quinientos dieciocho, una ciudad intentó curar una epidemia de
   baile... con más baile."
2. ESCENA (1-2 líneas): cuándo, dónde y quién, en presente, con algo concreto que se pueda ver.
3. ESCALADA (3-5 líneas): cada momento más grande que el anterior, conectados con "Pero", "Entonces", "Para colmo".
   Incluye 1 diálogo corto y 1 chiste de exageración.
4. MISTERIO (1 línea): la pregunta que el espectador ya se está haciendo ("¿Y por qué nadie lo detuvo?").
5. GIRO: una línea que empieza con "Resulta que" y explica el porqué real, simple, con una comparación de la vida
   cotidiana ("Es como cuando...").
6. REMATE (última línea): corto, cierra la historia con ironía y deja claro cómo terminó todo. Nada de moraleja ni
   de pedir likes: el pedido de like y seguir al canal lo agrega el sistema solo, como línea final.
- 105-145 palabras en total, 10-14 líneas.
- Cada línea tiene que poder MOSTRARSE. Los datos tienen que ser verdaderos y coincidir con las fuentes; si los
  historiadores no se ponen de acuerdo en un número, di "algunos dicen" o usa la estimación moderna. Los diálogos
  son dramatizaciones: no inventes citas presentadas como reales.
- Los números y años van con LETRAS, como se dicen ("cuatrocientos", "mil quinientos dieciocho"), para que la voz
  los lea bien. Los nombres extranjeros, en su forma española si existe; si no, que sean fáciles de pronunciar."""


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
First brainstorm 5 candidate stories and score each 1-10 on: (a) how jaw-dropping the paradox is in ONE sentence,
(b) how visual and funny it is with simple cartoon characters, (c) how solid the facts are. Pick the best total
(never a story whose facts are shaky). Then research ONLY that one.
Search the web, verify the key facts and numbers, then answer in plain text with:
CANDIDATES (the 5, with scores, one line each):
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
- MAKE IT ALIVE: every line has at least one character with a NON-neutral expression that matches the words, and
  the acts change during the video (walk, wave, cheer, fall, sit, dance), never a whole video of people standing.
  Use "fx" on the 2-4 funniest or most surprising moments (burst = shock/impact, stars = dizzy/defeat,
  puff = disappearing/failure, splash = water). Use era-fitting props to dress the place (1-2 per scene).
- "enter": true on an on_screen member makes that character WALK INTO the frame on that line (use it when a new
  person arrives in the story: 1-3 times per video).
- "crowd.looks": 1-3 LOOKS for the crowd that fit the era and place (e.g. modern city: suit, woman, worker; ancient
  or medieval: townsman, townswoman, farmer; ship: sailor; army: soldier). Never a medieval crowd in a modern story.

JSON format:
{{
 "story_key": "slug-en-ingles",
 "cover": "TEXTO DE PORTADA en español: 2-5 palabras que den ganas de tocar el video (la paradoja, no el título repetido; ej.: 'CURARON EL BAILE... BAILANDO')",
 "title": "en español, máx. 70 caracteres, genera curiosidad, sin mentir, sin hashtags",
 "description": "2-3 oraciones en español + 'Fuentes:' con 1-3 fuentes de la investigación (la URL si la hay; si no, el nombre del artículo, p. ej. 'Wikipedia: Tulipomanía'). Nunca inventes URLs.",
 "tags": ["8-12 tags en español"], "mood": "jig",
 "cast": [{{"id": "anna", "look": "townswoman", "v": 1}}],
 "lines": [
  {{"text": "línea hablada en español", "set": "street", "light": "day", "shot": "wide", "focus": "anna or crowd",
    "on_screen": [{{"id": "anna", "act": "dance", "expr": "dazed", "enter": false}}],
    "crowd": {{"size": "none", "act": "stand", "expr": "neutral", "looks": ["townsman", "townswoman"]}},
    "props": [], "fx": "none", "caption": ""}}
 ]
}}
Sources you may cite: {json.dumps(sources[:6])}"""
    sysmsg = "You are a top Spanish-language YouTube Shorts writer and storyboard artist. Output only JSON."
    out = llm.ask_json(prompt, system=sysmsg, temperature=0.85)
    draft = validate(out)
    try:
        rev = llm.ask_json(REVIEW.format(style=STYLE, notes=notes, draft=json.dumps(out, ensure_ascii=False),
                                         sets="|".join(SETS), shots="|".join(SHOTS), looks="|".join(LOOKS), acts="|".join(ACTS),
                                         exprs="|".join(EXPRS), props="|".join(PROPS), fx="|".join(FX), moods="|".join(MOODS)),
                           system=sysmsg, temperature=0.6)
        if isinstance(rev, dict) and "lines" not in rev:  # a veces lo devuelve envuelto: {"short": {...}}
            rev = next((v for v in rev.values() if isinstance(v, dict) and "lines" in v), rev)
        better = validate(rev)
        print("[guionista] guion revisado y mejorado")
        return better
    except Exception as e:  # noqa: BLE001
        print(f"[guionista] la revisión falló ({str(e)[:120]}): uso el primer borrador")
        return draft


REVIEW = """{style}

RESEARCH NOTES (the only facts you may use):
{notes}

Here is a DRAFT short (JSON). You are now the strict editor. Two goals, in this order:
(A) a viewer who knows NOTHING about the topic understands the whole story on ONE listen and could retell it;
(B) they watch to the last second.
Read the draft OUT LOUD in your head, line by line, as that viewer, and fix everything that fails:
1. CLARITY: is it obvious who the protagonist is, where and when we are, and what happens? Any line that needs
   context the viewer doesn't have, any weird word, any confusing "él/ella/esto", any unexplained place, title or
   currency → rewrite it simply. Max 2 proper names, max 3 numbers in the whole script.
2. FLOW: the story goes in chronological order, cause → consequence, and every line connects to the previous one
   (use "Entonces", "Pero", "Así que", "Para colmo", "Al final"...). Rewrite telegraphic or choppy lines as full,
   natural spoken sentences. Two lines in a row must never sound like separate facts from a list.
3. HOOK: would a stranger scrolling stop on line 1, and understand it without context? Keep the strongest,
   simplest paradox (no question, no "sabías que").
4. Every line adds something new or bigger; cut filler and repetitions; 6-15 words per sentence.
5. One short dialogue (saying who speaks) and one exaggeration joke in the escalation; the "Resulta que" line
   explains the real reason simply with an everyday comparison; the last line is a short ironic ending that makes
   clear how it all ended.
6. Facts match the notes exactly; numbers and years written in letters; neutral Latin American Spanish.
7. Visual beats: every line can be SHOWN with the vocabulary; expressions and acts illustrate the words literally;
   shot variety (never the same shot 3 times in a row); fx on the 2-4 strongest moments; era-fitting crowd looks;
   new characters "enter"; at most 4 sets and 3 light changes; 1-3 captions on key numbers.
8. Title: makes people curious without lying, max 70 characters.
Allowed values for the beats (keep using ONLY these codes): sets {sets}; light day|golden|night;
shot {shots}; looks {looks}; acts {acts}; expressions {exprs}; props {props}; fx {fx}; mood {moods}.

DRAFT:
{draft}

Return the FULL improved short as JSON in exactly the same format as the draft: the SAME top-level keys
(story_key, cover, title, description, tags, mood, cast, lines), not wrapped inside another object."""


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
                on.append({"id": oid, "act": _pick(o.get("act"), ACTS, "stand"), "expr": _pick(o.get("expr"), EXPRS, "neutral"),
                           "enter": bool(o.get("enter"))})
        cr = ln.get("crowd") or {}
        size = _pick(cr.get("size"), ["none", "few", "many", "huge"], "none")
        props = [p for p in (_pick(x, PROPS, "") for x in ln.get("props", [])[:2]) if p]
        focus = re.sub(r"[^a-z0-9_]", "", str(ln.get("focus", "")).lower())
        lines.append({
            "text": text, "set": st, "light": _pick(ln.get("light"), ["day", "golden", "night"], "day"),
            "shot": _pick(ln.get("shot"), SHOTS, "medium"),
            "focus": focus if focus in ids or focus == "crowd" else (on[0]["id"] if on else "crowd"),
            "on_screen": on, "crowd": {"size": size, "act": _pick(cr.get("act"), ACTS, "stand"), "expr": _pick(cr.get("expr"), EXPRS, "neutral"),
                      "looks": [x for x in (_pick(v, LOOKS, "") for v in (cr.get("looks") or [])[:3]) if x]},
            "props": props, "fx": _pick(ln.get("fx"), FX, "none"), "caption": str(ln.get("caption", "") or "")[:8],
        })
    if len(lines) < 6:
        raise ValueError(f"guion demasiado corto ({len(lines)} líneas)")
    words = sum(len(l["text"].split()) for l in lines)
    print(f"[guionista] {len(lines)} líneas, {words} palabras: {s.get('title')}")
    return {
        "story_key": re.sub(r"[^a-z0-9-]", "", str(s.get("story_key", "")).lower().replace(" ", "-"))[:60] or "story",
        "title": str(s.get("title", "Una historia real"))[:90], "description": str(s.get("description", "")),
        "cover": " ".join(str(s.get("cover") or s.get("title") or "").split())[:48],
        "tags": [str(t)[:40] for t in s.get("tags", [])][:12], "mood": _pick(s.get("mood"), MOODS, "playful"),
        "cast": cast, "lines": lines,
    }

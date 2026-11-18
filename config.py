"""Configuración central del sistema. Todo lo que quieras ajustar está acá."""
import os

# ---------- Canal ----------
CHANNEL_NAME = "WhatWouldHappenIf?"
NICHE = "WhatWouldHappenIf? — every video answers one 'What would happen if...?' question"
NICHE_DESCRIPTION = (
    "The channel is called WhatWouldHappenIf?. EVERY video answers exactly one hypothetical question "
    "that starts with 'What would happen if...?'. The subject is free and chosen by data: the human "
    "body, animals, space, Earth, physics, history, everyday life, technology, etc. "
    "(e.g. 'What would happen if the Moon disappeared?', 'What would happen if you never slept?'). "
    "Tone: curious, fast-paced, slightly humorous, scientifically grounded. Language: English."
)
# Búsquedas que usa el agente investigador para ver qué funciona en el nicho
TREND_QUERIES = [
    "what if",
    "what would happen if",
    "what if earth",
    "what if history",
]

# ---------- Modelos / herramientas gratuitas ----------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
# Se detectan solos los modelos disponibles; estos son solo respaldo si falla la detección.
GEMINI_FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
# Motor de voz: "kokoro" (local, gratis, confiable) o "edge" (Microsoft, a veces bloquea servidores)
TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro")
MODELS_DIR = os.getenv("MODELS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
KOKORO_DIR = os.getenv("KOKORO_DIR", MODELS_DIR)
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "am_michael")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.08"))
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AndrewNeural")
TTS_RATE = os.getenv("TTS_RATE", "+8%")

# Estilo visual fijo del canal (coherencia = marca reconocible)
# Aspecto fijo de Max, el personaje del canal: se agrega igual a cada imagen donde aparece
# para que se vea siempre igual (mismo pelo, ropa y accesorios).
MAX_NAME = "Max, an adult explorer"
MAX_LOOK = (
    "Max: the same cartoon man in every image, drawn in a hand-drawn adult-cartoon style with thick black "
    "outlines and simple cel shading; adult man around 30, fair skin with slightly rosy cheeks, very messy "
    "spiky dark brown hair sticking out in all directions with a fringe over his forehead, thick brown "
    "eyebrows, light brown stubble on chin and jaw, big round white eyes with small dark pupils, slightly "
    "rounded nose; loose bright orange zip-up jumpsuit with a hood collar and a front zipper, dark gray "
    "t-shirt visible at the neck, dark brown boots; no hat, no helmet, no glasses, no accessories. "
    "His default expression is calm, curious and friendly (relaxed smile); he only looks scared or shocked "
    "when the scene says so"
)

# Max narrador: Max aparece en una esquina hablando (boca sincronizada con la voz) y el guion se
# cuenta en primera persona ("I wake up and..."). Con MAX_NARRATOR=0 se vuelve a solo imágenes
# y narrador en tercera persona, como antes del 17/11.
MAX_NARRATOR = os.getenv("MAX_NARRATOR", "1") == "1"

IMAGE_STYLE = (
    "flat 2D vector cartoon illustration, simple geometric shapes, bold clean outlines, "
    "vibrant saturated colors, soft gradients, minimal background, expressive adult characters, "
    "fully clothed, educational explainer animation style, centered subject, "
    "no children, no text, no letters, no watermark"
)

# ---------- Series ----------
# Todos los videos siguen siendo "What would happen if...?"; la serie define CÓMO lo vive Max.
# El título queda genérico (lo que la gente busca); la serie cambia el tratamiento del guion.
SERIES = {
    "adventure": {
        "label": "Max's Adventures",
        "playlist": "Max's Adventures — What Would Happen If?",
        "hashtag": "#MaxAdventures",
        "topic_hint": "a place or extreme situation Max can physically go into and explore "
                      "(e.g. falling into a black hole, living on the bottom of the ocean, being stuck on Venus).",
        "script_rules": "ADVENTURE episode: Max is IN the scenario from the first second. Tell it as a journey with "
                        "a clear goal, obstacles and rising danger, moving from place to place; each new location "
                        "reveals a new piece of science. Tension, close calls and a satisfying ending (he makes it "
                        "out, or a twist).",
    },
    "challenge": {
        "label": "Max's Challenges",
        "playlist": "Max's Challenges — What Would Happen If?",
        "hashtag": "#MaxChallenge",
        "topic_hint": "something Max tries to endure or do for a set time "
                      "(e.g. not sleeping for 30 days, eating only potatoes for a year, staying awake on the Moon for a week).",
        "script_rules": "CHALLENGE episode: Max takes on the challenge and the story moves forward with a clear "
                        "time counter (\"Day 1...\", \"Hour 12...\", \"By day thirty...\"). Each step shows what "
                        "changes in his body or world and why (real science). Stakes rise; keep viewers asking "
                        "'will he make it?'. End with the final result and what it teaches.",
    },
    "curiosity": {
        "label": "Max's Curiosities",
        "playlist": "Max's Curiosities — What Would Happen If?",
        "hashtag": "#MaxCuriosities",
        "topic_hint": "a strange, funny or mind-bending tweak to everyday life, the body or physics that Max "
                      "can try out (e.g. shrinking to the size of an ant, having no friction, swapping senses with a bat).",
        "script_rules": "CURIOSITY episode: Max experiments with the strange idea in everyday situations, almost "
                        "like a playful science experiment. Lots of surprising facts, comparisons and 'wait, what?' "
                        "moments, light humour, Max discovering things step by step. End with the most surprising "
                        "consequence.",
    },
    "classic": {
        "label": "What Would Happen If?",
        "playlist": "What Would Happen If? — The Big Questions",
        "hashtag": "#WhatWouldHappenIf",
        "topic_hint": "a big 'what if' about the planet, space, history or humanity as a whole "
                      "(e.g. the Moon disappearing, all plastic vanishing, Earth spinning twice as fast).",
        "script_rules": "CLASSIC episode: the big-picture consequences of the scenario, minute by minute or "
                        "stage by stage, seen through Max's eyes as he lives through it.",
    },
}

# ---------- Formatos ----------
FORMATS = {
    "short": {"width": 1080, "height": 1920, "target_words": (110, 150), "scenes": (6, 9)},
    "long": {"width": 1920, "height": 1080, "target_words": (1100, 1400), "scenes": (28, 40)},
}
FPS = 30

# ---------- Publicación ----------
# "private"   -> sube en privado, vos lo publicás a mano (modo revisión, recomendado al inicio)
# "scheduled" -> sube en privado y se publica solo SCHEDULE_DELAY_HOURS después (tiempo para revisar)
# "public"    -> publica directo
PUBLISH_MODE = os.getenv("PUBLISH_MODE") or "scheduled"
SCHEDULE_DELAY_HOURS = int(os.getenv("SCHEDULE_DELAY_HOURS", "6"))
CATEGORY_ID = "27"  # Education

# ---------- Rutas ----------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
WORK_DIR = os.path.join(ROOT, "work")
OUTPUT_DIR = os.path.join(ROOT, "output")
FONT_BOLD = os.getenv("FONT_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

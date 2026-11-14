"""Configuración central del sistema. Todo lo que quieras ajustar está acá."""
import os

# ---------- Canal ----------
NICHE = "What If...? — mind-blowing science & history hypotheticals"
NICHE_DESCRIPTION = (
    "Animated explainers that answer fascinating hypothetical questions about science, "
    "space, nature, the human body and history (e.g. 'What if the Moon disappeared?', "
    "'What if you fell into a black hole?', 'What if Rome never fell?'). "
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
KOKORO_DIR = os.getenv("KOKORO_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "am_michael")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.08"))
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AndrewNeural")
TTS_RATE = os.getenv("TTS_RATE", "+8%")

# Estilo visual fijo del canal (coherencia = marca reconocible)
IMAGE_STYLE = (
    "flat 2D vector cartoon illustration, simple geometric shapes, bold clean outlines, "
    "vibrant saturated colors, soft gradients, minimal background, cute expressive characters, "
    "educational animation style, no text, no letters, no watermark"
)

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
PUBLISH_MODE = os.getenv("PUBLISH_MODE", "private")
SCHEDULE_DELAY_HOURS = int(os.getenv("SCHEDULE_DELAY_HOURS", "6"))
CATEGORY_ID = "27"  # Education

# ---------- Rutas ----------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
WORK_DIR = os.path.join(ROOT, "work")
OUTPUT_DIR = os.path.join(ROOT, "output")
FONT_BOLD = os.getenv("FONT_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

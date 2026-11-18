"""Max narrador: un muñeco de Max en una esquina que mueve la boca al ritmo de la voz, parpadea y
mueve la cabeza. La boca la sincroniza Rhubarb Lip Sync (gratis); si no está, se usa el volumen del audio.

Se apaga con MAX_NARRATOR=0 (config.MAX_NARRATOR) y el video vuelve a ser solo imágenes.
"""
import json
import math
import os
import random
import shutil
import subprocess
import wave

import numpy as np
from PIL import Image

import config

ASSETS = os.path.join(config.ROOT, "assets", "max_puppet")
LOGO_ASSETS = os.path.join(config.ROOT, "assets", "max_logo")
SHAPES = "ABCDEFGHX"


# ---------------- Sincronización de labios ----------------
def _rhubarb_bin():
    return os.getenv("RHUBARB_BIN") or shutil.which("rhubarb")


def _rhubarb(wav, text):
    exe = _rhubarb_bin()
    if not exe or not os.path.exists(exe):
        return None
    dialog = wav[:-4] + "_dialog.txt"
    with open(dialog, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        r = subprocess.run([exe, "-f", "json", "--extendedShapes", "GHX", "--dialogFile", dialog,
                            "--threads", str(os.cpu_count() or 2), "-q", wav],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            print(f"[max] Rhubarb falló: {r.stderr[-300:]}")
            return None
        cues = json.loads(r.stdout)["mouthCues"]
        return [(c["start"], c["end"], c["value"]) for c in cues]
    except Exception as e:  # noqa: BLE001
        print(f"[max] Rhubarb falló: {e}")
        return None


def _amplitude_cues(wav, fps):
    """Respaldo sin Rhubarb: abre más o menos la boca según el volumen de la voz."""
    with wave.open(wav) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    step = int(sr / fps)
    n = max(1, len(data) // step)
    rms = np.sqrt(np.mean(data[:n * step].reshape(n, step) ** 2, axis=1)) if n * step else np.zeros(1)
    ref = np.percentile(rms[rms > 0], 90) if np.any(rms > 0) else 1.0
    rnd = random.Random(7)
    cues = []
    for i, v in enumerate(rms / max(ref, 1e-6)):
        if v < 0.08:
            s = "X"
        elif v < 0.3:
            s = rnd.choice("BBAF")
        elif v < 0.65:
            s = rnd.choice("CCEG")
        else:
            s = rnd.choice("DDCH")
        cues.append((i / fps, (i + 1) / fps, s))
    # sin parpadeos de boca de un solo cuadro: cada forma dura al menos 2 cuadros
    for i in range(1, len(cues) - 1):
        if cues[i][2] != cues[i - 1][2] and cues[i][2] != cues[i + 1][2]:
            cues[i] = (cues[i][0], cues[i][1], cues[i - 1][2])
    return cues


def mouth_cues(video, text, wd, fps):
    wav = os.path.join(wd, "voice16k.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", wav], check=True)
    cues = _rhubarb(wav, text)
    if cues:
        print(f"[max] boca sincronizada con Rhubarb ({len(cues)} cambios)")
        return cues
    print("[max] sin Rhubarb: sincronizo la boca con el volumen")
    return _amplitude_cues(wav, fps)


def _shape_at(cues, t, idx):
    """Forma de boca en el tiempo t (idx = cursor que avanza, para no buscar desde cero)."""
    while idx < len(cues) - 1 and cues[idx][1] <= t:
        idx += 1
    s = cues[idx][2] if cues and cues[idx][0] <= t < cues[idx][1] else "X"
    return (s if s in SHAPES else "X"), idx


# ---------------- Dibujo ----------------
EMOTIONS = ("neutral", "happy", "excited", "surprised", "worried", "scared", "thinking")
GESTURES = ("none", "point", "explain", "shrug", "crossed")
HOP_EMOTIONS = ("surprised", "excited", "scared")
GESTURE_SECS = 3.5        # cuánto dura el gesto al empezar cada escena
ENTRANCE_SECS = 0.6       # Max entra desde abajo con un rebote al principio del video
HOP_SECS = 0.35           # saltito al empezar una escena sorprendente
# lienzo de los PNG: x 90..710, y 120..860 en las coordenadas del dibujo (cuello en x=400, y=585)
_CANVAS = (90, 120, 620, 740)


def _aspect():
    if config.MAX_PUPPET_STYLE == "logo":
        w, h = Image.open(os.path.join(LOGO_ASSETS, "base.png")).size
        return w / h
    return _CANVAS[2] / _CANVAS[3]


def layout(w, h):
    """Tamaño y posición del muñeco: abajo a la izquierda en Shorts (debajo de los subtítulos),
    abajo a la derecha en videos largos (los subtítulos van al centro). Devuelve (ancho, alto, x, y, a_la_derecha)."""
    if h > w:
        # en Shorts la parte de abajo la tapan el título y el nombre del canal: Max va un poco más
        # arriba y el cuerpo se desvanece hacia abajo
        ph = int(h * 0.27)                  # ~520 px en 1920
        pw = int(ph * _aspect())
        return pw, ph, 0, h - ph - int(h * 0.08), False
    ph = int(h * 0.42)                      # ~450 px en 1080
    pw = int(ph * _aspect())
    return pw, ph, w - pw, h - ph, True


def norm_emotion(e):
    e = (e or "").strip().lower()
    return e if e in EMOTIONS else "neutral"


def norm_gesture(g):
    g = (g or "").strip().lower()
    return g if g in GESTURES else "none"


def _ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


class Puppet:
    def __init__(self, pw, ph, fade=False, mirror=False):
        self.size = (pw, ph)
        self.mirror = mirror   # a la derecha de la pantalla: los gestos apuntan hacia el centro
        self._img = {}
        cx, cy, cw, ch = _CANVAS
        self.pivot = ((400 - cx) / cw * pw, (585 - cy) / ch * ph)
        self._torso, self._head, self._cache = {}, {}, {}
        self.fade = None
        if fade:  # el último 30% del cuerpo se desvanece (no queda "cortado" en el medio de la pantalla)
            g = np.ones(ph, dtype=np.float32)
            start = int(ph * 0.70)
            g[start:] = np.linspace(1, 0, ph - start)
            self.fade = Image.fromarray((np.repeat(g[:, None], pw, axis=1) * 255).astype(np.uint8), "L")

    def _layer(self, name):
        if name not in self._img:
            path = os.path.join(ASSETS, name + ".png")
            self._img[name] = Image.open(path).convert("RGBA").resize(self.size, Image.LANCZOS)
        return self._img[name]

    def torso(self, gesture):
        if gesture not in self._torso:
            img = self._layer("body").copy()
            if gesture != "none":
                arms = self._layer(f"arms_{gesture}")
                img.alpha_composite(arms.transpose(Image.FLIP_LEFT_RIGHT) if self.mirror else arms)
            self._torso[gesture] = img
        return self._torso[gesture]

    def head(self, emotion, shape, blink):
        mouth = f"mouth_idle_{emotion}" if shape == "X" else f"mouth_{shape}"
        key = (emotion, mouth, blink)
        if key not in self._head:
            img = self._layer("face").copy()
            for n in (f"eyes_{emotion}{'_blink' if blink else ''}", mouth, "hair", f"brows_{emotion}"):
                img.alpha_composite(self._layer(n))
            self._head[key] = img
        return self._head[key]

    def frame(self, emotion, gesture, shape, blink, angle, dy, lift):
        key = (emotion, gesture, shape, blink, angle, dy, lift)
        if key not in self._cache:
            head = self.head(emotion, shape, blink)
            if angle:
                head = head.rotate(angle, resample=Image.BICUBIC, center=self.pivot)
            img = self.torso(gesture).copy()
            img.alpha_composite(head, (0, dy))
            if lift:  # todo el muñeco desplazado (entrada / saltito): lo de abajo queda fuera del cuadro
                moved = Image.new("RGBA", self.size, (0, 0, 0, 0))
                moved.alpha_composite(img, (0, lift)) if lift > 0 else moved.alpha_composite(img.crop((0, -lift, *self.size)))
                img = moved
            if self.fade is not None:
                a = np.asarray(img.getchannel("A"), dtype=np.uint16) * np.asarray(self.fade, dtype=np.uint16) // 255
                img.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[key] = img.tobytes()
        return self._cache[key]


class LogoPuppet:
    """Max tal cual el dibujo del logo (assets/max_logo, sacado de la imagen del logo y ampliado):
    se le mueve la boca, parpadea, se balancea y salta. No tiene brazos ni cejas separados."""

    MARGIN = 0.04   # el dibujo es un poco más alto que el cuadro: al moverse nunca se ve el corte de abajo

    def __init__(self, pw, ph, fade=False, mirror=False):
        self.size = (pw, ph)
        self.mirror = mirror   # a la derecha de la pantalla: espejado para que mire hacia el centro
        self.dh = int(ph * (1 + self.MARGIN))
        self.dw = int(self.dh * pw / ph)
        self._img, self._cache = {}, {}
        self.fade = None
        if fade:
            g = np.ones(ph, dtype=np.float32)
            start = int(ph * 0.70)
            g[start:] = np.linspace(1, 0, ph - start)
            self.fade = Image.fromarray((np.repeat(g[:, None], pw, axis=1) * 255).astype(np.uint8), "L")

    def _layer(self, name):
        if name not in self._img:
            im = Image.open(os.path.join(LOGO_ASSETS, name + ".png")).convert("RGBA").resize((self.dw, self.dh), Image.LANCZOS)
            self._img[name] = im.transpose(Image.FLIP_LEFT_RIGHT) if self.mirror else im
        return self._img[name]

    def frame(self, emotion, gesture, shape, blink, angle, dy, lift):
        key = (shape, blink, angle, dy, lift)
        if key not in self._cache:
            img = self._layer("base").copy()
            if shape not in "XA":
                img.alpha_composite(self._layer(f"mouth_{shape}"))
            if blink:
                img.alpha_composite(self._layer("blink"))
            if angle:
                img = img.rotate(angle * 0.6, resample=Image.BICUBIC, center=(self.dw / 2, self.dh))
            pw, ph = self.size
            out = Image.new("RGBA", self.size, (0, 0, 0, 0))
            x0 = (self.dw - pw) // 2   # el dibujo es apenas más ancho: se recorta el centro
            out.alpha_composite(img.crop((x0, 0, x0 + pw, self.dh)), (0, int(ph * self.MARGIN / 2) + abs(dy) + lift))
            if self.fade is not None:
                a = np.asarray(out.getchannel("A"), dtype=np.uint16) * np.asarray(self.fade, dtype=np.uint16) // 255
                out.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[key] = out.tobytes()
        return self._cache[key]


def _scene_at(timeline, t, idx):
    while idx < len(timeline) - 1 and timeline[idx + 1]["start"] <= t:
        idx += 1
    return idx


def overlay_frames(video, text, wd, w, h, fps, duration, timeline=None):
    """Prepara el muñeco. timeline = [{"start": s, "emotion": ..., "gesture": ...}] por escena.
    Devuelve ((ancho, alto, x, y), generador de cuadros RGBA crudos) para pasarle a FFmpeg por stdin
    (un video largo serían GB si se guardara en disco)."""
    pw, ph, x, y, right = layout(w, h)
    cues = mouth_cues(video, text, wd, fps)
    cls = LogoPuppet if config.MAX_PUPPET_STYLE == "logo" else Puppet
    pup = cls(pw, ph, fade=h > w, mirror=right)
    timeline = timeline or [{"start": 0.0}]
    for sc in timeline:
        sc["emotion"], sc["gesture"] = norm_emotion(sc.get("emotion")), norm_gesture(sc.get("gesture"))
    n = int(math.ceil(duration * fps))

    def gen():
        rnd = random.Random(11)
        next_blink, blink_left, idx, sidx, talk = rnd.uniform(1.5, 4), 0, 0, 0, 0.0
        for i in range(n):
            t = i / fps
            shape, idx = _shape_at(cues, t, idx)
            sidx = _scene_at(timeline, t, sidx)
            sc = timeline[sidx]
            since = t - sc["start"]
            end = timeline[sidx + 1]["start"] if sidx + 1 < len(timeline) else duration
            gesture = sc["gesture"] if 0.15 <= since <= min(GESTURE_SECS, end - sc["start"] - 0.2) else "none"
            talk = talk * 0.85 + (0.15 if shape not in "XA" else 0.0)   # cuánto está hablando (suavizado)
            if t >= next_blink:
                blink_left, next_blink = 4, t + rnd.uniform(2.0, 5.0)
            blink = blink_left > 0
            blink_left = max(0, blink_left - 1)
            # cabeceo leve: respiración + más movimiento cuando habla
            angle = round((math.sin(t * 1.3) * 1.2 + math.sin(t * 4.1) * 1.6 * talk) * 2) / 2
            dy = int(round(math.sin(t * 2.2) * 2 + talk * 3 * math.sin(t * 7.0)))
            lift = 0
            if t < ENTRANCE_SECS:   # entra desde abajo con rebote
                lift = int(round((1 - _ease_out_back(t / ENTRANCE_SECS)) * ph * 0.7))
            elif sc["emotion"] in HOP_EMOTIONS and since < HOP_SECS and sidx > 0:
                lift = -int(round(math.sin(math.pi * since / HOP_SECS) * ph * 0.05))
            lift = int(round(lift / 3) * 3)   # de a 3 px: menos cuadros distintos que dibujar
            yield pup.frame(sc["emotion"], gesture, shape, blink, angle, dy, lift)

    return (pw, ph, x, y), gen()

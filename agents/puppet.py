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
def layout(w, h):
    """Tamaño y posición del muñeco: abajo a la izquierda en Shorts (debajo de los subtítulos),
    abajo a la derecha en videos largos (los subtítulos van al centro)."""
    if h > w:
        # en Shorts la parte de abajo la tapan el título y el nombre del canal: Max va un poco más
        # arriba y el cuerpo se desvanece hacia abajo
        ph = int(h * 0.27)                  # ~520 px en 1920
        pw = int(ph * 500 / 740)
        return pw, ph, int(w * 0.03), h - ph - int(h * 0.08)
    ph = int(h * 0.42)                      # ~450 px en 1080
    pw = int(ph * 500 / 740)
    return pw, ph, w - pw - int(w * 0.02), h - ph


class Puppet:
    def __init__(self, pw, ph, fade=False):
        self.size = (pw, ph)
        load = lambda n: Image.open(os.path.join(ASSETS, n)).convert("RGBA").resize((pw, ph), Image.LANCZOS)  # noqa: E731
        self.body = load("body.png")
        self.heads = {(s, b): load(f"head_{s}{'_blink' if b else ''}.png") for s in SHAPES for b in (False, True)}
        # la cabeza gira alrededor del cuello (en el lienzo original: x=400, y=585 dentro del recorte 150,120)
        self.pivot = ((400 - 150) / 500 * pw, (585 - 120) / 740 * ph)
        self._cache = {}
        self.fade = None
        if fade:  # el último 30% del cuerpo se desvanece (no queda "cortado" en el medio de la pantalla)
            g = np.ones(ph, dtype=np.float32)
            start = int(ph * 0.70)
            g[start:] = np.linspace(1, 0, ph - start)
            self.fade = Image.fromarray((np.repeat(g[:, None], pw, axis=1) * 255).astype(np.uint8), "L")

    def frame(self, shape, blink, angle, dy):
        key = (shape, blink, angle, dy)
        if key not in self._cache:
            head = self.heads[(shape, blink)]
            if angle:
                head = head.rotate(angle, resample=Image.BICUBIC, center=self.pivot)
            img = self.body.copy()
            img.alpha_composite(head, (0, dy))
            if self.fade is not None:
                a = np.asarray(img.getchannel("A"), dtype=np.uint16) * np.asarray(self.fade, dtype=np.uint16) // 255
                img.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[key] = img.tobytes()
        return self._cache[key]


def overlay_frames(video, text, wd, w, h, fps, duration):
    """Prepara el muñeco. Devuelve ((ancho, alto, x, y), generador de cuadros RGBA crudos) para pasarle
    a FFmpeg por stdin (un video largo serían GB si se guardara en disco)."""
    pw, ph, x, y = layout(w, h)
    cues = mouth_cues(video, text, wd, fps)
    pup = Puppet(pw, ph, fade=h > w)
    n = int(math.ceil(duration * fps))

    def gen():
        rnd = random.Random(11)
        next_blink, blink_left, idx, talk = rnd.uniform(1.5, 4), 0, 0, 0.0
        for i in range(n):
            t = i / fps
            shape, idx = _shape_at(cues, t, idx)
            talk = talk * 0.85 + (0.15 if shape not in "XA" else 0.0)   # cuánto está hablando (suavizado)
            if t >= next_blink:
                blink_left, next_blink = 4, t + rnd.uniform(2.0, 5.0)
            blink = blink_left > 0
            blink_left = max(0, blink_left - 1)
            # cabeceo leve: respiración + más movimiento cuando habla
            angle = round((math.sin(t * 1.3) * 1.2 + math.sin(t * 4.1) * 1.6 * talk) * 2) / 2
            dy = int(round(math.sin(t * 2.2) * 2 + talk * 3 * math.sin(t * 7.0)))
            yield pup.frame(shape, blink, angle, dy)

    return (pw, ph, x, y), gen()

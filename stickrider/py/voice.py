"""StickRider — Voz: un narrador masculino en español, claro y fluido.

La voz se genera por PÁRRAFOS (varias líneas juntas), no línea por línea: así la entonación sigue el hilo de la
historia en vez de "reiniciarse" en cada oración. Después se busca en el audio la pausa que corresponde a cada
cambio de línea, para que las imágenes caigan justo con lo que se dice."""
import os

import numpy as np
import soundfile as sf

MODELS = os.getenv("KOKORO_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
VOICE = os.getenv("SR_VOICE") or "em_alex"          # español; alternativa: em_santa
SPEED = float(os.getenv("SR_VOICE_SPEED") or "1.1")
MAX_CHARS = 260  # largo de cada párrafo que se genera de una vez
LANG = os.getenv("SR_LANG") or "es"


def _voice(k, spec):
    if "," not in spec and ":" not in spec:
        return spec
    mix = None
    for part in spec.split(","):
        name, w = part.split(":")
        v = k.get_voice_style(name.strip()) * float(w)
        mix = v if mix is None else mix + v
    return mix


def _chunks(lines):
    """Agrupa líneas seguidas en párrafos de hasta MAX_CHARS (la pregunta y el giro abren párrafo nuevo)."""
    groups, cur, n = [], [], 0
    for i, t in enumerate(lines):
        brk = cur and (n + len(t) > MAX_CHARS or t.lstrip().lower().startswith(("resulta que", "¿")))
        if brk:
            groups.append(cur); cur, n = [], 0
        cur.append(i); n += len(t) + 1
    if cur:
        groups.append(cur)
    return groups


def _silences(a, sr, thr=0.012, min_len=0.07):
    """Tramos de silencio (inicio, fin) en segundos."""
    hop = int(sr * 0.01)
    env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a) - hop, hop)])
    quiet = env < thr
    out, s0 = [], None
    for k, q in enumerate(quiet):
        if q and s0 is None:
            s0 = k
        elif not q and s0 is not None:
            if (k - s0) * 0.01 >= min_len:
                out.append((s0 * 0.01, k * 0.01))
            s0 = None
    return out


def _split_points(a, sr, texts):
    """Dónde termina cada línea dentro del audio de un párrafo: la pausa más cercana a la posición esperada
    (proporcional a la cantidad de letras), respetando el orden."""
    dur = len(a) / sr
    total = sum(len(t) for t in texts)
    sil = _silences(a, sr)
    cuts, acc, last = [], 0, 0.0
    for t in texts[:-1]:
        acc += len(t)
        exp = dur * acc / total
        cands = [(abs((s + e) / 2 - exp), (s + e) / 2) for s, e in sil if (s + e) / 2 > last + 0.4 and abs((s + e) / 2 - exp) < 1.6]
        cut = min(cands)[1] if cands else exp
        cuts.append(cut); last = cut
    return cuts


def speak(lines, out_wav):
    """Genera la voz por párrafos. Devuelve [{start, end}] en segundos para cada línea."""
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(MODELS, "kokoro-v1.0.onnx"), os.path.join(MODELS, "voices-v1.0.bin"))
    voice = _voice(k, VOICE)
    parts, meta, t, sr = [], [None] * len(lines), 0.0, 24000
    for g in _chunks(lines):
        texts = [lines[i].strip() for i in g]
        a, sr = k.create(" ".join(texts), voice=voice, speed=SPEED, lang=LANG)
        nz = np.where(np.abs(a) > 0.01)[0]
        if len(nz):
            a = a[max(0, nz[0] - 200): nz[-1] + 400]
        cuts = _split_points(a, sr, texts)
        bounds = [0.0] + cuts + [len(a) / sr]
        for j, i in enumerate(g):
            meta[i] = {"start": round(t + bounds[j], 3), "end": round(t + bounds[j + 1], 3)}
        gap = 0.32  # respiración entre párrafos
        parts += [a, np.zeros(int(gap * sr), dtype=a.dtype)]
        t += len(a) / sr + gap
    sf.write(out_wav, np.concatenate(parts), sr)
    words = sum(len(x.split()) for x in lines)
    print(f"[voz] {t:.1f}s, {words} palabras, {words / t:.2f} palabras/s, {len(_chunks(lines))} párrafos")
    return meta, t

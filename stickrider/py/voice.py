"""StickRider — Voz: un narrador masculino, rápido y parejo (referencia: ~3,7 palabras/s, casi sin pausas)."""
import os

import numpy as np
import soundfile as sf

MODELS = os.getenv("KOKORO_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
VOICE = os.getenv("SR_VOICE", "am_michael")
SPEED = float(os.getenv("SR_VOICE_SPEED", "1.32"))


def _voice(k, spec):
    if "," not in spec and ":" not in spec:
        return spec
    mix = None
    for part in spec.split(","):
        name, w = part.split(":")
        v = k.get_voice_style(name.strip()) * float(w)
        mix = v if mix is None else mix + v
    return mix


def speak(lines, out_wav):
    """Genera la voz línea por línea. Devuelve [{start, end}] en segundos para cada línea."""
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(MODELS, "kokoro-v1.0.onnx"), os.path.join(MODELS, "voices-v1.0.bin"))
    voice = _voice(k, VOICE)
    parts, meta, t, sr = [], [], 0.0, 24000
    for text in lines:
        a, sr = k.create(text, voice=voice, speed=SPEED, lang="en-us")
        nz = np.where(np.abs(a) > 0.01)[0]
        if len(nz):
            a = a[max(0, nz[0] - 200): nz[-1] + 400]
        gap = 0.16 if text.rstrip().endswith(("?", "!", "...")) else 0.09
        meta.append({"start": round(t, 3), "end": round(t + len(a) / sr, 3)})
        parts += [a, np.zeros(int(gap * sr), dtype=a.dtype)]
        t += len(a) / sr + gap
    sf.write(out_wav, np.concatenate(parts), sr)
    words = sum(len(x.split()) for x in lines)
    print(f"[voz] {t:.1f}s, {words} palabras, {words / t:.2f} palabras/s")
    return meta, t

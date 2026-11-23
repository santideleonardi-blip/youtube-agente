"""StickRider — Sonido: música original sintetizada según el clima del guion + whoosh en cada movimiento de cámara
y en los fundidos + golpe en cada título de número. Voz al frente, música ~9 dB abajo. Todo propio: sin licencias.
(Instrumentos y DSP del kit MIT de la referencia, en audio/.)"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio"))
from dsp import SR, ns, rng, place, pan, colored, bp, fades, make_ir, convolve_st  # noqa: E402
from instruments import fife, pluck, snare, brush, pad, m2f, vibes, musicbox, timpani, brass, glock  # noqa: E402

# escalas (MIDI) por clima; cada canción se arma con una semilla distinta para que no se repita
SCALES = {
    "jig": [62, 64, 65, 67, 69, 71, 72, 74],        # re dórico
    "playful": [60, 62, 64, 65, 67, 69, 71, 72],    # do mayor
    "mystery": [57, 59, 60, 62, 64, 65, 68, 69],    # la menor armónica
    "tense": [50, 52, 53, 55, 57, 58, 61, 62],      # re menor armónica (grave)
    "epic": [55, 57, 59, 60, 62, 64, 66, 67],       # sol mayor
}


def _melody(r, scale, n):
    """Melodía por grados (pasos cortos, vuelve a la tónica cada 8 notas)."""
    idx, out = 0, []
    for k in range(n):
        if k % 8 == 7:
            idx = 0
        else:
            idx = int(np.clip(idx + r.choice([-2, -1, -1, 1, 1, 2, 0]), 0, len(scale) - 1))
        out.append(scale[idx])
    return out


def music(mood, dur, seed):
    r = rng(seed)
    buf = np.zeros((2, ns(dur + 1)))
    sc = SCALES.get(mood, SCALES["playful"])
    if mood == "jig":
        E = 0.19
        mel = _melody(r, sc, int(dur / E) + 8)
        for k, note in enumerate(mel):
            t = k * E
            if t > dur:
                break
            place(buf, pan(fife(m2f(note + 12), E * 0.9, 0.5, r), 0.15), t)
            if k % 3 == 0:
                place(buf, pan(pluck(m2f(sc[0] - 12 + (5 if (k // 12) % 2 else 0)), 0.7, r, 0.5), -0.3), t, 0.9)
                place(buf, pan(snare(0.3, r, 0.2, 0.8, 0.4), 0.0), t, 0.5)
            else:
                place(buf, pan(brush(0.3, r, 0.15), 0.2), t, 0.45)
    elif mood in ("playful", "mystery"):
        E = 0.22 if mood == "playful" else 0.3
        mel = _melody(r, sc, int(dur / E) + 8)
        inst = musicbox if mood == "playful" else vibes
        for k, note in enumerate(mel):
            t = k * E
            if t > dur:
                break
            if mood == "mystery" and k % 4 == 3:
                continue
            place(buf, pan(inst(m2f(note + 12), 0.5, r, 1.2), 0.2 * np.sin(k)), t, 0.8)
            if k % 4 == 0:
                place(buf, pan(pluck(m2f(sc[0] - 12), 0.6, r, 0.8), -0.25), t, 0.7)
            if mood == "playful" and k % 2 == 1:
                place(buf, pan(brush(0.25, r, 0.12), 0.25), t, 0.35)
        if mood == "mystery":
            place(buf, pad([m2f(sc[0] - 12), m2f(sc[2] - 12), m2f(sc[4] - 12)], dur, 0.3, r, 1.5, 1.5), 0.0, 0.7)
    elif mood == "tense":
        B = 0.42
        for k in range(int(dur / B) + 1):
            t = k * B
            place(buf, pan(timpani(m2f(sc[0] - 12), 0.45 if k % 2 else 0.6, r, 1.0), 0.0), t, 0.8)
            if k % 4 == 2:
                place(buf, pan(pluck(m2f(sc[(k // 4) % 3 + 4]), 0.5, r, 0.6), 0.3), t, 0.6)
        place(buf, pad([m2f(sc[0]), m2f(sc[2]), m2f(sc[5])], dur, 0.28, r, 2.0, 1.5), 0.0, 0.7)
    else:  # epic
        B = 0.4
        mel = _melody(r, sc, int(dur / B) + 4)
        for k, note in enumerate(mel):
            t = k * B
            if t > dur:
                break
            if k % 2 == 0:
                place(buf, pan(brass(m2f(note), B * 1.8, 0.45, r, "horn"), 0.1), t, 0.6)
            place(buf, pan(snare(0.35 if k % 2 else 0.5, r, 0.25), 0.0), t, 0.5)
            if k % 4 == 0:
                place(buf, pan(timpani(m2f(sc[0] - 12), 0.6, r, 1.2), 0.0), t, 0.7)
    return buf


def whoosh(r, d=0.45):
    n = ns(d)
    x = bp(colored(n, r, -1.0), 400, 3500, 2) * np.sin(np.linspace(0, np.pi, n)) ** 2
    return fades(x)


def mix(voice_wav, spec, mood, seed, out_wav):
    v, vsr = sf.read(voice_wav)
    v = v if v.ndim == 1 else v.mean(1)
    if vsr != SR:
        from scipy.signal import resample_poly
        v = resample_poly(v, SR, vsr)
    fps, dur = spec["fps"], spec["total"] / spec["fps"] + 0.3
    N = ns(dur)
    r = rng(seed)
    voice = np.zeros((2, N)); place(voice, v, 0.0)
    mus = music(mood, dur, seed)[:, :N]
    mus = convolve_st(mus, make_ir(0.6, 3))[:, :N] * 0.55 + mus * 0.45
    # fade-out al final para que termine con la última palabra
    tail = ns(0.6)
    mus[:, -tail:] *= np.linspace(1, 0, tail)
    sfx = np.zeros((2, N))
    for sh in spec["shots"]:
        for k in sh["cam"][1:]:
            place(sfx, pan(whoosh(r, 0.35), 0.0), (sh["a"] + k["f"]) / fps - 0.15, 0.6)
        if sh.get("xfade"):
            place(sfx, pan(whoosh(r, 0.5), 0.0), sh["a"] / fps - 0.3, 1.0)
    for c in spec.get("captions", []):
        place(sfx, pan(glock(m2f(84), 0.7, r, 0.8), 0.0), c["a"] / fps, 0.8)
        place(sfx, pan(timpani(m2f(43), 0.7, r, 0.8), 0.0), c["a"] / fps, 0.8)
    rms = lambda x: np.sqrt(np.mean(x ** 2) + 1e-12)  # noqa: E731
    mus *= (rms(voice) / max(rms(mus), 1e-9)) * 10 ** (-9.0 / 20)
    sfx *= (rms(voice) / max(rms(sfx), 1e-9)) * 10 ** (-16.0 / 20)
    out = voice + mus + sfx
    out /= max(1.0, np.abs(out).max() / 0.95)
    sf.write(out_wav, out.T, SR, subtype="PCM_24")
    print(f"[sonido] mezcla {N / SR:.1f}s, clima {mood}")

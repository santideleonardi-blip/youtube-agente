"""Agente 3 — Animador.

Convierte el guion en video: voz (Edge TTS), una ilustración por escena (Pollinations),
movimiento de cámara (zoom/paneo), subtítulos animados palabra por palabra y montaje con FFmpeg.
Todo gratis.
"""
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

import config

MOCK_TTS = os.getenv("MOCK_TTS") == "1"        # para pruebas sin internet
MOCK_IMAGES = os.getenv("MOCK_IMAGES") == "1"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Falló: {' '.join(cmd[:6])}...\n{r.stderr[-1500:]}")
    return r.stdout


def _duration(path):
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path])
    return float(json.loads(out)["format"]["duration"])


# ---------------- Voz ----------------
async def _tts_async(text, mp3_path):
    import edge_tts

    try:
        com = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE, boundary="WordBoundary")
    except TypeError:  # versiones viejas de edge-tts
        com = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
    words = []
    with open(mp3_path, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    return words


_kokoro = None


def _estimate_words(text, dur, lead=0.05):
    """Reparte la duración entre las palabras según su largo (para los subtítulos)."""
    words = text.split()
    weights = [len(w) + 2 for w in words]
    total = sum(weights)
    t, out = lead, []
    usable = max(dur - lead - 0.1, 0.5)
    for w, wt in zip(words, weights):
        d = usable * wt / total
        out.append({"text": w, "start": t, "end": t + d})
        t += d
    return out


def _tts_kokoro(text, mp3_path):
    """Voz local con Kokoro (gratis, sin internet, no la bloquea nadie)."""
    global _kokoro
    import soundfile as sf
    from kokoro_onnx import Kokoro

    if _kokoro is None:
        _kokoro = Kokoro(os.path.join(config.KOKORO_DIR, "kokoro-v1.0.onnx"),
                         os.path.join(config.KOKORO_DIR, "voices-v1.0.bin"))
    samples, sr = _kokoro.create(text, voice=config.KOKORO_VOICE, speed=config.KOKORO_SPEED, lang="en-us")
    wav = mp3_path[:-4] + ".wav"
    sf.write(wav, samples, sr)
    _run(["ffmpeg", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", mp3_path])
    return _estimate_words(text, len(samples) / sr)


def tts(text, mp3_path):
    if MOCK_TTS:
        n = len(text.split())
        dur = max(n / 2.6, 1.5)
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{dur:.2f}", mp3_path])
        return _estimate_words(text, dur)
    if config.TTS_ENGINE == "kokoro":
        return _tts_kokoro(text, mp3_path)
    for attempt in range(3):
        try:
            words = asyncio.run(asyncio.wait_for(_tts_async(text, mp3_path), timeout=120))
            if os.path.getsize(mp3_path) > 1000:
                return words
        except Exception as e:  # noqa: BLE001
            print(f"[animador] Edge TTS intento {attempt + 1} falló: {e}")
        time.sleep(4 * (attempt + 1))
    raise RuntimeError("Edge TTS no responde")


def voices(scenes, wd):
    """Genera la voz de TODAS las escenas con el mismo motor (para que no cambie la voz a mitad del video)."""
    paths = [os.path.join(wd, f"s{i:03d}.mp3") for i in range(len(scenes))]
    try:
        return paths, [tts(sc["narration"], p) for sc, p in zip(scenes, paths)]
    except RuntimeError as e:
        if config.TTS_ENGINE == "kokoro" or MOCK_TTS:
            raise
        print(f"[animador] {e} — rehago todas las voces con Kokoro")
        config.TTS_ENGINE = "kokoro"
        return paths, [tts(sc["narration"], p) for sc, p in zip(scenes, paths)]


# ---------------- Imágenes ----------------
def _fallback_image(path, w, h, seed):
    rnd = random.Random(seed)
    c1 = tuple(rnd.randint(20, 120) for _ in range(3))
    c2 = tuple(rnd.randint(120, 255) for _ in range(3))
    img = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    for _ in range(6):
        r = rnd.randint(min(w, h) // 12, min(w, h) // 4)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        col = tuple(rnd.randint(150, 255) for _ in range(3))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img.filter(ImageFilter.GaussianBlur(2)).save(path)


_IMG_FAILS = 0
cf_quota_hit = False  # se agotó el cupo diario gratis de Cloudflare en esta corrida (lo usa el estratega)
cf_images = 0         # imágenes FLUX.2 generadas en esta corrida (para llevar la cuenta del cupo diario)

# Cupo de Cloudflare: 10.000 neurons por día (se renueva 00:00 UTC = 21:00 ARG).
# FLUX.2 klein a 768x1344 = 6 tiles de 512x512 x 26,05 neurons ≈ 157 por imagen → ~60 imágenes por día.
CF_DAILY_NEURONS = 10_000
CF_NEURONS_PER_IMAGE = 165   # 157 de la imagen + ~6 de la imagen de referencia de Max
LONG_SCENES_PER_IMAGE = 2   # en videos largos cada ilustración se usa en 2 escenas seguidas (otra cámara)
# El estilo que se eligió es el de FLUX.2. Si el cupo se acaba, el video se pospone en vez de
# hacerse con otro modelo (se ve distinto). main.py activa el respaldo solo si el canal lleva >36 h sin videos.
ALLOW_FALLBACK = False


class ImageQuotaExhausted(RuntimeError):
    """Se agotó el cupo diario de Cloudflare y no está permitido usar otro modelo."""


def images_needed(fmt, n_scenes):
    if fmt == "long":
        return -(-n_scenes // LONG_SCENES_PER_IMAGE)
    return n_scenes


def _cloudflare_image(prompt, path, w, h, seed):
    """FLUX en Cloudflare Workers AI (plan gratis: ~10.000 'neurons' por día, sin marca de agua)."""
    acc, tok = os.getenv("CF_ACCOUNT_ID"), os.getenv("CF_API_TOKEN")
    if not (acc and tok):
        return None
    import base64

    base = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/"
    headers = {"Authorization": f"Bearer {tok}"}
    gw, gh = (768, 1344) if h > w else (1344, 768)
    klein = "@cf/black-forest-labs/flux-2-klein-4b"
    skip_ref = False

    def klein_kwargs():
        files = {"prompt": (None, prompt), "width": (None, str(gw)), "height": (None, str(gh)),
                 "seed": (None, str(seed % 2_000_000_000))}
        ref = _max_reference() if _MAX_RE.search(prompt) and not skip_ref else None
        if ref:
            # Max tiene que verse SIEMPRE igual: se le pasa el dibujo oficial (el del logo) como imagen de referencia
            files["prompt"] = (None, MAX_REF_PROMPT + prompt)
            files["input_image_0"] = ("max.png", ref, "image/png")
        return dict(files=files)

    attempts = [
        # FLUX.2 klein (mejor calidad, acepta proporción vertical) — formato multipart
        (klein, klein_kwargs),
        # FLUX.1 schnell (respaldo, imagen cuadrada) — formato JSON
        ("@cf/black-forest-labs/flux-1-schnell", lambda: dict(json={"prompt": prompt, "steps": 8})),
    ]
    # klein va 2 veces (un error pasajero no debe cambiar el estilo); schnell solo si el filtro rechaza el prompt
    attempts = [attempts[0], attempts[0], attempts[0], attempts[1]]
    flagged = False
    for n, (model, make_kwargs) in enumerate(attempts):
        if model in _CF_BAD:
            continue
        if "schnell" in model and not flagged and not ALLOW_FALLBACK:
            continue
        if n == 1:
            time.sleep(5)
        try:
            kwargs = make_kwargs()
            with_ref = "input_image_0" in kwargs.get("files", {})
            r = requests.post(base + model, headers=headers, timeout=120, **kwargs)
            data = r.json() if "json" in r.headers.get("content-type", "") else {}
            img_b64 = (data.get("result") or {}).get("image")
            if r.ok and img_b64:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(img_b64))
                Image.open(path).convert("RGB").save(path, "PNG")
                if "klein" in model:
                    global cf_images
                    cf_images += 1
                print(f"[animador] imagen OK ({model.split('/')[-1]})")
                return path
            print(f"[animador] Cloudflare {model.split('/')[-1]} HTTP {r.status_code}: {str(data)[:200]}")
            if r.status_code == 429 and "daily free allocation" in str(data).lower():
                global cf_quota_hit
                cf_quota_hit = True
                _CF_BAD.update(m for m, _ in attempts)  # cupo del día agotado: no insistir, pasar a Pollinations
                print("[animador] cupo diario de Cloudflare agotado: sigo con Pollinations")
                return None
            if "flagged" in str(data).lower():
                if with_ref:
                    # el filtro rechazó ESTA combinación de prompt + referencia: reintentar esta imagen sin la referencia
                    print("[animador] el filtro rechazó la imagen con referencia: la reintento sin ella")
                    skip_ref = True
                flagged = True
                continue  # el filtro de contenido rechazó ESTE prompt: probar el otro modelo, no descartar
            if with_ref and r.status_code in (400, 413, 422):
                global _REF_BROKEN
                _REF_BROKEN = True   # la imagen de referencia no la acepta: seguir solo con la descripción
                print("[animador] FLUX.2 no aceptó la imagen de referencia de Max: sigo sin ella")
                continue
            if r.status_code in (400, 404, 422):
                _CF_BAD.add(model)  # formato/modelo no soportado: no reintentar en esta corrida
        except Exception as e:  # noqa: BLE001
            print(f"[animador] Cloudflare {model} falló: {e}")
    return None


_CF_BAD = set()
_REF_BROKEN = False
_REF_CACHE = None
MAX_REFERENCE = os.path.join(config.ROOT, "assets", "max_logo", "reference.png")
MAX_REF_PROMPT = ("Max is the man shown in image 0: draw him EXACTLY as in image 0 (same face, eyes, round pink nose, "
                  "shaggy brown hair, stubble, orange zip hoodie, same drawing style), only change his pose, "
                  "expression and the scene. ")


def _max_reference():
    """Bytes del dibujo oficial de Max (<512 px, como pide Cloudflare) o None si no se puede usar."""
    global _REF_CACHE
    if _REF_BROKEN or not config.MAX_REFERENCE_IMAGE or not os.path.exists(MAX_REFERENCE):
        return None
    if _REF_CACHE is None:
        with open(MAX_REFERENCE, "rb") as f:
            _REF_CACHE = f.read()
    return _REF_CACHE


_MAX_RE = re.compile(r"\bMax\b")
# Lo que el guionista suele escribir después de "Max" para describirlo ("an adult explorer with messy
# brown hair and an orange jumpsuit", etc.): se saca para que no compita con la descripción fija.
_MAX_DESC_RE = re.compile(r"\bMax\b(?:'s)?\s*(?:,|\()?\s*(?:the |an? )?(?:adult )?explorer"
                          r"(?:\s+(?:with|in|wearing)\b[^,.;)]*)?(?:\s+and\s+an?\s+[^,.;)]*jumpsuit)?\)?", re.I)


def with_max_look(prompt):
    """Si la escena muestra a Max, le pega siempre la misma descripción física."""
    if not _MAX_RE.search(prompt or ""):
        return prompt
    prompt = _MAX_DESC_RE.sub("Max", prompt)
    return f"{prompt}. {config.MAX_LOOK}"


def image(prompt, path, w, h, seed):
    if MOCK_IMAGES:
        return _fallback_image(path, w, h, seed)
    full = f"{with_max_look(prompt)}, {config.IMAGE_STYLE}"
    if _cloudflare_image(full, path, w, h, seed):
        return path
    if cf_quota_hit and not ALLOW_FALLBACK and os.getenv("CF_ACCOUNT_ID"):
        raise ImageQuotaExhausted("cupo diario de Cloudflare agotado: el video se pospone para mantener el estilo FLUX.2")
    # Pollinations limita el tamaño: pedimos ~1MP con la proporción correcta y después escalamos.
    gw, gh = (768, 1344) if h > w else (1344, 768)
    url = (
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full)
        + f"?width={gw}&height={gh}&seed={seed}&nologo=true&model=flux"
    )
    global _IMG_FAILS
    if _IMG_FAILS >= 3:  # el servicio no responde: no perder tiempo, usar respaldo
        return _fallback_image(path, w, h, seed)
    headers = {}
    if os.getenv("POLLINATIONS_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['POLLINATIONS_TOKEN']}"
    attempt = 0
    while attempt < 3:
        try:
            t0 = time.time()
            r = requests.get(url, timeout=90, headers=headers)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                with open(path, "wb") as f:
                    f.write(r.content)
                Image.open(path).convert("RGB").save(path, "PNG")
                print(f"[animador] imagen OK en {time.time() - t0:.0f}s")
                return path
            if r.status_code in (402, 429):
                # Límite gratuito (1 imagen cada ~45 s): esperar lo que pide y reintentar sin contar como fallo
                m = re.search(r"[Rr]etry after (\d+)", r.text)
                wait = int(m.group(1)) + 2 if m else 46
                print(f"[animador] límite gratuito de imágenes, espero {wait}s")
                time.sleep(wait)
                continue
            print(f"[animador] imagen HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[animador] imagen intento {attempt + 1} falló: {e}")
        attempt += 1
        time.sleep(5)
    _IMG_FAILS += 1
    print("[animador] uso imagen de respaldo")
    return _fallback_image(path, w, h, seed)


def _cover(path, w, h):
    """Recorta/escala la imagen a 1.3x el tamaño final (margen para la cámara virtual)."""
    img = Image.open(path).convert("RGB")
    img = img.crop((0, 0, img.width, int(img.height * 0.93)))  # saca la marca de agua de abajo
    tw, th = int(w * 1.3), int(h * 1.3)
    scale = max(tw / img.width, th / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - tw) // 2, (img.height - th) // 2
    img.crop((left, top, left + tw, top + th)).save(path)


# ---------------- Escenas ----------------


def _scene_clip(img, audio, out, w, h, dur, idx):
    """Una escena = varias tomas cortas (cortes cada ~2.5 s) con cámara 2.5D sobre la misma ilustración."""
    import cv2

    from agents import parallax

    shot_len = 2.5 if h > w else 4.0
    n = max(1, round(dur / shot_len))
    src = cv2.imread(img)
    depth = parallax.depth_map(src)
    shots = []
    for k in range(n):
        sp = out[:-4] + f"_k{k}.mp4"
        parallax.render_shot(src, depth, sp, w, h, dur / n, idx * 3 + k)
        shots.append(sp)
    lst = out[:-4] + "_list.txt"
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in shots)
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
        "-filter_complex", "[1:a]apad=pad_dur=0.35,aresample=44100[a]",
        "-map", "0:v", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ac", "2", out,
    ])


# ---------------- Subtítulos ----------------
def _ass_time(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _subtitles(words, path, w, h, fmt):
    size = int(h * 0.055) if fmt == "short" else int(h * 0.065)
    margin_v = int(h * (0.36 if config.MAX_NARRATOR else 0.30)) if fmt == "short" else int(h * 0.08)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,{size},&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{max(size // 9, 3)},2,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunk = []
    for i, wd in enumerate(words):
        chunk.append(wd)
        ends_sentence = wd["text"][-1:] in ".?!,"
        if len(chunk) == 3 or ends_sentence or i == len(words) - 1:
            start, end = chunk[0]["start"], chunk[-1]["end"]
            nxt = words[i + 1]["start"] if i + 1 < len(words) else end + 0.3
            end = max(end, min(nxt, end + 0.4))
            # palabra actual resaltada en amarillo (efecto karaoke)
            for j, cw in enumerate(chunk):
                s = cw["start"]
                e = chunk[j + 1]["start"] if j + 1 < len(chunk) else end
                parts = []
                for k, kw in enumerate(chunk):
                    t = kw["text"].upper().replace("{", "").replace("}", "")
                    parts.append(r"{\c&H0000E5FF&}" + t + r"{\c&H00FFFFFF&}" if k == j else t)
                pop = r"{\fscx112\fscy112\t(0,90,\fscx100\fscy100)}" if j == 0 else ""
                lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Main,,0,0,0,,{pop}{' '.join(parts)}")
            chunk = []
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")


def _final_with_max(joined, ass, script, wd, w, h, duration, enc, scene_meta=None):
    """Montaje final con el muñeco de Max narrando (boca sincronizada) encima de las escenas."""
    from agents import puppet

    text = " ".join(sc["narration"] for sc in script["scenes"])
    timeline = [{"start": m["start"], "emotion": sc.get("emotion"), "gesture": sc.get("gesture")}
                for m, sc in zip(scene_meta or [], script["scenes"])]
    (pw, ph, x, y), frames = puppet.overlay_frames(joined, text, wd, w, h, config.FPS, duration, timeline)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{pw}x{ph}", "-r", str(config.FPS), "-i", "pipe:0",
           "-filter_complex", f"[0:v][1:v]overlay={x}:{y}:eof_action=pass:format=auto,ass={ass}[v]",
           "-map", "[v]", "-map", "0:a", *enc]
    log = os.path.join(wd, "ffmpeg_max.log")
    with open(log, "w") as err:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        try:
            for fr in frames:
                p.stdin.write(fr)
        except BrokenPipeError:
            pass
        finally:
            try:
                p.stdin.close()
            except BrokenPipeError:
                pass
        p.wait()
    if p.returncode != 0:
        with open(log) as f:
            raise RuntimeError(f"FFmpeg con Max falló: {f.read()[-800:]}")
    print("[max] Max narrando agregado")


# ---------------- Principal ----------------
def run(script, fmt, job_id):
    spec = config.FORMATS[fmt]
    w, h = spec["width"], spec["height"]
    wd = os.path.join(config.WORK_DIR, job_id)
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    clips, all_words, scene_meta = [], [], []
    t = 0.0
    seed_base = random.randint(1, 10_000_000)
    print(f"[animador] generando voces ({config.TTS_ENGINE})")
    mp3s, all_scene_words = voices(script["scenes"], wd)
    for i, sc in enumerate(script["scenes"]):
        print(f"[animador] escena {i + 1}/{len(script['scenes'])}")
        mp3, words = mp3s[i], all_scene_words[i]
        png = os.path.join(wd, f"s{i:03d}.png")
        mp4 = os.path.join(wd, f"s{i:03d}.mp4")
        raw = os.path.join(wd, f"raw{i:03d}.png")
        if fmt == "long" and i % LONG_SCENES_PER_IMAGE:
            shutil.copy(os.path.join(wd, f"raw{i - i % LONG_SCENES_PER_IMAGE:03d}.png"), raw)
        else:
            image(sc.get("image_prompt") or sc["narration"], raw, w, h, seed_base + i)
        shutil.copy(raw, png)
        if i == 0:
            shutil.copy(png, os.path.join(wd, "cover.png"))
        _cover(png, w, h)
        dur = _duration(mp3) + 0.35
        _scene_clip(png, mp3, mp4, w, h, dur, i)
        dur = _duration(mp4)
        for wdict in words:
            all_words.append({"text": wdict["text"], "start": wdict["start"] + t, "end": wdict["end"] + t})
        scene_meta.append({"start": round(t, 2), "narration": sc["narration"]})
        clips.append(mp4)
        t += dur

    concat = os.path.join(wd, "list.txt")
    with open(concat, "w") as f:
        f.writelines(f"file '{c}'\n" for c in clips)
    joined = os.path.join(wd, "joined.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", joined])

    ass = os.path.join(wd, "subs.ass")
    _subtitles(all_words, ass, w, h, fmt)
    final = os.path.join(config.OUTPUT_DIR, f"{job_id}.mp4")
    enc = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", final]
    done = False
    if config.MAX_NARRATOR:
        try:
            _final_with_max(joined, ass, script, wd, w, h, t, enc, scene_meta)
            done = True
        except Exception as e:  # noqa: BLE001
            print(f"[max] no pude agregar a Max narrando, sigo sin él: {e}")
    if not done:
        _run(["ffmpeg", "-y", "-i", joined, "-vf", f"ass={ass}", *enc])
    total = _duration(final)
    print(f"[animador] video listo: {final} ({total:.1f}s)")
    return {"video": final, "cover": os.path.join(wd, "cover.png"), "duration": total, "scenes": scene_meta}

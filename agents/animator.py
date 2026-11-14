"""Agente 3 — Animador.

Convierte el guion en video: voz (Edge TTS), una ilustración por escena (Pollinations),
movimiento de cámara (zoom/paneo), subtítulos animados palabra por palabra y montaje con FFmpeg.
Todo gratis.
"""
import asyncio
import json
import os
import random
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


def tts(text, mp3_path):
    if MOCK_TTS:
        n = len(text.split())
        dur = max(n / 2.6, 1.5)
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{dur:.2f}", mp3_path])
        step = dur / n
        return [{"text": w, "start": i * step, "end": (i + 1) * step} for i, w in enumerate(text.split())]
    for attempt in range(4):
        try:
            words = asyncio.run(_tts_async(text, mp3_path))
            if os.path.getsize(mp3_path) > 1000:
                return words
        except Exception as e:  # noqa: BLE001
            print(f"[animador] TTS intento {attempt + 1} falló: {e}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("No se pudo generar la voz")


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


def image(prompt, path, w, h, seed):
    if MOCK_IMAGES:
        return _fallback_image(path, w, h, seed)
    full = f"{prompt}, {config.IMAGE_STYLE}"
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
    for attempt in range(2):
        try:
            t0 = time.time()
            r = requests.get(url, timeout=90, headers=headers)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                with open(path, "wb") as f:
                    f.write(r.content)
                Image.open(path).convert("RGB").save(path, "PNG")
                print(f"[animador] imagen OK en {time.time() - t0:.0f}s")
                return path
            print(f"[animador] imagen HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[animador] imagen intento {attempt + 1} falló: {e}")
        time.sleep(5)
    _IMG_FAILS += 1
    print("[animador] uso imagen de respaldo")
    return _fallback_image(path, w, h, seed)


def _cover(path, w, h):
    """Recorta/escala la imagen al doble del tamaño final (margen para el zoom suave)."""
    img = Image.open(path).convert("RGB")
    tw, th = w * 2, h * 2
    scale = max(tw / img.width, th / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - tw) // 2, (img.height - th) // 2
    img.crop((left, top, left + tw, top + th)).save(path)


# ---------------- Escenas ----------------
MOTIONS = [
    # (zoom, x, y) expresiones de zoompan — se alternan para que no se vea repetitivo
    ("min(zoom+0.0009,1.18)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                 # zoom in centro
    ("if(eq(on,0),1.18,max(zoom-0.0009,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # zoom out
    ("1.12", "(iw-iw/zoom)*on/{f}", "ih/2-(ih/zoom/2)"),                                # paneo der
    ("1.12", "(iw-iw/zoom)*(1-on/{f})", "ih/2-(ih/zoom/2)"),                            # paneo izq
    ("min(zoom+0.0007,1.15)", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*0.3"),                 # zoom arriba
]


def _scene_clip(img, audio, out, w, h, dur, idx):
    frames = int(dur * config.FPS) + 1
    z, x, y = MOTIONS[idx % len(MOTIONS)]
    x, y = x.format(f=frames), y.format(f=frames)
    vf = (
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={config.FPS},"
        f"fade=t=in:st=0:d=0.25,format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", img, "-i", audio,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad=pad_dur=0.35,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(config.FPS),
        "-c:a", "aac", "-b:a", "160k", "-ac", "2", out,
    ])


# ---------------- Subtítulos ----------------
def _ass_time(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _subtitles(words, path, w, h, fmt):
    size = int(h * 0.055) if fmt == "short" else int(h * 0.065)
    margin_v = int(h * 0.30) if fmt == "short" else int(h * 0.08)
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
    for i, sc in enumerate(script["scenes"]):
        print(f"[animador] escena {i + 1}/{len(script['scenes'])}")
        mp3 = os.path.join(wd, f"s{i:03d}.mp3")
        png = os.path.join(wd, f"s{i:03d}.png")
        mp4 = os.path.join(wd, f"s{i:03d}.mp4")
        words = tts(sc["narration"], mp3)
        image(sc.get("image_prompt") or sc["narration"], png, w, h, seed_base + i)
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
    _run([
        "ffmpeg", "-y", "-i", joined, "-vf", f"ass={ass}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", final,
    ])
    total = _duration(final)
    print(f"[animador] video listo: {final} ({total:.1f}s)")
    return {"video": final, "cover": os.path.join(wd, "cover.png"), "duration": total, "scenes": scene_meta}

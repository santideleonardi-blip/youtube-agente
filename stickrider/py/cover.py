"""StickRider — Portada propia de cada Short (para que no la elija YouTube).

Toma el cuadro más fuerte del comienzo del video (el primer momento con efecto, o el gancho) y le pone encima el
texto de portada grande, amarillo con borde negro, con la misma letra de los títulos del video. 1080x1920, JPG < 2 MB.
"""
import os
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "fonts", "LuckiestGuy.ttf")
FPS = 30


def pick_time(script, spec):
    """Segundo del video para la portada: la primera línea con efecto (sorpresa) dentro de las 6 primeras; si no hay,
    el medio del gancho."""
    starts = []
    for sh in spec["shots"]:
        for k in sh["cam"]:
            starts.append(sh["a"] + k["f"])
    starts = sorted(set(starts))
    for i, ln in enumerate(script["lines"][:6]):
        if ln.get("fx", "none") != "none" and i < len(starts):
            return (starts[i] + 20) / FPS
    return 1.4


def _font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)


def make(video, text, out, t=1.4):
    frame = out + ".png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", frame], check=True)
    img = Image.open(frame).convert("RGB")
    W, H = img.size
    # oscurecer arriba para que el texto se lea siempre
    shade = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(shade)
    for y in range(int(H * 0.45)):
        d.line([(0, y), (W, y)], fill=int(150 * (1 - y / (H * 0.45))))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade)
    text = " ".join(str(text).upper().split())
    size = 150
    while size > 70:
        f = _font(size)
        lines = textwrap.wrap(text, width=max(6, int(W * 0.88 / (size * 0.62))))
        if len(lines) <= 3 and all(f.getlength(l) <= W * 0.9 for l in lines):
            break
        size -= 8
    f = _font(size)
    lines = textwrap.wrap(text, width=max(6, int(W * 0.88 / (size * 0.62))))[:3]
    draw = ImageDraw.Draw(img)
    y = int(H * 0.09)
    for l in lines:
        w = f.getlength(l)
        draw.text(((W - w) / 2, y), l, font=f, fill="#FFD23F", stroke_width=max(8, size // 12), stroke_fill="black")
        y += int(size * 1.08)
    img.save(out, "JPEG", quality=90, optimize=True)
    os.remove(frame)
    return out

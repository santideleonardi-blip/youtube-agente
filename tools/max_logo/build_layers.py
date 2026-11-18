"""Arma las capas del muñeco a partir del Max del logo (max_cut.png, ya recortado y ampliado x4)."""
import subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, "/home/claude/repo/tools")
import make_max_puppet as M

src = Image.open("max_cut.png")
W, H = src.size
rgb = np.array(src.convert("RGB"))
alpha = np.array(src)[:, :, 3]

# arreglar el agujerito del brazo (abajo a la izquierda)
hole = np.zeros((H, W), np.uint8)
hole[1150:1345, 300:470] = 1
fill = (hole == 1) & (alpha < 250)
alpha2 = alpha.copy(); alpha2[hole == 1] = 255
rgb = cv2.inpaint(rgb, fill.astype(np.uint8), 9, cv2.INPAINT_TELEA)
base = Image.fromarray(np.dstack([rgb, alpha2]))

MOUTH = (772, 812); ANG = -8
# zona de la boca sin la boca (para dibujar las bocas que hablan encima)
mm = Image.new("L", (W, H), 0)
ImageDraw.Draw(mm).ellipse([MOUTH[0] - 125, MOUTH[1] - 42, MOUTH[0] + 125, MOUTH[1] + 52], fill=255)
mm = mm.rotate(-ANG, center=MOUTH)
clean = cv2.inpaint(rgb, (np.array(mm) > 0).astype(np.uint8), 21, cv2.INPAINT_TELEA)
clean = cv2.GaussianBlur(clean, (0, 0), 1.2) * (np.array(mm)[:, :, None] > 0) + rgb * (np.array(mm)[:, :, None] == 0)
patch_a = cv2.GaussianBlur(np.array(mm).astype(np.float32), (0, 0), 6)
patch = Image.fromarray(np.dstack([clean.astype(np.uint8), patch_a.clip(0, 255).astype(np.uint8)]))


def svg_layer(inner, name):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{inner}</svg>'
    subprocess.run(["rsvg-convert", "-o", name], input=svg.encode(), check=True)
    return Image.open(name).convert("RGBA")


def mouth_layer(shape):
    inner = M.mouth(shape).replace('stroke-width="7"', 'stroke-width="4.2"').replace('stroke-width="5"', 'stroke-width="3.4"')
    g = f'<g transform="translate({MOUTH[0]} {MOUTH[1]}) rotate({ANG}) scale(2.7) translate(-400 -520)">{inner}</g>'
    lay = patch.copy()
    lay.alpha_composite(svg_layer(g, "/tmp/_m.png"))
    return lay


SCALE = 0.62
out = "/home/claude/repo/assets/max_logo"
import os, shutil
shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
_ys, _xs = np.where(np.array(base)[:, :, 3] > 10)
BOX = (int(_xs.min()), int(_ys.min()), int(_xs.max()) + 1, int(_ys.max()) - 3)   # sin filas vacías abajo
small = lambda im: im.crop(BOX).resize((int((BOX[2] - BOX[0]) * SCALE), int((BOX[3] - BOX[1]) * SCALE)), Image.LANCZOS)  # noqa: E731
small(base).save(f"{out}/base.png", optimize=True)
base.crop(BOX).save("/home/claude/maxraster/base_full.png")
for s in "BCDEFGH":
    small(mouth_layer(s)).save(f"{out}/mouth_{s}.png", optimize=True)

# parpadeo: se "borra" el ojo rellenando con la piel de alrededor y se dibuja el ojo cerrado
EYES = [((630, 694), (90, 80)), ((860, 642), (88, 80))]
em = Image.new("L", (W, H), 0)
for (cx, cy), (rx, ry) in EYES:
    ImageDraw.Draw(em).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
emn = np.array(em)
lid = cv2.inpaint(rgb, (emn > 0).astype(np.uint8), 25, cv2.INPAINT_TELEA)
# color de piel: mediana de un anillo debajo de cada ojo; se mezcla con el relleno para que no queden manchas
lid = lid.astype(np.float32)
for (cx, cy), (rx, ry) in EYES:
    ring = rgb[cy + ry + 8: cy + ry + 40, cx - rx // 2: cx + rx // 2].reshape(-1, 3)
    skin = np.median(ring, axis=0)
    yy, xx = np.ogrid[:H, :W]
    inside = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    lid[inside] = lid[inside] * 0.25 + skin * 0.75
lid = cv2.GaussianBlur(lid.clip(0, 255).astype(np.uint8), (0, 0), 2.5)
ea = cv2.GaussianBlur(emn.astype(np.float32), (0, 0), 4)
lay = Image.fromarray(np.dstack([lid, ea.clip(0, 255).astype(np.uint8)]))
d = ImageDraw.Draw(lay)
for (cx, cy), (rx, ry) in EYES:
    d.arc([cx - rx * 0.85, cy - ry * 0.5, cx + rx * 0.85, cy + ry * 0.6], 12, 168, fill=(28, 22, 18, 255), width=12)
small(lay).save(f"{out}/blink.png", optimize=True)
print("listo", small(base).size)

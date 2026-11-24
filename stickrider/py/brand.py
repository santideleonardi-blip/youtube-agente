"""Arma el banner (tres épocas) y la foto de perfil de StickRider a partir de los paneles renderizados con el motor.
Uso: python brand.py <carpeta_paneles> <fuente.ttf> <carpeta_salida>"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

src, font_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
INK, GOLD, WHITE = (36, 23, 38), (255, 210, 63), (255, 255, 255)
W, H = 2560, 1440


def panel(name):
    return Image.open(os.path.join(src, name, "element-5.png")).convert("RGB")


def text(d, xy, s, size, fill, stroke, anchor="mm", shadow=0):
    f = ImageFont.truetype(font_path, size)
    if shadow:
        d.text((xy[0], xy[1] + shadow), s, font=f, fill=INK, anchor=anchor, stroke_width=stroke, stroke_fill=INK)
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=INK)


# ---------- banner: Antigüedad | Edad Media | Hoy ----------
anc, med, mod = panel("ancient"), panel("medieval"), panel("modern")
ban = med.copy()
# franjas laterales con corte diagonal (los personajes quedan dentro de la franja visible en escritorio: y 508-931)
cut, slant = 640, 130
left = Image.new("L", (W, H), 0)
ImageDraw.Draw(left).polygon([(0, 0), (cut + slant, 0), (cut - slant, H), (0, H)], fill=255)
right = Image.new("L", (W, H), 0)
ImageDraw.Draw(right).polygon([(W - cut + slant, 0), (W, 0), (W, H), (W - cut - slant, H)], fill=255)
# centrar a los personajes de cada época en su franja
ban.paste(anc.crop((W // 2 - (cut // 2) - 30, 0, W // 2 - (cut // 2) - 30 + W, H)), (0, 0), left)
ban.paste(mod.transform((W, H), Image.AFFINE, (1, 0, -(W - cut // 2 - W // 2) + 30, 0, 1, 0)), (0, 0), right)
d = ImageDraw.Draw(ban)
for x0, x1 in ((cut + slant, cut - slant), (W - cut + slant, W - cut - slant)):
    d.line([(x0, 0), (x1, H)], fill=INK, width=16)
    d.line([(x0, 0), (x1, H)], fill=WHITE, width=6)
# nombre + lema en la zona segura (1546 x 423 centrada)
text(d, (W // 2, 655), "STICKRIDER", 190, GOLD, 18, shadow=12)
text(d, (W // 2, 800), "HISTORIAS REALES DE TODAS LAS ÉPOCAS", 66, WHITE, 10)
ban.save(os.path.join(out, "StickRider_banner_2560x1440.png"))

# guía de zonas (solo para revisar)
g = ban.copy(); gd = ImageDraw.Draw(g)
gd.rectangle([507, 508, 2053, 931], outline=(255, 0, 0), width=6); gd.rectangle([0, 508, 2559, 931], outline=(0, 200, 255), width=4)
g.resize((1280, 720)).save(os.path.join(out, "guia_banner.png"))

# ---------- foto de perfil ----------
av = panel("avatar")
av.save(os.path.join(out, "StickRider_perfil_800x800.png"))
m = Image.new("L", av.size, 0); ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
c = Image.new("RGB", av.size, WHITE); c.paste(av, (0, 0), m); c.resize((400, 400)).save(os.path.join(out, "guia_perfil.png"))
print("listo")

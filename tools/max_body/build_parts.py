"""Arma el Max de cuerpo entero por partes (para animarlo caminando, saltando, etc. dentro de las escenas).

Entrada:
  - assets/max_body/source/body_canva.png: Max de cuerpo entero hecho en Canva con el logo de referencia
    (campera naranja, jean azul, zapatillas blancas), 1024x1536, fondo blanco. Aprobado por Santi el 20/11.
  - assets/max_logo/: la cabeza es SIEMPRE la del logo (con sus bocas y parpadeo), para que la cara no cambie.

Salida: assets/max_body/*.png (una imagen por parte) + rig.json (dónde va cada parte y sobre qué punto gira).

Uso:  python tools/max_body/build_parts.py
"""
import json
import os

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "assets", "max_body", "source", "body_canva.png")
LOGO = os.path.join(ROOT, "assets", "max_logo")
OUT = os.path.join(ROOT, "assets", "max_body")

# Puntos del dibujo de Canva (en píxeles de la imagen de 1024x1536)
NECK = (497, 452)                       # donde se apoya la cabeza del logo
SHOULDER_L, SHOULDER_R = (318, 525), (680, 525)
HIP_L, HIP_R = (428, 872), (566, 872)
ARM_CUT_L, ARM_CUT_R = 362, 632         # costura entre manga y cuerpo
LEG_TOP = 852                           # debajo de esto, piernas
LEG_SPLIT = 498                         # entre una pierna y la otra
TORSO_TOP = 398
OLD_HEAD = ((497, 285), (232, 178))   # cabeza de Canva (se tapa con la del logo): elipse centro, radios
OVERLAP = 30                            # las partes de atrás se meten un poco debajo del cuerpo (sin huecos al girar)
HEAD_WIDTH = 450                        # ancho de la cabeza del logo (pelo) en este dibujo


def _alpha_from_white(rgb):
    """Fondo blanco -> transparente, rellenando desde los bordes (las zapatillas blancas tienen contorno negro)."""
    h, w = rgb.shape[:2]
    light = (rgb.min(axis=2) > 214).astype(np.uint8)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flood = light.copy()
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)]:
        if flood[y, x]:
            cv2.floodFill(flood, mask, (x, y), 2)
    bg = flood == 2
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    # borde suave de 1 px
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return alpha


def _remove_sticker_border(img):
    """El logo tiene un borde blanco de sticker: se saca (rellenando desde afuera por los píxeles claros)."""
    a = np.array(img)
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    outside = (al < 40)
    light = (rgb.min(axis=2) > 175) & (rgb.max(axis=2) - rgb.min(axis=2) < 45)
    reach = (outside | light).astype(np.uint8)
    lab_n, lab = cv2.connectedComponents(reach)
    border_labels = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    kill = np.isin(lab, list(border_labels)) & reach.astype(bool)
    al = np.where(kill, 0, al)
    # restos de la sombra rosada del sticker pegados al contorno: erosión mínima del alfa
    al = cv2.erode(al, np.ones((3, 3), np.uint8), iterations=1)
    al = cv2.GaussianBlur(al, (3, 3), 0)
    return Image.fromarray(np.dstack([rgb, al]))


def _part(rgba, mask, pivot):
    """Recorta la parte según la máscara; devuelve (imagen, posición de su esquina, pivote relativo)."""
    a = rgba.copy()
    a[..., 3] = np.minimum(a[..., 3], mask)
    ys, xs = np.where(a[..., 3] > 8)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    im = Image.fromarray(a[y0:y1, x0:x1])
    return im, (int(x0), int(y0)), (int(pivot[0] - x0), int(pivot[1] - y0))


def main():
    src = np.array(Image.open(SRC).convert("RGB"))
    H, W = src.shape[:2]
    assert (W, H) == (1024, 1536), f"se esperaba 1024x1536, vino {W}x{H}"
    rgba = np.dstack([src, _alpha_from_white(src)])
    yy, xx = np.mgrid[0:H, 0:W]

    arm_l = (xx < ARM_CUT_L) & (yy > TORSO_TOP + 72) & (yy < LEG_TOP + 140)
    arm_r = (xx > ARM_CUT_R) & (yy > TORSO_TOP + 72) & (yy < LEG_TOP + 140)
    # las manos llegan más abajo que el cuerpo y quedan al costado de las piernas
    leg_zone = (yy >= LEG_TOP) & ~arm_l & ~arm_r
    leg_zone &= (xx > ARM_CUT_L - 110) & (xx < ARM_CUT_R + 110)
    hand_l = (yy >= LEG_TOP) & (xx < 352) & (yy < 990)
    hand_r = (yy >= LEG_TOP) & (xx > 642) & (yy < 990)
    arm_l |= hand_l
    arm_r |= hand_r
    leg_zone &= ~hand_l & ~hand_r
    (hcx, hcy), (hrx, hry) = OLD_HEAD
    old_head = ((xx - hcx) / hrx) ** 2 + ((yy - hcy) / hry) ** 2 < 1
    torso = (yy >= TORSO_TOP) & (yy < LEG_TOP + 14) & ~arm_l & ~arm_r & ~old_head

    def m(b):
        return (b * 255).astype(np.uint8)

    # partes de atrás con un poco de sobra hacia adentro (quedan tapadas por el cuerpo)
    arm_l_ext = arm_l | ((xx < ARM_CUT_L + OVERLAP) & (yy > TORSO_TOP + 102) & (yy < LEG_TOP - 20))
    arm_r_ext = arm_r | ((xx > ARM_CUT_R - OVERLAP) & (yy > TORSO_TOP + 102) & (yy < LEG_TOP - 20))
    leg_l = (leg_zone & (xx < LEG_SPLIT)) | ((yy >= LEG_TOP - 60) & (yy < LEG_TOP) & (xx > 370) & (xx < LEG_SPLIT))
    leg_r = (leg_zone & (xx >= LEG_SPLIT)) | ((yy >= LEG_TOP - 60) & (yy < LEG_TOP) & (xx >= LEG_SPLIT) & (xx < 625))

    os.makedirs(OUT, exist_ok=True)
    rig = {"canvas": [W, H], "ground_y": None, "parts": {}}
    for name, mask, piv in [("arm_l", arm_l_ext, SHOULDER_L), ("arm_r", arm_r_ext, SHOULDER_R),
                            ("leg_l", leg_l, HIP_L), ("leg_r", leg_r, HIP_R), ("torso", torso, NECK)]:
        im, pos, pv = _part(rgba, m(mask), piv)
        im.save(os.path.join(OUT, f"{name}.png"), optimize=True)
        rig["parts"][name] = {"pos": pos, "pivot": pv, "size": im.size}

    # suelo: la fila más baja con zapatilla (sin la sombra gris de Canva, que el fondo ya sacó)
    ys = np.where(rgba[..., 3].max(axis=1) > 128)[0]
    rig["ground_y"] = int(ys.max())

    # cabeza: la del logo, sin el borde de sticker, recortada arriba del cuello de la campera
    base = _remove_sticker_border(Image.open(os.path.join(LOGO, "base.png")).convert("RGBA"))
    bw, bh = base.size
    ba = np.array(base)
    hair = np.where(ba[:, :, 3].max(axis=0) > 128)[0]
    scale = HEAD_WIDTH / (hair.max() - hair.min())
    # se queda con la cabeza y el cuello de la capucha (lo de abajo lo pone el cuerpo de Canva)
    cut_y = int(bh * 0.80)
    hy, hx = np.mgrid[0:bh, 0:bw]
    keep = (hy < cut_y) & (np.abs(hx - bw * 0.50) < bw * 0.38) | (hy < int(bh * 0.62))
    fade = np.clip((cut_y - hy) / 30.0, 0, 1)
    head_mask = (keep * fade * 255).astype(np.uint8)

    def head_layer(img, crop_alpha=True):
        a = np.array(img.convert("RGBA"))
        if crop_alpha:
            a[..., 3] = np.minimum(a[..., 3], head_mask)
        return Image.fromarray(a)

    neck_logo = (bw * 0.50, bh * 0.66)    # punto del logo (cuello) que va sobre el NECK del cuerpo
    sz = (int(bw * scale), int(bh * scale))
    hb = head_layer(base)
    ys2, xs2 = np.where(np.array(hb)[..., 3] > 8)
    box = (xs2.min(), ys2.min(), xs2.max() + 1, ys2.max() + 1)
    layers = {"head": hb}
    for f in sorted(os.listdir(LOGO)):
        if f.startswith("mouth_") or f == "blink.png":
            layers["head_" + f[:-4]] = head_layer(Image.open(os.path.join(LOGO, f)), crop_alpha=False)
    for name, im in layers.items():
        im.crop(box).resize((int((box[2] - box[0]) * scale), int((box[3] - box[1]) * scale)),
                            Image.LANCZOS).save(os.path.join(OUT, f"{name}.png"), optimize=True)
    piv = (int((neck_logo[0] - box[0]) * scale), int((neck_logo[1] - box[1]) * scale))
    rig["parts"]["head"] = {"pos": (NECK[0] - piv[0], NECK[1] - piv[1]), "pivot": piv,
                            "size": [int((box[2] - box[0]) * scale), int((box[3] - box[1]) * scale)]}
    rig["head_layers"] = sorted(k for k in layers if k != "head")
    with open(os.path.join(OUT, "rig.json"), "w") as f:
        json.dump(rig, f, indent=1)
    print("listo:", {k: v["size"] for k, v in rig["parts"].items()}, "suelo", rig["ground_y"])


if __name__ == "__main__":
    main()

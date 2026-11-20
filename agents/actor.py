"""Max actor: Max de cuerpo entero DENTRO de las escenas (camina, corre, salta, se cae, flota, señala...).

El cuerpo es el de assets/max_body (hecho en Canva con el logo de referencia, aprobado por Santi el 20/11) y la
cabeza es SIEMPRE la del logo (con sus bocas y parpadeo), así la cara de Max no cambia nunca. Cada parte
(cabeza, torso, brazos, piernas) gira sobre su articulación: animación de recortes, gratis y en CPU.

Se prende con MAX_ACTOR=1 (config.MAX_ACTOR). Las escenas de FLUX se generan SIN Max (solo el lugar) y Max se
dibuja encima, sincronizado con la voz. Si algo falla, el animador sigue con el Max narrador de la esquina.
"""
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import config

ASSETS = os.path.join(config.ROOT, "assets", "max_body")
ACTIONS = ("idle", "walk", "run", "jump", "fall", "float", "scared", "point", "wave", "celebrate")
ORDER = ("leg_l", "leg_r", "arm_l", "arm_r", "torso", "head")   # de atrás hacia adelante

_KEYWORDS = [
    ("float", r"float|weightless|zero.?g|drift|hover|levitat|space ?walk|no gravity|orbit"),
    ("fall", r"\bfall|falling|fell\b|plung|drop(?:s|ped)? |crash|slam|tumbl|collaps"),
    ("run", r"\brun\b|running|\bran\b|sprint|chase|escape|flee|rush|race"),
    ("jump", r"jump|leap|bounc|hop\b|launch"),
    ("scared", r"scar|terrif|panic|scream|afraid|fear|trembl|shak|horrif|danger|help!"),
    ("celebrate", r"made it|surviv|\bwin\b|victory|finally|amazing|incredible|yes!"),
    ("wave", r"\bhello\b|\bhi\b|welcome|goodbye|\bbye\b"),
    ("walk", r"\bwalk|arriv|enter|step|explor|head (?:to|into)|wander"),
    ("point", r"look at|see (?:this|that)|notice|here's|check|imagine|this is|that's"),
]


def norm_action(a):
    a = (a or "").strip().lower()
    return a if a in ACTIONS else ""


def infer_action(narration, idx=0):
    """Si el guionista no eligió acción, se deduce del texto de la escena."""
    import re

    text = (narration or "").lower()
    for action, rx in _KEYWORDS:
        if re.search(rx, text):
            return action
    return "walk" if idx == 0 else ("point", "idle", "point", "jump")[idx % 4]


def background_prompt(prompt):
    """La escena de FLUX va sin Max (él se agrega animado): se lo saca del prompt y se pide el lugar vacío."""
    import re

    p = re.sub(r"\bMax'?s?\b", "", prompt or "")
    p = re.sub(r"\s{2,}", " ", p).strip(" ,.;:")
    return (f"{p}. Wide shot of the place only, empty of people and characters, open clear ground in the lower "
            f"third of the image")


# ---------------- Rig ----------------
def _premul(img):
    """PIL RGBA -> numpy BGRA premultiplicado en float32 (para girar y mezclar rápido con OpenCV)."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0
    out = np.empty_like(a)
    out[..., :3] = a[..., 2::-1] * a[..., 3:4]
    out[..., 3] = a[..., 3]
    return out


def _over(dst, src, x0, y0):
    """Pega src (BGRA premultiplicado) sobre dst en (x0, y0), recortando a los bordes."""
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    s = src[ya - y0:yb - y0, xa - x0:xb - x0]
    d = dst[ya:yb, xa:xb]
    d *= 1 - s[..., 3:4]
    d += s


class Rig:
    """Partes del cuerpo ya escaladas al tamaño del video; cada una gira sobre su articulación."""

    def __init__(self, height_px):
        import cv2  # noqa: F401  (se usa en draw)

        with open(os.path.join(ASSETS, "rig.json")) as f:
            rig = json.load(f)
        parts = rig["parts"]
        top = min(p["pos"][1] for p in parts.values())
        self.ground = rig["ground_y"]
        self.s = s = height_px / (self.ground - top)
        xs = [p["pos"][0] for p in parts.values()] + [p["pos"][0] + p["size"][0] for p in parts.values()]
        self.cx = (min(xs) + max(xs)) / 2
        self.height = height_px
        self.W = int(height_px * 1.3)
        self.H = int(height_px * 1.4)
        self.foot = (self.W / 2, self.H - height_px * 0.08)   # dónde quedan los pies en el lienzo local
        gx = self.foot[0] - self.cx * s
        gy = self.foot[1] - self.ground * s
        self.parts = {}
        for name in ORDER:
            p = parts[name]
            img = Image.open(os.path.join(ASSETS, name + ".png")).convert("RGBA")
            img = img.resize((max(int(round(img.width * s)), 1), max(int(round(img.height * s)), 1)), Image.LANCZOS)
            local = (p["pivot"][0] * s, p["pivot"][1] * s)
            world = (gx + (p["pos"][0] + p["pivot"][0]) * s, gy + (p["pos"][1] + p["pivot"][1]) * s)
            self.parts[name] = {"img": img, "arr": _premul(img), "local": local, "world": world}
        self._heads = {}
        self._head_layers = {lay: Image.open(os.path.join(ASSETS, lay + ".png")).convert("RGBA")
                             .resize(self.parts["head"]["img"].size, Image.LANCZOS)
                             for lay in rig.get("head_layers", [])}

    def _head(self, mouth, blink):
        key = (mouth, blink)
        if key not in self._heads:
            im = self.parts["head"]["img"].copy()
            if mouth not in "XA" and f"head_mouth_{mouth}" in self._head_layers:
                im.alpha_composite(self._head_layers[f"head_mouth_{mouth}"])
            if blink and "head_blink" in self._head_layers:
                im.alpha_composite(self._head_layers["head_blink"])
            self._heads[key] = _premul(im)
        return self._heads[key]

    def draw(self, pose, mouth="X", blink=False):
        """Max en su lienzo local (BGRA premultiplicado float32). pose: ángulos (grados, + = antihorario)
        de cada parte, más la transformación de todo el cuerpo: face (espejo), sx/sy (estirar), body (giro)."""
        import cv2

        fx, fy = self.foot
        # transformación del cuerpo entero: espejo y estiramiento desde los pies, giro desde el centro del cuerpo
        B = np.array([[pose.get("face", 1) * pose.get("sx", 1.0), 0, 0], [0, pose.get("sy", 1.0), 0], [0, 0, 1]])
        B = _T(fx, fy) @ B @ _T(-fx, -fy)
        if pose.get("body"):
            cyb = fy - self.height * 0.5
            B = _T(fx, cyb) @ _R(pose["body"]) @ _T(-fx, -cyb) @ B
        out = np.zeros((self.H, self.W, 4), np.float32)
        for name in ORDER:
            pt = self.parts[name]
            src = self._head(mouth, blink) if name == "head" else pt["arr"]
            wx, wy = pt["world"]
            if name == "head":
                wy += pose.get("head_dy", 0)
            A = B @ _T(wx, wy) @ _R(pose.get(name, 0.0)) @ _T(-pt["local"][0], -pt["local"][1])
            h, w = src.shape[:2]
            corners = A @ np.array([[0, w, 0, w], [0, 0, h, h], [1, 1, 1, 1]], dtype=np.float64)
            x0, y0 = int(np.floor(corners[0].min())) - 1, int(np.floor(corners[1].min())) - 1
            x1, y1 = int(np.ceil(corners[0].max())) + 1, int(np.ceil(corners[1].max())) + 1
            if x1 <= 0 or y1 <= 0 or x0 >= self.W or y0 >= self.H:
                continue
            M = (_T(-x0, -y0) @ A)[:2]
            warped = cv2.warpAffine(src, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            _over(out, warped, x0, y0)
        return out


def _T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], dtype=np.float64)


def _R(deg):
    """Giro antihorario en pantalla (como PIL.rotate) de deg grados."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]], dtype=np.float64)


# ---------------- Movimientos ----------------
def _ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _walk_cycle(t, speed, amp_leg, amp_arm):
    ph = math.sin(t * speed)
    return {"leg_l": amp_leg * ph, "leg_r": -amp_leg * ph, "arm_l": -amp_arm * ph, "arm_r": amp_arm * ph,
            "bob": abs(math.cos(t * speed))}


def pose_at(action, t, dur, home, rnd_seed=0):
    """Estado de Max en el tiempo t de la escena.
    Devuelve dict con x (fracción del ancho), lift (fracción de la altura de Max), body (giro), sx, sy,
    face (1 mira a la derecha, -1 a la izquierda) y los ángulos de cada parte."""
    p = {"x": home, "lift": 0.0, "body": 0.0, "sx": 1.0, "sy": 1.0, "face": 1, "head": 0.0,
         "arm_l": -3.0, "arm_r": 3.0, "leg_l": 0.0, "leg_r": 0.0}
    breath = math.sin(t * 2.0)
    p["arm_l"] += 2.0 * breath
    p["arm_r"] -= 2.0 * breath
    p["sy"] = 1 + 0.008 * breath
    side = -1 if home > 0.5 else 1          # hacia dónde queda el centro de la pantalla

    if action == "walk":
        T = min(2.2, max(dur * 0.55, 0.8))
        if t < T:
            start = home - side * 0.75
            p["x"] = start + (home - start) * (t / T)
            c = _walk_cycle(t, 9.0, 22, 16)
            p.update({k: c[k] for k in ("leg_l", "leg_r", "arm_l", "arm_r")})
            p["lift"] = 0.025 * c["bob"]
            p["face"] = side
        else:
            q = t - T
            p["leg_l"] = p["leg_r"] = 0
            p["sy"] *= 1 - 0.04 * math.exp(-q * 9) * math.cos(q * 25)   # se frena con un rebote
    elif action == "run":
        a, b = (0.12, 0.88) if side > 0 else (0.88, 0.12)
        u = (t / max(dur, 0.1)) * 1.6
        k = int(u)
        f = u - k
        p["x"] = a + (b - a) * f if k % 2 == 0 else b + (a - b) * f      # va y vuelve
        p["face"] = (1 if b > a else -1) * (1 if k % 2 == 0 else -1)
        c = _walk_cycle(t, 15.0, 34, 40)
        p.update({k2: c[k2] for k2 in ("leg_l", "leg_r", "arm_l", "arm_r")})
        p["lift"] = 0.05 * c["bob"]
        p["body"] = -7 * p["face"]
    elif action == "jump":
        period = 1.5
        q = (t % period) / period
        if q < 0.12:                         # se agacha
            p["sx"], p["sy"] = 1.08, 0.9
            p["arm_l"], p["arm_r"] = -20, 20
        elif q < 0.62:                       # en el aire, brazos arriba
            r = (q - 0.12) / 0.5
            p["lift"] = 0.45 * math.sin(math.pi * r)
            p["sx"], p["sy"] = 0.94, 1.07
            p["arm_l"], p["arm_r"] = -150, 150
            p["leg_l"], p["leg_r"] = 10, -10
        elif q < 0.72:                       # aterriza aplastándose
            p["sx"], p["sy"] = 1.12, 0.86
            p["arm_l"], p["arm_r"] = -35, 35
    elif action == "fall":
        T = 0.9
        if t < T:
            r = t / T
            p["lift"] = 2.3 * (1 - r * r)
            p["body"] = 380 * r
            p["arm_l"], p["arm_r"] = -140 + 25 * math.sin(t * 30), 140 - 25 * math.sin(t * 30)
            p["leg_l"], p["leg_r"] = 20 * math.sin(t * 22), -20 * math.sin(t * 22)
        else:
            q = t - T
            sq = math.exp(-q * 7) * math.cos(q * 22)
            p["sx"], p["sy"] = 1 + 0.22 * sq, 1 - 0.22 * sq
            p["body"] = 0
            shake = math.sin(t * 60) * 1.5 * math.exp(-q * 1.5)
            p["head"] = shake
    elif action == "float":
        p["lift"] = 0.38 + 0.07 * math.sin(t * 1.4)
        p["x"] = home + 0.05 * math.sin(t * 0.7)
        p["body"] = 14 * math.sin(t * 0.9) + 6 * t
        p["arm_l"], p["arm_r"] = -55 + 15 * math.sin(t * 1.7), 55 + 15 * math.sin(t * 1.9 + 1)
        p["leg_l"], p["leg_r"] = -12 + 10 * math.sin(t * 1.3), 12 + 10 * math.sin(t * 1.5 + 2)
    elif action == "scared":
        tr = math.sin(t * 55)
        p["x"] = home + 0.004 * tr
        p["arm_l"], p["arm_r"] = -120 + 6 * tr, 120 - 6 * tr
        p["leg_l"], p["leg_r"] = -5, 5
        p["sx"], p["sy"] = 1.03, 0.97
        p["head"] = 2.0 * tr
    elif action == "point":
        e = _ease(t / 0.4)
        p["arm_r" if side > 0 else "arm_l"] = side * (3 + 122 * e)
        p["head"] = 4 * side * e
    elif action == "wave":
        e = _ease(t / 0.35)
        arm = "arm_r" if side > 0 else "arm_l"
        p[arm] = side * (3 + (150 + 22 * math.sin(t * 11)) * e)
    elif action == "celebrate":
        q = (t % 0.9) / 0.9
        p["lift"] = 0.18 * math.sin(math.pi * q) if q < 0.6 else 0
        p["arm_l"], p["arm_r"] = -155 + 10 * math.sin(t * 9), 155 - 10 * math.sin(t * 9)
    # ¿mira hacia donde camina? la cabeza del logo mira a la derecha: se espeja todo el cuerpo
    return p


# ---------------- En la escena ----------------
def layout(w, h):
    """(altura de Max, línea del suelo, x de reposo) según el formato."""
    if h > w:   # Short: abajo al centro, por encima de la zona que tapa el título de YouTube
        return int(h * 0.31), int(h * 0.80), 0.5
    return int(h * 0.62), int(h * 0.95), 0.18


class SceneActor:
    """Dibuja a Max encima de los cuadros de una escena (numpy BGR), sincronizado con la voz de esa escena."""

    def __init__(self, w, h, action, dur, cues, idx=0, rig=None):
        self.w, self.h = w, h
        mh, self.ground, home = layout(w, h)
        if w > h and idx % 2:           # en los largos va alternando de lado entre escenas
            home = 1 - home
        self.home = home
        self.rig = rig or get_rig(mh)
        self.action = norm_action(action) or "idle"
        self.dur = dur
        self.cues = cues or []
        self.rnd = random.Random(idx)
        self._ci = 0
        self.blinks = []
        t = self.rnd.uniform(0.8, 2.5)
        while t < dur:
            self.blinks.append(t)
            t += self.rnd.uniform(2.0, 4.5)
        self.talk = 0.0
        self._last_t = -1

    def _mouth(self, t):
        c = self.cues
        while self._ci < len(c) - 1 and c[self._ci][1] <= t:
            self._ci += 1
        if c and c[self._ci][0] <= t < c[self._ci][1]:
            return c[self._ci][2]
        return "X"

    def composite(self, frame, t):
        """Pega a Max (y su sombra en el piso) sobre el cuadro BGR uint8, en el lugar."""
        p = pose_at(self.action, t, self.dur, self.home)
        mouth = self._mouth(t)
        self.talk = self.talk * 0.85 + (0.15 if mouth not in "XA" else 0)
        blink = any(0 <= t - b < 0.12 for b in self.blinks)
        p["head"] += 2.5 * math.sin(t * 4.3) * self.talk + 1.0 * math.sin(t * 1.3)
        spr = self.rig.draw(p, mouth, blink)
        lift = p["lift"] * self.rig.height
        x = p["x"] * self.w
        _shadow(frame, x, self.ground, self.rig.height, lift)
        fx, fy = self.rig.foot
        x0, y0 = int(round(x - fx)), int(round(self.ground - lift - fy))
        H, W = frame.shape[:2]
        h, w = spr.shape[:2]
        xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
        if xa < xb and ya < yb:
            s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
            roi = frame[ya:yb, xa:xb].astype(np.float32)
            frame[ya:yb, xa:xb] = np.clip(s[..., :3] * 255 + roi * (1 - s[..., 3:4]), 0, 255).astype(np.uint8)
        return frame


_RIG = {}


def get_rig(height):
    if height not in _RIG:
        _RIG.clear()
        _RIG[height] = Rig(height)
    return _RIG[height]


_SHADOW = {}


def _shadow(frame, x, ground, height, lift):
    k = max(0.25, 1 - lift / (height * 1.6))
    sw, sh = int(height * 0.32 * k), int(height * 0.045 * k) + 2
    key = (sw, sh)
    if key not in _SHADOW:
        im = Image.new("L", (sw * 2 + 40, sh * 2 + 40), 0)
        ImageDraw.Draw(im).ellipse([20, 20, 20 + 2 * sw, 20 + 2 * sh], fill=255)
        if len(_SHADOW) > 200:
            _SHADOW.clear()
        _SHADOW[key] = np.asarray(im.filter(ImageFilter.GaussianBlur(8)), dtype=np.float32) / 255.0
    m = _SHADOW[key] * (0.45 * k)
    H, W = frame.shape[:2]
    x0, y0 = int(x - m.shape[1] / 2), int(ground - m.shape[0] / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + m.shape[1], W), min(y0 + m.shape[0], H)
    if xa >= xb or ya >= yb:
        return
    sub = m[ya - y0:yb - y0, xa - x0:xb - x0, None]
    frame[ya:yb, xa:xb] = (frame[ya:yb, xa:xb].astype(np.float32) * (1 - sub)).astype(np.uint8)

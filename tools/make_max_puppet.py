"""Dibuja a Max como "muñeco" por capas y las guarda en assets/max_puppet/. Se corre a mano cuando se
quiere cambiar el dibujo (necesita rsvg-convert); el sistema solo usa los PNG.

    python tools/make_max_puppet.py

Capas (todas del mismo tamaño, se apilan en este orden):
  body            torso con el mono naranja
  arms_<gesto>    brazos: point, explain, shrug, crossed (sin capa = brazos al costado)
  face            orejas, cara, sombras, barba
  eyes_<emo>[_blink]
  mouth_<forma>   bocas de Rhubarb A-H + idle_<emo> (boca en reposo según la emoción)
  hair
  brows_<emo>     (encima del flequillo, para que siempre se vean las expresiones)

Emociones: neutral, happy, excited, surprised, worried, scared, thinking.
Estilo: cartoon adulto dibujado a mano, contornos negros gruesos, sombreado plano (cel), como el Max
de las imágenes de FLUX (docs/max_referencia.png).
"""
import os
import subprocess

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "max_puppet")
VIEWBOX = "90 120 620 740"   # más ancho que el cuerpo para que entren los brazos
W, H = 620, 740

INK = "#1c1612"
SKIN = "#f7d0b4"
SKIN_SH = "#e8ad8f"
HAIR = "#7b5230"     # castaño como el Max del logo
HAIR_SH = "#5a3a1f"
HAIR_HI = "#9c6c42"
BROW = "#3b2412"
STUBBLE = "#c79f78"
ORANGE = "#f8921f"
ORANGE_SH = "#d26f12"
ORANGE_HI = "#ffae4d"
TEE = "#45484f"
MOUTH_IN = "#5b1717"
TONGUE = "#e4707c"
CHEEK = "#f08a8a"

EMOTIONS = ["neutral", "happy", "excited", "surprised", "worried", "scared", "thinking"]
GESTURES = ["point", "explain", "shrug", "crossed"]


def _svg(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" width="{W}" height="{H}">{inner}</svg>'


SLIM_FACE = 'transform="translate(400 0) scale(0.93 1) translate(-400 0)"'
SLIM_BODY = 'transform="translate(400 0) scale(0.84 1) translate(-400 0)"'


def _render(inner, name):
    subprocess.run(["rsvg-convert", "-o", os.path.join(OUT, name + ".png")], input=_svg(inner).encode(), check=True)


# ---------------- Cuerpo y brazos ----------------
BODY = f"""
<path d="M372 520 L372 608 C388 622 412 622 428 608 L428 520 Z" fill="{SKIN}" stroke="{INK}" stroke-width="9"/>
<path d="M372 560 L428 560 L428 608 C412 620 388 620 372 608 Z" fill="{SKIN_SH}"/>
<path d="M148 875 C146 705 214 622 330 598 L470 598 C586 622 654 705 652 875 Z" fill="{ORANGE}" stroke="{INK}" stroke-width="10" stroke-linejoin="round"/>
<path d="M560 640 C610 680 640 760 646 875 L560 875 C566 790 560 700 520 650 Z" fill="{ORANGE_SH}" opacity="0.9"/>
<path d="M240 650 C210 700 200 780 206 875 L180 875 C176 770 196 700 240 650 Z" fill="{ORANGE_HI}" opacity="0.6"/>
<path d="M350 598 L400 670 L450 598 Z" fill="{TEE}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
<path d="M294 592 C314 648 358 674 400 676 C360 646 344 616 344 598 Z" fill="{ORANGE_HI}" stroke="{INK}" stroke-width="9" stroke-linejoin="round"/>
<path d="M506 592 C486 648 442 674 400 676 C440 646 456 616 456 598 Z" fill="{ORANGE}" stroke="{INK}" stroke-width="9" stroke-linejoin="round"/>
<path d="M400 676 L400 875" stroke="{INK}" stroke-width="6"/>
<path d="M392 690 L408 690 L408 724 L392 724 Z" fill="#9aa0a6" stroke="{INK}" stroke-width="5"/>
<path d="M248 690 C262 720 266 760 262 800" fill="none" stroke="{ORANGE_SH}" stroke-width="7" stroke-linecap="round"/>
<path d="M552 690 C538 720 534 760 538 800" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round" opacity="0.5"/>
"""


def _limb(points, width=74):
    """Manga naranja con contorno (polilínea gruesa) desde el hombro."""
    d = "M" + " L".join(f"{x} {y}" for x, y in points)
    return (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{width + 18}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="{ORANGE}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def _cuff(x, y, r=24):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{ORANGE_SH}" stroke="{INK}" stroke-width="8"/>'


def _fist_point_up(x, y):
    return f"""
<rect x="{x - 10}" y="{y - 78}" width="22" height="62" rx="11" fill="{SKIN}" stroke="{INK}" stroke-width="8"/>
<ellipse cx="{x}" cy="{y}" rx="30" ry="27" fill="{SKIN}" stroke="{INK}" stroke-width="8"/>
<path d="M{x - 22} {y - 4} Q{x - 6} {y + 4} {x + 6} {y - 4}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
<path d="M{x - 24} {y + 10} Q{x - 6} {y + 18} {x + 10} {y + 10}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>"""


def _palm_up(x, y, flip=1):
    """Mano abierta con la palma hacia arriba (flip=-1 la espeja)."""
    f = flip
    return f"""
<path d="M{x - 42 * f} {y + 6} Q{x - 40 * f} {y - 22} {x} {y - 20} Q{x + 44 * f} {y - 22} {x + 46 * f} {y - 2}
 Q{x + 30 * f} {y + 26} {x} {y + 26} Q{x - 30 * f} {y + 28} {x - 42 * f} {y + 6} Z" fill="{SKIN}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
<path d="M{x - 40 * f} {y + 2} Q{x - 54 * f} {y - 18} {x - 46 * f} {y - 34}" fill="none" stroke="{INK}" stroke-width="8" stroke-linecap="round"/>
<path d="M{x - 20 * f} {y} Q{x} {y + 8} {x + 24 * f} {y}" fill="none" stroke="{SKIN_SH}" stroke-width="6" stroke-linecap="round"/>"""


def arms(gesture):
    if gesture == "point":     # brazo derecho (del lado del espectador) levantado señalando arriba
        return _limb([(560, 650), (664, 600), (650, 470)]) + _cuff(650, 462) + _fist_point_up(648, 432)
    if gesture == "explain":   # mano abierta a la altura del pecho, como explicando
        return _limb([(560, 650), (640, 740), (590, 640)]) + _cuff(588, 634) + _palm_up(582, 606)
    if gesture == "shrug":     # se encoge de hombros: las dos manos arriba
        return (_limb([(240, 650), (172, 720), (196, 610)]) + _cuff(196, 602) + _palm_up(200, 576, -1)
                + _limb([(560, 650), (628, 720), (604, 610)]) + _cuff(604, 602) + _palm_up(600, 576))
    if gesture == "crossed":   # brazos cruzados sobre el pecho
        return (_limb([(236, 660), (300, 760), (540, 744)], 70)
                + f'<ellipse cx="548" cy="736" rx="24" ry="20" fill="{SKIN}" stroke="{INK}" stroke-width="8"/>'
                + _limb([(564, 660), (500, 770), (262, 752)], 70)
                + f'<ellipse cx="252" cy="746" rx="24" ry="20" fill="{SKIN}" stroke="{INK}" stroke-width="8"/>')
    raise ValueError(gesture)


# ---------------- Cabeza ----------------
FACE = f"""
<g stroke="{INK}" stroke-width="8" stroke-linejoin="round">
  <ellipse cx="270" cy="440" rx="27" ry="36" fill="{SKIN}"/>
  <ellipse cx="530" cy="440" rx="27" ry="36" fill="{SKIN}"/>
</g>
<path d="M262 428 Q272 418 280 436" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
<path d="M538 428 Q528 418 520 436" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
<path d="M280 372 C276 266 524 266 520 372 L522 456 C522 548 468 595 400 595 C332 595 278 548 278 456 Z" fill="{SKIN}"/>
<path d="M488 300 C516 334 522 384 522 456 C522 530 482 584 420 594 C470 556 498 508 500 456 C502 392 500 342 488 300 Z" fill="{SKIN_SH}" opacity="0.8"/>
<path d="M290 488 C300 556 346 592 400 592 C454 592 500 556 510 488 C496 520 470 528 446 524 C420 520 380 520 354 524 C330 528 304 520 290 488 Z" fill="{STUBBLE}" opacity="0.45"/>
<g fill="#8f6a46" opacity="0.8">{''.join(f'<circle cx="{x}" cy="{y}" r="2.3"/>' for x, y in [
    (316, 532), (338, 554), (362, 570), (438, 570), (462, 554), (484, 532), (400, 582), (350, 580), (450, 580),
    (326, 560), (474, 560), (380, 578), (420, 578), (372, 538), (428, 538), (300, 512), (500, 512)])}</g>
<path d="M280 372 C276 266 524 266 520 372 L522 456 C522 548 468 595 400 595 C332 595 278 548 278 456 Z" fill="none" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
<ellipse cx="312" cy="482" rx="26" ry="14" fill="{CHEEK}" opacity="0.45"/>
<ellipse cx="488" cy="482" rx="26" ry="14" fill="{CHEEK}" opacity="0.45"/>
<g fill="#c98a6a">{''.join(f'<circle cx="{x}" cy="{y}" r="2.2"/>' for x, y in [(300, 476), (314, 470), (322, 486), (478, 486), (486, 470), (500, 476)])}</g>
<path d="M398 446 Q391 462 392 474" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
<ellipse cx="405" cy="484" rx="19" ry="16" fill="#f4b3a2" stroke="{INK}" stroke-width="6"/>
<ellipse cx="410" cy="480" rx="9" ry="6" fill="#f08a84" opacity="0.7"/>
<ellipse cx="400" cy="476" rx="4" ry="3" fill="#fff" opacity="0.7"/>
"""

# Pelo como el Max de FLUX (docs/max_referencia.png): melena despeinada y ancha, mechones finos en punta que
# salen para los costados y flequillo desprolijo cayendo sobre la frente hasta las cejas
HAIR_PATH = ("M286 446 Q270 420 262 396 Q274 398 278 388 Q252 372 246 344 Q262 350 270 346 Q252 320 256 292 "
             "Q270 306 280 302 Q272 270 290 248 Q300 266 312 266 Q316 238 340 222 Q346 242 356 244 "
             "Q368 216 396 206 Q400 226 410 230 Q430 208 458 214 Q454 232 462 238 Q488 232 508 248 "
             "Q496 260 502 268 Q530 274 544 298 Q526 302 524 310 Q546 330 550 360 Q532 352 524 356 "
             "Q540 384 536 408 Q524 396 518 398 Q520 424 512 446 Q506 416 498 392 Q492 404 484 410 "
             "Q480 384 468 368 Q456 380 444 386 Q440 364 428 352 Q414 366 396 376 Q398 356 392 344 "
             "Q376 358 356 366 Q360 350 356 340 Q340 352 326 368 Q326 352 318 340 Q306 376 304 404 "
             "Q296 424 286 446 Z")
HAIR = f"""<g transform="translate(400 372) scale(1.13 1.1) translate(-400 -372)">
<path d="{HAIR_PATH}" fill="{HAIR}"/>
<g fill="{HAIR_SH}">
  <path d="M508 248 Q496 260 502 268 Q530 274 544 298 Q526 302 524 310 Q546 330 550 360 Q532 352 524 356
           Q540 384 536 408 Q524 396 518 398 Q520 424 512 446 Q506 416 498 392 Q508 360 500 330 Q506 296 492 270 Z"/>
  <path d="M428 352 Q414 366 396 376 Q402 352 428 352 Z"/>
  <path d="M356 340 Q340 352 326 368 Q330 346 356 340 Z"/>
  <path d="M286 446 Q270 420 262 396 Q274 398 278 388 Q290 410 296 430 Z"/>
</g>
<path d="{HAIR_PATH}" fill="none" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
<g fill="none" stroke="{HAIR_HI}" stroke-width="6" stroke-linecap="round">
  <path d="M306 286 Q324 262 350 252"/><path d="M386 244 Q406 228 428 226"/><path d="M276 340 Q284 320 300 310"/>
</g>
<g fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round">
  <path d="M322 320 Q344 296 376 286"/><path d="M398 306 Q420 284 450 276"/><path d="M456 330 Q478 310 500 304"/>
  <path d="M290 372 Q298 346 316 334"/><path d="M370 340 Q380 320 398 312"/><path d="M506 354 Q516 334 524 322"/>
  <path d="M440 352 Q452 336 470 330"/>
</g></g>"""


def _eye_whites(cx, cy, rx, ry):
    rx, ry = rx * 0.8, ry * 0.8
    return f'<ellipse cx="{cx}" cy="{cy + 6}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#fff" stroke="{INK}" stroke-width="6"/>'


def _pupils(dx=4, dy=4, r=12, spark=True):
    out = ""
    for cx in (350, 450):
        x = cx + (dx if cx == 350 else -dx)
        out += f'<circle cx="{x}" cy="{426 + dy}" r="{r}" fill="{INK}"/>'
        if spark:
            out += f'<circle cx="{x + 4}" cy="{426 + dy - 5}" r="{max(2, r // 3)}" fill="#fff"/>'
    return out


SWEAT = (f'<path d="M524 334 Q538 360 524 372 Q510 360 524 334 Z" fill="#a8dcff" stroke="{INK}" stroke-width="5"/>'
         '<path d="M521 356 Q520 364 525 366" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>')


def eyes(emo, closed):
    if closed:
        arc = "M314 426 Q350 448 386 426 M414 426 Q450 448 486 426"
        if emo in ("happy", "excited"):
            arc = "M314 432 Q350 404 386 432 M414 432 Q450 404 486 432"  # ojos ^^
        extra = SWEAT if emo == "scared" else ""
        return f'<path d="{arc}" fill="none" stroke="{INK}" stroke-width="8" stroke-linecap="round"/>' + extra
    if emo == "happy":  # ojos un poco entrecerrados por la sonrisa
        return (_eye_whites(350, 422, 37, 38) + _eye_whites(450, 422, 37, 38) + _pupils(dy=0, r=12)
                + f'<path d="M328 472 Q350 464 372 472 M428 472 Q450 464 472 472" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>')
    if emo == "excited":
        return _eye_whites(350, 418, 38, 46) + _eye_whites(450, 418, 38, 46) + _pupils(dy=0, r=13) + \
            '<circle cx="342" cy="428" r="3" fill="#fff"/><circle cx="442" cy="428" r="3" fill="#fff"/>'
    if emo == "surprised":
        return _eye_whites(350, 416, 38, 48) + _eye_whites(450, 416, 38, 48) + _pupils(dx=0, dy=0, r=9)
    if emo == "scared":
        return _eye_whites(350, 416, 38, 48) + _eye_whites(450, 416, 38, 48) + _pupils(dx=0, dy=2, r=7, spark=False) + SWEAT
    if emo == "worried":
        return _eye_whites(350, 422, 36, 40) + _eye_whites(450, 422, 36, 40) + _pupils(dx=2, dy=6, r=11)
    if emo == "thinking":  # mira hacia arriba y al costado
        return _eye_whites(350, 420, 37, 43) + _eye_whites(450, 420, 37, 43) + \
            '<circle cx="362" cy="414" r="11" fill="#1c1612"/><circle cx="460" cy="414" r="11" fill="#1c1612"/>' + \
            '<circle cx="366" cy="409" r="4" fill="#fff"/><circle cx="464" cy="409" r="4" fill="#fff"/>'
    return _eye_whites(350, 420, 37, 43) + _eye_whites(450, 420, 37, 43) + _pupils()


BROWS = {
    "neutral": ("M312 368 C330 354 360 352 384 360", "M416 360 C440 352 470 354 488 368"),
    "happy": ("M312 360 C330 344 360 342 384 350", "M416 350 C440 342 470 344 488 360"),
    "excited": ("M312 358 C330 340 362 338 386 348", "M414 348 C438 338 470 340 488 358"),
    "surprised": ("M314 356 C330 336 364 334 386 346", "M414 346 C436 334 470 336 486 356"),
    "worried": ("M312 368 C334 366 360 356 382 340", "M418 340 C440 356 466 366 488 368"),
    "scared": ("M312 364 C334 362 360 352 382 336", "M418 336 C440 352 466 362 488 364"),
    "thinking": ("M312 372 C334 368 362 368 384 370", "M416 350 C440 336 470 338 488 354"),
}


def brows(emo):
    a, b = BROWS[emo]
    return f'<path d="{a} M{b[1:]}" fill="none" stroke="{BROW}" stroke-width="16" stroke-linecap="round"/>'


def mouth(shape):
    s = f'stroke="{INK}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"'
    teeth_top = '<path d="M372 508 Q400 503 428 508 L426 517 Q400 513 374 517 Z" fill="#fff"/>'
    m = {
        "X": f'<path d="M370 512 Q400 532 430 510" fill="none" {s}/>',
        "A": f'<path d="M370 516 Q400 522 430 516" fill="none" {s}/>'
             f'<path d="M386 528 Q400 532 414 528" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>',
        "B": f'<path d="M370 508 Q400 503 430 508 Q426 528 400 530 Q374 528 370 508 Z" fill="{MOUTH_IN}" {s}/>'
             '<path d="M374 510 Q400 506 426 510 L424 520 Q400 517 376 520 Z" fill="#fff"/>'
             '<path d="M378 523 Q400 520 422 523 L420 527 Q400 528 380 527 Z" fill="#fff"/>',
        "C": f'<path d="M366 504 Q400 497 434 504 Q430 542 400 545 Q370 542 366 504 Z" fill="{MOUTH_IN}" {s}/>'
             f'{teeth_top}<path d="M380 536 Q400 524 420 536 Q410 543 400 543 Q390 543 380 536 Z" fill="{TONGUE}"/>',
        "D": f'<path d="M362 500 Q400 490 438 500 Q436 560 400 565 Q364 560 362 500 Z" fill="{MOUTH_IN}" {s}/>'
             '<path d="M370 503 Q400 496 430 503 L428 514 Q400 509 372 514 Z" fill="#fff"/>'
             f'<path d="M376 552 Q400 532 424 552 Q414 562 400 562 Q386 562 376 552 Z" fill="{TONGUE}"/>',
        "E": f'<ellipse cx="400" cy="522" rx="24" ry="22" fill="{MOUTH_IN}" {s}/>'
             f'<path d="M386 536 Q400 527 414 536 Q406 542 400 542 Q394 542 386 536 Z" fill="{TONGUE}"/>',
        "F": f'<ellipse cx="400" cy="520" rx="15" ry="15" fill="{MOUTH_IN}" {s}/>'
             f'<path d="M382 508 Q400 500 418 508" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>',
        "G": f'<path d="M370 508 Q400 503 430 508 Q426 526 400 528 Q374 526 370 508 Z" fill="{MOUTH_IN}" {s}/>'
             '<path d="M376 509 Q400 505 424 509 L422 521 Q400 518 378 521 Z" fill="#fff"/>'
             f'<path d="M374 524 Q400 516 426 524" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
        "H": f'<path d="M366 504 Q400 497 434 504 Q430 542 400 545 Q370 542 366 504 Z" fill="{MOUTH_IN}" {s}/>'
             f'{teeth_top}<path d="M382 520 Q400 510 418 520 Q414 540 400 541 Q386 540 382 520 Z" fill="{TONGUE}"/>',
        # bocas en reposo según la emoción
        "idle_neutral": f'<path d="M370 512 Q400 532 430 510" fill="none" {s}/>',
        "idle_happy": f'<path d="M364 504 Q400 512 436 502 Q430 544 400 546 Q370 544 364 504 Z" fill="{MOUTH_IN}" {s}/>'
                      '<path d="M370 506 Q400 512 430 504 L428 516 Q400 521 372 517 Z" fill="#fff"/>'
                      f'<path d="M382 536 Q400 526 418 536 Q410 543 400 543 Q390 543 382 536 Z" fill="{TONGUE}"/>',
        "idle_excited": f'<path d="M358 500 Q400 508 442 498 Q438 560 400 564 Q362 560 358 500 Z" fill="{MOUTH_IN}" {s}/>'
                        '<path d="M366 502 Q400 509 434 500 L432 514 Q400 521 368 516 Z" fill="#fff"/>'
                        f'<path d="M378 550 Q400 532 422 550 Q412 560 400 560 Q388 560 378 550 Z" fill="{TONGUE}"/>',
        "idle_surprised": f'<ellipse cx="400" cy="524" rx="17" ry="22" fill="{MOUTH_IN}" {s}/>',
        "idle_worried": f'<path d="M368 522 Q384 510 400 518 Q416 526 432 512" fill="none" {s}/>',
        "idle_scared": f'<path d="M364 506 Q400 500 436 506 Q436 534 400 536 Q364 534 364 506 Z" fill="#fff" {s}/>'
                       f'<path d="M366 520 L434 520 M384 506 L384 534 M400 504 L400 536 M416 506 L416 534" stroke="{INK}" stroke-width="4"/>',
        "idle_thinking": f'<path d="M380 522 Q402 518 426 508" fill="none" {s}/>',
    }
    return m[shape]


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    _render(f"<g {SLIM_BODY}>{BODY}</g>", "body")
    for g in GESTURES:
        _render(f"<g {SLIM_BODY}>{arms(g)}</g>", f"arms_{g}")
    _render(f"<g {SLIM_FACE}>{FACE}</g>", "face")
    _render(HAIR, "hair")
    for e in EMOTIONS:
        _render(eyes(e, False), f"eyes_{e}")
        _render(eyes(e, True), f"eyes_{e}_blink")
        _render(brows(e), f"brows_{e}")
        _render(mouth(f"idle_{e}"), f"mouth_idle_{e}")
    for s in "ABCDEFGHX":
        _render(mouth(s), f"mouth_{s}")
    print(f"listo: {OUT}")


if __name__ == "__main__":
    main()

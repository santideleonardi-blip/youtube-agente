"""Dibuja a Max como "muñeco" por partes (cuerpo + cabeza con 9 bocas x ojos abiertos/cerrados) y
lo guarda en assets/max_puppet/. Se corre UNA vez a mano (necesita rsvg-convert); el sistema usa los PNG.

    python tools/make_max_puppet.py

Bocas = las de Rhubarb Lip Sync (A-H, X): A cerrada (M/B/P), B dientes (K/S/T/EE), C abierta (EH/AE),
D muy abierta (AA), E redondeada (AO/ER), F labios en trompa (OO/W), G dientes sobre labio (F/V),
H lengua arriba (L), X reposo.
"""
import os
import subprocess

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "max_puppet")
VIEWBOX = "150 120 500 740"   # recorte del lienzo de 800x860
SCALE = 1.0                  # 500x740 px

INK = "#1b1b1b"
SKIN = "#f6cfb2"
HAIR = "#5a3417"
BEARD = "#c49a6c"
ORANGE = "#ff8a1f"
MOUTH_IN = "#5b1717"
TONGUE = "#e4707c"

BODY = f"""
<g stroke="{INK}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round">
  <path d="M150 870 C150 700 220 615 330 595 L470 595 C580 615 650 700 650 870 Z" fill="{ORANGE}"/>
  <path d="M372 520 L372 606 C388 620 412 620 428 606 L428 520 Z" fill="#efbf9f"/>
  <path d="M350 595 L400 668 L450 595 Z" fill="#4a4d55"/>
  <path d="M296 590 C316 645 358 670 400 672 C360 644 344 614 344 595 Z" fill="#ff9d3d"/>
  <path d="M504 590 C484 645 442 670 400 672 C440 644 456 614 456 595 Z" fill="#ff9d3d"/>
  <path d="M400 672 L400 870" fill="none" stroke-width="6"/>
  <rect x="390" y="686" width="20" height="34" rx="4" fill="#9aa0a6" stroke-width="5"/>
  <path d="M235 740 C250 720 262 700 268 680" fill="none" stroke-width="6" opacity="0.6"/>
  <path d="M565 740 C550 720 538 700 532 680" fill="none" stroke-width="6" opacity="0.6"/>
</g>"""


def _eyes(closed):
    if closed:
        return f"""
<g fill="none" stroke="{INK}" stroke-width="8" stroke-linecap="round">
  <path d="M314 424 Q350 446 386 424"/><path d="M414 424 Q450 446 486 424"/>
</g>"""
    return f"""
<g stroke="{INK}" stroke-width="8">
  <ellipse cx="350" cy="420" rx="37" ry="43" fill="#fff"/>
  <ellipse cx="450" cy="420" rx="37" ry="43" fill="#fff"/>
</g>
<circle cx="354" cy="424" r="13" fill="{INK}"/><circle cx="446" cy="424" r="13" fill="{INK}"/>
<circle cx="358" cy="419" r="4" fill="#fff"/><circle cx="450" cy="419" r="4" fill="#fff"/>"""


def _mouth(shape):
    s = f'stroke="{INK}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"'
    teeth_top = '<path d="M372 508 Q400 503 428 508 L426 517 Q400 513 374 517 Z" fill="#fff"/>'
    if shape == "X":
        return f'<path d="M370 512 Q400 532 430 510" fill="none" {s}/>'
    if shape == "A":
        return f'<path d="M370 516 Q400 522 430 516" fill="none" {s}/><path d="M384 528 Q400 532 416 528" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
    if shape == "B":
        return (f'<path d="M370 508 Q400 503 430 508 Q426 528 400 530 Q374 528 370 508 Z" fill="{MOUTH_IN}" {s}/>'
                '<path d="M374 510 Q400 506 426 510 L424 520 Q400 517 376 520 Z" fill="#fff"/>'
                '<path d="M378 523 Q400 520 422 523 L420 527 Q400 528 380 527 Z" fill="#fff"/>')
    if shape == "C":
        return (f'<path d="M366 504 Q400 497 434 504 Q430 542 400 545 Q370 542 366 504 Z" fill="{MOUTH_IN}" {s}/>'
                f'{teeth_top}<path d="M380 536 Q400 524 420 536 Q410 543 400 543 Q390 543 380 536 Z" fill="{TONGUE}"/>')
    if shape == "D":
        return (f'<path d="M362 500 Q400 490 438 500 Q436 560 400 565 Q364 560 362 500 Z" fill="{MOUTH_IN}" {s}/>'
                '<path d="M370 503 Q400 496 430 503 L428 514 Q400 509 372 514 Z" fill="#fff"/>'
                f'<path d="M376 552 Q400 532 424 552 Q414 562 400 562 Q386 562 376 552 Z" fill="{TONGUE}"/>')
    if shape == "E":
        return (f'<ellipse cx="400" cy="522" rx="24" ry="22" fill="{MOUTH_IN}" {s}/>'
                f'<path d="M386 536 Q400 527 414 536 Q406 542 400 542 Q394 542 386 536 Z" fill="{TONGUE}"/>')
    if shape == "F":
        return (f'<ellipse cx="400" cy="520" rx="15" ry="15" fill="{MOUTH_IN}" {s}/>'
                f'<path d="M382 508 Q400 500 418 508" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    if shape == "G":
        return (f'<path d="M370 508 Q400 503 430 508 Q426 526 400 528 Q374 526 370 508 Z" fill="{MOUTH_IN}" {s}/>'
                '<path d="M376 509 Q400 505 424 509 L422 521 Q400 518 378 521 Z" fill="#fff"/>'
                f'<path d="M374 524 Q400 516 426 524" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>')
    if shape == "H":
        return (f'<path d="M366 504 Q400 497 434 504 Q430 542 400 545 Q370 542 366 504 Z" fill="{MOUTH_IN}" {s}/>'
                f'{teeth_top}<path d="M382 520 Q400 510 418 520 Q414 540 400 541 Q386 540 382 520 Z" fill="{TONGUE}"/>')
    raise ValueError(shape)


HAIR_PATH = ("M266 405 L246 360 L218 352 L242 320 L206 292 L248 280 L226 236 L274 240 L270 192 L314 212 "
             "L330 160 L364 196 L392 140 L414 190 L452 150 L460 200 L506 176 L500 222 L548 214 L530 256 "
             "L578 262 L548 294 L582 322 L540 330 L556 372 L534 400 L524 356 L506 330 L494 352 L470 318 "
             "L452 340 L436 306 L414 330 L398 296 L378 328 L360 300 L340 330 L322 304 L306 336 L292 316 "
             "L284 352 Z")


def head(shape, closed):
    stubble = "".join(f'<circle cx="{x}" cy="{y}" r="3"/>' for x, y in
                      [(318, 530), (338, 552), (362, 568), (438, 568), (462, 552), (482, 530), (400, 578),
                       (300, 500), (500, 500), (350, 578), (450, 578), (325, 560), (475, 560)])
    return f"""
<g stroke="{INK}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round">
  <ellipse cx="270" cy="430" rx="28" ry="38" fill="{SKIN}"/>
  <ellipse cx="530" cy="430" rx="28" ry="38" fill="{SKIN}"/>
  <path d="M278 370 C278 270 522 270 522 370 L522 455 C522 545 468 592 400 592 C332 592 278 545 278 455 Z" fill="{SKIN}"/>
</g>
<path d="M286 462 C294 545 342 588 400 588 C458 588 506 545 514 462 C506 498 482 506 462 500 C440 494 360 494 338 500 C318 506 294 498 286 462 Z" fill="{BEARD}" opacity="0.85"/>
<g fill="#8a6440">{stubble}</g>
<path d="M284 470 C292 548 342 590 400 590 C458 590 508 548 516 470" fill="none" stroke="{INK}" stroke-width="9" stroke-linecap="round"/>
<ellipse cx="316" cy="472" rx="24" ry="14" fill="#f08c8c" opacity="0.55"/>
<ellipse cx="484" cy="472" rx="24" ry="14" fill="#f08c8c" opacity="0.55"/>
{_eyes(closed)}
<path d="M400 440 C392 468 386 478 396 486 C402 490 412 487 414 481" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>
{_mouth(shape)}
<path d="M312 372 C330 358 360 356 384 364" fill="none" stroke="#4a2a12" stroke-width="15" stroke-linecap="round"/>
<path d="M416 364 C440 356 470 358 488 372" fill="none" stroke="#4a2a12" stroke-width="15" stroke-linecap="round"/>
<path d="{HAIR_PATH}" fill="{HAIR}" stroke="{INK}" stroke-width="9" stroke-linejoin="round"/>
<g fill="none" stroke="#7a4a24" stroke-width="6" stroke-linecap="round">
  <path d="M300 262 L330 236"/><path d="M398 205 L410 180"/><path d="M470 240 L495 222"/><path d="M500 290 L530 280"/>
</g>"""


def _svg(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" width="{int(500 * SCALE)}" height="{int(740 * SCALE)}">{inner}</svg>'


def _render(svg, png):
    subprocess.run(["rsvg-convert", "-o", png], input=svg.encode(), check=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    _render(_svg(BODY), os.path.join(OUT, "body.png"))
    for shape in "ABCDEFGHX":
        for closed in (False, True):
            _render(_svg(head(shape, closed)), os.path.join(OUT, f"head_{shape}{'_blink' if closed else ''}.png"))
    _render(_svg(BODY + head("X", False)), os.path.join(OUT, "preview.png"))
    print(f"listo: {OUT}")


if __name__ == "__main__":
    main()

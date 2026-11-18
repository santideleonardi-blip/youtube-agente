# Max del logo como muñeco

`assets/max_logo/` sale del logo del canal (`docs/max_logo.png`), elegido por Santi el 18/11:

1. Se amplía x4 con Real-ESRGAN anime (`esrgan.py`, necesita torch y `RealESRGAN_x4plus_anime_6B.pth`).
2. Se recorta a Max con rembg (`isnet-anime`) y se limpian restos del fondo -> `max_cut.png`.
3. `build_layers.py` arma `base.png` (Max tal cual), `mouth_B..H.png` (boca borrada + boca dibujada encima)
   y `blink.png` (ojos cerrados).

Se usa con `MAX_PUPPET_STYLE=logo` (por defecto). `MAX_PUPPET_STYLE=dibujo` vuelve al muñeco vectorial con
expresiones y brazos (`assets/max_puppet`).

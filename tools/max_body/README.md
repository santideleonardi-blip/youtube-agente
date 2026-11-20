# Max de cuerpo entero (Max actor)

`assets/max_body/` es el Max que se anima DENTRO de las escenas (`agents/actor.py`, se prende con `MAX_ACTOR=1`).

- Cuerpo: `assets/max_body/source/body_canva.png`, hecho en Canva el 20/11 con el logo como referencia
  (campera naranja, jean azul, zapatillas blancas). Aprobado por Santi.
- Cabeza: SIEMPRE la del logo (`assets/max_logo/`, con sus bocas y parpadeo): la cara de Max no cambia.
- `build_parts.py` corta el cuerpo en partes (torso, brazos, piernas), pone la cabeza del logo y escribe
  `rig.json` con la articulación de cada parte. Si se cambia el dibujo del cuerpo, volver a correrlo
  (los puntos están en píxeles de la imagen de 1024x1536).

Acciones de Max por escena (`max_action`, las elige el guionista): idle, walk, run, jump, fall, float, scared,
point, wave, celebrate. Si no viene, se deduce del texto de la escena.

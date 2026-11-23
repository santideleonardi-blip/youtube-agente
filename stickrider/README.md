# StickRider

Segundo canal del sistema: Shorts en inglés de **historias reales**, con personajes de palito en un mundo 3D pintado.
Todo se dibuja con código (three.js dentro de Remotion): sin IA de video, gratis, y los personajes nunca cambian.

## Cómo sale un video (`py/main.py`)
1. **Guionista** (`py/writer.py`): Gemini con búsqueda de Google elige una historia real que no se haya usado, junta
   los datos con fuentes y escribe el guion con la fórmula medida en 20 shorts virales del género (gancho-paradoja,
   escalada con diálogos, pregunta, "You see," + analogía cotidiana, remate irónico). Cada línea trae su "beat"
   visual con el vocabulario que el motor sabe dibujar.
2. **Voz** (`py/voice.py`): Kokoro `am_michael`, ~3,6 palabras/s.
3. **Director** (`py/director.py`): convierte líneas + tiempos de la voz en `spec.json`: escenas continuas
   (la cámara se mueve en ráfagas al comienzo de cada línea), fundidos al cambiar de lugar, elenco, multitudes,
   props, efectos, títulos con números y el destello después del gancho.
4. **Sonido** (`py/sound.py`): música original sintetizada según el clima + whooshes; -14 LUFS.
5. **Render** (`py/render.py`): cada toma en su propio proceso de Remotion (si no, la memoria gráfica se agota),
   con 4 cuadros de calentamiento descartados; fundidos con ffmpeg.
6. **Publicador** (`py/publish.py`): sube programado a las 15:00 ET y guarda estadísticas en `data/state.json`;
   el guionista recibe qué historias/ganchos retuvieron más y cuáles no.

## Motor (`src/engine/`)
`spec.ts` (formato), `sets.ts` (street, square, road, shrine, field, sea, desert, snow, room, city + props),
`world.ts` (cielo, luz day/golden/night, personajes y efectos), `Short.tsx` (post: tinta → desenfoque → bloom → tone
map → grade). Basado en el motor MIT de Mr omi / Crea con LuisPa (`claude-animated-shorts`, `shorts-animados-claude`).

## Secrets de GitHub
`SR_YT_CLIENT_ID`, `SR_YT_CLIENT_SECRET`, `SR_YT_REFRESH_TOKEN` (canal StickRider, proyecto de Google Cloud propio,
con `python auth_setup.py client_secret.json`) y `SR_GEMINI_API_KEY` (si falta, usa `GEMINI_API_KEY`).
Sin las credenciales de YouTube, el workflow genera el video y no sube nada.

## Probar a mano
Actions → "StickRider — producir y subir un Short" → Run workflow (con dry_run = prueba, se descarga en Artifacts).
Con un guion propio: `SR_SCRIPT=stickrider/examples/tulip-mania.script.json DRY_RUN=1 python stickrider/py/main.py`.

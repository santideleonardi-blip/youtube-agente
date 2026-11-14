# youtube-agente 🤖🎬

Canal de YouTube automatizado con 5 agentes de IA. Nicho: **What If...?** (ciencia e historia, en inglés).
Corre gratis en GitHub Actions, 2 veces por día.

| Agente | Archivo | Qué hace |
|---|---|---|
| 5. Analista | `agents/analyst.py` | Lee la retención de cada video, detecta dónde se va la gente, deja notas al guionista y decide si el próximo es Short o largo |
| 1. Investigador | `agents/trends.py` | Busca lo que más vistas por hora saca en el nicho y elige un tema nuevo |
| 2. Guionista | `agents/scriptwriter.py` | Escribe el guion escena por escena siguiendo las notas del analista |
| 3. Animador | `agents/animator.py` | Voz (Edge TTS) + ilustraciones (Pollinations) + zoom/paneo + subtítulos animados (FFmpeg) |
| 4. Publicador | `agents/publisher.py` | Título llamativo, descripción, tags, miniatura y subida a YouTube |

La memoria de los agentes (historial, notas, estadísticas) se guarda en `data/state.json`.

## Puesta en marcha

1. **Secrets** (repo → Settings → Secrets and variables → Actions → *New repository secret*):
   - `GEMINI_API_KEY` — de aistudio.google.com
   - `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` — los da `auth_setup.py`
2. **Autorizar el canal** (una sola vez, en tu compu):
   ```
   pip install google-auth-oauthlib
   python auth_setup.py client_secret.json
   ```
3. **Prueba**: pestaña *Actions* → "Producir y subir video" → *Run workflow* con `dry_run` activado.
   El video queda para descargar en *Artifacts* (no se sube).
4. Cuando te guste, ya corre solo 2 veces por día.

## Modos de publicación
Variable de repo `PUBLISH_MODE` (Settings → Secrets and variables → Actions → *Variables*):
- `private` (por defecto): sube en privado, vos lo publicás.
- `scheduled`: se publica solo 6 horas después de subirse (tiempo para revisarlo).
- `public`: publica directo.

Ajustes generales (nicho, voz, estilo visual, duración) en `config.py`.

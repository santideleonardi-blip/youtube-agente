"""Cliente de Gemini (plan gratuito) con reintentos y salida JSON."""
import json
import os
import re
import time

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Falta la variable GEMINI_API_KEY")
        # timeout de 2 minutos por consulta (en ms) para que nunca se quede colgado
        _client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=120_000))
    return _client


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return json.loads(text[start:])


_models = None


def _version(name):
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def _available_models():
    """Detecta los modelos Flash disponibles para esta clave (los nombres cambian seguido)."""
    global _models
    if _models is not None:
        return _models
    found = []
    try:
        for m in _get_client().models.list():
            name = m.name.replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            if "flash" not in name or any(x in name for x in ("image", "tts", "live", "audio", "embed", "thinking-exp")):
                continue
            found.append(name)
    except Exception as e:  # noqa: BLE001
        print(f"[llm] no pude listar modelos: {e}")
    # Primero los Flash más nuevos (no "lite"), después los "lite" como respaldo; estables antes que preview.
    found.sort(key=lambda n: ("lite" in n, "preview" in n or "exp" in n, -_version(n)))
    preferred = [config.GEMINI_MODEL] if os.getenv("GEMINI_MODEL") else []
    _models = list(dict.fromkeys(preferred + found[:6] + config.GEMINI_FALLBACK_MODELS))
    print(f"[llm] modelos a usar: {_models[:4]}")
    return _models


def ask_json(prompt: str, system: str = "", temperature: float = 0.9):
    """Pide una respuesta JSON. Prueba el mejor modelo disponible y luego los de respaldo."""
    from google.genai import types

    models = _available_models()
    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                resp = _get_client().models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system or None,
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )
                print(f"[llm] respuesta de {model}")
                return _extract_json(resp.text)
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                print(f"[llm] {model} intento {attempt + 1} falló: {msg[:200]}")
                if "404" in msg or "not found" in msg.lower():
                    break  # el modelo no existe: pasar al siguiente
                if "503" in msg or "UNAVAILABLE" in msg or "disconnected" in msg.lower() or "timed out" in msg.lower():
                    if attempt >= 1:
                        break  # modelo saturado: probar el siguiente
                    time.sleep(8)
                    continue
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if attempt >= 1:
                        break  # cupo agotado en este modelo: probar el siguiente
                    time.sleep(20)
                else:
                    time.sleep(5)
    raise RuntimeError(f"Gemini no respondió: {last_err}")

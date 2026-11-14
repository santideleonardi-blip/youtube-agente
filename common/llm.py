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

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Falta la variable GEMINI_API_KEY")
        _client = genai.Client(api_key=key)
    return _client


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return json.loads(text[start:])


def ask_json(prompt: str, system: str = "", temperature: float = 0.9):
    """Pide una respuesta JSON. Prueba el modelo principal y luego los de respaldo."""
    from google.genai import types

    models = [config.GEMINI_MODEL] + [m for m in config.GEMINI_FALLBACK_MODELS if m != config.GEMINI_MODEL]
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
                return _extract_json(resp.text)
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                print(f"[llm] {model} intento {attempt + 1} falló: {msg[:200]}")
                if "404" in msg or "not found" in msg.lower():
                    break  # el modelo no existe: pasar al siguiente
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    time.sleep(30 * (attempt + 1))
                else:
                    time.sleep(5)
    raise RuntimeError(f"Gemini no respondió: {last_err}")

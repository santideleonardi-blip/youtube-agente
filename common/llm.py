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
_exhausted = set()
quota_hit = set()  # modelos que agotaron el cupo diario gratis en esta corrida (lo usa el estratega)


def _with_timeout(fn, secs):
    """Corre fn con un límite duro de tiempo (si la API se cuelga, no bloquea todo el sistema)."""
    import threading

    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as e:  # noqa: BLE001
            box["error"] = e

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(secs)
    if th.is_alive():
        raise TimeoutError(f"timed out after {secs}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


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
        listed = _with_timeout(lambda: list(_get_client().models.list()), 40)
        for m in listed:
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


OVERLOAD_ROUNDS = 3          # si TODOS los modelos están saturados (503/504), se espera y se vuelve a probar
OVERLOAD_WAITS = (60, 150)   # segundos de espera entre vueltas


def all_exhausted():
    """¿Se agotó el cupo de TODOS los modelos? (que se agote uno y responda otro es normal en el plan gratis)"""
    try:
        models = _available_models()
    except Exception:  # noqa: BLE001
        return bool(quota_hit)
    return bool(models) and all(m in _exhausted for m in models)


def ask_json(prompt: str, system: str = "", temperature: float = 0.9):
    """Pide una respuesta JSON. Prueba el mejor modelo disponible y luego los de respaldo. Si fallan todos
    solo por saturación de Google (pasajera), espera y da otra vuelta antes de rendirse."""
    last_err = None
    for rnd in range(OVERLOAD_ROUNDS):
        ok, result, overloaded = _ask_round(prompt, system, temperature)
        if ok:
            return result
        last_err = result
        if not overloaded or rnd == OVERLOAD_ROUNDS - 1:
            break
        wait = OVERLOAD_WAITS[min(rnd, len(OVERLOAD_WAITS) - 1)]
        print(f"[llm] todos los modelos saturados: espero {wait} s y vuelvo a probar (vuelta {rnd + 2}/{OVERLOAD_ROUNDS})")
        time.sleep(wait)
    raise RuntimeError(f"Gemini no respondió: {last_err}")


def _is_overload(msg):
    return any(x in msg for x in ("503", "UNAVAILABLE", "504", "DEADLINE_EXCEEDED")) or \
        "disconnected" in msg.lower() or "timed out" in msg.lower()


def _ask_round(prompt, system, temperature):
    """Una vuelta por todos los modelos. Devuelve (ok, resultado_o_error, todo_fue_saturación)."""
    from google.genai import types

    models = [m for m in _available_models() if m not in _exhausted]
    last_err = None
    overloaded = bool(models)
    for model in models:
        for attempt in range(3):
            try:
                cfg = types.GenerateContentConfig(
                    system_instruction=system or None,
                    temperature=temperature,
                    response_mime_type="application/json",
                )
                resp = _with_timeout(lambda: _get_client().models.generate_content(
                    model=model, contents=prompt, config=cfg), 150)
                print(f"[llm] respuesta de {model}")
                return True, _extract_json(resp.text), False
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                if not _is_overload(msg):
                    overloaded = False
                print(f"[llm] {model} intento {attempt + 1} falló: {msg[:200]}")
                if "404" in msg or "not found" in msg.lower() or "no longer available" in msg.lower():
                    _exhausted.add(model)  # el modelo no existe: no volver a probarlo en esta corrida
                    break
                if _is_overload(msg):
                    if attempt >= 1:
                        break  # modelo saturado: probar el siguiente
                    time.sleep(8)
                    continue
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if "quota" in msg.lower():
                        _exhausted.add(model)
                        quota_hit.add(model)  # cupo diario agotado: no volver a probarlo en esta corrida
                        break
                    if attempt >= 1:
                        break  # cupo agotado en este modelo: probar el siguiente
                    time.sleep(20)
                else:
                    time.sleep(5)
    return False, last_err, overloaded

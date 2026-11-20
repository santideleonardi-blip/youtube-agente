"""Animación 2.5D (efecto parallax) a partir de una ilustración fija.

1. Estima la profundidad de la imagen con Depth Anything V2 (modelo local, gratis, CPU).
2. Mueve una "cámara virtual": lo que está cerca se desplaza más que el fondo,
   así la imagen parece tener volumen en vez de ser una foto con zoom.
Si el modelo no está disponible, usa una profundidad aproximada (no se corta nada).
"""
import os
import subprocess

import cv2
import numpy as np

import config

_session = None


def _load_model():
    global _session
    if _session is None:
        path = os.path.join(config.MODELS_DIR, "depth_anything_v2_small.onnx")
        if not os.path.exists(path):
            _session = False
            print("[parallax] sin modelo de profundidad, uso profundidad aproximada")
        else:
            import onnxruntime as ort

            _session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    return _session


def _heuristic_depth(img):
    """Aproximación: el centro y lo de abajo suele estar más cerca; bordes y arriba, más lejos."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vert = yy / h
    center = 1 - np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h * 0.55) / (h / 2)) ** 2) / 1.5
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255
    return 0.45 * vert + 0.35 * np.clip(center, 0, 1) + 0.2 * sat


def depth_map(img):
    """Devuelve profundidad normalizada 0..1 (1 = más cerca), suavizada."""
    sess = _load_model()
    h, w = img.shape[:2]
    if sess:
        try:
            x = cv2.resize(img, (518, 518), interpolation=cv2.INTER_CUBIC)[..., ::-1].astype(np.float32) / 255
            x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
            x = x.transpose(2, 0, 1)[None].astype(np.float32)
            out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
            d = np.squeeze(out).astype(np.float32)
            d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
        except Exception as e:  # noqa: BLE001
            print(f"[parallax] falló el modelo de profundidad: {e}")
            d = _heuristic_depth(img)
    else:
        d = _heuristic_depth(img)
    d = (d - d.min()) / max(d.max() - d.min(), 1e-6)
    k = max(3, (min(w, h) // 40) | 1)
    return cv2.GaussianBlur(d, (k, k), 0)


# Movimientos de cámara: (zoom inicio, zoom fin, paneo x inicio, fin, paneo y inicio, fin, fuerza parallax)
MOVES = [
    (1.00, 1.12, 0.00, 0.00, 0.00, 0.00, 0.05),    # avance hacia el centro (dolly in)
    (1.10, 1.03, -0.04, 0.04, 0.00, 0.00, 0.06),   # travelling a la derecha
    (1.10, 1.03, 0.04, -0.04, 0.00, 0.00, 0.06),   # travelling a la izquierda
    (1.12, 1.00, 0.00, 0.00, 0.00, 0.00, 0.05),    # retroceso (dolly out)
    (1.18, 1.26, 0.00, 0.02, 0.05, -0.03, 0.04),   # primer plano subiendo
    (1.08, 1.12, 0.00, 0.00, -0.04, 0.04, 0.06),   # tilt hacia abajo
    (1.25, 1.35, -0.06, -0.03, 0.02, 0.00, 0.04),  # detalle izquierda
    (1.25, 1.35, 0.06, 0.03, 0.02, 0.00, 0.04),    # detalle derecha
]


def _ease(t):
    return t * t * (3 - 2 * t)


def render_shot(img, depth, out_path, w, h, dur, move_idx, fps=config.FPS, overlay=None, t0=0.0):
    """Renderiza una toma con cámara virtual 2.5D y la guarda como mp4 (sin audio).
    overlay(frame, t) dibuja algo encima de cada cuadro (Max actor); t = t0 + tiempo dentro de la toma."""
    z0, z1, px0, px1, py0, py1, k = MOVES[move_idx % len(MOVES)]
    sh, sw = img.shape[:2]
    # coordenadas de salida centradas, en escala de la imagen fuente (la fuente cubre la salida)
    base = min(sw / w, sh / h)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs = (xs - w / 2) * base
    ys = (ys - h / 2) * base
    cx, cy = sw / 2, sh / 2
    n = max(int(round(dur * fps)), 1)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
         "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", out_path],
        stdin=subprocess.PIPE,
    )
    move_dir = np.array([px1 - px0, py1 - py0], dtype=np.float32)
    if not move_dir.any():
        move_dir = np.array([0.0, -0.3], dtype=np.float32)  # dolly: leve subida para que se note el volumen
    move_dir /= max(np.linalg.norm(move_dir), 1e-6)
    try:
        for i in range(n):
            t = _ease(i / max(n - 1, 1))
            zoom = z0 + (z1 - z0) * t
            panx = (px0 + (px1 - px0) * t) * sw
            pany = (py0 + (py1 - py0) * t) * sh
            mx = cx + panx + xs / zoom
            my = cy + pany + ys / zoom
            d = cv2.remap(depth, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            # parallax: lo cercano se mueve más que el fondo, y crece más al avanzar
            shift = (t - 0.5) * k * sw * (d - 0.5)
            dz = 1 + (zoom - 1) * 0.6 * (d - 0.5)
            fx = cx + panx + (xs / zoom) / dz - shift * move_dir[0]
            fy = cy + pany + (ys / zoom) / dz - shift * move_dir[1]
            frame = cv2.remap(img, fx, fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            if overlay is not None:
                overlay(frame, t0 + i / fps)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg falló renderizando la toma parallax")

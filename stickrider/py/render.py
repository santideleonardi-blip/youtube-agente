"""StickRider — Render: cada toma en su propio proceso de Remotion (memoria gráfica limpia), con 4 cuadros de
arranque que se descartan (el post necesita "calentar"), y fundidos armados con ffmpeg. Si la máquina se reinicia,
las tomas ya hechas no se vuelven a renderizar."""
import json
import os
import subprocess

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAD = 8        # el motor corre la línea de tiempo 8 cuadros (props.lead) para poder arrancar antes del cuadro 0
WARM = 4        # cuadros de calentamiento que se tiran
CHUNK = 240     # tomas largas se parten en tramos de este largo
GL = os.getenv("REMOTION_GL", "swangle")
CHROME = os.getenv("CHROME_BIN", "/usr/bin/google-chrome")
CONC = os.getenv("REMOTION_CONCURRENCY", "")


def _run(cmd, **kw):
    print("[render] $", " ".join(cmd[:6]), "...", flush=True)
    subprocess.run(cmd, check=True, **kw)


def bundle(wd):
    out = os.path.join(wd, "bundle")
    if not os.path.exists(os.path.join(out, "index.html")):
        _run(["npx", "remotion", "bundle", "src/index.ts", "--out-dir", out], cwd=ENGINE)
    return out


def _frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", path], capture_output=True, text=True)
    return int(r.stdout.strip().strip(",") or 0)


def render(spec, wd, scale=1.0):
    os.makedirs(wd, exist_ok=True)
    srv = bundle(wd)
    shots = spec["shots"]
    segs = []  # (path, frames, xfade_in)
    for i, sh in enumerate(shots):
        xin = sh.get("xfade", 0) if i > 0 else 0
        xout = shots[i + 1].get("xfade", 0) if i + 1 < len(shots) else 0
        s0, s1 = sh["a"] - xin // 2, sh["b"] + (xout - xout // 2)
        props = os.path.join(wd, f"props_{i:02d}.json")
        with open(props, "w") as f:
            json.dump({"spec": spec, "onlyShot": i, "lead": LEAD}, f)
        start = s0
        first = True
        while start < s1:
            end = min(s1, start + CHUNK)
            out = os.path.join(wd, f"shot_{i:02d}_{start:05d}.mp4")
            if not (os.path.exists(out) and _frames(out) == end - start + WARM):
                tmp = out + ".tmp.mp4"
                cmd = ["npx", "remotion", "render", srv, "Short", tmp, f"--props={props}",
                       f"--frames={start - WARM + LEAD}-{end - 1 + LEAD}", f"--scale={scale}", "--codec=h264", "--crf=16",
                       f"--browser-executable={CHROME}", f"--gl={GL}", "--log=error"]
                if CONC:
                    cmd.append(f"--concurrency={CONC}")
                _run(cmd, cwd=ENGINE)
                os.replace(tmp, out)
            segs.append((out, end - start, xin if first else 0))
            first = False
            start = end
    return segs


def assemble(segs, audio, out, fps=30):
    """Pega los tramos (descarta los 4 de calentamiento), hace los fundidos y agrega el sonido a -14 LUFS."""
    ins, fl = [], []
    for k, (p, n, _) in enumerate(segs):
        ins += ["-i", p]
        fl.append(f"[{k}:v]trim=start_frame={WARM}:end_frame={WARM + n},setpts=PTS-STARTPTS,fps={fps},format=yuv420p,settb=AVTB[s{k}]")
    cur, cur_len = "s0", segs[0][1]
    for k in range(1, len(segs)):
        x = segs[k][2]
        nxt = f"j{k}"
        if x > 0:
            fl.append(f"[{cur}][s{k}]xfade=transition=fade:duration={x / fps:.4f}:offset={(cur_len - x) / fps:.4f}[{nxt}]")
            cur_len += segs[k][1] - x
        else:
            fl.append(f"[{cur}][s{k}]concat=n=2:v=1:a=0[{nxt}]")
            cur_len += segs[k][1]
        cur = nxt
    na = len(segs)
    fl.append(f"[{na}:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", *ins, "-i", audio, "-filter_complex", ";".join(fl), "-map", f"[{cur}]",
           "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]
    _run(cmd)
    n = _frames(out)
    print(f"[render] video final: {out} ({n} cuadros = {n / fps:.1f}s)")
    return n


def blank_frames(path):
    """Cuadros planos (sin imagen) = algo falló en el render."""
    p = subprocess.run(f'ffmpeg -loglevel error -i "{path}" -vf scale=9:16 -f rawvideo -pix_fmt gray -', shell=True, capture_output=True)
    d, sz = p.stdout, 144
    out = []
    for i in range(len(d) // sz):
        px = d[i * sz:(i + 1) * sz]
        if max(px) - min(px) < 6 and min(px) < 235:  # plano y no blanco (el destello blanco es a propósito)
            out.append(i)
    return out

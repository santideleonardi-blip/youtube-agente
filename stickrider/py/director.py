"""StickRider — Director: convierte el guion (líneas + beats) y los tiempos de la voz en el spec.json del motor.

Gramática de cámara medida en la referencia: casi sin cortes. Las líneas seguidas en el mismo lugar son UNA toma
continua y la cámara se mueve en ráfagas cortas (ease-out) al comienzo de cada línea; cambiar de lugar = fundido.
"""
import math

FPS = 30
LANE = {"street": 2.5, "city": 4.2, "sea": 3.4, "room": 5.0}     # media anchura útil de sets angostos
Y0 = {"sea": 1.2}                                                 # altura del piso (cubierta del barco)
CROWD_N = {"few": 8, "many": 40, "huge": 150}
CROWD_LOOKS = {"city": ["suit", "woman", "worker"], "sea": ["sailor"], "snow": ["soldier", "townsman"]}
ENTER = 40  # cuadros que tarda un personaje en entrar caminando
DOF = {"close": 14, "medium": 8, "low": 6, "wide": 0, "crowd": 4, "aerial": 0}


def _camera(shot, F, y0, side, set_name):
    """Encuadre de cada tipo de toma alrededor del punto F (x, z) del sujeto."""
    x, z = F
    s = 0.55 * side
    presets = {
        "wide": ((x + s, y0 + 2.3, z + 9.5), (x, y0 + 1.3, z - 1.5), 40),
        "medium": ((x + s, y0 + 1.75, z + 4.4), (x, y0 + 1.45, z), 36),
        "close": ((x + 0.3 * s, y0 + 1.8, z + 2.5), (x, y0 + 1.65, z), 34),
        "low": ((x + s, y0 + 0.55, z + 4.0), (x, y0 + 1.8, z), 38),
        "crowd": ((x + s, y0 + 4.0, z + 13.0), (x, y0 + 1.0, z - 5.0), 42),
        "aerial": ((x + s, y0 + 15.0, z + 19.0), (x, y0 + 0.5, z - 6.0), 40),
    }
    pos, look, fov = presets.get(shot, presets["medium"])
    pos = list(pos)
    if set_name in LANE:  # que la cámara no atraviese las casas / paredes
        lim = LANE[set_name] + (0.3 if set_name != "room" else 0.5)
        pos[0] = max(-lim, min(lim, pos[0]))
    if set_name == "room":
        pos[2] = min(pos[2], 5.5)
        pos[1] = min(pos[1], 3.9)
    return {"pos": [round(v, 3) for v in pos], "look": [round(v, 3) for v in look], "fov": fov, "cInf": DOF.get(shot, 0)}


def build(script, timings, total_s):
    lines = script["lines"]
    cast = {c["id"]: c for c in script["cast"]}
    starts = [round(t["start"] * FPS) for t in timings]
    total = math.ceil((total_s + 0.35) * FPS)
    # ---- escenas: líneas seguidas con el mismo set y la misma luz ----
    scenes = []
    for i, ln in enumerate(lines):
        if scenes and scenes[-1]["set"] == ln["set"] and scenes[-1]["light"] == ln["light"]:
            scenes[-1]["lines"].append(i)
        else:
            scenes.append({"set": ln["set"], "light": ln["light"], "lines": [i]})
    shots, captions = [], []
    for si, sc in enumerate(scenes):
        a = 0 if si == 0 else starts[sc["lines"][0]]
        b = total if si == len(scenes) - 1 else starts[scenes[si + 1]["lines"][0]]
        st, y0 = sc["set"], Y0.get(sc["set"], 0.0)
        rel = lambda i: max(0, starts[i] - a)  # noqa: E731
        # ---- elenco de la escena, en fila, en el orden en que aparece ----
        order = []
        for i in sc["lines"]:
            for o in lines[i]["on_screen"]:
                if o["id"] not in order:
                    order.append(o["id"])
        n = len(order)
        gap = 1.25 if st in LANE else 1.45
        pos = {cid: (round((k - (n - 1) / 2) * gap, 2), -0.35 * (k % 2)) for k, cid in enumerate(order)}
        has_stage = any("stage" in lines[i]["props"] for i in sc["lines"]) and st in ("square", "field", "street")
        actors = []
        for cid in order:
            c = cast[cid]
            first = next(i for i in sc["lines"] if any(o["id"] == cid for o in lines[i]["on_screen"]))
            acts, exprs = [], []
            act0 = expr0 = None
            for i in sc["lines"]:
                o = next((o for o in lines[i]["on_screen"] if o["id"] == cid), None)
                if not o:
                    continue
                f = max(0, rel(i) - 2)  # la reacción cae 0-3 cuadros antes de la palabra
                if act0 is None:
                    act0, expr0 = o["act"], o["expr"]
                else:
                    acts.append([f, o["act"]]); exprs.append([f, o["expr"]])
            x, z = pos[cid]
            a_spec = {"look": c["look"], "v": c["v"], "x": x, "z": z, "act": act0, "expr": expr0, "actAt": acts, "exprAt": exprs}
            # mira hacia los otros personajes cuando comparte línea con alguien (diálogo), no a cámara
            if n > 1 and x != 0 and any(len(lines[i]["on_screen"]) > 1 and any(o["id"] == cid for o in lines[i]["on_screen"]) for i in sc["lines"]):
                a_spec["facing"] = 1 if x < 0 else -1
            # entra caminando desde el costado en su primera línea
            o_first = next(o for o in lines[first]["on_screen"] if o["id"] == cid)
            if o_first.get("enter"):
                f0 = max(0, rel(first) - 2)
                side = -1 if x < 0 else 1
                lim = LANE.get(st, 9.0) - 0.3
                a_spec["to"] = [x, z]
                a_spec["x"] = round(max(-lim, min(lim, x + side * 4.0)), 2)
                a_spec["walk"] = [f0, f0 + ENTER]
                after = a_spec["act"] if first == sc["lines"][0] else next((v for f, v in acts if f == f0), "stand")
                if after == "walk":
                    after = "stand"
                if first == sc["lines"][0]:
                    a_spec["act"] = "walk"
                    a_spec["actAt"] = [[f0 + ENTER, after]] + acts
                else:
                    a_spec["actAt"] = [[f, v] for f, v in acts if f != f0] + [[f0, "walk"], [f0 + ENTER, after]]
                    a_spec["actAt"].sort(key=lambda e: e[0])
                a_spec["from"] = f0
            if y0:
                a_spec["y0"] = y0
            if has_stage and c["look"] == "musician":
                a_spec.update(y0=1.1, z=-8.6)
            if first != sc["lines"][0]:
                a_spec["from"] = max(0, rel(first) - 2)
            actors.append(a_spec)
        # ---- multitud ----
        crowd = []
        cl = [i for i in sc["lines"] if lines[i]["crowd"]["size"] != "none"]
        if cl:
            size = max((CROWD_N[lines[i]["crowd"]["size"]] for i in cl))
            if st in LANE:
                size = min(size, 40 if st != "room" else 12)
                hx = LANE[st]
                xr, zr = [-hx, hx], ([-7, 7] if st == "sea" else [-18, -2.2] if st != "room" else [-5, -1.6])
            else:
                # densidad pareja: el área crece con la cantidad de gente
                hw = {8: 5, 40: 8.5, 150: 15}.get(size, 10)
                xr, zr = [-hw, hw], [-2.2 - 1.3 * hw, -2.2]
            c0 = lines[cl[0]]["crowd"]
            cr = {"n": size, "x": xr, "z": zr, "act": c0["act"], "expr": c0["expr"] if c0["expr"] != "neutral" else None, "seed": si + 1,
                  "looks": next((lines[i]["crowd"].get("looks") for i in cl if lines[i]["crowd"].get("looks")), None)
                  or CROWD_LOOKS.get(st, ["townsman", "townswoman"])}
            if cr["expr"] is None:
                cr.pop("expr")
            if y0:
                cr["y0"] = y0
            if cl[0] != sc["lines"][0]:
                g0 = rel(cl[0])
                cr["grow"] = [g0, g0 + 45]
            crowd.append(cr)
        # ---- props ----
        props, seen = [], set()
        for i in sc["lines"]:
            for p in lines[i]["props"]:
                if p in seen:
                    continue
                seen.add(p)
                if p == "stage":
                    if has_stage:
                        props.append({"kind": "stage", "x": 0, "z": -8})
                    continue
                k = len(props)
                side = 1 if k % 2 == 0 else -1
                px = side * min((n * 1.45) / 2 + 1.6, LANE.get(st, 9) - 0.8)
                props.append({"kind": p, "x": round(px, 2), "z": -1.8, **({"s": 1} if True else {})})
        # ---- cámara y efectos por línea ----
        keys, fx = [], []
        for j, i in enumerate(sc["lines"]):
            ln = lines[i]
            if ln["focus"] in pos:
                F = pos[ln["focus"]]
            elif ln["focus"] == "crowd" and cl:
                F = (0.0, -5.0)
            elif order:
                F = (0.0, 0.0)
            else:
                F = (0.0, -4.0)
            if has_stage and ln["focus"] in cast and cast[ln["focus"]]["look"] == "musician":
                F = (pos[ln["focus"]][0], -8.6)
            yF = 1.1 if (has_stage and ln["focus"] in cast and cast[ln["focus"]]["look"] == "musician") else y0
            k = _camera(ln["shot"], F, yF, 1 if (i % 2 == 0) else -1, st)
            k["f"] = 0 if j == 0 else rel(i)
            if j > 0:
                k["dur"] = 14
            keys.append(k)
            if ln["fx"] != "none":
                fx.append({"kind": ln["fx"], "x": F[0], "y": yF + 1.95, "z": F[1] + 0.3, "at": rel(i) + 6, "size": 1.0})
            if ln["caption"]:
                end = starts[i + 1] if i + 1 < len(starts) else total
                captions.append({"a": max(starts[i] + 3, 27), "b": end, "text": ln["caption"]})  # después de la portada del comienzo
        shot = {"a": a, "b": b, "set": st, "light": sc["light"], "cam": keys, "actors": actors, "crowd": crowd, "props": props, "fx": fx}
        if any(a_["look"] == "musician" and (a_["act"] == "play" or any(x[1] == "play" for x in a_["actAt"])) for a_ in actors):
            shot["notes"] = True
        if si > 0:
            prev = scenes[si - 1]
            shot["xfade"] = 8 if prev["set"] != st else 6
        shots.append(shot)
    flash = [starts[1]] if len(starts) > 1 and len(scenes) > 0 else []
    spec = {"title": script["title"], "fps": FPS, "total": total, "shots": shots, "captions": captions, "flash": flash}
    print(f"[director] {len(shots)} tomas, {total} cuadros ({total / FPS:.1f}s), {len(captions)} títulos")
    return spec

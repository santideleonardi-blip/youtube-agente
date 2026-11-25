// StickRider scene spec: what a short is made of. The writer agent (Gemini) fills this JSON; the engine turns it
// into frames. Everything is a pure function of the frame number, so any frame renders the same on any machine.
import type { Expr } from "./toon";

export type V3 = [number, number, number];
export type Light = "day" | "golden" | "night";
/** each set lives in its own corner of the world (sets.ts); x/z of actors are LOCAL to the set's origin */
export type SetName = "street" | "square" | "road" | "shrine" | "field" | "council" | "sea" | "desert" | "snow" | "room" | "city";
export type Act = "stand" | "walk" | "dance" | "wave" | "cheer" | "sit" | "fall" | "play";
export type Look = "townsman" | "townswoman" | "noble" | "musician" | "priest" | "soldier" | "kid"
  | "king" | "queen" | "worker" | "suit" | "woman" | "scientist" | "sailor" | "pilot" | "farmer" | "doctor";

export type ActorSpec = {
  look: Look; v?: number;               // look preset + variant (colours / face)
  x: number; z: number;                 // feet position (metres, set-local)
  y0?: number;                          // standing height (e.g. 1.1 on the stage)
  to?: [number, number];                // walk target (reached at the shot's end, or at walk[1])
  walk?: [number, number];              // [start, end] frames of the walk to `to` (default: from → shot end)
  act?: Act; expr?: Expr;
  exprAt?: [number, Expr][];            // [frame within shot, expression] changes
  actAt?: [number, Act][];              // [frame within shot, action] changes
  from?: number;                        // appears at this frame within the shot
  facing?: -1 | 0 | 1;                  // head/eyes turn
  side?: boolean;                       // side view (walking across the frame)
  mirror?: boolean;                     // side view facing screen-left
  shoes?: string;                       // override boot colour (e.g. red shoes)
  scale?: number;
};
export type CrowdSpec = {
  n: number; x: [number, number]; z: [number, number]; act: Act; expr?: Expr;
  grow?: [number, number];              // members appear one by one between these shot frames
  looks?: Look[]; seed?: number; y0?: number;
};
export type PropName = "stage" | "drum" | "wagon" | "table" | "statue" | "shoes" | "barrel" | "crate" | "chest" | "car" | "tent" | "rock";
export type PropSpec = { kind: PropName; x: number; z: number; yaw?: number; s?: number };
export type FxSpec = { kind: "burst" | "stars" | "puff" | "splash"; x: number; y: number; z: number; at: number; size?: number };
export type CamKey = { f: number; pos: V3; look: V3; fov?: number; dur?: number; cInf?: number };
export type ShotSpec = {
  a: number; b: number; set: SetName; light: Light;
  cam: CamKey[];                        // f relative to the shot start; one key = automatic slow push-in
  dof?: { cInf: number; focus?: V3 };   // lens blur at infinity (px @1080p), focus point (set-local)
  actors?: ActorSpec[]; crowd?: CrowdSpec[]; props?: PropSpec[];
  notes?: boolean;                      // floating music notes over the musicians
  fx?: FxSpec[];                        // cartoon bursts / stars / puffs / splashes
  caption?: string;                     // a key number, small, top of frame
  xfade?: number;                       // crossfade frames from the previous shot
};
export type Caption = { a: number; b: number; text: string };
export type Spec = { title: string; fps: number; total: number; shots: ShotSpec[]; flash?: number[]; captions?: Caption[] };

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
const lerp3 = (a: V3, b: V3, t: number): V3 => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

/** camera at frame f (relative to the shot). Measured reference grammar: the camera HOLDS most of the time (a slow
 *  push-in, ~1.5 % of the distance per second) and MOVES in short ease-out bursts: each key starts a move toward its
 *  pose at its frame, fastest on the first frame, settled after `dur` frames (default 14). */
const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 3;
export const camAt = (s: ShotSpec, f: number) => {
  const ks = s.cam;
  let pos: V3 = ks[0].pos, look: V3 = ks[0].look, fov = ks[0].fov ?? 36, since = f - ks[0].f, cInf = ks[0].cInf ?? s.dof?.cInf ?? 0;
  for (let i = 1; i < ks.length && f >= ks[i].f; i++) {
    const k = ks[i], u = easeOut((f - k.f) / (k.dur ?? 14));
    pos = lerp3(pos, k.pos, u); look = lerp3(look, k.look, u); fov = fov + ((k.fov ?? fov) - fov) * u;
    cInf = cInf + ((k.cInf ?? cInf) - cInf) * u;
    since = f - k.f;
  }
  const creep = Math.min(0.25, 0.015 * (since / 30));
  pos = lerp3(pos, look, creep);
  const w = 0.025 * Math.sin(f / 23 + s.a);
  return { pos: [pos[0] + w, pos[1] + 0.6 * w, pos[2]] as V3, look, fov, cInf };
};

export const shotAt = (spec: Spec, f: number) => spec.shots.find((s) => f >= s.a && f < s.b) ?? spec.shots[spec.shots.length - 1];
export const layersAt = (spec: Spec, f: number): { i: number; alpha: number }[] => {
  for (let i = 1; i < spec.shots.length; i++) {
    const s = spec.shots[i], x = s.xfade ?? 0;
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ i: i - 1, alpha: 1 }, { i, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ i: spec.shots.indexOf(shotAt(spec, f)), alpha: 1 }];
};

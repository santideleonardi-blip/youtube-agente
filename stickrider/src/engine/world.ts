// StickRider generic world: sky, sun, every set (sets.ts), props and the cast, posed per frame from the spec.
// Lighting, cards, ink and lens are the look engine of the MIT "claude-animated-shorts" (Mr omi), reused as is.
import * as THREE from "three";
import { Pen, bodyFront, bodySide, soldier, KID, SKINS, fxNote, fxDrum, fxContact, fxBurst, fxStars, fxPuff, fxSplash, Outfit, FrontOpts, SideOpts, Expr, INK } from "./toon";
import { LIGHTS, LOOK } from "./lights";
import { TONE, CHAR, untone } from "./shade";
import { cardShade, blobMaterial, CARD_K } from "./cardshade";
import { NOINK } from "./ink";
import { cloudHD, ctex } from "./paint";
import { buildSets, ORIGIN, propObject } from "./sets";
import { Spec, ShotSpec, ActorSpec, Look, Act, camAt, V3 } from "./spec";

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };
const q = (v: number, n = 60) => Math.round(v * n) / n;

// ---------------- canvas pool (one canvas per distinct drawing) ----------------
type Entry = { cv: HTMLCanvasElement; tex: THREE.CanvasTexture; w: number; h: number };
type Req = { key: string; w: number; h: number; k: number; draw: (p: Pen) => void; tex?: THREE.CanvasTexture };
const makeEntry = (w: number, h: number): Entry => {
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return { cv, tex, w, h };
};
class Pool {
  private live = new Map<string, Entry>(); private free: Entry[] = []; private reqs: Req[] = [];
  req(key: string, w: number, h: number, k: number, draw: (p: Pen) => void) { const r: Req = { key: `${w}x${h}|${key}`, w, h, k, draw }; this.reqs.push(r); return r; }
  flush() {
    const want = new Map<string, Req[]>();
    for (const r of this.reqs) { const l = want.get(r.key); if (l) l.push(r); else want.set(r.key, [r]); }
    for (const [key, e] of this.live) if (!want.has(key)) { this.live.delete(key); this.free.push(e); }
    for (const [key, rs] of want) {
      let e = this.live.get(key);
      if (!e) {
        const r = rs[0], i = this.free.findIndex((x) => x.w === r.w && x.h === r.h);
        e = i >= 0 ? this.free.splice(i, 1)[0] : makeEntry(r.w, r.h);
        const g = e.cv.getContext("2d")!;
        g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, e.w, e.h); g.setTransform(r.k, 0, 0, r.k, 0, 0);
        r.draw(new Pen(g)); e.tex.needsUpdate = true; this.live.set(key, e);
      }
      for (const r of rs) r.tex = e.tex;
    }
    this.reqs = [];
  }
}
const blank = (() => { const c = document.createElement("canvas"); c.width = c.height = 2; return new THREE.CanvasTexture(c); })();
const SU = 0.00216; // metres per design unit: 1000 units = 2.16 m
const BODY = (() => { const g = new THREE.PlaneGeometry(600 * SU, 1000 * SU); g.translate(0, (975 - 500) * SU, 0); return g; })();
const CARD = new THREE.PlaneGeometry(1, 1);
class Actor {
  mesh: THREE.Mesh; mat: THREE.MeshLambertMaterial; dmat: THREE.MeshDepthMaterial; r: Req | null = null;
  constructor(parent: THREE.Object3D) {
    this.mat = cardShade(new THREE.MeshLambertMaterial({ map: blank, alphaTest: 0.5, side: THREE.DoubleSide }));
    this.dmat = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: blank, alphaTest: 0.5, side: THREE.DoubleSide });
    this.mesh = new THREE.Mesh(BODY, this.mat); this.mesh.customDepthMaterial = this.dmat;
    this.mesh.onBeforeRender = (r) => { const rt = r.getRenderTarget(); CARD_K.uPx.value = (rt ? rt.height : r.domElement.height) / 1920; };
    this.mesh.receiveShadow = true; this.mesh.visible = false; this.mesh.rotation.order = "YXZ"; this.mesh.renderOrder = 1; this.mesh.layers.set(NOINK);
    parent.add(this.mesh);
  }
  bind() { const t = this.r?.tex; if (t) { this.mat.map = t; this.dmat.map = t; } }
}
class Fx {
  mesh: THREE.Mesh; mat: THREE.MeshBasicMaterial; blob: THREE.MeshBasicMaterial; r: Req | null = null; isBlob = false;
  constructor(parent: THREE.Object3D) {
    this.mat = new THREE.MeshBasicMaterial({ map: blank, alphaTest: 0.5, side: THREE.DoubleSide });
    this.blob = blobMaterial(blank);
    this.mesh = new THREE.Mesh(CARD, this.mat); this.mesh.visible = false; this.mesh.layers.set(NOINK); parent.add(this.mesh);
  }
  bind() {
    const t = this.r?.tex; if (!t) return;
    if (this.isBlob) {
      if (t.generateMipmaps) { t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; t.needsUpdate = true; }
      this.blob.map = t; this.mesh.material = this.blob; this.mesh.renderOrder = 0.5;
    } else { this.mat.map = t; this.mesh.material = this.mat; this.mesh.renderOrder = 0; }
  }
}

// ---------------- the cast ----------------
const COATS = ["#3f6fb5", "#8c3b4a", "#5d7a3a", "#b5653f", "#2f5f6a", "#7b5ac9", "#c28a2c", "#4a5a8c"];
const DRESSES = ["#d9a441", "#c25a7a", "#5a8fc2", "#6aa05a", "#e07a4a"];
const HAIRS = ["#5a3b2a", "#2a201a", "#8a5a2c", "#b08040", "#3a2a24"];
export const outfitOf = (look: Look, v = 0, shoes?: string): Outfit => {
  const skin = SKINS[v % 4];
  let o: Outfit;
  switch (look) {
    case "townswoman": o = { jacket: COATS[(v + 3) % 8], pants: "#3b3f52", boots: "#4a3426", skin, hat: v % 3 === 2 ? "hair" : "bonnet", hair: HAIRS[v % 5], dress: DRESSES[v % 5] }; break;
    case "noble": o = { jacket: ["#5b2c6f", "#2c3e6f", "#6f2c2c"][v % 3], pants: "#2a2a35", boots: INK, skin, hat: "tophat", sash: "#e8c45a", buttons: "#e8c45a", moustache: v % 2 ? "#4a3020" : undefined, build: "stout" }; break;
    case "musician": o = { jacket: ["#d0453a", "#2f8a6a", "#e0a030"][v % 3], pants: "#3b3f52", boots: "#4a3426", skin, hat: "cap", cap: ["#2f5fa5", "#c8323a", "#5a3b8a"][v % 3] }; break;
    case "priest": o = { jacket: "#2b2b3a", pants: "#2b2b3a", boots: INK, skin, hat: "hair", hair: "#9a9aa0", dress: "#2b2b3a" }; break;
    case "soldier": o = soldier(v); break;
    case "kid": o = { ...KID, jacket: COATS[v % 8], skin }; break;
    case "king": o = { jacket: "#8a2a3a", pants: "#2a2a35", boots: INK, skin, hat: "crown", sash: "#f2c23a", buttons: "#f2c23a", moustache: v % 2 ? undefined : "#6a4a2a", build: "stout" }; break;
    case "queen": o = { jacket: "#5a2a7a", pants: "#2a2a35", boots: INK, skin, hat: "crown", dress: "#7a3a9a" }; break;
    case "worker": o = { jacket: ["#3f6fb5", "#b5653f", "#5d7a3a"][v % 3], pants: "#3b3f52", boots: "#4a3426", skin, hat: v % 2 ? "helmet" : "cap", cap: v % 2 ? "#e8b830" : "#5a4a3a", moustache: v % 3 === 1 ? "#4a3426" : undefined }; break;
    case "suit": o = { jacket: ["#2c3448", "#3a3a3a", "#4a3a2c"][v % 3], pants: "#22252e", boots: INK, skin, hat: "hair", hair: HAIRS[v % 5], buttons: "#d9dde0", moustache: v % 4 === 2 ? "#3a2a24" : undefined }; break;
    case "woman": o = { jacket: COATS[(v + 5) % 8], pants: "#3b3f52", boots: "#4a3426", skin, hat: "hair", hair: HAIRS[(v + 2) % 5], dress: DRESSES[(v + 1) % 5] }; break;
    case "scientist": case "doctor": o = { jacket: "#f2f2f2", pants: "#3b3f52", boots: INK, skin, hat: "hair", hair: v % 2 ? "#9a9aa0" : HAIRS[v % 5], buttons: "#b0b4bc", moustache: v % 3 === 0 ? "#6a6a6a" : undefined }; break;
    case "sailor": o = { jacket: "#2a4a8a", pants: "#f2f2f2", boots: INK, skin, hat: "cap", cap: "#f2f2f2", belt: "#f2f2f2" }; break;
    case "pilot": o = { jacket: "#7a5a3a", pants: "#4a4a3a", boots: INK, skin, hat: "helmet", cap: "#5a4030" }; break;
    case "farmer": o = { jacket: ["#c28a2c", "#6a8a3a", "#8a5a3a"][v % 3], pants: "#3a4a6a", boots: "#4a3426", skin, hat: "cap", cap: "#b08040", moustache: v % 2 ? "#5a3b2a" : undefined }; break;
    default: o = { jacket: COATS[v % 8], pants: ["#3b3f52", "#5a4a3a", "#2f3a4a"][v % 3], boots: "#4a3426", skin, hat: v % 3 === 0 ? "cap" : "hair", cap: "#8a5a2c", hair: HAIRS[v % 5], moustache: v % 4 === 1 ? "#4a3426" : undefined };
  }
  return shoes ? { ...o, boots: shoes } : o;
};
const tier = (d: number): [number, number, number] =>
  d < 3.2 ? [1800, 3000, 3.0] : d < 6.5 ? [1080, 1800, 1.8] : d < 16 ? [480, 800, 0.8] : [240, 400, 0.4];

type Placed = { key: string; draw: (p: Pen) => void; x: number; y: number; z: number; mirror: boolean; size: [number, number, number]; scale: number };
type FxPlaced = { key: string; cw: number; ch: number; draw: (p: Pen) => void; x: number; y: number; z: number; w: number; h: number; flat?: boolean; blob?: boolean };

const actAt = (a: ActorSpec, f: number): Act => { let act = a.act ?? "stand"; for (const [t, x] of a.actAt ?? []) if (f >= t) act = x; return act; };
const exprAt = (a: ActorSpec, f: number): Expr => { let e = a.expr ?? "neutral"; for (const [t, x] of a.exprAt ?? []) if (f >= t) e = x; return e; };
/** eyelid: a 4-frame blink every 0.5-2.3 s per character */
const LID = [0.5, 1, 1, 0.5];
const lidAt = (f: number, i: number) => {
  let s = Math.round(-60 * hh(i, 9));
  for (let n = 0; s <= f && n < 400; n++) { const k = f - s; if (k >= 0 && k < 4) return LID[k]; s += Math.round(15 + 54 * hh(i * 31 + n, 13)); }
  return 0;
};

// ---------------- world ----------------
export class World {
  root = new THREE.Group();
  private pool = new Pool(); private actors: Actor[] = []; private fxs: Fx[] = [];
  private hemi: THREE.HemisphereLight; private sun: THREE.DirectionalLight;
  private sky: THREE.Mesh; private skyMat: THREE.ShaderMaterial; private fog = new THREE.Fog("#bccbec", 25, 420);
  private clouds: THREE.Mesh[] = []; private cloudMaps: Record<"day" | "golden" | "night", THREE.Texture[]>;
  private props = new THREE.Group(); private propKey = "";
  private sunDir = new THREE.Vector3(); private frustum = new THREE.Frustum(); private m4 = new THREE.Matrix4(); private sph = new THREE.Sphere();

  constructor(private spec: Spec) {
    const R = this.root;
    this.skyMat = new THREE.ShaderMaterial({
      uniforms: { c0: { value: new THREE.Color() }, c1: { value: new THREE.Color() }, c2: { value: new THREE.Color() }, c3: { value: new THREE.Color() }, c4: { value: new THREE.Color() }, e: { value: new THREE.Vector4() } },
      vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `uniform vec3 c0, c1, c2, c3, c4; uniform vec4 e; varying vec3 vP;
        void main(){ float el = asin(clamp(normalize(vP).y, -1.0, 1.0));
          vec3 c = mix(c0, c1, smoothstep(0.0, e.x, el)); c = mix(c, c2, smoothstep(e.x, e.y, el));
          c = mix(c, c3, smoothstep(e.y, e.z, el)); c = mix(c, c4, smoothstep(e.z, e.w, el)); gl_FragColor = vec4(c, 1.0); }`,
      side: THREE.BackSide, depthWrite: false, fog: false,
    });
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(1100, 48, 24), this.skyMat);
    this.sky.renderOrder = -1; this.sky.frustumCulled = false; this.sky.layers.set(NOINK); R.add(this.sky);
    this.hemi = new THREE.HemisphereLight("#cfe6ff", "#6c5c8c", 1.1);
    this.sun = new THREE.DirectionalLight("#fff0d6", 2.6); this.sun.castShadow = true; this.sun.shadow.mapSize.set(4096, 4096);
    R.add(this.hemi, this.sun, this.sun.target);
    this.cloudMaps = { day: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.day.cloud)), golden: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.golden.cloud)), night: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.night.cloud)) };
    for (let i = 0; i < 10; i++) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: this.cloudMaps.day[i % 4], color: new THREE.Color(1.1, 1.1, 1.1), transparent: true, depthWrite: false, fog: false }));
      m.layers.set(NOINK); m.userData.k = i; this.clouds.push(m); R.add(m);
    }
    buildSets(R);
    R.add(this.props);
  }

  private actor(i: number) { while (this.actors.length <= i) this.actors.push(new Actor(this.root)); return this.actors[i]; }
  private fx(i: number) { while (this.fxs.length <= i) this.fxs.push(new Fx(this.root)); return this.fxs[i]; }

  /** pose the world for shot s at frame f (absolute). Returns the camera look point (for the lens focus). */
  update(s: ShotSpec, f: number, cam: THREE.PerspectiveCamera, scene: THREE.Scene) {
    const fs = f - s.a, t = f / this.spec.fps, L = LIGHTS[s.light], K = LOOK[s.light];
    const [ox, oz] = ORIGIN[s.set], W = (p: V3) => V(p[0] + ox, p[1], p[2] + oz);
    // ---- camera ----
    const c = camAt(s, fs);
    cam.position.copy(W(c.pos)); cam.up.set(0, 1, 0); cam.lookAt(W(c.look));
    cam.fov = c.fov; cam.near = 0.2; cam.far = 1500; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    cam.layers.enable(NOINK);
    const focus = W(c.look), dist = cam.position.distanceTo(focus);
    // ---- sun: camera-relative, frozen per shot (from the shot's first camera key) ----
    const c0 = camAt(s, 0), fw = W(c0.look).sub(W(c0.pos)).setY(0).normalize();
    const az = THREE.MathUtils.degToRad(L.az), el = THREE.MathUtils.degToRad(L.el);
    const hor = fw.clone().applyAxisAngle(V(0, 1, 0), -az);
    this.sunDir.copy(hor).multiplyScalar(Math.cos(el)).setY(Math.sin(el)).normalize();
    this.hemi.color.set(L.sky); this.hemi.groundColor.set(L.ground); this.hemi.intensity = L.hemiI;
    this.sun.color.set(L.sunCol); this.sun.intensity = L.sunI;
    const Rr = THREE.MathUtils.clamp(dist * 1.15 + 7, 12, 95);
    this.sun.position.copy(focus).addScaledVector(this.sunDir, 220); this.sun.target.position.copy(focus);
    const sc = this.sun.shadow.camera; sc.left = -Rr; sc.right = Rr; sc.top = Rr; sc.bottom = -Rr; sc.near = 20; sc.far = 480; sc.updateProjectionMatrix();
    this.sun.shadow.bias = L.bias; this.sun.shadow.normalBias = L.normalBias * (Rr / 12);
    TONE.uLitCol.value.set(...L.lit); TONE.uShadeCol.value.set(...L.shade); TONE.uShadeLift.value.set(...L.lift);
    TONE.uLambert.value = L.lambert; TONE.uSideK.value = L.sideK; TONE.uTerm.value = L.term; TONE.uBounce.value.set(...K.bounce); TONE.uSat.value = K.sat;
    CHAR.uCharTint.value.set(...L.charTint); CHAR.uCharShade.value = L.charShade; CHAR.uGrad.value = L.charGrad;
    CHAR.uBodyGrad.value = L.bodyGrad; CHAR.uSideTint.value.set(...L.sideTint);
    // ---- sky, fog, clouds ----
    const su = this.skyMat.uniforms;
    K.sky.c.forEach((h, i) => untone(h, su["c" + i].value));
    const e = K.sky.e.map((deg) => THREE.MathUtils.degToRad(deg));
    su.e.value.set(e[1], e[2], e[3], e[4]);
    this.sky.position.copy(cam.position);
    untone(L.fog, this.fog.color); this.fog.near = L.fogNear; this.fog.far = L.fogFar; scene.fog = this.fog; scene.background = null;
    for (const m of this.clouds) {
      const i = m.userData.k as number, a = (i / 10) * Math.PI * 2 + 0.3 + t * 0.004, d = 620 + (i % 3) * 60, w = 130 + (i % 4) * 30;
      m.position.set(cam.position.x + Math.cos(a) * d, 120 + (i % 4) * 38, cam.position.z + Math.sin(a) * d); m.scale.set(w, w / 2, 1);
      m.lookAt(cam.position.x, m.position.y, cam.position.z);
      (m.material as THREE.MeshBasicMaterial).map = this.cloudMaps[s.light][i % 4];
    }
    // ---- props of this shot ----
    const pk = `${this.spec.shots.indexOf(s)}`;
    if (pk !== this.propKey) {
      this.props.clear();
      for (const p of s.props ?? []) {
        const tpl = propObject(p);
        if (!tpl) continue;
        const o = tpl.clone(); o.position.copy(W([p.x, 0, p.z])); o.rotation.y = p.yaw ?? 0; o.scale.setScalar(p.s ?? 1);
        o.traverse((m) => { const mm = m as THREE.Mesh; if (mm.isMesh) { mm.castShadow = true; mm.receiveShadow = true; } });
        this.props.add(o);
      }
      this.propKey = pk;
    }
    // ---- cast ----
    const right = V(0, 0, 0).setFromMatrixColumn(cam.matrixWorld, 0);
    const light2D = (mirror: boolean) => {
      const sx = this.sunDir.dot(right) * (mirror ? -1 : 1), sy = -this.sunDir.y;
      return Math.round(Math.atan2(sy, sx) / (Math.PI / 4)) * (Math.PI / 4);
    };
    const places: Placed[] = [], fx: FxPlaced[] = [];
    const contact = (x: number, z: number, sc2: number, y = 0) => {
      const col = s.light === "golden" ? "#7a6a8a" : s.light === "night" ? "#30304a" : "#5a5a78";
      fx.push({ key: `blob|contact|${col}`, cw: 128, ch: 128, draw: (p) => fxContact(p, col), x, y: y + 0.022, z, w: 0.6 * sc2, h: 0.45 * sc2, flat: true, blob: true });
    };
    const person = (a: ActorSpec, idx: number, fx2: number) => {
      if (a.from !== undefined && fs < a.from) return;
      const len = Math.max(1, s.b - s.a), u = a.to ? Math.min(1, Math.max(0, (fs - (a.from ?? 0)) / (len - (a.from ?? 0)))) : 0;
      const lx = a.to ? a.x + (a.to[0] - a.x) * u : a.x, lz = a.to ? a.z + (a.to[1] - a.z) * u : a.z;
      const x = lx + ox, z = lz + oz, sc2 = a.scale ?? 1, y0 = a.y0 ?? 0;
      if (!this.frustum.intersectsSphere(this.sph.set(V(x, y0 + 1.1 * sc2, z), 3))) return;
      const d = cam.position.distanceTo(V(x, 1.2, z)) / sc2, [w, h, k] = tier(d);
      const act = actAt(a, fs), expr = exprAt(a, fs), seed = (idx % 7) + 1, ph = hh(idx, 3);
      const o = outfitOf(a.look, a.v ?? idx, a.shoes), okey = JSON.stringify(o);
      const blink = act === "dance" ? 0 : lidAt(f, idx);
      const tt = fx2 / this.spec.fps;
      if (a.side) {
        const mirror = !!a.mirror, so: SideOpts = { expr, mode: act === "walk" ? "march" : "stand", phase: q((tt * 1.0 + ph) % 1), stride: 0.8, light: light2D(mirror), seed, blink };
        places.push({ key: `S|${okey}|${JSON.stringify(so)}`, draw: (p) => bodySide(p, o, so), x, y: y0, z, mirror, size: [w, h, k], scale: sc2 });
      } else {
        let fo: FrontOpts = { expr, mode: "stand", light: light2D(false), seed, facing: a.facing ?? 0, blink };
        if (act === "dance") {
          const dp = q((tt * 1.8 + ph) % 1, 24);
          fo = { ...fo, mode: "march", phase: dp, lift: 95, dance: q((tt * 1.8 + ph * 0.6) % 1, 24), tilt: q(10 * Math.sin(2 * Math.PI * (tt * 0.9 + ph)), 1) };
        } else if (act === "walk") fo = { ...fo, mode: "stroll", phase: q((tt * 1.0 + ph) % 1, 24) };
        else if (act === "wave") fo = { ...fo, wave: q(0.5 + 0.5 * Math.sin(tt * 7 + ph * 6), 12) };
        else if (act === "cheer") fo = { ...fo, mode: "march", phase: q((tt * 1.4 + ph) % 1, 24), lift: 40, arms: "up" };
        else if (act === "play") fo = { ...fo, wave: q(0.5 + 0.5 * Math.sin(tt * 14 + ph * 6), 8) };
        else if (act === "sit") fo = { ...fo, mode: "sit" };
        else if (act === "fall") fo = { ...fo, mode: "fall" };
        places.push({ key: `F|${okey}|${JSON.stringify(fo)}`, draw: (p) => bodyFront(p, o, fo), x, y: y0 + (act === "fall" ? -0.25 : 0), z, mirror: false, size: [w, h, k], scale: sc2 });
      }
      if (act !== "fall") contact(x, z, sc2, y0);
    };
    this.frustum.setFromProjectionMatrix(this.m4.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    (s.actors ?? []).forEach((a, i) => person(a, i, fs + i * 7));
    (s.crowd ?? []).forEach((cr, ci) => {
      const seed = (cr.seed ?? 1) * 101 + ci * 977, looks = cr.looks ?? ["townsman", "townswoman"];
      for (let k = 0; k < cr.n; k++) {
        const at = cr.grow ? cr.grow[0] + ((cr.grow[1] - cr.grow[0]) * k) / cr.n : 0;
        if (fs < at) continue;
        const a: ActorSpec = { look: looks[k % looks.length], v: k + ci * 3, x: cr.x[0] + (cr.x[1] - cr.x[0]) * hh(seed + k, 1), z: cr.z[0] + (cr.z[1] - cr.z[0]) * hh(seed + k, 2),
          act: cr.act, y0: cr.y0, expr: cr.expr ?? (cr.act === "dance" ? (["dazed", "pained", "laugh", "shock", "nervous"] as Expr[])[k % 5] : "neutral") };
        person(a, 100 + ci * 300 + k, fs + k * 3);
      }
    });
    // ---- effects: music notes, drums ----
    if (s.notes) for (let k = 0; k < 6; k++) {
      const u = (t * 0.35 + k / 6) % 1, mus = (s.actors ?? []).filter((a) => a.look === "musician");
      const m = mus[k % Math.max(1, mus.length)]; if (!m) break;
      const kind = k % 2, col = ["#1f2a44", "#7a2a3a", "#2a5a3a"][k % 3];
      fx.push({ key: `note|${kind}|${col}`, cw: 220, ch: 260, draw: (p) => fxNote(p, kind, col), x: m.x + ox + 0.5 * Math.sin(u * 6 + k), y: 2.2 + u * 2.2 + (m.y0 ?? 0), z: m.z + oz, w: 0.45, h: 0.53 });
    }
    for (const a of s.actors ?? []) if (a.look === "musician" && (a.act === "play")) {
      fx.push({ key: "drum", cw: 260, ch: 240, draw: (p) => fxDrum(p), x: a.x + ox + 0.5, y: 0.55 + (a.y0 ?? 0), z: a.z + oz + 0.25, w: 0.75, h: 0.7 });
    }
    for (const e of s.fx ?? []) {
      const u = (fs - e.at) / 14;
      if (u < 0 || u >= 1) continue;
      const k = Math.round(u * 14) / 14, sz = e.size ?? 1, draw = (pp: Pen) => {
        if (e.kind === "burst") fxBurst(pp, k); else if (e.kind === "stars") fxStars(pp, k); else if (e.kind === "puff") fxPuff(pp, k); else fxSplash(pp, k);
      };
      const [cw, ch] = ({ burst: [500, 500], splash: [800, 800], puff: [300, 300], stars: [420, 220] } as Record<string, [number, number]>)[e.kind];
      fx.push({ key: `fx|${e.kind}|${k}`, cw, ch, draw, x: e.x + ox, y: e.y, z: e.z + oz, w: 1.6 * sz, h: (1.6 * sz * ch) / cw });
    }
    // red shoes close-up
    for (const p of s.props ?? []) if (p.kind === "shoes") {
      fx.push({ key: "shoes2", cw: 520, ch: 260, draw: (pp) => {
        for (const dx of [0, 250]) {
          pp.poly([[22 + dx, 205], [26 + dx, 120], [60 + dx, 92], [120 + dx, 92], [150 + dx, 140], [215 + dx, 160], [236 + dx, 190], [232 + dx, 215], [22 + dx, 215]], "#d0283a", 9);
          pp.poly([[18 + dx, 212], [240 + dx, 212], [236 + dx, 232], [22 + dx, 232]], "#5a1a22", 8);
          pp.ell(96 + dx, 112, 34, 12, "#5a1020", 0);
          pp.ell(150 + dx, 150, 16, 9, "#e8c45a", 5);
          pp.line([[48 + dx, 135], [70 + dx, 112]], "#ff9aa6", 7, false);
        }
      }, x: p.x + ox, y: 0.14 * (p.s ?? 1), z: p.z + oz, w: 0.7 * (p.s ?? 1), h: 0.35 * (p.s ?? 1) });
    }
    // ---- mesh assignment ----
    const tint = s.light === "golden" ? "#ffcf9e" : s.light === "night" ? "#b8c8ff" : "#ffffff";
    let ai = 0;
    for (const p of places) {
      const a = this.actor(ai++);
      a.r = this.pool.req(p.key, p.size[0], p.size[1], p.size[2], p.draw);
      a.mesh.visible = true; a.mesh.position.set(p.x, p.y, p.z);
      a.mesh.rotation.set(0, Math.atan2(cam.position.x - p.x, cam.position.z - p.z), 0);
      a.mesh.scale.set(p.mirror ? -p.scale : p.scale, p.scale, p.scale);
      if (a.mat.emissiveMap) a.mat.emissive.set(tint);
      a.mesh.castShadow = L.actorShadow;
    }
    for (let i = ai; i < this.actors.length; i++) this.actors[i].mesh.visible = false;
    let fi = 0;
    for (const p of fx) {
      const e = this.fx(fi++);
      e.r = this.pool.req(p.key, p.cw, p.ch, 1, p.draw); e.isBlob = !!p.blob;
      e.mesh.visible = true; e.mesh.position.set(p.x, p.y, p.z);
      if (p.flat) e.mesh.rotation.set(-Math.PI / 2, 0, 0); else e.mesh.quaternion.copy(cam.quaternion);
      e.mesh.scale.set(p.w, p.h, 1);
    }
    for (let i = fi; i < this.fxs.length; i++) this.fxs[i].mesh.visible = false;
    this.pool.flush();
    for (let i = 0; i < ai; i++) this.actors[i].bind();
    for (let i = 0; i < fi; i++) this.fxs[i].bind();
    return focus;
  }
}

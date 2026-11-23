// Reusable sets (scenery) for StickRider shorts. Each set is built once, far from the others, so one world holds
// every place a story visits and a shot just points the camera at its set. Actor / prop coordinates in the spec are
// local to the set origin (ORIGIN[set]).
import * as THREE from "three";
import { Batch, lam, house, boxGeo, quad, V } from "./build";
import { cobbleHD, grassHD, planksHD, stoneHD, roofHD, rep, ctex, rng } from "./paint";
import type { SetName, PropSpec } from "./spec";

export const ORIGIN: Record<SetName, [number, number]> = {
  street: [0, 0], square: [700, 0], road: [1400, 0], shrine: [2100, 0], field: [2800, 0], council: [700, 0],
  sea: [0, 1400], desert: [700, 1400], snow: [1400, 1400], room: [2100, 1400], city: [2800, 1400],
};

const ground = (b: Batch, x0: number, x1: number, z0: number, z1: number, mat: THREE.Material, tile: number, y = 0) =>
  b.add(quad(V(x0, y, z1), V(x1, y, z1), V(x1, y, z0), V(x0, y, z0), (x1 - x0) / tile, (z1 - z0) / tile), mat);

const M = () => ({
  grass: lam("grassHD", () => ({ map: grassHD() })),
  cobble: lam("cobbleHD", () => ({ map: cobbleHD() })),
  dirt: lam("dirt", () => ({ map: ctex("dirt", 512, 512, (g, r) => {
    g.fillStyle = "#c9a46e"; g.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 900; i++) { g.fillStyle = r() < 0.5 ? "rgba(120,80,40,.12)" : "rgba(255,240,200,.14)"; const s = 2 + r() * 7; g.fillRect(r() * 512, r() * 512, s, s * 0.6); }
  }) })),
  planks: lam("planksHD", () => ({ map: planksHD() })),
  stone: lam("stoneHDw", () => ({ map: stoneHD("stoneHDw") })),
  wood: lam("woodDark", () => ({ color: "#8a5a3c" })),
  woodL: lam("woodLight", () => ({ color: "#c08a55" })),
  red: lam("cloth_red", () => ({ color: "#c8323a" })),
  leaf: [lam("leafA", () => ({ color: "#5aa64a" })), lam("leafB", () => ({ color: "#4a9142" })), lam("leafC", () => ({ color: "#6fb653" }))],
  hill: lam("hill", () => ({ map: rep(grassHD(), 30, 30) })),
  rock: lam("rock", () => ({ color: "#9d97a8" })),
  snow: lam("snow", () => ({ color: "#f4f4fa" })),
  roof: lam("roofRed", () => ({ map: roofHD("#b5543f"), side: THREE.DoubleSide })),
  sand: lam("sandHD", () => ({ map: ctex("sandHD", 512, 512, (g, r) => {
    g.fillStyle = "#e9c88a"; g.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 260; i++) { g.strokeStyle = r() < 0.5 ? "rgba(190,140,80,.22)" : "rgba(255,240,205,.3)"; g.lineWidth = 3; const y = r() * 512, x = r() * 512; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + 30, y - 8, x + 70, y); g.stroke(); }
  }) })),
  snowG: lam("snowGround", () => ({ map: ctex("snowHD", 512, 512, (g, r) => {
    g.fillStyle = "#eef3fb"; g.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 300; i++) { g.fillStyle = r() < 0.5 ? "rgba(170,190,230,.18)" : "rgba(255,255,255,.6)"; g.beginPath(); g.ellipse(r() * 512, r() * 512, 4 + r() * 14, 2 + r() * 5, 0, 0, 7); g.fill(); }
  }) })),
  water: lam("waterFlat", () => ({ map: ctex("waterT", 512, 512, (g, r) => {
    g.fillStyle = "#2a8fc0"; g.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 120; i++) { g.strokeStyle = "rgba(190,240,255,.55)"; g.lineWidth = 4; const x = r() * 512, y = r() * 512; g.beginPath(); g.arc(x, y, 16 + r() * 12, 1.1 * Math.PI, 1.9 * Math.PI); g.stroke(); }
  }) })),
  asphalt: lam("asphalt", () => ({ map: ctex("asphaltT", 512, 512, (g, r) => {
    g.fillStyle = "#5a5c66"; g.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 900; i++) { g.fillStyle = r() < 0.5 ? "rgba(0,0,0,.12)" : "rgba(255,255,255,.08)"; g.fillRect(r() * 512, r() * 512, 3, 3); }
    g.fillStyle = "#f2e6b0"; g.fillRect(246, 0, 20, 200); g.fillRect(246, 300, 20, 200);
  }) })),
  sidewalk: lam("sidewalk", () => ({ color: "#c9c4bb" })),
  floor: lam("floorPlanks", () => ({ map: planksHD() })),
  wallpaper: lam("wallpaper", () => ({ map: ctex("wallpaperT", 512, 512, (g) => {
    g.fillStyle = "#e8d6b0"; g.fillRect(0, 0, 512, 512);
    g.fillStyle = "rgba(160,90,60,.18)"; for (let x = 0; x < 512; x += 64) g.fillRect(x, 0, 18, 512);
  }) })),
  hull: lam("hull", () => ({ map: planksHD() })),
  sail: lam("sail", () => ({ color: "#f4eedf", side: THREE.DoubleSide })),
  pine: lam("pine", () => ({ color: "#3f7a4a" })),
  glass: lam("glassBlue", () => ({ color: "#7fb0e0" })),
  bld: [lam("bldA", () => ({ color: "#c98a5a" })), lam("bldB", () => ({ color: "#8fa0b8" })), lam("bldC", () => ({ color: "#d8c49a" })), lam("bldD", () => ({ color: "#a0685a" }))],
});

/** modern building: a box with a window grid painted on */
const winTex = (key: string, wall: string, cols: number, rows: number) => ctex(key, 512, 1024, (g) => {
  g.fillStyle = wall; g.fillRect(0, 0, 512, 1024);
  const cw = 512 / cols, rh = 1024 / rows;
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
    g.fillStyle = (i * 7 + j * 3) % 5 === 0 ? "#ffe9a8" : "#5b7fb0"; g.fillRect(i * cw + cw * 0.2, j * rh + rh * 0.2, cw * 0.6, rh * 0.55);
    g.strokeStyle = "rgba(30,20,40,.7)"; g.lineWidth = 4; g.strokeRect(i * cw + cw * 0.2, j * rh + rh * 0.2, cw * 0.6, rh * 0.55);
  }
});
const building = (b: Batch, x: number, z: number, w: number, d: number, h: number, k: number) => {
  const walls = ["#c98a5a", "#8fa0b8", "#d8c49a", "#a0685a", "#9a8ab0"], wall = walls[k % walls.length];
  const m = lam(`bld_${k % 5}_${Math.round(h)}`, () => ({ map: winTex(`bldT_${k % 5}_${Math.round(h)}`, wall, Math.max(2, Math.round(w / 3)), Math.max(2, Math.round(h / 3.2))) }));
  b.add(boxGeo(V(x - w / 2, 0, z - d / 2), V(x + w / 2, h, z + d / 2)), m);
  b.add(boxGeo(V(x - w / 2 - 0.2, h, z - d / 2 - 0.2), V(x + w / 2 + 0.2, h + 0.5, z + d / 2 + 0.2)), lam("roofTrim", () => ({ color: "#6a6470" })));
};
const pine = (b: Batch, m: ReturnType<typeof M>, x: number, z: number, h: number, snow: boolean) => {
  b.add(new THREE.CylinderGeometry(0.15, 0.22, h * 0.25, 6).translate(x, h * 0.125, z), m.wood);
  for (let k = 0; k < 3; k++) b.add(new THREE.ConeGeometry(h * (0.32 - k * 0.07), h * 0.4, 8).translate(x, h * (0.35 + k * 0.2), z), k === 2 && snow ? m.snow : m.pine);
};

const tree = (b: Batch, m: ReturnType<typeof M>, x: number, z: number, h: number, k: number) => {
  b.add(new THREE.CylinderGeometry(0.18 * h / 6, 0.26 * h / 6, h * 0.45, 8).translate(x, h * 0.225, z), m.wood);
  b.add(new THREE.SphereGeometry(h * 0.3, 12, 9).scale(1, 1.15, 1).translate(x, h * 0.68, z), m.leaf[k % 3]);
  b.add(new THREE.SphereGeometry(h * 0.2, 10, 8).translate(x + h * 0.15, h * 0.85, z - h * 0.05), m.leaf[(k + 1) % 3]);
};
const mountain = (b: Batch, m: ReturnType<typeof M>, x: number, z: number, r: number, h: number) => {
  b.add(new THREE.ConeGeometry(r, h, 7).translate(x, h / 2 - 2, z), m.rock);
  b.add(new THREE.ConeGeometry(r * 0.32, h * 0.32, 7).translate(x, h - h * 0.16 - 2 + 0.05, z), m.snow);
};
const hill = (b: Batch, m: ReturnType<typeof M>, x: number, z: number, rx: number, h: number) =>
  b.add(new THREE.SphereGeometry(1, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2).scale(rx, h, rx * 0.7).translate(x, -0.2, z), m.hill);

export const buildSets = (root: THREE.Object3D) => {
  const b = new Batch(), m = M(), r = rng(5);
  // ---------- street: a narrow cobbled lane between gabled houses (runs along z) ----------
  {
    const [ox, oz] = ORIGIN.street;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.grass, 4);
    ground(b, ox - 3.2, ox + 3.2, oz - 90, oz + 30, m.cobble, 4, 0.01);
    ground(b, ox - 9, ox + 9, oz - 90, oz + 30, m.cobble, 4, 0.005);
    let z = oz + 24, i = 0;
    while (z > oz - 88) {
      const w = 6 + Math.floor(r() * 3), d = 8, h = 5.6 + Math.floor(r() * 3) * 1.4;
      house(b, ox - 3.4 - d / 2, z - w / 2, Math.PI / 2, w, d, h, i);
      house(b, ox + 3.4 + d / 2, z - w / 2 - 1, -Math.PI / 2, w, d, h + (i % 2 ? 1.4 : 0), i + 3);
      z -= w + 0.3; i++;
    }
    mountain(b, m, ox - 120, oz - 330, 90, 120);
    mountain(b, m, ox + 80, oz - 360, 110, 150);
  }
  // ---------- square: the market square, houses on three sides, open to +z ----------
  {
    const [ox, oz] = ORIGIN.square;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.grass, 4);
    ground(b, ox - 26, ox + 26, oz - 26, oz + 40, m.cobble, 4, 0.01);
    for (const k of [0, 1, 4, 5]) house(b, ox - 22.5 + k * 9, oz - 30, 0, 8.4, 8, 7 + (k % 3) * 1.4, k + 1);
    for (let k = 0; k < 6; k++) {
      house(b, ox - 30, oz - 21 + k * 9, Math.PI / 2, 8.4, 8, 7 + (k % 2) * 1.4, k + 2);
      house(b, ox + 30, oz - 21 + k * 9, -Math.PI / 2, 8.4, 8, 7 + ((k + 1) % 2) * 1.4, k + 4);
    }
    // town hall: wide, tall, red banner
    house(b, ox, oz - 32, 0, 16, 10, 11, 2);
    mountain(b, m, ox - 150, oz - 330, 100, 140);
    mountain(b, m, ox + 120, oz - 380, 120, 170);
  }
  // ---------- road: a dirt road through fields and hills, mountains ahead (runs along -z) ----------
  {
    const [ox, oz] = ORIGIN.road;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.grass, 4);
    ground(b, ox - 2.4, ox + 2.4, oz - 260, oz + 40, m.dirt, 4, 0.01);
    for (let k = 0; k < 40; k++) {
      const side = k % 2 ? 1 : -1, x = ox + side * (6 + r() * 30), z = oz + 20 - k * 7 - r() * 4;
      tree(b, m, x, z, 5 + r() * 4, k);
    }
    hill(b, m, ox - 70, oz - 120, 50, 18); hill(b, m, ox + 80, oz - 160, 60, 24); hill(b, m, ox - 20, oz - 230, 70, 20);
    mountain(b, m, ox - 60, oz - 330, 90, 160); mountain(b, m, ox + 70, oz - 300, 80, 130); mountain(b, m, ox + 10, oz - 380, 120, 200);
  }
  // ---------- shrine: a chapel on a green hilltop, mountains behind ----------
  {
    const [ox, oz] = ORIGIN.shrine;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.grass, 4);
    ground(b, ox - 2.2, ox + 2.2, oz - 12, oz + 40, m.dirt, 4, 0.01);
    house(b, ox, oz - 20, 0, 9, 12, 7, 5);
    // bell tower
    const tx = ox + 6.6;
    b.add(boxGeo(V(tx - 1.6, 0, oz - 17), V(tx + 1.6, 13, oz - 13.8), 2), m.stone);
    b.add(new THREE.ConeGeometry(2.6, 4, 4).rotateY(Math.PI / 4).translate(tx, 15, oz - 15.4), m.roof);
    b.add(boxGeo(V(tx - 0.08, 17, oz - 15.48), V(tx + 0.08, 19.2, oz - 15.32)), m.wood);
    b.add(boxGeo(V(tx - 0.7, 18.2, oz - 15.48), V(tx + 0.7, 18.36, oz - 15.32)), m.wood);
    for (let k = 0; k < 14; k++) tree(b, m, ox + (k % 2 ? 1 : -1) * (10 + r() * 25), oz - 10 - r() * 40, 5 + r() * 3, k);
    mountain(b, m, ox - 80, oz - 260, 110, 180); mountain(b, m, ox + 90, oz - 300, 120, 210); mountain(b, m, ox, oz - 360, 140, 240);
  }
  // ---------- field: open countryside ----------
  {
    const [ox, oz] = ORIGIN.field;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.grass, 4);
    for (let k = 0; k < 25; k++) tree(b, m, ox + (r() - 0.5) * 160, oz - 20 - r() * 120, 5 + r() * 4, k);
    hill(b, m, ox - 60, oz - 140, 60, 20); hill(b, m, ox + 70, oz - 150, 70, 26);
    mountain(b, m, ox, oz - 340, 130, 190);
  }
  // ---------- sea: open water, a wooden ship deck at the origin (deck top y = 1.2), coast far away ----------
  {
    const [ox, oz] = ORIGIN.sea;
    ground(b, ox - 500, ox + 500, oz - 500, oz + 500, m.water, 6, -1.2);
    // deck (x -4..4, z -9..9) with rails, mast and sail
    b.add(boxGeo(V(ox - 4, -3, oz - 9), V(ox + 4, 1.2, oz + 9), 2), m.hull);
    b.add(new THREE.ConeGeometry(4, 6, 4, 1).rotateX(-Math.PI / 2).rotateZ(Math.PI / 4).scale(1, 0.55, 1).translate(ox, -0.3, oz - 12), m.hull);
    for (const sx of [-1, 1]) b.add(boxGeo(V(ox + sx * 4 - 0.12, 1.2, oz - 9), V(ox + sx * 4 + 0.12, 2.1, oz + 9)), m.woodL);
    b.add(new THREE.CylinderGeometry(0.22, 0.28, 16, 10).translate(ox, 9.2, oz - 3), m.wood);
    b.add(boxGeo(V(ox - 3.5, 5, oz - 3.25), V(ox + 3.5, 13, oz - 3.15)), m.sail);
    b.add(boxGeo(V(ox - 3.8, 13, oz - 3.35), V(ox + 3.8, 13.25, oz - 3.05)), m.wood);
    mountain(b, m, ox - 200, oz - 420, 120, 90); mountain(b, m, ox + 150, oz - 450, 100, 70);
  }
  // ---------- desert: dunes, pyramids, a few rocks ----------
  {
    const [ox, oz] = ORIGIN.desert;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.sand, 5);
    for (let k = 0; k < 8; k++) b.add(new THREE.SphereGeometry(1, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2).scale(25 + r() * 30, 5 + r() * 6, 20 + r() * 20).translate(ox + (r() - 0.5) * 260, -0.3, oz - 40 - r() * 200), m.sand);
    for (const [px, pz, sz] of [[-60, -200, 70], [30, -260, 90], [110, -230, 50]]) b.add(new THREE.ConeGeometry(sz, sz * 0.8, 4).rotateY(Math.PI / 4).translate(ox + px, sz * 0.4 - 0.5, oz + pz), m.sand);
    for (let k = 0; k < 10; k++) b.add(new THREE.DodecahedronGeometry(0.6 + r() * 1.4).translate(ox + (r() - 0.5) * 60, 0.3, oz - 8 - r() * 40), m.rock);
  }
  // ---------- snow: snowy plain, pine forest, mountains ----------
  {
    const [ox, oz] = ORIGIN.snow;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.snowG, 5);
    for (let k = 0; k < 50; k++) { const x = ox + (r() - 0.5) * 140, z = oz - 12 - r() * 120; if (Math.abs(x - ox) < 6 && z > oz - 30) continue; pine(b, m, x, z, 6 + r() * 6, true); }
    mountain(b, m, ox - 70, oz - 280, 120, 200); mountain(b, m, ox + 90, oz - 320, 130, 230);
  }
  // ---------- room: an interior 12 x 10 m, window on the back wall, door, open to +z ----------
  {
    const [ox, oz] = ORIGIN.room;
    ground(b, ox - 200, ox + 200, oz - 200, oz + 200, m.grass, 4, -0.02);
    ground(b, ox - 6, ox + 6, oz - 6, oz + 6, m.floor, 2, 0.01);
    b.add(boxGeo(V(ox - 6, 0, oz - 6.3), V(ox + 6, 4.2, oz - 6)), m.wallpaper);
    for (const sx of [-1, 1]) b.add(boxGeo(V(ox + sx * 6 - 0.15, 0, oz - 6), V(ox + sx * 6 + 0.15, 4.2, oz + 6)), m.wallpaper);
    b.add(boxGeo(V(ox - 1.6, 1.2, oz - 5.98), V(ox + 1.6, 3.2, oz - 5.94)), m.glass);
    for (const x of [-1.6, 0, 1.6]) b.add(boxGeo(V(ox + x - 0.06, 1.2, oz - 5.93), V(ox + x + 0.06, 3.2, oz - 5.9)), m.woodL);
    b.add(boxGeo(V(ox - 1.6, 2.17, oz - 5.93), V(ox + 1.6, 2.23, oz - 5.9)), m.woodL);
    b.add(boxGeo(V(ox + 5.84, 0, oz - 2), V(ox + 5.88, 2.6, oz - 0.6)), m.wood);
    b.add(boxGeo(V(ox - 6, 4.2, oz - 6.3), V(ox + 6, 4.35, oz + 6)), lam("ceiling", () => ({ color: "#f0e6d0" })));
  }
  // ---------- city: a modern street (runs along z), sidewalks, blocks of buildings ----------
  {
    const [ox, oz] = ORIGIN.city;
    ground(b, ox - 400, ox + 400, oz - 400, oz + 400, m.sidewalk, 4);
    ground(b, ox - 5, ox + 5, oz - 300, oz + 60, m.asphalt, 10, 0.01);
    let z = oz + 40, k = 0;
    while (z > oz - 260) {
      const w = 12 + Math.floor(r() * 3) * 4, h = 12 + Math.floor(r() * 6) * 4;
      building(b, ox - 9 - 7, z - w / 2, 14, w, h, k);
      building(b, ox + 9 + 7, z - w / 2 - 2, 14, w, h + (k % 3) * 4, k + 2);
      z -= w + 1; k++;
    }
  }
  b.build(root);
};

// ---------- props (per shot, built on demand and cached by key) ----------
const propCache = new Map<string, THREE.Object3D>();
export const propObject = (p: PropSpec): THREE.Object3D | null => {
  const key = p.kind;
  let o = propCache.get(key);
  if (!o) {
    const b = new Batch(), m = M(), g = new THREE.Group();
    if (p.kind === "stage") {
      b.add(boxGeo(V(-5, 0, -2.5), V(5, 1.1, 2.5), 2), m.planks);
      for (let k = 0; k < 3; k++) b.add(boxGeo(V(-1.2, 0, 2.5 + k * 0.4), V(1.2, 0.85 - k * 0.3, 2.9 + k * 0.4)), m.woodL);
      for (const x of [-4.8, 4.8]) b.add(boxGeo(V(x - 0.12, 1.1, -2.4), V(x + 0.12, 4.2, -2.16)), m.wood);
      b.add(boxGeo(V(-5, 3.9, -2.4), V(5, 4.4, -2.2)), m.red);
    } else if (p.kind === "wagon") {
      b.add(boxGeo(V(-1.1, 0.8, -1.8), V(1.1, 1.0, 1.8), 1), m.planks);
      for (const s of [-1, 1]) b.add(boxGeo(V(s * 1.1 - 0.06, 1.0, -1.8), V(s * 1.1 + 0.06, 1.55, 1.8)), m.woodL);
      b.add(boxGeo(V(-1.1, 1.0, -1.86), V(1.1, 1.55, -1.74)), m.woodL);
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) b.add(new THREE.CylinderGeometry(0.55, 0.55, 0.12, 16).rotateZ(Math.PI / 2).translate(sx * 1.2, 0.55, sz * 1.2), m.wood);
      b.add(boxGeo(V(-0.06, 0.7, 1.8), V(0.06, 0.82, 3.6)), m.wood);
    } else if (p.kind === "table") {
      b.add(boxGeo(V(-2.5, 0.85, -0.8), V(2.5, 0.95, 0.8), 1), m.planks);
      for (const sx of [-2.3, 2.3]) for (const sz of [-0.6, 0.6]) b.add(boxGeo(V(sx - 0.07, 0, sz - 0.07), V(sx + 0.07, 0.85, sz + 0.07)), m.wood);
    } else if (p.kind === "statue") {
      b.add(boxGeo(V(-0.6, 0, -0.6), V(0.6, 1.2, 0.6), 1), m.stone);
      b.add(new THREE.CylinderGeometry(0.28, 0.42, 1.5, 10).translate(0, 1.95, 0), m.stone);
      b.add(new THREE.SphereGeometry(0.26, 12, 10).translate(0, 2.95, 0), m.stone);
    } else if (p.kind === "barrel") {
      b.add(new THREE.CylinderGeometry(0.42, 0.42, 1.0, 14).translate(0, 0.5, 0), m.woodL);
      for (const y of [0.15, 0.85]) b.add(new THREE.CylinderGeometry(0.44, 0.44, 0.08, 14).translate(0, y, 0), m.rock);
    } else if (p.kind === "crate") {
      b.add(boxGeo(V(-0.5, 0, -0.5), V(0.5, 1, 0.5), 1), m.planks);
    } else if (p.kind === "chest") {
      b.add(boxGeo(V(-0.6, 0, -0.4), V(0.6, 0.6, 0.4), 1), m.woodL);
      b.add(new THREE.CylinderGeometry(0.4, 0.4, 1.2, 12, 1, false, 0, Math.PI).rotateZ(Math.PI / 2).translate(0, 0.6, 0), m.wood);
      b.add(boxGeo(V(-0.1, 0.4, 0.4), V(0.1, 0.65, 0.44)), lam("gold", () => ({ color: "#f2c23a" })));
    } else if (p.kind === "car") {
      b.add(boxGeo(V(-0.9, 0.35, -2), V(0.9, 1.0, 2)), lam("carRed", () => ({ color: "#c8323a" })));
      b.add(boxGeo(V(-0.8, 1.0, -1), V(0.8, 1.55, 0.9)), m.glass);
      for (const sx of [-1, 1]) for (const sz of [-1.3, 1.3]) b.add(new THREE.CylinderGeometry(0.36, 0.36, 0.25, 14).rotateZ(Math.PI / 2).translate(sx * 0.9, 0.36, sz), lam("tyre", () => ({ color: "#2a2a30" })));
    } else if (p.kind === "tent") {
      b.add(new THREE.ConeGeometry(2.2, 2.8, 4).rotateY(Math.PI / 4).translate(0, 1.4, 0), lam("tentCloth", () => ({ color: "#d8c8a0" })));
    } else if (p.kind === "rock") {
      b.add(new THREE.DodecahedronGeometry(1).scale(1.2, 0.8, 1).translate(0, 0.5, 0), m.rock);
    } else return null;
    b.build(g);
    o = g; propCache.set(key, o);
  }
  return o;
};

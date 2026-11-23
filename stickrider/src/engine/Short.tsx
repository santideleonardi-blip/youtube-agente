// StickRider short: one three.js world posed per frame from the spec (spec.ts). Post chain from the reference engine:
// ink -> lens blur -> bloom -> NEUTRAL tone map -> grade. Crossfades stack a second canvas for the fade frames.
import React, { useMemo } from "react";
import * as THREE from "three";
import { AbsoluteFill, useCurrentFrame, staticFile, delayRender, continueRender } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import { EffectComposer } from "@react-three/postprocessing";
import { BlendFunction, BloomEffect, ToneMappingEffect, ToneMappingMode } from "postprocessing";
import { World } from "./world";
import { InkPass, noInkFallback } from "./ink";
import { LensBlur } from "./lensblur";
import { GradeEffect, GRADES, GRADE_STRENGTH, gradeFor } from "./grade";
import { Spec, layersAt, camAt } from "./spec";
import { ORIGIN } from "./sets";

/** onlyShot: render that shot for every frame (the pipeline renders shot by shot and dissolves them with ffmpeg) */
export type ShortProps = { spec: Spec; onlyShot?: number; lead?: number };

// caption font (Luckiest Guy, OFL), loaded from public/ so renders never need the network
if (typeof document !== "undefined") {
  const h = delayRender("caption font");
  new FontFace("Luckiest Guy", `url(${staticFile("fonts/luckiest-guy-latin-400-normal.woff2")})`).load()
    .then((ff) => { document.fonts.add(ff); continueRender(h); }).catch(() => continueRender(h));
}

const makeBloom = () => {
  const b = new BloomEffect({ blendFunction: BlendFunction.ADD, intensity: 0.5, luminanceThreshold: 1.0, luminanceSmoothing: 0.2, mipmapBlur: true, levels: 6, radius: 0.6 });
  const mip = b.mipmapBlurPass, setSize = mip.setSize.bind(mip);
  mip.setSize = (w: number, h: number) => setSize(Math.round((1920 * w) / Math.max(h, 1)), 1920);
  return b;
};
const fwd = new THREE.Vector3(), fpt = new THREE.Vector3();

const Inner: React.FC<{ i: number; spec: Spec; lead: number }> = ({ i, spec, lead }) => {
  const f = useCurrentFrame() - lead;
  const { camera, scene } = useThree();
  const world = useMemo(() => new World(spec), [spec]);
  const fx = useMemo(() => ({
    ink: new InkPass(scene, camera as THREE.PerspectiveCamera),
    lens: new LensBlur({ maxCoC: 24, nearScale: 1.2 }),
    bloom: makeBloom(),
    tone: new ToneMappingEffect({ mode: ToneMappingMode.NEUTRAL }),
    grade: new GradeEffect(GRADES.day, GRADE_STRENGTH.day),
  }), [camera, scene]);
  const post = useMemo(() => (
    <EffectComposer multisampling={4}>
      <primitive object={fx.ink} dispose={null} />
      <primitive object={fx.lens.pre} dispose={null} />
      <primitive object={fx.lens.main} dispose={null} />
      <primitive object={fx.bloom} dispose={null} />
      <primitive object={fx.tone} dispose={null} />
      <primitive object={fx.grade} dispose={null} />
    </EffectComposer>
  ), [fx]);
  const s = spec.shots[i];
  const cam = camera as THREE.PerspectiveCamera;
  const target = world.update(s, f, cam, scene);
  noInkFallback(world.root);
  cam.getWorldDirection(fwd);
  const [ox, oz] = ORIGIN[s.set];
  if (s.dof?.focus) fpt.set(s.dof.focus[0] + ox, s.dof.focus[1], s.dof.focus[2] + oz); else fpt.copy(target);
  fx.lens.focus = Math.max(0.3, fpt.sub(cam.position).dot(fwd));
  fx.lens.cInf = camAt(s, f - s.a).cInf;
  gradeFor(fx.grade, s.light);
  return (<><primitive object={world.root} dispose={null} />{post}</>);
};

const ShotView: React.FC<{ i: number; spec: Spec; alpha: number; lead: number }> = ({ i, spec, alpha, lead }) => (
  <AbsoluteFill style={{ opacity: alpha }}>
    <ThreeCanvas width={1080} height={1920} shadows gl={{ antialias: false, stencil: false, powerPreference: "high-performance", toneMappingExposure: 1.0 }}
      camera={{ fov: 36, near: 0.2, far: 1500 }}>
      <Inner i={i} spec={spec} lead={lead} />
    </ThreeCanvas>
  </AbsoluteFill>
);

export const Short: React.FC<ShortProps> = ({ spec, onlyShot, lead = 0 }) => {
  const f = useCurrentFrame() - lead;
  const shot = onlyShot !== undefined ? spec.shots[onlyShot] : spec.shots.find((s) => f >= s.a && f < s.b);
  const layers = onlyShot !== undefined ? [{ i: onlyShot, alpha: 1 }] : layersAt(spec, f);
  const fl = (spec.flash ?? []).map((a) => f - a).find((d) => d >= 0 && d < 4);
  const flash = fl === undefined ? 0 : [1, 0.75, 0.45, 0.2][fl];
  const c2 = (spec.captions ?? []).find((c) => f >= c.a && f < c.b);
  const cap = c2?.text ?? shot?.caption, capIn = c2 ? Math.min(1, (f - c2.a) / 6) : shot ? Math.min(1, (f - shot.a) / 6) : 0;
  return (
    <AbsoluteFill style={{ background: "#cfe3f2" }}>
      {layers.map((l, k) => <ShotView key={k ? "over" : "base"} i={l.i} spec={spec} alpha={l.alpha} lead={lead} />)}
      {flash > 0 ? <AbsoluteFill style={{ background: "#ffffff", opacity: flash }} /> : null}
      {cap ? (
        <div style={{ position: "absolute", top: 230, width: "100%", textAlign: "center", fontFamily: "Luckiest Guy, Arial Black, sans-serif",
          fontSize: 120, color: "#fff7e6", WebkitTextStroke: "14px #241726", letterSpacing: 4, paintOrder: "stroke", opacity: capIn, transform: `scale(${0.85 + 0.15 * capIn})` }}>{cap}</div>
      ) : null}
    </AbsoluteFill>
  );
};

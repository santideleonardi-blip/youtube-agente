// Identidad del canal: paneles del banner (2560x1440) y foto de perfil (800x800), dibujados con el mismo motor que
// los videos. El texto y el montaje de las tres épocas se hacen en py/brand.py.
import React from "react";
import { AbsoluteFill } from "remotion";
import { Short } from "./engine/Short";
import type { Spec } from "./engine/spec";

export const Panel: React.FC<{ spec: Spec }> = ({ spec }) => (
  <AbsoluteFill><Short spec={spec} onlyShot={0} lead={8} /></AbsoluteFill>
);

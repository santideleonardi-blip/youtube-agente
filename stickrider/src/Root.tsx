import React from "react";
import { Composition, CalculateMetadataFunction } from "remotion";
import { Short, ShortProps } from "./engine/Short";
import demo from "../examples/dancing-plague.json";
import { Panel } from "./Brand";
import brand from "../examples/brand.json";

// lead: frames rendered before the shot (the post chain warms up on them); +12 tail for dissolves
const meta: CalculateMetadataFunction<ShortProps> = ({ props }) => ({ durationInFrames: props.spec.total + (props.lead ?? 0) + 12, fps: props.spec.fps });
export const Root: React.FC = () => (
  <>
  <Composition id="Short" component={Short} defaultProps={{ spec: demo as ShortProps["spec"] }} calculateMetadata={meta}
    durationInFrames={demo.total} fps={30} width={1080} height={1920} />
  <Composition id="Banner" component={Panel} defaultProps={{ spec: brand.ancient as ShortProps["spec"] }} durationInFrames={20} fps={30} width={2560} height={1440} />
  <Composition id="Avatar" component={Panel} defaultProps={{ spec: brand.avatar as ShortProps["spec"] }} durationInFrames={20} fps={30} width={800} height={800} />
  </>
);

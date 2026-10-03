import { AdditiveBlending, NormalBlending } from 'three';
import type { FlowLineLayer } from './AnimatedFlowLine';

/** Shared by the measured traffic arc and its legend sample. */
export const TRAFFIC_PATH_STYLE: Record<
  'outer' | 'glow' | 'core',
  FlowLineLayer
> = {
  outer: {
    color: '#7e22ce',
    linewidth: 8,
    opacity: 0.12,
    blending: AdditiveBlending,
    maxWorldWidth: 0.035,
  },
  glow: {
    color: '#a855f7',
    linewidth: 4,
    opacity: 0.3,
    blending: AdditiveBlending,
    maxWorldWidth: 0.02,
  },
  core: {
    color: '#c084fc',
    linewidth: 1.25,
    opacity: 0.95,
    blending: NormalBlending,
    maxWorldWidth: 0.008,
  },
};

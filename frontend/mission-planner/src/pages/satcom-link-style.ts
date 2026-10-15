import * as THREE from 'three';

const SATCOM_NORMAL_LINE = {
  outer: {
    color: '#1d4ed8',
    linewidth: 9,
    opacity: 0.12,
    blending: THREE.AdditiveBlending,
  },
  glow: {
    color: '#3b82f6',
    linewidth: 5,
    opacity: 0.34,
    blending: THREE.AdditiveBlending,
  },
  core: {
    color: '#3b82f6',
    linewidth: 1.5,
    opacity: 0.88,
    blending: THREE.NormalBlending,
  },
};

const SATCOM_WARNING_LINE = {
  outer: {
    color: '#b91c1c',
    linewidth: 9,
    opacity: 0.13,
    blending: THREE.AdditiveBlending,
  },
  glow: {
    color: '#ef4444',
    linewidth: 5,
    opacity: 0.36,
    blending: THREE.AdditiveBlending,
  },
  core: {
    color: '#ef4444',
    linewidth: 1.5,
    opacity: 0.9,
    blending: THREE.NormalBlending,
  },
};

export function satcomLineStyle(activeXLinkState: string | null | undefined) {
  return activeXLinkState === 'warning'
    ? SATCOM_WARNING_LINE
    : SATCOM_NORMAL_LINE;
}

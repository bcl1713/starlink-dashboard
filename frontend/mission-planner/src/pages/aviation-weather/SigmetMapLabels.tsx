import type { RefObject } from 'react';
import type * as THREE from 'three';
import { OverviewMapLabel } from '../OverviewMapLabel';
import type { SigmetMapLabel } from './route-sigmet-presentation';

export function SigmetMapLabels({
  labels,
  globeOccluder,
}: {
  labels: readonly SigmetMapLabel[];
  globeOccluder: RefObject<THREE.Group>;
}) {
  return labels.map((label) => (
    <OverviewMapLabel
      key={label.id}
      id={label.id}
      kind="sigmet"
      text={label.text}
      color={label.color}
      priority={2}
      markerRadiusPixels={0}
      position={label.position}
      globeOccluder={globeOccluder}
    />
  ));
}

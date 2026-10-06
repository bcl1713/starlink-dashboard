import { Html } from '@react-three/drei';
import type { RefObject } from 'react';
import type * as THREE from 'three';
import { positionOverviewDisclosure } from './overview-label-dom';

interface ContentProps {
  id: string;
  kind: 'poi' | 'adsb' | 'gep' | 'satellite';
  text: string;
  priority?: number;
  poiId?: string;
  hex?: string;
  title?: string;
}

export function OverviewMapLabelContent({
  id,
  kind,
  text,
  priority = 0,
  poiId,
  hex,
  title,
}: ContentProps) {
  const label = text.replace(/\s+/g, ' ').trim();
  return (
    <div
      className="overview-map-callout"
      data-overview-label-id={id}
      data-label-kind={kind}
      data-label-text={label}
      data-label-priority={priority}
      data-label-retain-identity={kind === 'adsb' ? 'true' : undefined}
    >
      <svg
        className="overview-label-stick"
        aria-hidden="true"
        width="1"
        height="1"
      >
        <path className="overview-label-stick-shadow" />
        <path data-label-leader="true" />
      </svg>
      <span
        className="globe-marker-label"
        data-label-source="true"
        data-poi-label={poiId}
        data-adsb-label={hex}
        title={title ?? label}
      >
        {label}
      </span>
      <details
        className="overview-label-group"
        onToggle={(event) => positionOverviewDisclosure(event.currentTarget)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.currentTarget.open = false;
            event.currentTarget.querySelector('summary')?.focus();
          }
        }}
      >
        <summary aria-label="Show crowded map labels" />
        <ul />
      </details>
    </div>
  );
}

export function OverviewMapLabel({
  position,
  globeOccluder,
  ...content
}: ContentProps & {
  position: [number, number, number];
  globeOccluder: RefObject<THREE.Object3D>;
}) {
  return (
    <Html
      position={position}
      occlude={[globeOccluder]}
      zIndexRange={[0, 0]}
      style={{ pointerEvents: 'none' }}
      wrapperClass="overview-callout-wrapper"
    >
      <OverviewMapLabelContent {...content} />
    </Html>
  );
}

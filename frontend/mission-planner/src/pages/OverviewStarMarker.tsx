import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { GlobeCoordinate } from './globe-route';
import { globePosition } from './globe-coordinates';

interface StarMarkerProps {
  coordinate: GlobeCoordinate;
  color: string;
  size: number;
}

function createStarTexture(color: string) {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;

  const context = canvas.getContext('2d');

  if (!context) {
    throw new Error('Unable to create star marker texture.');
  }

  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, '#ffffff');
  gradient.addColorStop(0.12, '#ffffff');
  gradient.addColorStop(0.14, color);
  gradient.addColorStop(0.45, `${color}00`);

  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;

  return texture;
}

export function StarMarker({ coordinate, color, size }: StarMarkerProps) {
  const texture = useMemo(() => createStarTexture(color), [color]);

  useEffect(() => {
    return () => {
      texture.dispose();
    };
  }, [texture]);

  return (
    <sprite
      position={globePosition(coordinate.latitude, coordinate.longitude, 2.002)}
      scale={[size, size, 1]}
      renderOrder={1}
    >
      <spriteMaterial
        map={texture}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </sprite>
  );
}

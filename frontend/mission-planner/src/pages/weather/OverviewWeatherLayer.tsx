import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { WeatherAtlasPair } from './weather-atlas';
import { WeatherTextureOwner } from './weather-textures';
import { weatherFragmentShader } from './weather-shader';
import { WeatherDetailTextureOwner } from './weather-detail-textures';
import type { DetailContext, DetailPair } from './weather-detail';
import { WeatherWork } from './weather-work';

const vertexShader = `
  varying vec3 vWeatherPosition;
  void main() {
    vWeatherPosition = position;
    // Match the base globe projection operation order so coplanar vertices
    // have identical depth instead of matrix-product rounding interference.
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;
const ignoreRaycast: THREE.Mesh['raycast'] = () => undefined;

export function OverviewWeatherLayer({
  atlas,
  context = null,
  pairs = [],
  work,
}: {
  atlas: WeatherAtlasPair | null;
  context?: DetailContext | null;
  pairs?: readonly DetailPair[];
  work?: WeatherWork | null;
}) {
  const owner = useMemo(() => new WeatherTextureOwner(), []);
  const detailOwner = useMemo(
    () => new WeatherDetailTextureOwner(work ?? new WeatherWork()),
    [work]
  );
  const previous = useRef<WeatherAtlasPair | null>(null);
  const material = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      radarTexture: { value: null as THREE.Texture | null },
      coverageTexture: { value: null as THREE.Texture | null },
      detailRadar: { value: null as THREE.Texture | null },
      detailCoverage: { value: null as THREE.Texture | null },
      detailBounds: {
        value: Array.from({ length: 8 }, () => new THREE.Vector4()),
      },
      detailRects: {
        value: Array.from({ length: 8 }, () => new THREE.Vector4()),
      },
      detailValid: { value: new Float32Array(8) },
      detailFades: { value: new Float32Array(8) },
    }),
    []
  );
  useLayoutEffect(() => {
    if (previous.current !== atlas) {
      detailOwner.dispose();
      previous.current = atlas;
    }
    const textures = owner.replace(atlas);
    const detail = detailOwner.replace(
      atlas ? context : null,
      pairs,
      performance.now()
    );
    const target = material.current?.uniforms;
    if (target) {
      target.detailRadar.value = detail?.radar ?? null;
      target.detailCoverage.value = detail?.coverage ?? null;
      if (detail) {
        target.detailBounds.value = detail.bounds;
        target.detailRects.value = detail.rects;
        target.detailValid.value = detail.valid;
        target.detailFades.value = detail.fades;
      } else {
        target.detailValid.value.fill(0);
        target.detailFades.value.fill(0);
      }
    }
    if (material.current) {
      material.current.uniforms.radarTexture.value = textures?.radar ?? null;
      material.current.uniforms.coverageTexture.value =
        textures?.coverage ?? null;
    }
  }, [owner, detailOwner, atlas, context, pairs]);
  useFrame(() => detailOwner.updateFades(performance.now()));
  useEffect(
    () => () => {
      detailOwner.dispose();
      owner.dispose();
    },
    [owner, detailOwner]
  );
  if (!atlas) return null;
  return (
    <mesh
      name="Overview precipitation radar"
      renderOrder={-100}
      raycast={ignoreRaycast}
    >
      <sphereGeometry args={[2, 64, 64]} />
      <shaderMaterial
        ref={material}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={weatherFragmentShader}
        transparent
        depthTest
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

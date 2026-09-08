import { useEffect, useMemo } from 'react';
import { useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import { TERMINATOR_HALF_WIDTH } from './night-side-factor';

interface NightCityLightsProps {
  sunPosition: [number, number, number];
}

const CITY_LIGHT_INTENSITY = 0.5;

const vertexShader = `
  varying vec2 vUv;
  varying vec3 vWorldNormal;

  void main() {
    vUv = uv;
    vWorldNormal = normalize(mat3(modelMatrix) * normal);

    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  uniform sampler2D nightMap;
  uniform vec3 sunDirection;

  varying vec2 vUv;
  varying vec3 vWorldNormal;

  void main() {
    vec3 nightRgb = texture2D(nightMap, vUv).rgb;
    float sunFacing = dot(
      normalize(vWorldNormal),
      normalize(sunDirection)
    );
    float nightFactor = smoothstep(
      -${TERMINATOR_HALF_WIDTH},
      ${TERMINATOR_HALF_WIDTH},
      -sunFacing
    );
    float luminance = dot(nightRgb, vec3(0.2126, 0.7152, 0.0722));
    float cityMask = smoothstep(0.08, 0.3, luminance);
    vec3 cityEmission = nightRgb * cityMask * nightFactor * ${CITY_LIGHT_INTENSITY};

    gl_FragColor = vec4(cityEmission, cityMask * nightFactor);
  }
`;

export function NightCityLights({ sunPosition }: NightCityLightsProps) {
  const sourceTexture = useLoader(THREE.TextureLoader, '/earth-night-hi.jpg');

  const nightMap = useMemo(() => {
    const texture = sourceTexture.clone();

    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    return texture;
  }, [sourceTexture]);

  useEffect(() => {
    return () => {
      nightMap.dispose();
    };
  }, [nightMap]);

  const uniforms = useMemo(
    () => ({
      nightMap: { value: nightMap },
      sunDirection: {
        value: new THREE.Vector3(...sunPosition).normalize(),
      },
    }),
    [nightMap, sunPosition]
  );

  return (
    <mesh scale={1.001} renderOrder={1}>
      <sphereGeometry args={[2, 64, 64]} />
      <shaderMaterial
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        fragmentShader={fragmentShader}
        toneMapped={false}
        transparent
        uniforms={uniforms}
        vertexShader={vertexShader}
      />
    </mesh>
  );
}

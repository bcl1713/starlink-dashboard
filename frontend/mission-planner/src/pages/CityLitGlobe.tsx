import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import { TERMINATOR_HALF_WIDTH } from './night-side-factor';

interface CityLitGlobeProps {
  sunPosition: [number, number, number];
}

const CITY_LIGHT_INTENSITY = 0.35;
const CITY_LIGHT_COLOR = 'vec3(0.92, 0.96, 1.0)';

type CompiledShader = Parameters<THREE.Material['onBeforeCompile']>[0];

export function CityLitGlobe({ sunPosition }: CityLitGlobeProps) {
  const [sourceDayMap, sourceCityLightMask] = useLoader(THREE.TextureLoader, [
    '/earth-day-hi.jpg',
    '/city-lights-mask.png',
  ]);

  const [dayMap, cityLightMask] = useMemo(() => {
    const dayTexture = sourceDayMap.clone();

    dayTexture.colorSpace = THREE.SRGBColorSpace;
    dayTexture.needsUpdate = true;

    const maskTexture = sourceCityLightMask.clone();

    maskTexture.colorSpace = THREE.NoColorSpace;
    maskTexture.needsUpdate = true;

    return [dayTexture, maskTexture];
  }, [sourceDayMap, sourceCityLightMask]);

  useEffect(() => {
    return () => {
      dayMap.dispose();
      cityLightMask.dispose();
    };
  }, [dayMap, cityLightMask]);

  const sunDirection = useRef(new THREE.Vector3(...sunPosition).normalize());

  useEffect(() => {
    sunDirection.current.set(...sunPosition).normalize();
  }, [sunPosition]);

  const onBeforeCompile = useCallback(
    (shader: CompiledShader) => {
      shader.uniforms.cityLightMask = { value: cityLightMask };
      shader.uniforms.citySunDirection = {
        value: sunDirection.current,
      };

      shader.vertexShader =
        `
          varying vec3 vCityWorldNormal;
        ` +
        shader.vertexShader.replace(
          '#include <beginnormal_vertex>',
          `
            #include <beginnormal_vertex>
            vCityWorldNormal = normalize(
              mat3(modelMatrix) * objectNormal
            );
          `
        );

      shader.fragmentShader =
        `
          uniform sampler2D cityLightMask;
          uniform vec3 citySunDirection;

          varying vec3 vCityWorldNormal;
        ` +
        shader.fragmentShader.replace(
          '#include <emissivemap_fragment>',
          `
            #include <emissivemap_fragment>

            float cityStrength = texture2D(
              cityLightMask,
              vMapUv
            ).r;
            float sunFacing = dot(
              normalize(vCityWorldNormal),
              normalize(citySunDirection)
            );
            float nightFactor = smoothstep(
              -${TERMINATOR_HALF_WIDTH},
              ${TERMINATOR_HALF_WIDTH},
              -sunFacing
            );

            totalEmissiveRadiance +=
              ${CITY_LIGHT_COLOR} *
              cityStrength *
              nightFactor *
              ${CITY_LIGHT_INTENSITY};
          `
        );
    },
    [cityLightMask]
  );

  return (
    <mesh>
      <sphereGeometry args={[2, 64, 64]} />
      <meshStandardMaterial
        customProgramCacheKey={() => 'city-lights-surface-v1'}
        map={dayMap}
        metalness={0.05}
        onBeforeCompile={onBeforeCompile}
        roughness={0.8}
      />
    </mesh>
  );
}

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
  const [sourceDayMap, sourceNightMap] = useLoader(
    THREE.TextureLoader,
    ['/earth-day-hi.jpg', '/earth-night-hi.jpg']
  );

  const [dayMap, nightMap] = useMemo(() => {
    const clone = (sourceTexture: THREE.Texture) => {
      const texture = sourceTexture.clone();

      texture.colorSpace = THREE.SRGBColorSpace;
      texture.needsUpdate = true;
      return texture;
    };

    return [clone(sourceDayMap), clone(sourceNightMap)];
  }, [sourceDayMap, sourceNightMap]);

  useEffect(() => {
    return () => {
      dayMap.dispose();
      nightMap.dispose();
    };
  }, [dayMap, nightMap]);

  const sunDirection = useRef(
    new THREE.Vector3(...sunPosition).normalize()
  );

  useEffect(() => {
    sunDirection.current.set(...sunPosition).normalize();
  }, [sunPosition]);

  const onBeforeCompile = useCallback(
    (shader: CompiledShader) => {
      shader.uniforms.cityNightMap = { value: nightMap };
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
          uniform sampler2D cityNightMap;
          uniform vec3 citySunDirection;

          varying vec3 vCityWorldNormal;
        ` +
        shader.fragmentShader.replace(
          '#include <emissivemap_fragment>',
          `
            #include <emissivemap_fragment>

            vec3 cityRgb = texture2D(cityNightMap, vMapUv).rgb;
            float cityLuminance = dot(
              cityRgb,
              vec3(0.2126, 0.7152, 0.0722)
            );
            float cityStrength = smoothstep(
              0.18,
              0.55,
              cityLuminance
            );
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
    [nightMap]
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

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
} from 'react';
import { useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import {
  useOverviewBloom,
  useOverviewBloomEmission,
  useOverviewCityIsolation,
  updateCityEmissionUniforms,
} from './overview-bloom-mode';
import { TERMINATOR_HALF_WIDTH } from './night-side-factor';

interface CityLitGlobeProps {
  sunPosition: [number, number, number];
}

type CompiledShader = Parameters<THREE.Material['onBeforeCompile']>[0];

export function CityLitGlobe({ sunPosition }: CityLitGlobeProps) {
  const bloom = useOverviewBloom();
  const emission = useOverviewBloomEmission();
  const isolateCities = useOverviewCityIsolation();
  const emissionUniforms = useMemo(
    () => ({
      cityEmissionIntensity: { value: 0.35 },
      citySurfaceScale: { value: 1 },
      cityEmissionColor: { value: new THREE.Color() },
    }),
    []
  );
  useLayoutEffect(() => {
    updateCityEmissionUniforms(
      emissionUniforms,
      bloom,
      emission,
      isolateCities
    );
  }, [emissionUniforms, bloom, emission, isolateCities]);
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
      Object.assign(shader.uniforms, emissionUniforms);
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
          uniform vec3 cityEmissionColor;
          uniform float cityEmissionIntensity;
          uniform float citySurfaceScale;
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
              cityEmissionColor *
              cityStrength *
              nightFactor *
              cityEmissionIntensity;
          `
        );
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <opaque_fragment>',
        'if (citySurfaceScale < 0.5) outgoingLight = totalEmissiveRadiance;\n#include <opaque_fragment>'
      );
    },
    [cityLightMask, emissionUniforms]
  );

  return (
    <mesh>
      <sphereGeometry args={[2, 64, 64]} />
      <meshStandardMaterial
        key={bloom ? 'bloom' : 'current'}
        customProgramCacheKey={() =>
          bloom ? 'city-lights-bloom-v1' : 'city-lights-surface-v1'
        }
        map={dayMap}
        metalness={0.05}
        onBeforeCompile={onBeforeCompile}
        roughness={0.8}
      />
    </mesh>
  );
}

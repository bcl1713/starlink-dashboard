import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { WeatherAtlasPair } from './weather-atlas';
import { WeatherTextureOwner } from './weather-textures';
import { MERCATOR_LIMIT } from './weather-projection';

const vertexShader = `
  varying vec3 vWeatherPosition;
  void main() {
    vWeatherPosition = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const fragmentShader = `
  uniform sampler2D radarTexture;
  uniform sampler2D coverageTexture;
  varying vec3 vWeatherPosition;
  void main() {
    vec3 p = normalize(vWeatherPosition);
    float latitude = asin(clamp(p.y, -1.0, 1.0));
    float longitude = atan(-p.z, p.x);
    float absent = 1.0;
    vec4 radar = vec4(0.0);
    if (abs(latitude) <= ${MERCATOR_LIMIT}) {
      vec2 uv = vec2(fract(longitude / 6.28318530718 + 0.5),
        clamp(0.5 - log(tan(0.78539816339 + latitude / 2.0)) / 6.28318530718, 0.0, 1.0));
      absent = texture2D(coverageTexture, uv).a;
      radar = texture2D(radarTexture, uv) * (1.0 - absent);
    }
    float hatch = 1.0 - step(1.5, mod(gl_FragCoord.x + gl_FragCoord.y, 12.0));
    float hatchAlpha = absent * hatch * 0.17;
    float alpha = radar.a * 0.72 + hatchAlpha;
    if (alpha <= 0.001) discard;
    vec3 color = (radar.rgb * radar.a * 0.72 + vec3(0.42) * hatchAlpha) / alpha;
    gl_FragColor = vec4(color, alpha);
    #include <colorspace_fragment>
  }
`;
const ignoreRaycast: THREE.Mesh['raycast'] = () => undefined;

export function OverviewWeatherLayer({
  atlas,
}: {
  atlas: WeatherAtlasPair | null;
}) {
  const owner = useMemo(() => new WeatherTextureOwner(), []);
  const material = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({ radarTexture: { value: null }, coverageTexture: { value: null } }),
    []
  );
  useLayoutEffect(() => {
    const textures = owner.replace(atlas);
    if (material.current) {
      material.current.uniforms.radarTexture.value = textures?.radar ?? null;
      material.current.uniforms.coverageTexture.value =
        textures?.coverage ?? null;
    }
  }, [owner, atlas]);
  useEffect(() => () => owner.dispose(), [owner]);
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
        fragmentShader={fragmentShader}
        transparent
        depthTest
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
import type { GfsDrawing } from './gfs-controller';
import { weatherKey, type WeatherBudget } from './weather-budget';
import {
  createWindParticles,
  advanceWindParticles,
  WIND_PARTICLE_BYTES,
} from './wind-particles';

export function createWindParticleDrawing(
  lease: GridLease,
  budget: WeatherBudget
): GfsDrawing & { update(deltaSeconds: number): void } {
  const bytes = {
    decoded: WIND_PARTICLE_BYTES.decoded + 4096,
    gpu: WIND_PARTICLE_BYTES.gpu + 4096,
  };
  const retained = budget.reserve(weatherKey('gfs-particles'), {
    encoded: 0,
    ...bytes,
  });
  let geometry: THREE.BufferGeometry | undefined,
    material: THREE.ShaderMaterial | undefined;
  try {
    const state = createWindParticles(lease);
    geometry = new THREE.BufferGeometry();
    const position = new THREE.BufferAttribute(state.positions, 3).setUsage(
      THREE.DynamicDrawUsage
    );
    const alpha = new THREE.BufferAttribute(state.alpha, 1).setUsage(
      THREE.DynamicDrawUsage
    );
    geometry.setAttribute('position', position);
    geometry.setAttribute('trailAlpha', alpha);
    geometry.setDrawRange(0, 0);
    material = new THREE.ShaderMaterial({
      vertexShader:
        'attribute float trailAlpha; varying float opacity; void main(){opacity=trailAlpha;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader:
        'varying float opacity; void main(){if(opacity<=0.0)discard;gl_FragColor=vec4(vec3(248.0,250.0,252.0)/255.0,opacity);}',
      transparent: true,
      depthTest: true,
      depthWrite: false,
      toneMapped: false,
    });
    const object = new THREE.LineSegments(geometry, material);
    object.name = 'GFS wind particles';
    object.renderOrder = -100;
    object.frustumCulled = false;
    object.raycast = () => {};
    object.userData.windParticles = state;
    const ownedGeometry = geometry,
      ownedMaterial = material;
    let owned = true;
    return {
      object,
      bytes,
      update(delta) {
        if (!owned || !Number.isFinite(delta) || delta <= 0) return;
        advanceWindParticles(state, delta);
        ownedGeometry.setDrawRange(0, state.vertexCount);
        position.needsUpdate = true;
        alpha.needsUpdate = true;
      },
      dispose() {
        if (!owned) return;
        owned = false;
        object.userData = {};
        ownedGeometry.dispose();
        ownedGeometry.deleteAttribute('position');
        ownedGeometry.deleteAttribute('trailAlpha');
        ownedMaterial.dispose();
        position.array = new Float32Array(0);
        alpha.array = new Float32Array(0);
        state.grid = undefined;
        state.count = state.vertexCount = 0;
        state.points =
          state.history =
          state.ages =
          state.lifetimes =
          state.sample =
            new Float64Array(0);
        state.heads = state.lengths = state.attempts = new Uint8Array(0);
        state.positions = state.alpha = new Float32Array(0);
        retained.release();
      },
    };
  } catch (error) {
    geometry?.dispose();
    material?.dispose();
    retained.release();
    throw error;
  }
}

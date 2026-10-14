import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
import type { GfsDrawing } from './gfs-controller';
import { weatherKey, type WeatherBudget } from './weather-budget';
import {
  gridVertexShader,
  gridFragmentShader,
  windFragmentShader,
} from './grid-shader';
import { WIND_COLOR_STOPS, windColor } from './wind-scale';
export function earthPoint(lat: number, lon: number, r = 2.012) {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180;
  return new THREE.Vector3(
    r * Math.cos(a) * Math.cos(b),
    r * Math.sin(a),
    -r * Math.cos(a) * Math.sin(b)
  );
}
export function createGridRaster(
  lease: GridLease,
  mode: 'winds' | 'temperature',
  budget: WeatherBudget
): GfsDrawing {
  const resources: (() => void)[] = [];
  const rasterVertices = 128 * 63 * 6;
  const textureBytes = 720 * 361 * 4 * (mode === 'winds' ? 2 : 1);
  const bytes = {
    decoded: textureBytes + rasterVertices * 7 * 4 + 4096,
    gpu: textureBytes + rasterVertices * 7 * 4 + 4096,
  };
  const retained = budget.reserve(weatherKey('gfs-raster'), {
    encoded: 0,
    ...bytes,
  });
  try {
    const values = mode === 'winds' ? [lease.u, lease.v] : [lease.t];
    const textures = values.map((buffer) => {
      const packed = new Uint8Array(720 * 361 * 4);
      for (let i = 0; i < buffer.length; i++) {
        packed[i * 4] = buffer[i] & 255;
        packed[i * 4 + 1] = (buffer[i] >> 8) & 255;
        packed[i * 4 + 2] = lease.mask[i];
        packed[i * 4 + 3] = 255;
      }
      const texture = new THREE.DataTexture(packed, 720, 361, THREE.RGBAFormat);
      texture.minFilter = texture.magFilter = THREE.NearestFilter;
      texture.generateMipmaps = false;
      texture.needsUpdate = true;
      resources.push(() => {
        texture.dispose();
        texture.image.data = new Uint8Array(0);
      });
      return texture;
    });
    const positions = new Float32Array(rasterVertices * 3),
      planes = new Float32Array(rasterVertices * 4);
    let cursor = 0;
    const put = (lat: number, lon: number) => {
      const a = (lat * Math.PI) / 180,
        b = (lon * Math.PI) / 180;
      positions[cursor] = 2.012 * Math.cos(a) * Math.cos(b);
      positions[cursor + 1] = 2.012 * Math.sin(a);
      positions[cursor + 2] = -2.012 * Math.cos(a) * Math.sin(b);
      cursor += 3;
    };
    for (let row = 0; row < 64; row++)
      for (let col = 0; col < 128; col++) {
        const a = 90 - (row * 180) / 64,
          b = 90 - ((row + 1) * 180) / 64,
          x = -180 + (col * 360) / 128,
          y = -180 + ((col + 1) * 360) / 128;
        if (row > 0) {
          put(a, x);
          put(b, x);
          put(a, y);
        }
        if (row < 63) {
          put(a, y);
          put(b, x);
          put(b, y);
        }
      }
    const a = new THREE.Vector3(),
      b = new THREE.Vector3(),
      c = new THREE.Vector3();
    for (let i = 0; i < rasterVertices; i += 3) {
      a.fromArray(positions, i * 3);
      b.fromArray(positions, (i + 1) * 3);
      c.fromArray(positions, (i + 2) * 3);
      const n = b.sub(a).cross(c.sub(a)).normalize(),
        distance = n.dot(a);
      for (let j = 0; j < 3; j++) {
        const k = (i + j) * 4;
        planes[k] = n.x;
        planes[k + 1] = n.y;
        planes[k + 2] = n.z;
        planes[k + 3] = distance;
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute(
      'trianglePlane',
      new THREE.BufferAttribute(planes, 4)
    );
    resources.push(() => {
      geometry.dispose();
      geometry.deleteAttribute('position');
      geometry.deleteAttribute('trianglePlane');
    });
    const component = lease.descriptor.grid.components[2];
    const material = new THREE.ShaderMaterial({
      uniforms: {
        ...(mode === 'winds'
          ? {
              packedU: { value: textures[0] },
              packedV: { value: textures[1] },
              windScale: {
                value: new THREE.Vector2(
                  lease.descriptor.grid.components[0].scale,
                  lease.descriptor.grid.components[1].scale
                ),
              },
              windOffset: {
                value: new THREE.Vector2(
                  lease.descriptor.grid.components[0].offset,
                  lease.descriptor.grid.components[1].offset
                ),
              },
              windStops: { value: WIND_COLOR_STOPS.map((s) => s.knots) },
              // These are already sRGB values; Color would convert them to linear.
              windColors: {
                value: WIND_COLOR_STOPS.map(
                  (s) => new THREE.Vector3(...windColor(s.knots))
                ),
              },
            }
          : { packedGrid: { value: textures[0] } }),
        size: { value: new THREE.Vector2(720, 361) },
        scale: { value: component.scale },
        offset: { value: component.offset },
        diagnostic: { value: 0 },
        inverseProjection: { value: new THREE.Matrix4() },
        cameraWorld: { value: new THREE.Matrix4() },
        eye: { value: new THREE.Vector3() },
        framebuffer: { value: new THREE.Vector2() },
      },
      vertexShader: gridVertexShader,
      fragmentShader:
        mode === 'winds' ? windFragmentShader : gridFragmentShader,
      transparent: true,
      depthWrite: false,
      toneMapped: false,
      side: THREE.FrontSide,
    });
    resources.push(() => material.dispose());
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = mode === 'winds' ? 'GFS wind speed' : 'GFS temperature';
    mesh.renderOrder = -101;
    mesh.raycast = () => {};
    mesh.onBeforeRender = (renderer, _scene, camera) => {
      material.uniforms.inverseProjection.value.copy(
        camera.projectionMatrixInverse
      );
      material.uniforms.cameraWorld.value.copy(camera.matrixWorld);
      material.uniforms.eye.value.setFromMatrixPosition(camera.matrixWorld);
      const target = renderer.getRenderTarget();
      if (target)
        material.uniforms.framebuffer.value.set(target.width, target.height);
      else renderer.getDrawingBufferSize(material.uniforms.framebuffer.value);
    };
    let owned = true;
    return {
      object: mesh,
      bytes,
      dispose() {
        if (!owned) return;
        owned = false;
        mesh.onBeforeRender = () => {};
        mesh.userData = {};
        resources.forEach((dispose) => dispose());
        retained.release();
      },
    };
  } catch (error) {
    resources.forEach((dispose) => dispose());
    retained.release();
    throw error;
  }
}

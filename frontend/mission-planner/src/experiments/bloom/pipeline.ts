import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { bloomSize, type BloomMode, type BloomSettings } from './contracts';

export function createBloomPipeline(
  gl: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera
) {
  // Half-float preserves HDR. Main image stays at the renderer's drawing size;
  // only UnrealBloom's bright/blur targets are reduced after composer resizing.
  const target = new THREE.WebGLRenderTarget(1, 1, {
    type: THREE.HalfFloatType,
  });
  target.samples = 4;
  const composer = new EffectComposer(gl, target);
  composer.setPixelRatio(1);
  const render = new RenderPass(scene, camera);
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 1, 0.5, 1.2);
  const output = new OutputPass();
  composer.addPass(render);
  composer.addPass(bloom);
  composer.addPass(output);
  return {
    resize(width: number, height: number, settings: BloomSettings) {
      composer.setSize(width, height);
      // Composer.setSize calls pass.setSize, so apply this override LAST.
      bloom.setSize(...bloomSize(width, height, settings.maxDimension));
    },
    configure(mode: BloomMode, settings: BloomSettings) {
      bloom.enabled = mode === 'bloom';
      bloom.strength = settings.strength;
      bloom.threshold = settings.threshold;
      bloom.radius = settings.radius;
    },
    render(delta: number) {
      composer.render(delta);
    },
    dimensions() {
      const dimensions = (rt: THREE.WebGLRenderTarget) => [rt.width, rt.height];
      return {
        scene: dimensions(composer.renderTarget1),
        bright: dimensions(bloom.renderTargetBright),
        horizontal: bloom.renderTargetsHorizontal.map(dimensions),
        vertical: bloom.renderTargetsVertical.map(dimensions),
      };
    },
    dispose() {
      // EffectComposer.dispose releases its two targets/copy pass, NOT passes.
      render.dispose();
      bloom.dispose();
      output.dispose();
      composer.dispose();
    },
  };
}
export type BloomPipeline = ReturnType<typeof createBloomPipeline>;
export function renderExperimentFrame(
  mode: BloomMode,
  gl: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera,
  pipeline: BloomPipeline | null,
  delta: number
) {
  if (mode === 'current' || !pipeline) gl.render(scene, camera);
  else pipeline.render(delta);
}

export function setRenderStatsAutoReset(
  gl: THREE.WebGLRenderer,
  value: boolean
) {
  gl.info.autoReset = value;
}

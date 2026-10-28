import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { createBloomPipeline, renderExperimentFrame } from './pipeline';
import { DEFAULT_BLOOM } from './contracts';

const calls = vi.hoisted(() => ({
  renders: 0,
  debug: null as null | {
    enabled: boolean;
    uniforms: { uSource: { value: unknown } };
  },
  passes: [] as { dispose: ReturnType<typeof vi.fn> }[],
}));
vi.mock('three/addons/postprocessing/EffectComposer.js', () => ({
  EffectComposer: class {
    passes: unknown[] = [];
    renderTarget1 = { width: 0, height: 0 };
    renderTarget2 = { width: 0, height: 0 };
    dispose = vi.fn();
    setPixelRatio() {}
    setSize(w: number, h: number) {
      this.renderTarget1 = this.renderTarget2 = { width: w, height: h };
    }
    addPass(pass: unknown) {
      this.passes.push(pass);
    }
    render() {
      calls.renders++;
    }
  },
}));
vi.mock('three/addons/postprocessing/ShaderPass.js', () => ({
  ShaderPass: class {
    enabled = false;
    uniforms = { uSource: { value: null as unknown } };
    dispose = vi.fn();
    constructor() {
      calls.debug = this;
      calls.passes.push(this);
    }
  },
}));
vi.mock('three/addons/postprocessing/RenderPass.js', () => ({
  RenderPass: class {
    dispose = vi.fn();
    constructor() {
      calls.passes.push(this);
    }
  },
}));
vi.mock('three/addons/postprocessing/OutputPass.js', () => ({
  OutputPass: class {
    dispose = vi.fn();
    constructor() {
      calls.passes.push(this);
    }
  },
}));
vi.mock('three/addons/postprocessing/UnrealBloomPass.js', () => ({
  UnrealBloomPass: class {
    enabled = true;
    strength = 1;
    threshold = 1;
    radius = 1;
    renderTargetBright = { width: 0, height: 0, texture: 'bright' };
    renderTargetsHorizontal = [{ width: 1, height: 1, texture: 'bloom' }];
    renderTargetsVertical: { width: number; height: number }[] = [];
    dispose = vi.fn();
    constructor() {
      calls.passes.push(this);
    }
    setSize(w: number, h: number) {
      this.renderTargetBright = {
        texture: 'bright',
        width: Math.round(w / 2),
        height: Math.round(h / 2),
      };
    }
  },
}));

it('has one final-render owner, keeps full-size scene targets, bounds bloom, and disposes every pass', () => {
  const render = vi.fn();
  const gl = {
    render,
    toneMappingExposure: 1,
    getPixelRatio: () => 2,
    getSize: (v: THREE.Vector2) => v.set(1920, 1080),
  } as unknown as THREE.WebGLRenderer;
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera();
  renderExperimentFrame('current', gl, scene, camera, null, 1 / 60);
  expect(render).toHaveBeenCalledOnce();
  const pipeline = createBloomPipeline(gl, scene, camera);
  pipeline.resize(3840, 2160, DEFAULT_BLOOM);
  expect(pipeline.dimensions().scene).toEqual([3840, 2160]);
  expect(pipeline.dimensions().bright).toEqual([480, 270]);
  renderExperimentFrame('bloom', gl, scene, camera, pipeline, 1 / 60);
  renderExperimentFrame('output', gl, scene, camera, pipeline, 1 / 60);
  expect(render).toHaveBeenCalledOnce();
  expect(calls.renders).toBe(2);
  pipeline.configure('bloom', {
    ...DEFAULT_BLOOM,
    view: 'bright',
    exposure: 2,
  });
  expect(gl.toneMappingExposure).toBe(2);
  expect(calls.debug?.enabled).toBe(true);
  expect(calls.debug?.uniforms.uSource.value).toBe('bright');
  pipeline.configure('bloom', { ...DEFAULT_BLOOM, view: 'bloom' });
  expect(calls.debug?.uniforms.uSource.value).toBe('bloom');
  pipeline.configure('output', {
    ...DEFAULT_BLOOM,
    view: 'bright',
    exposure: 3,
  });
  expect(calls.debug?.enabled).toBe(false);
  expect(gl.toneMappingExposure).toBe(1);
  pipeline.dispose();
  expect(gl.toneMappingExposure).toBe(1);
  for (const pass of calls.passes) expect(pass.dispose).toHaveBeenCalledOnce();
});

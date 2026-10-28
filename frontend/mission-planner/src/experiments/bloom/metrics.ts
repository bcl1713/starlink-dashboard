import type { RootState } from '@react-three/fiber';
import * as THREE from 'three';
import { frameSummary, type BloomMode, type BloomSettings } from './contracts';
import type { FrameEvidence } from './OverviewBloomComposer';
import { SCENARIO } from './scenario';
declare const __BLOOM_SHA__: string;
declare const __BLOOM_DIRTY__: boolean;

export interface RunConfig {
  mode: BloomMode;
  settings: BloomSettings;
  full: boolean;
  path: boolean;
  power: string;
  sampleFrames: number;
}
export function describeFrame(state: RootState, dimensions: FrameEvidence) {
  const gl = state.gl,
    context = gl.getContext();
  const debug = context.getExtension('WEBGL_debug_renderer_info');
  const renderer = String(
    context.getParameter(
      debug ? debug.UNMASKED_RENDERER_WEBGL : context.RENDERER
    )
  );
  const vendor = String(
    context.getParameter(debug ? debug.UNMASKED_VENDOR_WEBGL : context.VENDOR)
  );
  const drawing = gl.getDrawingBufferSize(new THREE.Vector2());
  const memory = (
    performance as Performance & {
      memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number };
    }
  ).memory;
  return {
    cssViewport: [state.size.width, state.size.height],
    drawingBuffer: [drawing.x, drawing.y],
    dpr: gl.getPixelRatio(),
    bloomTargets: dimensions,
    vendor,
    renderer,
    softwareRenderer: /SwiftShader|llvmpipe|softpipe|software rasterizer/i.test(
      renderer
    )
      ? 'reported-software'
      : 'not-identified-as-software',
    webglVersion: context.getParameter(context.VERSION),
    userAgent: navigator.userAgent,
    resources: {
      ...gl.info.memory,
      programs: gl.info.programs?.length ?? null,
    },
    drawCalls: gl.info.render.calls,
    triangles: gl.info.render.triangles,
    points: gl.info.render.points,
    heap: memory
      ? { usedBytes: memory.usedJSHeapSize, limitBytes: memory.jsHeapSizeLimit }
      : null,
    gpuTiming: 'not sampled; frame intervals are not GPU timings',
  };
}
export function makeRun(
  config: RunConfig,
  samples: number[],
  start: ReturnType<typeof describeFrame>,
  end: ReturnType<typeof describeFrame>
) {
  return {
    sourceSha: __BLOOM_SHA__,
    sourceDirty: __BLOOM_DIRTY__,
    scenario: SCENARIO,
    texture: 'settlement-mask-current',
    capturedAt: new Date().toISOString(),
    ...config,
    warmupFrames: 60,
    summary: frameSummary(samples),
    start,
    end,
    intervalsMs: samples,
    simulationStepSeconds: 1 / 60,
    note: 'Synthetic specimen, not the complete operational Overview workload. Laptop measurements require physical-laptop renderer/power review.',
  };
}
export type Run = ReturnType<typeof makeRun>;
export function download(name: string, body: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function runsCsv(runs: Run[]) {
  const rows = [
    [
      'sha',
      'scenario',
      'mode',
      'maxBloomDimension',
      'strength',
      'threshold',
      'radius',
      'full',
      'path',
      'power',
      'renderer',
      'count',
      'durationMs',
      'medianIntervalMs',
      'p95IntervalMs',
    ],
    ...runs.map((r) => [
      r.sourceSha,
      r.scenario,
      r.mode,
      r.settings.maxDimension,
      r.settings.strength,
      r.settings.threshold,
      r.settings.radius,
      r.full,
      r.path,
      r.power,
      r.end.renderer,
      r.summary?.count,
      r.summary?.durationMs,
      r.summary?.medianMs,
      r.summary?.p95Ms,
    ]),
  ];
  return rows
    .map((row) =>
      row.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(',')
    )
    .join('\n');
}

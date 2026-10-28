import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, type RootState } from '@react-three/fiber';
import * as THREE from 'three';
import { OverviewBloomMode } from '../../pages/overview-bloom-mode';
import { DEFAULT_BLOOM, type BloomMode, type BloomSettings } from './contracts';
import { capturePhase, type ViewportSignature } from './contracts';
import { CameraReplay } from './CameraReplay';
import { Fixture } from './Fixture';
import {
  OverviewBloomComposer,
  type FrameEvidence,
} from './OverviewBloomComposer';
import {
  describeFrame,
  download,
  makeRun,
  runsCsv,
  type Run,
  type RunConfig,
} from './metrics';
import { INITIAL_CAMERA } from './scenario';
import '../../pages/OverviewPage.css';
import './style.css';
declare const __BLOOM_SHA__: string;

interface Capture {
  config: RunConfig;
  frame: number;
  samples: number[];
  start: ReturnType<typeof describeFrame> | null;
}
export function App() {
  const [mode, setMode] = useState<BloomMode>('current');
  const [settings, setSettings] = useState<BloomSettings>(DEFAULT_BLOOM);
  const [full, setFull] = useState(false),
    [path, setPath] = useState(false),
    [paused, setPaused] = useState(false);
  const [power, setPower] = useState(
    'Unrecorded — enter OS / power / battery mode'
  );
  const [epoch, setEpoch] = useState(0),
    [status, setStatus] = useState('Ready · synthetic offline scene');
  const [busy, setBusy] = useState(false),
    [runs, setRuns] = useState<Run[]>([]);
  const capture = useRef<Capture | null>(null),
    queue = useRef<RunConfig[]>([]);
  const observedFrames = useRef(0);
  const viewport = useRef<ViewportSignature | null>(null);
  const seriesViewport = useRef<ViewportSignature | null>(null);
  const [sampleFrames, setSampleFrames] = useState(300);
  const ready = useRef(false),
    screenshot = useRef(false);
  const latest = useRef<Record<string, unknown>>({});

  const cancel = useCallback((reason: string) => {
    capture.current = null;
    queue.current = [];
    setBusy(false);
    setStatus(reason);
  }, []);
  useEffect(() => {
    if (!busy) return;
    const hidden = () => {
      if (document.hidden) cancel('Capture cancelled: page hidden');
    };
    document.addEventListener('visibilitychange', hidden);
    return () => document.removeEventListener('visibilitychange', hidden);
  }, [busy, cancel]);
  const next = () => {
    const config = queue.current.shift();
    if (!config) {
      capture.current = null;
      setBusy(false);
      setStatus('Capture series complete · export JSON/CSV');
      return;
    }
    setMode(config.mode);
    setSettings(config.settings);
    setFull(config.full);
    setPath(config.path);
    setPaused(false);
    setEpoch((e) => e + 1);
    capture.current = { config, frame: 0, samples: [], start: null };
    setStatus(`Warm-up · ${config.mode}`);
  };
  const start = (diagnostic: boolean) => {
    if (!ready.current) {
      setStatus('Wait for the local textures and scene to load.');
      return;
    }
    seriesViewport.current = viewport.current;
    const base = {
      settings: { ...settings },
      full,
      path: true,
      power,
      sampleFrames,
    };
    queue.current = diagnostic
      ? [
          { ...base, mode: 'output' as const },
          {
            ...base,
            mode: 'bloom' as const,
            settings: { ...settings, maxDimension: 480 },
          },
          {
            ...base,
            mode: 'bloom' as const,
            settings: { ...settings, maxDimension: 1920 },
          },
        ]
      : Array.from({ length: 3 }, () =>
          ['current', 'bloom', 'current'].map((mode) => ({
            ...base,
            mode: mode as BloomMode,
          }))
        ).flat();
    setBusy(true);
    next();
  };
  const onFrame = (
    state: RootState,
    dimensions: FrameEvidence,
    delta: number
  ) => {
    viewport.current = {
      css: [state.size.width, state.size.height],
      drawing: [state.gl.domElement.width, state.gl.domElement.height],
      dpr: state.gl.getPixelRatio(),
    };
    // Cheap observability for smoke checks, no per-frame React state updates.
    if (observedFrames.current++ % 30 === 0) {
      latest.current = {
        mode,
        camera: state.camera.position.toArray(),
        drawingBuffer: [state.gl.domElement.width, state.gl.domElement.height],
        dimensions,
        resources: { ...state.gl.info.memory },
        drawCalls: state.gl.info.render.calls,
      };
      Object.assign(state.gl.domElement.dataset, {
        frame: JSON.stringify(latest.current),
      });
    }
    if (screenshot.current) {
      screenshot.current = false;
      // Called immediately after rendering; preserveDrawingBuffer is unnecessary.
      state.gl.domElement.toBlob((blob) => {
        if (blob)
          download(
            `bloom-${mode}-${__BLOOM_SHA__.slice(0, 8)}-${settings.maxDimension}.png`,
            blob,
            'image/png'
          );
      });
    }
    const active = capture.current;
    if (!active) return;
    if (document.hidden || state.gl.getContext().isContextLost()) {
      cancel('Capture cancelled: hidden page or lost WebGL context');
      return;
    }
    active.frame++;
    if (!seriesViewport.current) {
      cancel('Capture cancelled: viewport not ready');
      return;
    }
    const phase = capturePhase(
      seriesViewport.current,
      viewport.current,
      active.frame
    );
    if (phase === 'changed') {
      cancel('Capture cancelled: viewport/DPR changed');
      return;
    }
    if (phase === 'warmup') return;
    if (!active.start) active.start = describeFrame(state, dimensions);
    active.samples.push(delta * 1000);
    if (active.samples.length % 60 === 0)
      setStatus(
        `${active.config.mode} · ${active.samples.length}/${active.config.sampleFrames} frame intervals`
      );
    if (active.samples.length < active.config.sampleFrames) return;
    const result = makeRun(
      active.config,
      active.samples,
      active.start,
      describeFrame(state, dimensions)
    );
    setRuns((previous) => [...previous.slice(-47), result]);
    next();
  };
  return (
    <main>
      <header>
        <strong>Overview / real bloom</strong>
        <span>SYNTHETIC · OFFLINE · EXPERIMENT</span>
        <small>{__BLOOM_SHA__.slice(0, 12)}</small>
      </header>
      <div className="controls">
        <label>
          Mode{' '}
          <select
            aria-label="Mode"
            value={mode}
            disabled={busy}
            onChange={(e) => setMode(e.target.value as BloomMode)}
          >
            <option value="current">A · Current</option>
            <option value="output">Diagnostic · Output only</option>
            <option value="bloom">B · Real bloom</option>
          </select>
        </label>
        {(['strength', 'threshold', 'radius'] as const).map((key) => (
          <label key={key}>
            {key}{' '}
            <input
              aria-label={key}
              type="range"
              disabled={busy}
              min="0"
              max={key === 'radius' ? 1 : 3}
              step="0.05"
              value={settings[key]}
              onChange={(e) =>
                setSettings((s) => ({ ...s, [key]: Number(e.target.value) }))
              }
            />
            <output>{settings[key].toFixed(2)}</output>
          </label>
        ))}
        <label>
          Bloom bound{' '}
          <select
            aria-label="Bloom bound"
            value={settings.maxDimension}
            disabled={busy}
            onChange={(e) =>
              setSettings((s) => ({
                ...s,
                maxDimension: Number(e.target.value),
              }))
            }
          >
            {[480, 960, 1920].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          <input
            aria-label="Full overlays"
            type="checkbox"
            checked={full}
            disabled={busy}
            onChange={(e) => setFull(e.target.checked)}
          />
          Full overlays
        </label>
        <label>
          <input
            aria-label="Camera path"
            type="checkbox"
            checked={path}
            disabled={busy}
            onChange={(e) => setPath(e.target.checked)}
          />
          Camera path
        </label>
        <button disabled={busy} onClick={() => setPaused((p) => !p)}>
          {paused ? 'Play' : 'Pause'}
        </button>
        <button disabled={busy} onClick={() => setEpoch((e) => e + 1)}>
          Reset / replay
        </button>
      </div>
      <section
        className="overview-page overview-map-stage"
        aria-label="Synthetic globe"
      >
        <Canvas
          camera={{ position: INITIAL_CAMERA, fov: 45 }}
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener('webglcontextlost', () =>
              cancel('Capture cancelled: WebGL context lost')
            );
          }}
        >
          <CameraReplay epoch={epoch} path={path} paused={paused} />
          <OverviewBloomMode value={mode === 'bloom'}>
            <Suspense fallback={null}>
              <Fixture
                key={epoch}
                full={full}
                paused={paused}
                onPick={(id) => setStatus(`Picked synthetic POI: ${id}`)}
              />
              <Loaded
                onReady={() => {
                  ready.current = true;
                }}
              />
            </Suspense>
          </OverviewBloomMode>
          <OverviewBloomComposer
            mode={mode}
            settings={settings}
            onFrame={onFrame}
          />
        </Canvas>
        <div className="scene-caption">
          {mode === 'current'
            ? 'A · CURRENT'
            : mode === 'output'
              ? 'OUTPUT ONLY'
              : 'B · REAL BLOOM'}
          <br />
          <small>
            {full ? 'Full specimen' : 'Default specimen'} · fixed sun ·
            settlement mask
          </small>
        </div>
      </section>
      <footer>
        <label>
          Samples{' '}
          <select
            aria-label="Samples"
            disabled={busy}
            value={sampleFrames}
            onChange={(e) => setSampleFrames(Number(e.target.value))}
          >
            {[60, 300, 600].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          OS / power{' '}
          <input
            aria-label="OS and power mode"
            value={power}
            disabled={busy}
            onChange={(e) => setPower(e.target.value)}
          />
        </label>
        <button disabled={busy} onClick={() => start(false)}>
          Measure A→B→A ×3
        </button>
        <button disabled={busy} onClick={() => start(true)}>
          Measure output / B bounds
        </button>
        {busy && (
          <button onClick={() => cancel('Capture cancelled by operator')}>
            Cancel
          </button>
        )}
        <button
          disabled={busy}
          onClick={() => {
            screenshot.current = true;
          }}
        >
          Save canvas PNG
        </button>
        <button
          disabled={!runs.length || busy}
          onClick={() =>
            download(
              'bloom-runs.json',
              JSON.stringify(runs, null, 2),
              'application/json'
            )
          }
        >
          Export JSON
        </button>
        <button
          disabled={!runs.length || busy}
          onClick={() => download('bloom-runs.csv', runsCsv(runs), 'text/csv')}
        >
          Export CSV
        </button>
        <span role="status">{status}</span>
        <p>
          Orbit / zoom manually, or replay the same camera path. Measurements:
          60 warm-up + selected sampled frames per run, capped at 48 retained
          runs. PNG includes the canvas; use a browser screenshot to include
          HTML labels. Full overlays are synthetic weather, wind and traffic
          specimens, not the complete operational stack.
        </p>
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Mode / bound</th>
              <th>Median interval</th>
              <th>p95 interval</th>
              <th>Samples</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>
                  {run.mode} / {run.settings.maxDimension}
                </td>
                <td>{run.summary?.medianMs.toFixed(2)} ms</td>
                <td>{run.summary?.p95Ms.toFixed(2)} ms</td>
                <td>{run.summary?.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </footer>
    </main>
  );
}
function Loaded({ onReady }: { onReady: () => void }) {
  useEffect(onReady, [onReady]);
  return null;
}
createRoot(document.getElementById('root')!).render(<App />);

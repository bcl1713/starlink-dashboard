import {
  createContext,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { RootState } from '@react-three/fiber';
import { TuningPanel } from '../experiments/bloom/TuningPanel';
import {
  DEFAULT_BLOOM,
  type BloomMode,
  type BloomSettings,
} from '../experiments/bloom/contracts';
import {
  OverviewBloomComposer,
  type FrameEvidence,
} from '../experiments/bloom/OverviewBloomComposer';
import { describeFrame } from '../experiments/bloom/metrics';
import {
  DEFAULT_EMISSION,
  OverviewBloomEmission,
  OverviewBloomMode,
} from './overview-bloom-mode';

type RenderedFrame = { state: RootState; dimensions: FrameEvidence };
const DebugScene = createContext<{
  mode: BloomMode;
  settings: BloomSettings;
  onFrame: (state: RootState, dimensions: FrameEvidence) => void;
} | null>(null);

// The provider stays in place while tuning, keeping the real Canvas and all its
// live data, camera controls and animation pools mounted.
export function OverviewBloomDebug({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  const [mode, setMode] = useState<BloomMode>('bloom');
  const [settings, setSettings] = useState(DEFAULT_BLOOM);
  const [emissions, setEmissions] = useState(DEFAULT_EMISSION);
  const frame = useRef<RenderedFrame | null>(null);
  const active = enabled && mode === 'bloom';
  const getReport = () => {
    const last = frame.current;
    return {
      schema: 'overview-bloom-tuning/v1',
      scene: 'overview',
      capturedAt: new Date().toISOString(),
      mode,
      settings,
      emissions,
      emissionOverridesActive: active,
      frame: last
        ? {
            ...describeFrame(last.state, last.dimensions),
            camera: {
              position: last.state.camera.position.toArray(),
              quaternion: last.state.camera.quaternion.toArray(),
              zoom: last.state.camera.zoom,
            },
          }
        : null,
    };
  };
  return (
    <DebugScene.Provider
      value={
        enabled
          ? {
              mode,
              settings,
              onFrame: (state, dimensions) => {
                frame.current = { state, dimensions };
              },
            }
          : null
      }
    >
      <OverviewBloomMode.Provider value={active}>
        <OverviewBloomEmission.Provider value={emissions}>
          {children}
          {enabled && (
            <TuningPanel
              active={active}
              busy={false}
              mode={mode}
              onMode={setMode}
              settings={settings}
              emissions={emissions}
              isolateCities={false}
              allowIsolation={false}
              onIsolate={() => {}}
              onSettings={setSettings}
              onEmissions={setEmissions}
              onCityPreset={() => {
                setMode('bloom');
                setSettings({
                  ...DEFAULT_BLOOM,
                  strength: 1,
                  threshold: 0.4,
                  radius: 0.3,
                  maxDimension: 1920,
                });
                setEmissions({ ...DEFAULT_EMISSION, cities: 30 });
              }}
              onReset={() => {
                setSettings(DEFAULT_BLOOM);
                setEmissions(DEFAULT_EMISSION);
              }}
              getReport={getReport}
            />
          )}
        </OverviewBloomEmission.Provider>
      </OverviewBloomMode.Provider>
    </DebugScene.Provider>
  );
}

export function OverviewBloomDebugScene() {
  const debug = useContext(DebugScene);
  return debug ? <OverviewBloomComposer {...debug} /> : null;
}
